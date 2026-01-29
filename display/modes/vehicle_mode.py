from typing import Dict, Any, List, Tuple, Optional
from .base_mode import DisplayModeBase
from config.constants import LED_OFF

class VehicleMode(DisplayModeBase):
    """Display mode that shows vehicle status (stopped, incoming, in transit)."""
    
    def __init__(self, led_count: int, station_maps: Dict, station_id_map: Dict, settings: Dict):
        """Initialize the vehicle mode.
        
        Args:
            led_count: Number of LEDs in the strip
            station_maps: Dictionary containing station mappings
            station_id_map: Dictionary mapping station IDs to station names
            settings: Dictionary containing color settings
        """
        super().__init__(led_count, station_maps, station_id_map, settings)
        
    def set_vehicle_led_color(self, vehicle_data: Dict[str, Any], led_position: int) -> Optional[Tuple[int, int, int]]:
        """Determine LED color based on vehicle status."""
        current_status = vehicle_data['attributes'].get('current_status')
        
        if current_status == 'STOPPED_AT':
            return tuple(self.settings['stopped_color'])
        elif current_status == 'INCOMING_AT':
            return tuple(self.settings['incoming_color'])
        elif current_status == 'IN_TRANSIT_TO':
            return tuple(self.settings['transit_color'])
        else:
            return LED_OFF
    
    def get_color_key(self) -> List[Tuple[int, int, int]]:
        """Return the color key showing what each color means."""
        return [
            tuple(self.settings['stopped_color']),
            tuple(self.settings['incoming_color']),
            tuple(self.settings['transit_color'])
        ]
    
    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """Update the mode's settings.
        
        Args:
            new_settings: Dictionary containing new settings
        """
        self.settings = new_settings 