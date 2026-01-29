from typing import Dict, Any, List, Tuple, Optional
from .base_mode import DisplayModeBase
from .color_utils import interpolate_color
from config.constants import MAX_VEHICLE_SPEED_MPH
from config.validation import DEFAULT_SETTINGS

class SpeedMode(DisplayModeBase):
    """Display mode that shows vehicle speeds using color intensity."""
    
    def __init__(self, led_count: int, station_maps: Dict, station_id_map: Dict, settings: Dict):
        """Initialize the speed mode."""
        super().__init__(led_count, station_maps, station_id_map, settings)
        self.max_speed = MAX_VEHICLE_SPEED_MPH  # Maximum expected speed in mph
        
        # Get color settings with defaults from DEFAULT_SETTINGS
        self.min_speed_color = settings.get('min_speed_color', DEFAULT_SETTINGS['min_speed_color'])
        self.max_speed_color = settings.get('max_speed_color', DEFAULT_SETTINGS['max_speed_color'])
        self.null_speed_color = settings.get('null_speed_color', DEFAULT_SETTINGS['null_speed_color'])
    
    def set_vehicle_led_color(self, vehicle_data: Dict[str, Any], led_position: int) -> Optional[Tuple[int, int, int]]:
        """Determine LED color based on vehicle speed."""
        # Get speed data
        speed = vehicle_data['attributes'].get('speed')
        
        if speed is None or speed == 0:
            # No speed data or stopped
            return tuple(self.null_speed_color)
        
        # Interpolate between min and max speed colors
        return interpolate_color(speed, self.max_speed, self.min_speed_color, self.max_speed_color)
    
    def get_color_key(self) -> List[Tuple[int, int, int]]:
        """Return the color key showing speed levels."""
        return [
            tuple(self.min_speed_color),    # Min speed color
            tuple(self.max_speed_color),    # Max speed color
            tuple(self.null_speed_color)    # No data/stopped color
        ]
    
    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """Update the mode's settings and refresh color variables.
        
        Args:
            new_settings: Dictionary containing new settings
        """
        self.settings = new_settings
        
        # Update color settings with new values from DEFAULT_SETTINGS
        self.min_speed_color = new_settings.get('min_speed_color', DEFAULT_SETTINGS['min_speed_color'])
        self.max_speed_color = new_settings.get('max_speed_color', DEFAULT_SETTINGS['max_speed_color'])
        self.null_speed_color = new_settings.get('null_speed_color', DEFAULT_SETTINGS['null_speed_color'])