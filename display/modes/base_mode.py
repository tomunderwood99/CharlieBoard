from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional
from config.constants import LED_OFF

class DisplayModeBase(ABC):
    """Base class for all display modes.
    
    This class defines the interface that all display modes must implement.
    Each mode is responsible for processing vehicle data and determining LED colors.
    """
    
    def __init__(self, led_count: int, station_maps: Dict, station_id_map: Dict, settings: Dict):
        """Initialize the display mode.
        
        Args:
            led_count: Number of LEDs in the strip (excluding color key LEDs)
            station_maps: Dictionary containing inbound and outbound station to LED mappings
            station_id_map: Dictionary mapping station IDs to station names
            settings: Dictionary containing display settings (colors, etc.)
        """
        self.led_count = led_count
        self.outbound_map = station_maps.get('outbound', {})
        self.inbound_map = station_maps.get('inbound', {})
        self.station_id_map = station_id_map
        self.settings = settings
        self.led_colors = [LED_OFF] * led_count  # Initialize all LEDs to off
        # Track vehicle positions
        self.vehicle_positions = {}
    
    def process_vehicle(self, vehicle_data: Dict[str, Any]) -> None:
        """Process a vehicle update and update LED colors accordingly.
        
        This method handles the common vehicle position tracking and delegates
        the specific color determination to set_vehicle_led_color().
        
        Args:
            vehicle_data: Dictionary containing vehicle data from MBTA API
        """
        vehicle_id = vehicle_data.get('id')
        
        # Clear previous position if vehicle moved
        if vehicle_id in self.vehicle_positions:
            old_position = self.vehicle_positions[vehicle_id]
            if old_position is not None:
                self.led_colors[old_position] = LED_OFF
        
        # Get new LED position
        led_position = self.get_vehicle_led_position(vehicle_data)
        if led_position is not None:
            # Let the specific mode determine the color
            color = self.set_vehicle_led_color(vehicle_data, led_position)
            if color is not None:
                self.led_colors[led_position] = color
            # Store new position
            self.vehicle_positions[vehicle_id] = led_position
    
    @abstractmethod
    def set_vehicle_led_color(self, vehicle_data: Dict[str, Any], led_position: int) -> Optional[Tuple[int, int, int]]:
        """Determine the LED color for a vehicle at the given position.
        
        This method should be implemented by each mode to determine the specific
        color logic for that mode.
        
        Args:
            vehicle_data: Dictionary containing vehicle data from MBTA API
            led_position: The LED position to set
            
        Returns:
            RGB color tuple or None if the LED should not be updated
        """
        pass
    
    @abstractmethod
    def get_color_key(self) -> List[Tuple[int, int, int]]:
        """Return the colors for the mode's color key LEDs.
        
        Returns:
            List of RGB tuples for the color key LEDs
        """
        pass
    
    def get_vehicle_led_position(self, vehicle_data: Dict[str, Any]) -> Optional[int]:
        """Get the LED position for a vehicle based on its stop data.
        
        Args:
            vehicle_data: Dictionary containing vehicle data
            
        Returns:
            LED position index if valid stop found, None otherwise
        """
        attrs = vehicle_data['attributes']
        stop_data = vehicle_data.get('relationships', {}).get('stop', {}).get('data')
        
        if stop_data:
            stop_id = stop_data['id']
            station_name = self.station_id_map.get(stop_id)
            direction = int(attrs.get('direction_id', 0))
            
            if station_name:
                return (self.outbound_map if direction == 0 else self.inbound_map).get(station_name)
        return None
    
    def clear_vehicle(self, vehicle_data: Dict[str, Any]) -> None:
        """Clear the LED for a vehicle's previous position.
        
        Args:
            vehicle_data: Dictionary containing vehicle data
        """
        vehicle_id = vehicle_data.get('id')
        if vehicle_id in self.vehicle_positions:
            position = self.vehicle_positions[vehicle_id]
            if position is not None:
                self.led_colors[position] = LED_OFF
            del self.vehicle_positions[vehicle_id]
    
    def get_led_colors(self) -> List[Tuple[int, int, int]]:
        """Get the current LED colors for the strip.
        
        Returns:
            List of RGB tuples for each LED
        """
        return self.led_colors
    
    def clear_display(self) -> None:
        """Clear all LEDs in the display and reset vehicle positions."""
        self.led_colors = [LED_OFF] * self.led_count
        self.vehicle_positions = {}
    
    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """Update the mode's settings.
        
        This method can be overridden by subclasses that need to update
        additional instance variables when settings change.
        
        Args:
            new_settings: Dictionary containing new settings
        """
        self.settings = new_settings 