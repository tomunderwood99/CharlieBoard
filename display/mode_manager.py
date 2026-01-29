from typing import Dict, Type, Optional
from .modes.base_mode import DisplayModeBase
from .controller.led_controller import LEDController
from config.validation import DEFAULT_SETTINGS
import time

class ModeManager:
    """Manages display modes and handles switching between them."""
    
    def __init__(self, led_controller: LEDController, station_maps: Dict, station_id_map: Dict, settings: Dict, metrics=None):
        """Initialize the mode manager.
        
        Args:
            led_controller: LED controller instance
            station_maps: Dictionary containing station mappings
            station_id_map: Dictionary mapping station IDs to station names
            settings: Dictionary containing display settings
            metrics: Optional SystemMetrics instance for performance tracking
        """
        self.led_controller = led_controller
        self.station_maps = station_maps
        self.station_id_map = station_id_map
        self.settings = settings
        self.metrics = metrics
        self.available_modes: Dict[str, Type[DisplayModeBase]] = {}
        self.current_mode: Optional[DisplayModeBase] = None
        self.current_mode_name: Optional[str] = None
        # Track all known vehicles for mode switching
        self.known_vehicles: Dict[str, Dict] = {}
    
    def register_mode(self, name: str, mode_class: Type[DisplayModeBase]) -> None:
        """Register a new display mode.
        
        Args:
            name: Name of the mode
            mode_class: Class implementing DisplayModeBase
        """
        self.available_modes[name] = mode_class
    
    def switch_mode(self, mode_name: str) -> bool:
        """Switch to a different display mode.
        
        Args:
            mode_name: Name of the mode to switch to
            
        Returns:
            bool: True if switch successful, False otherwise
        """
        if mode_name not in self.available_modes:
            return False
        
        # Clear current mode if it exists
        if self.current_mode:
            self.current_mode.clear_display()
        
        # Initialize new mode
        mode_class = self.available_modes[mode_name]
        self.current_mode = mode_class(
            self.led_controller.led_count,
            self.station_maps,
            self.station_id_map,
            self.settings
        )
        self.current_mode_name = mode_name
        
        # Reprocess all known vehicles in new mode
        for vehicle_data in self.known_vehicles.values():
            self.current_mode.process_vehicle(vehicle_data)
        
        # Update display with reprocessed vehicles
        self.update_display()
        
        return True
    
    def process_vehicle(self, vehicle_data: Dict) -> None:
        """Process vehicle data with current mode.
        
        Args:
            vehicle_data: Dictionary containing vehicle data
        """
        if self.current_mode:
            # Update known vehicles
            vehicle_id = vehicle_data.get('id')
            if vehicle_id:
                self.known_vehicles[vehicle_id] = vehicle_data
                
                # Record vehicle update for health monitoring
                if self.metrics:
                    vehicle_status = vehicle_data.get('attributes', {}).get('current_status', 'unknown')
                    self.metrics.record_vehicle_update(vehicle_id, vehicle_status)
                    self.metrics.update_active_vehicles(len(self.known_vehicles))
            
            self.current_mode.process_vehicle(vehicle_data)
            self.update_display()
    
    def update_display(self) -> None:
        """Update the LED display with current mode's colors."""
        if self.current_mode:
            start_time = time.time()
            colors = self.current_mode.get_led_colors()
            color_key = self.current_mode.get_color_key()
            self.led_controller.update_display(colors, color_key)
            
            # Record LED update time for health monitoring
            if self.metrics:
                update_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                self.metrics.record_update_time(update_time)
    
    def update_settings(self, new_settings: Dict) -> None:
        """Update settings and reinitialize current mode if needed.
        
        Args:
            new_settings: Dictionary containing new settings
        """
        old_mode = self.settings.get('display_mode')
        self.settings = new_settings
        
        # Update power state
        power_state = new_settings.get('power_switch', 'off')
        self.led_controller.set_power(power_state)
        
        # Always update bedtime with current settings (using defaults if not provided)
        bedtime_start = new_settings.get('bedtime_start', DEFAULT_SETTINGS['bedtime_start'])
        bedtime_end = new_settings.get('bedtime_end', DEFAULT_SETTINGS['bedtime_end'])
        self.led_controller.update_bedtime(bedtime_start, bedtime_end)
        
        # If display mode changed, switch to new mode
        new_mode = new_settings.get('display_mode')
        if new_mode != old_mode:
            self.switch_mode(new_mode)
        else:
            # If mode didn't change, update the current mode's settings
            if self.current_mode and hasattr(self.current_mode, 'update_settings'):
                self.current_mode.update_settings(new_settings)
                # Reprocess all known vehicles with the new color settings
                # This ensures existing vehicles get the new colors immediately
                # Skip reprocessing for rainbow mode since it doesn't use vehicle colors
                if self.current_mode_name != 'rainbow':
                    for vehicle_data in self.known_vehicles.values():
                        self.current_mode.process_vehicle(vehicle_data)
                # Force a display update to show the new colors
                self.update_display()
        
        # Update brightness
        brightness = new_settings.get('brightness', DEFAULT_SETTINGS['brightness'])
        self.led_controller.set_brightness(brightness)
    
    def remove_vehicle(self, vehicle_data: Dict) -> None:
        """Remove a vehicle from tracking and display.
        
        Args:
            vehicle_data: Dictionary containing vehicle data
        """
        if self.current_mode:
            vehicle_id = vehicle_data.get('id')
            if vehicle_id and vehicle_id in self.known_vehicles:
                del self.known_vehicles[vehicle_id]
                self.current_mode.clear_vehicle(vehicle_data)
                
                # Update active vehicle count for health monitoring
                if self.metrics:
                    self.metrics.update_active_vehicles(len(self.known_vehicles))
                
                self.update_display()
    
    def clear_all_vehicles(self) -> None:
        """Clear all tracked vehicles and reset display (used for straggler trains during quiet hours).
        
        This clears the internal vehicle tracking and updates metrics to show 0 active vehicles.
        The caller is responsible for updating the physical LED display as needed.
        """
        if self.current_mode:
            # Clear each vehicle from the mode's internal tracking
            for vehicle_data in list(self.known_vehicles.values()):
                self.current_mode.clear_vehicle(vehicle_data)
            
            # Clear the known vehicles dictionary
            self.known_vehicles.clear()
            
            # Update metrics to show 0 active vehicles
            if self.metrics:
                self.metrics.update_active_vehicles(0)
    
    def cleanup(self) -> None:
        """Clean up resources before shutting down."""
        # Clear all known vehicles
        if self.current_mode:
            for vehicle_data in list(self.known_vehicles.values()):
                self.current_mode.clear_vehicle(vehicle_data)
            self.current_mode.clear_display()
        self.led_controller.cleanup()
        self.known_vehicles.clear() 