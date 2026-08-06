from typing import Dict, Any, List, Tuple, Optional
from .base_mode import DisplayModeBase
from .color_utils import interpolate_color
from ..speed_estimator import line_max_speed_mph
from config.validation import DEFAULT_SETTINGS

class SpeedMode(DisplayModeBase):
    """Display mode that shows vehicle speeds using color intensity."""
    
    def __init__(self, led_count: int, station_maps: Dict, station_id_map: Dict, settings: Dict):
        """Initialize the speed mode."""
        super().__init__(led_count, station_maps, station_id_map, settings)
        route = settings.get('route', 'Red')
        self.max_speed = line_max_speed_mph(route)  # Maximum expected speed in mph
        
        # Get color settings with defaults from DEFAULT_SETTINGS
        self.min_speed_color = settings.get('min_speed_color', DEFAULT_SETTINGS['min_speed_color'])
        self.max_speed_color = settings.get('max_speed_color', DEFAULT_SETTINGS['max_speed_color'])
        self.null_speed_color = settings.get('null_speed_color', DEFAULT_SETTINGS['null_speed_color'])
    
    def set_vehicle_led_color(self, vehicle_data: Dict[str, Any], led_position: int) -> Optional[Tuple[int, int, int]]:
        """Determine LED color based on vehicle speed.
        
        Expects attributes._display_speed_mph (enriched by ModeManager):
        None → null_speed_color (unknown)
        0 → min_speed_color (STOPPED_AT / stopped)
        >0 → interpolate toward max_speed_color
        """
        speed = vehicle_data['attributes'].get('_display_speed_mph')
        
        if speed is None:
            return tuple(self.null_speed_color)
        
        if speed == 0:
            return tuple(self.min_speed_color)
        
        return interpolate_color(speed, self.max_speed, self.min_speed_color, self.max_speed_color)
    
    def get_color_key(self) -> List[Tuple[int, int, int]]:
        """Return the color key showing speed levels."""
        return [
            tuple(self.min_speed_color),    # Min speed color
            tuple(self.max_speed_color),    # Max speed color
            tuple(self.null_speed_color)    # Unknown / no speed data
        ]
    
    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """Update the mode's settings and refresh color variables.
        
        Args:
            new_settings: Dictionary containing new settings
        """
        self.settings = new_settings
        
        route = new_settings.get('route', 'Red')
        self.max_speed = line_max_speed_mph(route)
        
        # Update color settings with new values from DEFAULT_SETTINGS
        self.min_speed_color = new_settings.get('min_speed_color', DEFAULT_SETTINGS['min_speed_color'])
        self.max_speed_color = new_settings.get('max_speed_color', DEFAULT_SETTINGS['max_speed_color'])
        self.null_speed_color = new_settings.get('null_speed_color', DEFAULT_SETTINGS['null_speed_color'])
