from typing import Dict, Any, List, Tuple, Optional
from .base_mode import DisplayModeBase
from .color_utils import interpolate_color
from config.constants import MAX_OCCUPANCY_PERCENTAGE
from config.validation import DEFAULT_SETTINGS

class OccupancyMode(DisplayModeBase):
    """Display mode that shows vehicle occupancy levels."""
    
    def __init__(self, led_count: int, station_maps: Dict, station_id_map: Dict, settings: Dict):
        """Initialize the occupancy mode."""
        super().__init__(led_count, station_maps, station_id_map, settings)
        
        # Get color settings with defaults from DEFAULT_SETTINGS
        self.min_occupancy_color = settings.get('min_occupancy_color', DEFAULT_SETTINGS['min_occupancy_color'])
        self.max_occupancy_color = settings.get('max_occupancy_color', DEFAULT_SETTINGS['max_occupancy_color'])
        self.null_occupancy_color = settings.get('null_occupancy_color', DEFAULT_SETTINGS['null_occupancy_color'])
    
    def set_vehicle_led_color(self, vehicle_data: Dict[str, Any], led_position: int) -> Optional[Tuple[int, int, int]]:
        """Determine LED color based on vehicle occupancy."""
        # Get carriages data
        carriages = vehicle_data['attributes'].get('carriages', [])
        if not carriages:
            return tuple(self.null_occupancy_color)
        
        # Calculate average occupancy percentage
        valid_percentages = [
            c['occupancy_percentage'] 
            for c in carriages 
            if c.get('occupancy_percentage') is not None
        ]
        
        if not valid_percentages:
            return tuple(self.null_occupancy_color)
        
        avg_occupancy = sum(valid_percentages) / len(valid_percentages)
        
        # Interpolate between min and max occupancy colors (100% is max)
        return interpolate_color(avg_occupancy, MAX_OCCUPANCY_PERCENTAGE, self.min_occupancy_color, self.max_occupancy_color)
    
    def get_color_key(self) -> List[Tuple[int, int, int]]:
        """Return the color key showing occupancy levels."""
        return [
            tuple(self.min_occupancy_color),    # Min occupancy color
            tuple(self.max_occupancy_color),    # Max occupancy color
            tuple(self.null_occupancy_color)    # No data color
        ]
    
    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """Update the mode's settings and refresh color variables.
        
        Args:
            new_settings: Dictionary containing new settings
        """
        self.settings = new_settings
        
        # Update color settings with new values from DEFAULT_SETTINGS
        self.min_occupancy_color = new_settings.get('min_occupancy_color', DEFAULT_SETTINGS['min_occupancy_color'])
        self.max_occupancy_color = new_settings.get('max_occupancy_color', DEFAULT_SETTINGS['max_occupancy_color'])
        self.null_occupancy_color = new_settings.get('null_occupancy_color', DEFAULT_SETTINGS['null_occupancy_color'])