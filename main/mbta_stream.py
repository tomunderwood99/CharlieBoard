#!/usr/bin/env python3
import sys
import os

# Add project root to Python path to ensure local modules are found first
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import sseclient
import json
import requests
import time
import threading
from typing import Dict, Any
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

from display.controller.led_controller import LEDController
from display.mode_manager import ModeManager
from config.settings import SettingsManager
from config.station_led_maps import station_led_maps
from config.station_id_maps import station_id_maps
from config.validation import validate_vehicle_data
from config.constants import (
    MAX_CONSECUTIVE_ERRORS,
    ERROR_LOG_COOLDOWN_SECONDS,
    ERROR_FILE_MAX_AGE_DAYS,
    ERROR_DATA_PREVIEW_LENGTH,
    ERROR_LOG_PREVIEW_LENGTH,
    HEALTH_LOG_FREQUENCY,
    SSE_CHUNK_SIZE,
    COLOR_KEY_LED_COUNT,
    HEALTH_CHECK_INTERVAL_SECONDS,
    STALE_VEHICLE_DATA_SECONDS,
    NETWORK_DISCONNECTION_WAIT_SECONDS,
    STREAM_ERROR_RETRY_WAIT_SECONDS,
    LOG_FILE_MAX_BYTES,
    LOG_FILE_BACKUP_COUNT,
)
from monitoring.network_monitor import NetworkMonitor
from monitoring.metrics import SystemMetrics
from config.bedtime import is_mbta_quiet_hours

# Import all available modes
from display.modes.vehicle_mode import VehicleMode
from display.modes.occupancy_mode import OccupancyMode
from display.modes.speed_mode import SpeedMode
from display.modes.rainbow_mode import RainbowMode
# Import additional modes here as they are created

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.WARNING,  # Changed back to WARNING to reduce noise
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'logs/mbta_display.log',
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)

# Set specific loggers to reduce noise
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.ERROR)

class MBTAStream:
    """Handles MBTA data streaming and display coordination."""
    
    def __init__(self, line: str = None):
        """Initialize the MBTA stream handler.
        
        Args:
            line: MBTA line to track (e.g., 'Red', 'Blue', etc.)
        """
        # Error tracking for graceful recovery
        self.consecutive_json_errors = 0
        self.consecutive_data_errors = 0
        self.max_consecutive_errors = MAX_CONSECUTIVE_ERRORS  # Suppress detailed logs after this many consecutive errors
        self.last_error_time = 0
        self.error_cooldown = ERROR_LOG_COOLDOWN_SECONDS  # Seconds between detailed error logs when errors persist
        
        # Error data saving (disabled by default, enable via SAVE_ERROR_DATA=true in .env)
        self.save_error_data_enabled = False  # Will be set after settings load
        self.error_data_dir = 'logs/error_data'
        
        # Load settings
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load_settings()
        
        # Configure error data saving based on settings
        self.save_error_data_enabled = self.settings.get('save_error_data', False)
        if self.save_error_data_enabled:
            os.makedirs(self.error_data_dir, exist_ok=True)
            self.cleanup_old_error_files()  # Clean up old error files on startup
            logger.info("Error data saving enabled - problematic API data will be saved to logs/error_data/")
        
        self.line = line or self.settings['route']
        
        # Get station mappings
        self.outbound_map, self.inbound_map = station_led_maps[self.line]()
        self.station_maps = {
            'outbound': self.outbound_map,
            'inbound': self.inbound_map
        }
        self.station_id_map = station_id_maps[self.line]()
        
        # Calculate LED strip size
        self.train_leds = max(
            max(self.outbound_map.values() if self.outbound_map else [0]),
            max(self.inbound_map.values() if self.inbound_map else [0])
        )
        
        # Initialize SystemMetrics for health tracking (as writer)
        self.metrics = SystemMetrics(is_writer=True)
        
        # Initialize LED controller
        # Note: LEDController adds color_key_count to led_count internally to get total_leds
        color_key_count = COLOR_KEY_LED_COUNT
        train_led_count = self.train_leds + 1  # +1 because LED positions are 0-indexed
        
        self.led_controller = LEDController(
            led_count=train_led_count,
            color_key_count=color_key_count,
            brightness=self.settings['brightness'],
            power_state=self.settings['power_switch'],
            bedtime_start=self.settings['bedtime_start'],
            bedtime_end=self.settings['bedtime_end'],
            metrics=self.metrics  # Pass metrics to LED controller
        )
        
        # Initialize mode manager
        self.mode_manager = ModeManager(
            self.led_controller,
            self.station_maps,
            self.station_id_map,
            self.settings,
            self.metrics  # Pass metrics to mode manager
        )
        
        # Register available modes
        self.register_modes()
        
        # Set initial mode
        self.mode_manager.switch_mode(self.settings['display_mode'])
        
        # Initialize network monitor
        self.network_monitor = NetworkMonitor(
            on_disconnect=self._handle_network_disconnect,
            on_reconnect=self._handle_network_reconnect,
            max_retries=5,
            check_interval=30
        )
    
    def register_modes(self) -> None:
        """Register all available display modes."""
        self.mode_manager.register_mode('vehicles', VehicleMode)
        self.mode_manager.register_mode('occupancy', OccupancyMode)
        self.mode_manager.register_mode('speed', SpeedMode)
        self.mode_manager.register_mode('rainbow', RainbowMode)
        # Register additional modes here as they are created
    
    def save_error_data(self, event_type: str, raw_data: str, error: Exception, error_category: str) -> str:
        """Save problematic data to a file for debugging.
        
        This method only saves data if save_error_data is enabled in settings.
        Enable via SAVE_ERROR_DATA=true in .env file.
        
        Args:
            event_type: Type of SSE event that caused the error
            raw_data: Raw data string that caused the error (JSON or non-JSON)
            error: The exception that occurred
            error_category: Category of error (e.g., 'json_decode', 'data_structure')
            
        Returns:
            Path to the saved error file, or None if saving is disabled
        """
        # Skip if error data saving is disabled
        if not self.save_error_data_enabled:
            return None
            
        try:
            # Handle None or non-string data
            if raw_data is None:
                raw_data = "None"
            elif not isinstance(raw_data, str):
                raw_data = str(raw_data)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
            
            # Use .txt extension for clearly non-JSON data, .json for potential JSON
            file_extension = ".json" if error_category == "json_decode" else ".txt"
            filename = f"{error_category}_{event_type}_{timestamp}{file_extension}"
            filepath = os.path.join(self.error_data_dir, filename)
            
            # Create error metadata - handle potential issues with data preview
            try:
                # Keep the preview but make it longer and always show full data in raw section
                data_preview = raw_data[:ERROR_DATA_PREVIEW_LENGTH] + "..." if len(raw_data) > ERROR_DATA_PREVIEW_LENGTH else raw_data
                # Ensure preview is safe for JSON serialization
                data_preview = data_preview.encode('utf-8', errors='replace').decode('utf-8')
            except Exception:
                data_preview = "[Data preview unavailable - contains problematic characters]"
            
            error_metadata = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "error_category": error_category,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "data_length": len(raw_data),
                "data_preview": data_preview,
                "data_type": type(raw_data).__name__
            }
            
            # Save both metadata and raw data
            with open(filepath, 'w', encoding='utf-8', errors='replace') as f:
                f.write("=== ERROR METADATA ===\n")
                f.write(json.dumps(error_metadata, indent=2, ensure_ascii=False))
                f.write("\n\n=== RAW DATA ===\n")
                f.write(raw_data)
            
            return filepath
        except Exception as save_error:
            logger.error(f"Failed to save error data: {save_error}")
            return None
    
    def cleanup_old_error_files(self, max_age_days: int = ERROR_FILE_MAX_AGE_DAYS) -> None:
        """Clean up error data files older than specified days.
        
        Args:
            max_age_days: Maximum age of error files to keep (default: 7 days)
        """
        try:
            import glob
            cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
            
            cleaned_count = 0
            # Clean up both .json and .txt error files
            for pattern in ["*.json", "*.txt"]:
                full_pattern = os.path.join(self.error_data_dir, pattern)
                for filepath in glob.glob(full_pattern):
                    try:
                        if os.path.getmtime(filepath) < cutoff_time:
                            os.remove(filepath)
                            cleaned_count += 1
                    except OSError:
                        continue  # Skip files that can't be removed
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old error data files")
                
        except Exception as cleanup_error:
            logger.warning(f"Error during error file cleanup: {cleanup_error}")
    
    def _process_single_vehicle(self, vehicle_data: dict, event_type: str, raw_event_data: str = None) -> bool:
        """Process a single vehicle and return True if successful.
        
        Args:
            vehicle_data: Dictionary containing vehicle data from MBTA API
            event_type: Type of event (reset, add, update, remove)
            raw_event_data: Optional raw event data for error logging
            
        Returns:
            True if vehicle was processed successfully, False otherwise
        """
        try:
            validated_vehicle = validate_vehicle_data(vehicle_data)
            
            if event_type == 'remove':
                if self.mode_manager.current_mode:
                    self.mode_manager.remove_vehicle(validated_vehicle)
            else:
                self.mode_manager.process_vehicle(validated_vehicle)
            
            return True
        except ValueError as e:
            logger.debug(f"Skipping invalid vehicle in {event_type}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Error processing vehicle in {event_type}: {e}")
            if raw_event_data:
                self.save_error_data(event_type, raw_event_data, e, 'processing_error')
            return False
    
    def initialize_state(self) -> None:
        """Get initial state of all vehicles on the line."""
        url = "https://api-v3.mbta.com/vehicles"
        headers = {"x-api-key": self.settings['mbta_api_key']} if self.settings.get('mbta_api_key') else {}
        params = {
            "filter[route]": self.line,
            "include": "trip,stop"
        }
        
        try:
            start_time = time.time()
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            api_latency = (time.time() - start_time) * 1000  # Convert to milliseconds
            self.metrics.record_api_latency(api_latency)
            data = response.json()
            
            if 'data' in data:
                logger.info(f"Initializing state with {len(data['data'])} vehicles")
                for vehicle in data['data']:
                    try:
                        validated_vehicle = validate_vehicle_data(vehicle)
                        self.mode_manager.process_vehicle(validated_vehicle)
                    except ValueError as e:
                        logger.warning(f"Skipping invalid vehicle data: {e}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting initial state: {e}")
    
    def handle_event(self, event, event_count: int = 0) -> None:
        """Handle different types of SSE events with robust error handling."""
        # Skip events with no data or invalid event types
        if not event or not hasattr(event, 'event') or not hasattr(event, 'data'):
            logger.warning("Received invalid event object, skipping")
            return
            
        event_type = event.event
        if not event_type:
            logger.warning("Received event with no event type, skipping")
            return
        
        # Handle empty data
        if not event.data or event.data.strip() == '':
            logger.debug(f"Received empty event (type: '{event_type}')")
            # Note: True keep-alive comment lines (": keep-alive") are not exposed by sseclient
            # This is just an event with no data, which we've already tracked via record_stream_activity()
            return
            
        try:
            # Attempt to parse JSON with better error handling
            data = json.loads(event.data)
            
            # Validate that data is not None and has expected structure
            if data is None:
                logger.warning(f"Received null data for event type '{event_type}', skipping")
                return
            
            # Record successful data reception from SSE stream after successful JSON parsing
            self.metrics.record_stream_activity()
            
            # Check if this is vehicle data (not stop data) to track vehicle updates
            is_vehicle_data = False
            if isinstance(data, dict) and data.get('type') == 'vehicle':
                is_vehicle_data = True
            elif isinstance(data, list):
                # For reset events, check if list contains vehicle data
                is_vehicle_data = any(isinstance(item, dict) and item.get('type') == 'vehicle' for item in data)
            
            if event_type == "reset":
                # Clear display and process all vehicles
                if self.mode_manager.current_mode:
                    self.mode_manager.current_mode.clear_display()
                
                # Handle empty or missing data in reset events
                if not data:
                    logger.debug("Reset event has no data, display cleared")
                    return
                
                # Ensure data is a list for reset events
                if not isinstance(data, list):
                    logger.warning(f"Reset event data is not a list (type: {type(data)}), skipping")
                    return
                
                # Process all vehicles in the reset event
                vehicles_processed = sum(
                    1 for vehicle in data 
                    if isinstance(vehicle, dict) and vehicle.get('type') == 'vehicle'
                    and self._process_single_vehicle(vehicle, 'reset', event.data)
                )
                
                if vehicles_processed > 0:
                    self.metrics.record_vehicle_update('multiple', 'reset')
                    
            elif event_type in ["add", "update"]:
                if not isinstance(data, dict):
                    logger.warning(f"{event_type.capitalize()} event data is not a dict (type: {type(data)}), skipping")
                    return
                
                # Only process vehicle data, skip stop data
                if data.get('type') != 'vehicle':
                    logger.debug(f"Skipping non-vehicle {event_type} event: {data.get('type', 'unknown')} data")
                    return
                
                if self._process_single_vehicle(data, event_type, event.data):
                    self.metrics.record_vehicle_update(data.get('id', 'unknown'), event_type)
                
            elif event_type == "remove":
                if not isinstance(data, dict):
                    logger.warning(f"Remove event data is not a dict (type: {type(data)}), skipping")
                    return
                
                # Remove events can contain stop data or vehicle data
                if data.get('type') == 'vehicle':
                    if self._process_single_vehicle(data, 'remove', event.data):
                        self.metrics.record_vehicle_update(data.get('id', 'unknown'), 'remove')
                elif data.get('type') == 'stop':
                    logger.debug(f"Received stop removal event for stop {data.get('id', 'unknown')}")
                else:
                    logger.debug(f"Skipping unknown remove event type: {data.get('type', 'unknown')}")
            else:
                logger.debug(f"Received unknown event type: '{event_type}', skipping")
                    
        except json.JSONDecodeError as e:
            self.consecutive_json_errors += 1
            current_time = time.time()
            
            # Save the problematic JSON data for debugging
            saved_file = self.save_error_data(event_type or 'unknown', event.data, e, 'json_decode')
            
            # For reset events, fall back to REST API since SSE can truncate large payloads
            if event_type == 'reset':
                logger.info(f"Reset event JSON truncated ({len(event.data)} chars), falling back to REST API")
                self.initialize_state()
                return  # Skip further error handling since we recovered
            
            # Only log detailed errors if we haven't exceeded max consecutive errors
            # or if enough time has passed since the last detailed error log
            if (self.consecutive_json_errors <= self.max_consecutive_errors or 
                current_time - self.last_error_time > self.error_cooldown):
                
                error_preview = event.data[:ERROR_LOG_PREVIEW_LENGTH] + "..." if len(event.data) > ERROR_LOG_PREVIEW_LENGTH else event.data
                log_message = f"JSON decode error for event '{event_type}': {e}. Data preview: {error_preview}"
                if saved_file:
                    log_message += f" Raw data saved to: {saved_file}"
                logger.warning(log_message)
                self.last_error_time = current_time
            elif self.consecutive_json_errors == self.max_consecutive_errors + 1:
                logger.warning(f"Suppressing further JSON decode error logs for {self.error_cooldown}s to prevent spam")
                
        except AttributeError as e:
            self.consecutive_data_errors += 1
            current_time = time.time()
            
            # Save the problematic data for debugging (if we have access to raw data)
            saved_file = None
            if hasattr(event, 'data') and event.data:
                saved_file = self.save_error_data(event_type or 'unknown', event.data, e, 'data_structure')
            
            if (self.consecutive_data_errors <= self.max_consecutive_errors or 
                current_time - self.last_error_time > self.error_cooldown):
                
                log_message = f"Data structure error for event '{event_type}': {e}"
                if saved_file:
                    log_message += f" Raw data saved to: {saved_file}"
                logger.warning(log_message)
                self.last_error_time = current_time
            elif self.consecutive_data_errors == self.max_consecutive_errors + 1:
                logger.warning(f"Suppressing further data structure error logs for {self.error_cooldown}s to prevent spam")
                
        except Exception as e:
            logger.error(f"Unexpected error processing event '{event_type}': {e}")
        else:
            # Reset error counters on successful processing
            if self.consecutive_json_errors > 0:
                logger.info(f"JSON processing recovered after {self.consecutive_json_errors} consecutive errors")
                self.consecutive_json_errors = 0
            if self.consecutive_data_errors > 0:
                logger.info(f"Data processing recovered after {self.consecutive_data_errors} consecutive errors")
                self.consecutive_data_errors = 0
    
    def _handle_network_disconnect(self) -> None:
        """Handle network disconnection."""
        logger.warning("Network disconnected - updating display")
        self.led_controller.set_network_status('disconnected')
    
    def _handle_network_reconnect(self) -> None:
        """Handle network reconnection."""
        logger.info("Network reconnected - restoring display")
        self.led_controller.set_network_status('connected')
        # Reinitialize state to update display
        self.initialize_state()

    def _monitor_and_maintain(self) -> None:
        """Monitor system health and manage display during quiet hours.
        
        This method runs in a background thread and handles:
        - Bedtime transitions (entering/exiting quiet hours)
        - Clearing stale vehicle data during quiet hours
        """
        # Track bedtime state to detect transitions
        last_display_state = self.led_controller.is_display_on()
        
        while True:
            try:
                health_status = self.metrics.get_health_status()
                
                # Check for bedtime transitions (entering or exiting bedtime)
                # This ensures bedtime is enforced even when no events are coming in
                # (e.g., late at night when trains aren't running)
                current_display_state = self.led_controller.is_display_on()
                if current_display_state != last_display_state:
                    # Display state changed - update the display
                    if current_display_state:
                        # Coming out of bedtime - restore last state
                        logger.info("Exiting bedtime - restoring display")
                        self.led_controller.update_display(
                            self.led_controller._last_colors, 
                            self.led_controller._last_color_key
                        )
                    else:
                        # Entering bedtime - clear display
                        logger.info("Entering bedtime - clearing display")
                        self.led_controller.clear_display()
                    last_display_state = current_display_state
                
                # Check for stale vehicle data during quiet hours (handles "straggler trains")
                # If display is on, in quiet hours, API is healthy, but no vehicle data for 10+ min
                # then clear station LEDs (trains likely stopped running)
                # This prevents end-of-service trains from staying lit until bedtime
                if (is_mbta_quiet_hours() and 
                    self.led_controller.is_display_on() and
                    health_status.get('api_healthy', False)):
                    
                    time_since_vehicle_data = self.metrics.get_time_since_last_vehicle_data()
                    # Only clear if we have stale data AND there are still vehicles tracked
                    if (time_since_vehicle_data and 
                        time_since_vehicle_data.total_seconds() > STALE_VEHICLE_DATA_SECONDS and
                        health_status.get('active_vehicles', 0) > 0):  # Still have vehicles
                        # No vehicle data for 10+ minutes during quiet hours
                        # Clear vehicle tracking (sets active_vehicles to 0) and station LEDs
                        # Note: LED health will remain True during quiet hours (see metrics.py line 309-316)
                        logger.info("No vehicle data for 10+ minutes during quiet hours - clearing straggler trains")
                        self.mode_manager.clear_all_vehicles()  # Clear vehicle tracking
                        self.led_controller.clear_station_leds()  # Clear LEDs but keep color key
                
                time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in _monitor_and_maintain thread: {e}")
                time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)

    def run(self) -> None:
        """Run the MBTA stream and display updates."""
        # Initialize display with current state once at startup
        self.initialize_state()
        
        health_thread = threading.Thread(target=self._monitor_and_maintain, daemon=True)
        health_thread.start()
        
        while True:
            messages = None
            session = None
            try:
                # Check network status
                if not self.network_monitor.is_connected():
                    logger.warning("Network not connected - waiting for reconnection")
                    self.led_controller.set_network_status('disconnected')
                    time.sleep(NETWORK_DISCONNECTION_WAIT_SECONDS)
                    continue
                
                url = "https://api-v3.mbta.com/vehicles"
                headers = {
                    "Accept": "text/event-stream",
                    "x-api-key": self.settings['mbta_api_key']
                } if self.settings.get('mbta_api_key') else {"Accept": "text/event-stream"}
                params = {
                    "filter[route]": self.line,
                    "include": "trip,stop"
                }
                
                logger.info(f"\nStarting MBTA {self.line} line vehicle stream...")
                logger.info("Waiting for events (press Ctrl+C to stop)...")
                
                # Start SSE client with a properly configured session
                # Using a session with chunk_size helps ensure proper buffering of large events
                # (reset events can be 30KB+ and were getting truncated)
                session = requests.Session()
                # Use larger chunk size to better handle large reset events
                messages = sseclient.SSEClient(
                    url, 
                    session=session,
                    headers=headers, 
                    params=params,
                    chunk_size=SSE_CHUNK_SIZE  # 64KB chunks to handle large reset events
                )
                
                # The SSE client's event loop blocks while waiting for new events from the MBTA API stream
                # loop is only exited when the stream is stopped by the user or a network error occurs
                event_count = 0
                for event in messages:
                    event_count += 1
                    
                    # Record that we received an event from the SSE stream
                    # This keeps connection health tracking updated even if events are empty/unknown
                    # Note: sseclient doesn't expose actual keep-alive comment lines (": keep-alive"),
                    # but receiving any event from the iterator means the connection is alive
                    self.metrics.record_stream_activity()
                    
                    # Check for settings changes
                    new_settings = self.settings_manager.check_and_reload()
                    if new_settings is not None:
                        self.mode_manager.update_settings(new_settings)
                        self.settings = new_settings
                        self.initialize_state()  # Refresh display state with new settings
                    
                    self.handle_event(event, event_count)
                
                if event_count % HEALTH_LOG_FREQUENCY == 0:
                    health_status = self.metrics.get_health_status()
                    
            except KeyboardInterrupt:
                logger.info("\nStream stopped by user")
                break
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error in stream: {e}")
                self.led_controller.set_network_status('reconnecting')
                time.sleep(STREAM_ERROR_RETRY_WAIT_SECONDS)
                continue
                
            except Exception as e:
                logger.error(f"Error in stream: {e}")
                time.sleep(STREAM_ERROR_RETRY_WAIT_SECONDS)
                continue
                
            finally:
                # Clean up streaming resources
                if messages:
                    del messages
                if session:
                    session.close()
        
        # Clean up
        self.network_monitor.cleanup()
        self.mode_manager.cleanup()
        if hasattr(self, 'metrics'):
            self.metrics.cleanup()

if __name__ == "__main__":
    stream = MBTAStream()
    stream.run() 