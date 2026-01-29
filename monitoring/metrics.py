"""Performance metrics collection and tracking optimized for Raspberry Pi."""
import time
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque
import json
import os
import fcntl  # For file locking
from dotenv import load_dotenv
from config.bedtime import is_mbta_quiet_hours
from config.constants import (
    API_LATENCY_HISTORY_SIZE,
    UPDATE_TIMES_HISTORY_SIZE,
    VALIDATION_TIMES_HISTORY_SIZE,
    SYSTEM_RESOURCE_UPDATE_INTERVAL_SECONDS,
    METRICS_FILE_MAX_AGE_SECONDS,
    HEALTH_CHECK_QUIET_HOURS_TIMEOUT_HOURS,
    HEALTH_CHECK_API_TIMEOUT_MINUTES,
    HEALTH_CHECK_LED_TIMEOUT_MINUTES,
    METRICS_INITIAL_SAVE_DELAY_SECONDS,
    METRICS_SAVE_INTERVAL_SECONDS,
)
from .system_utils import get_memory_usage, get_cpu_temperature

logger = logging.getLogger(__name__)

class SystemMetrics:
    """Tracks system performance metrics and health indicators."""
    
    def __init__(self, metrics_file: str = 'logs/metrics.json', is_writer: bool = False):
        """Initialize the metrics tracker.
        
        Args:
            metrics_file: Path to store metrics data
            is_writer: Whether this instance writes metrics (True for display controller, False for website)
        """
        self.metrics_file = metrics_file
        self.is_writer = is_writer
        self._lock = threading.Lock()
        
        # Uptime tracking - use system boot time instead of instance start time
        self._first_start_file = 'logs/first_start.json'
        self._first_start_time = self._load_or_create_first_start()
        
        # Performance metrics - reduced history size
        self._api_latency = deque(maxlen=API_LATENCY_HISTORY_SIZE)    # Last 20 API response times
        self._update_times = deque(maxlen=UPDATE_TIMES_HISTORY_SIZE)    # Last 20 LED update times
        self._validation_times = deque(maxlen=VALIDATION_TIMES_HISTORY_SIZE) # Last 10 validation times
        
        # Health metrics
        self._error_counts: Dict[str, int] = {
            'api_errors': 0,
            'validation_errors': 0,
            'led_errors': 0,
            'process_crashes': 0
        }
        self._last_api_success: Optional[datetime] = None
        self._last_led_update: Optional[datetime] = None
        self._last_vehicle_data: Optional[datetime] = None  # Track when we last received vehicle data
        
        # System resource metrics
        self._memory_usage: Optional[Dict] = None
        self._cpu_temperature: Optional[float] = None
        self._last_resource_check: Optional[datetime] = None
        
        # Vehicle metrics - minimal tracking
        self._active_vehicles = 0
        self._last_vehicle_update = None
        
        # Start periodic save only for writer instances
        self._should_run = True
        if self.is_writer:
            self._save_thread = threading.Thread(target=self._periodic_save, daemon=True)
            self._save_thread.start()
        else:
            self._save_thread = None
            # Reader instances should not create empty metrics files
            self._last_api_success = None
            self._last_led_update = None
    
    def _get_system_boot_time(self) -> Optional[datetime]:
        """Get the system boot time from /proc/uptime.
        
        Returns:
            datetime: System boot time, or None if unable to determine
        """
        try:
            # Read system uptime from /proc/uptime (available on Linux/Raspberry Pi)
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
            
            # Calculate boot time
            boot_time = datetime.now() - timedelta(seconds=uptime_seconds)
            return boot_time
        except Exception as e:
            logger.warning(f"Could not determine system boot time: {e}")
            return None
    
    def _load_or_create_first_start(self) -> datetime:
        """Load or create the first start timestamp.
        
        Returns:
            datetime: The timestamp when the system was first started
        """
        try:
            # Ensure logs directory exists
            os.makedirs('logs', exist_ok=True)
            
            # Try to load existing first start time
            if os.path.exists(self._first_start_file):
                with open(self._first_start_file, 'r') as f:
                    data = json.load(f)
                    first_start_str = data.get('first_start_time')
                    if first_start_str:
                        return datetime.fromisoformat(first_start_str)
            
            # If file doesn't exist or is invalid, create it with current time
            first_start = datetime.now()
            if self.is_writer:  # Only writer should create this file
                with open(self._first_start_file, 'w') as f:
                    json.dump({
                        'first_start_time': first_start.isoformat(),
                        'note': 'This file tracks when the MBTA LED Controller was first deployed'
                    }, f, indent=2)
                logger.info(f"Created first start timestamp: {first_start.isoformat()}")
            
            return first_start
            
        except Exception as e:
            logger.error(f"Failed to load/create first start time: {e}")
            # Return current time as fallback
            return datetime.now()
    
    def record_api_latency(self, latency_ms: float) -> None:
        """Record API response latency."""
        if not self.is_writer:
            return  # Reader instances don't record data
        with self._lock:
            self._api_latency.append(latency_ms)
            self._last_api_success = datetime.now()
    
    def record_stream_activity(self) -> None:
        """Record activity from the SSE stream (data received or event).
        
        This method updates the last_api_success timestamp whenever we receive
        any event from the MBTA SSE stream, confirming the connection is alive.
        
        LIMITATION: The underlying sseclient library does NOT expose SSE comment lines
        (": keep-alive"). During MBTA quiet hours (2am-5am) when no trains run, the
        server only sends keep-alive comments, which sseclient silently consumes without
        yielding events. This means during quiet hours, this method won't be called for
        4+ hours even though the connection is perfectly healthy. Health checks account
        for this by using extended timeouts during quiet hours.
        """
        if not self.is_writer:
            return  # Reader instances don't record data
        with self._lock:
            self._last_api_success = datetime.now()
    
    def record_update_time(self, update_ms: float) -> None:
        """Record LED update time."""
        if not self.is_writer:
            return  # Reader instances don't record data
        with self._lock:
            self._update_times.append(update_ms)
            # Don't update _last_led_update here - that's handled by record_led_update()
    
    def record_led_update(self) -> None:
        """Record LED update occurrence (without timing).
        
        This method updates the last_led_update timestamp whenever LEDs are updated,
        even when the update doesn't go through the normal update_display flow.
        """
        if not self.is_writer:
            return  # Reader instances don't record data
        with self._lock:
            self._last_led_update = datetime.now()
    
    def record_validation_time(self, validation_ms: float) -> None:
        """Record data validation time."""
        if not self.is_writer:
            return  # Reader instances don't record data
        with self._lock:
            self._validation_times.append(validation_ms)
    
    def record_error(self, error_type: str) -> None:
        """Record an error occurrence."""
        if not self.is_writer:
            return  # Reader instances don't record data
        with self._lock:
            if error_type in self._error_counts:
                self._error_counts[error_type] += 1
    
    def record_vehicle_update(self, vehicle_id: str, status: str) -> None:
        """Record a vehicle update."""
        if not self.is_writer:
            return  # Reader instances don't record data
        with self._lock:
            self._last_vehicle_data = datetime.now()  # Track when we received vehicle data
            self._last_vehicle_update = {
                'timestamp': datetime.now().isoformat(),
                'vehicle_id': vehicle_id,
                'status': status
            }
    
    def update_active_vehicles(self, count: int) -> None:
        """Update count of active vehicles."""
        if not self.is_writer:
            return  # Reader instances don't record data
        with self._lock:
            self._active_vehicles = count
    
    def get_time_since_last_vehicle_data(self) -> Optional[timedelta]:
        """Get time since last vehicle data was received.
        
        Returns:
            timedelta if vehicle data has been received, None otherwise
        """
        with self._lock:
            if self._last_vehicle_data is None:
                return None
            return datetime.now() - self._last_vehicle_data
    
    def _get_current_display_mode(self) -> str:
        """Read the current display mode from the .env file.
        
        Returns:
            str: The current display mode, or 'unknown' if unable to read
        """
        try:
            # Try to find the .env file in common locations
            possible_env_paths = [
                '.env',  # Current working directory
                os.path.join(os.getcwd(), '.env'),  # Explicit current directory
                os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),  # Project root
            ]
            
            env_file = None
            for path in possible_env_paths:
                if os.path.exists(path):
                    env_file = path
                    break
            
            if not env_file:
                return 'unknown'
            
            # Read the .env file directly to get current display mode
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('DISPLAY_MODE='):
                        # Extract value, removing quotes if present
                        value = line.split('=', 1)[1].strip()
                        # Remove surrounding quotes if they exist
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        return value.lower()
            
            return 'unknown'
        except Exception as e:
            logger.debug(f"Could not read display mode from .env: {e}")
            return 'unknown'
    
    def _update_system_resources(self) -> None:
        """Update system resource metrics if needed."""
        if not self.is_writer:
            return  # Only writer instances collect resource data
            
        now = datetime.now()
        # Update every 30 seconds
        if (self._last_resource_check is None or 
            now - self._last_resource_check > timedelta(seconds=SYSTEM_RESOURCE_UPDATE_INTERVAL_SECONDS)):
            self._memory_usage = get_memory_usage()
            self._cpu_temperature = get_cpu_temperature()
            self._last_resource_check = now
    
    def get_health_status(self) -> Dict:
        """Get current system health status."""
        with self._lock:
            # If this is a reader instance (website), always try to load from shared file first
            if not self.is_writer:
                shared_health = self._load_shared_health()
                if shared_health:
                    return shared_health
                else:
                    # Return a default unhealthy status if no shared data available
                    # Try to read display mode from .env even if metrics aren't available
                    display_mode = self._get_current_display_mode()
                    default_health = {
                        'timestamp': datetime.now().isoformat(),
                        'healthy': False,
                        'api_healthy': False,
                        'led_healthy': False,
                        'active_vehicles': 0,
                        'display_mode': display_mode,
                        'avg_api_latency_ms': 0,
                        'avg_update_time_ms': 0,
                        'error_counts': {'api_errors': 0, 'validation_errors': 0, 'led_errors': 0, 'process_crashes': 0},
                        'last_api_success': None,
                        'last_led_update': None,
                        'note': 'No shared metrics available - display controller may not be running'
                    }
                    return default_health
            
            # Use local metrics for writer instances
            now = datetime.now()
            
            # Get system boot time (session start = last reboot)
            system_boot = self._get_system_boot_time()
            
            # Check if we're in MBTA quiet hours (late night when service is minimal/off)
            is_quiet_hours = is_mbta_quiet_hours()
            
            # Adjust health check thresholds based on time of day
            # Note: sseclient does NOT expose SSE comment lines (": keep-alive"), so during
            # quiet hours when no trains run, we won't get any events for extended periods (4+ hours)
            # even though the TCP connection is alive. We adjust timeouts to reflect this reality.
            if is_quiet_hours:
                api_timeout = timedelta(hours=HEALTH_CHECK_QUIET_HOURS_TIMEOUT_HOURS)  # Assume healthy during entire quiet hours period
                led_timeout = timedelta(hours=HEALTH_CHECK_QUIET_HOURS_TIMEOUT_HOURS)  # LED updates not expected during quiet hours
            else:
                api_timeout = timedelta(minutes=HEALTH_CHECK_API_TIMEOUT_MINUTES)  # Normal hours: expect regular vehicle updates
                led_timeout = timedelta(minutes=HEALTH_CHECK_LED_TIMEOUT_MINUTES)  # Normal hours: expect regular LED updates
            
            # Check API health - MBTA API calls happen when events occur, not continuously
            # For SSE streams, we track any event from the iterator to monitor connection health
            api_healthy = (
                self._last_api_success is not None and
                (now - self._last_api_success) < api_timeout
            )
            
            # Check LED update health - LEDs update when vehicles change, not continuously
            # During quiet hours, if API is healthy (stream connected), LED health is less critical
            # since no trains running = no LED updates is expected behavior
            if is_quiet_hours and api_healthy:
                led_healthy = True
            else:
                # Normal hours or API unhealthy: require recent LED updates
                led_healthy = (
                    self._last_led_update is not None and
                    (now - self._last_led_update) < led_timeout
                )
            
            # Calculate average latencies - only if we have data
            avg_api_latency = (
                sum(self._api_latency) / len(self._api_latency)
                if self._api_latency else 0
            )
            avg_update_time = (
                sum(self._update_times) / len(self._update_times)
                if self._update_times else 0
            )
            
            # Calculate uptime in seconds - use system boot time for accurate session tracking
            if system_boot:
                session_uptime_seconds = int((now - system_boot).total_seconds())
                session_start_iso = system_boot.isoformat()
            else:
                # Fallback if we can't read system boot time
                session_uptime_seconds = 0
                session_start_iso = None
            
            total_uptime_seconds = int((now - self._first_start_time).total_seconds())
            
            # Get current display mode from settings
            display_mode = self._get_current_display_mode()
            
            # Update system resources
            self._update_system_resources()
            
            health_status = {
                'timestamp': now.isoformat(),
                'healthy': api_healthy and led_healthy,
                'api_healthy': api_healthy,
                'led_healthy': led_healthy,
                'is_quiet_hours': is_quiet_hours,
                'active_vehicles': self._active_vehicles,
                'display_mode': display_mode,
                'avg_api_latency_ms': round(avg_api_latency, 2),
                'avg_update_time_ms': round(avg_update_time, 2),
                'error_counts': self._error_counts.copy(),
                'last_api_success': (
                    self._last_api_success.isoformat()
                    if self._last_api_success else None
                ),
                'last_led_update': (
                    self._last_led_update.isoformat()
                    if self._last_led_update else None
                ),
                'session_uptime_seconds': session_uptime_seconds,
                'total_uptime_seconds': total_uptime_seconds,
                'session_start_time': session_start_iso,
                'first_start_time': self._first_start_time.isoformat(),
                'memory_usage': self._memory_usage,
                'cpu_temperature': self._cpu_temperature
            }
            
            return health_status
    
    def get_performance_metrics(self) -> Dict:
        """Get detailed performance metrics."""
        with self._lock:
            metrics = {}
            
            # Only include metrics if we have data
            if self._api_latency:
                metrics['api_latency'] = {
                    'avg': round(sum(self._api_latency) / len(self._api_latency), 2),
                    'min': round(min(self._api_latency), 2),
                    'max': round(max(self._api_latency), 2),
                    'samples': len(self._api_latency)
                }
            
            if self._update_times:
                metrics['update_times'] = {
                    'avg': round(sum(self._update_times) / len(self._update_times), 2),
                    'min': round(min(self._update_times), 2),
                    'max': round(max(self._update_times), 2),
                    'samples': len(self._update_times)
                }
            
            if self._validation_times:
                metrics['validation_times'] = {
                    'avg': round(sum(self._validation_times) / len(self._validation_times), 2),
                    'min': round(min(self._validation_times), 2),
                    'max': round(max(self._validation_times), 2),
                    'samples': len(self._validation_times)
                }
            
            return metrics
    
    def _load_shared_health(self) -> Optional[Dict]:
        """Load health status from shared metrics file.
        
        Returns:
            Dict containing health status if file exists and is recent, None otherwise
        """
        try:
            if not os.path.exists(self.metrics_file):
                logger.info(f"Shared metrics file does not exist: {self.metrics_file}")
                return None
            
            # Check if file is recent (within last 2 minutes for inter-process communication)
            file_age = time.time() - os.path.getmtime(self.metrics_file)
            if file_age > METRICS_FILE_MAX_AGE_SECONDS:
                logger.info(f"Shared metrics file too old: {file_age:.1f}s")
                return None
            
            with open(self.metrics_file, 'r') as f:
                # Acquire shared lock for reading
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    health_data = data.get('health')
                    logger.info(f"Loaded shared health data: file_age={file_age:.1f}s, healthy={health_data.get('healthy', 'unknown')}")
                    return health_data
                finally:
                    # Release the lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception as e:
            logger.error(f"Could not load shared health data: {e}")
            return None
    
    def _periodic_save(self) -> None:
        """Periodically save metrics to file."""
        # Wait 30 seconds before first save to allow system to initialize
        time.sleep(METRICS_INITIAL_SAVE_DELAY_SECONDS)
        
        while self._should_run:
            try:
                # Always save if we have any meaningful data
                has_data = (
                    self._last_api_success is not None or 
                    self._last_led_update is not None or
                    self._active_vehicles > 0 or
                    any(count > 0 for count in self._error_counts.values())
                )
                
                if has_data:
                    metrics = {
                        'health': self.get_health_status(),
                        'performance': self.get_performance_metrics()
                    }
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
                    
                    # Save metrics with file locking to prevent concurrent access conflicts
                    with open(self.metrics_file, 'w') as f:
                        # Acquire exclusive lock on the file
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        try:
                            json.dump(metrics, f)
                            f.flush()  # Ensure data is written to disk
                            os.fsync(f.fileno())  # Force sync to disk
                        finally:
                            # Release the lock
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    
                    logger.debug(f"Saved metrics to {self.metrics_file} - last_api_success: {metrics['health'].get('last_api_success')}")
                
            except Exception as e:
                logger.error(f"Failed to save metrics: {e}")
            
            time.sleep(METRICS_SAVE_INTERVAL_SECONDS)  # Save every 15 seconds for better responsiveness with SSE data
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self._should_run = False
        if self._save_thread and self._save_thread.is_alive():
            self._save_thread.join(timeout=5) 