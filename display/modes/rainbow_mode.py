from typing import Dict, Any, List, Tuple, Optional
from .base_mode import DisplayModeBase
from config.constants import (
    RAINBOW_ANIMATION_SPEED,
    RAINBOW_WHEEL_POSITIONS,
    RAINBOW_WHEEL_SEGMENT_1,
    RAINBOW_WHEEL_SEGMENT_2,
    RAINBOW_WHEEL_MULTIPLIER,
    COLOR_MAX,
)

class RainbowMode(DisplayModeBase):
    """Display mode that shows an animated rainbow pattern."""
    
    def __init__(self, led_count: int, station_maps: Dict, station_id_map: Dict, settings: Dict):
        """Initialize the rainbow mode."""
        super().__init__(led_count, station_maps, station_id_map, settings)
        self.rainbow_position = 0
        self.rainbow_speed = RAINBOW_ANIMATION_SPEED  # Adjust this to change animation speed
    
    def wheel(self, pos: int) -> Tuple[int, int, int]:
        """Generate rainbow colors across 0-255 positions.
        
        Args:
            pos: Position in the color wheel (0-255)
            
        Returns:
            RGB color tuple
        """
        pos = pos % RAINBOW_WHEEL_POSITIONS
        if pos < RAINBOW_WHEEL_SEGMENT_1:
            return (pos * RAINBOW_WHEEL_MULTIPLIER, COLOR_MAX - pos * RAINBOW_WHEEL_MULTIPLIER, 0)
        elif pos < RAINBOW_WHEEL_SEGMENT_2:
            pos -= RAINBOW_WHEEL_SEGMENT_1
            return (COLOR_MAX - pos * RAINBOW_WHEEL_MULTIPLIER, 0, pos * RAINBOW_WHEEL_MULTIPLIER)
        else:
            pos -= RAINBOW_WHEEL_SEGMENT_2
            return (0, pos * RAINBOW_WHEEL_MULTIPLIER, COLOR_MAX - pos * RAINBOW_WHEEL_MULTIPLIER)
    
    def set_vehicle_led_color(self, vehicle_data: Dict[str, Any], led_position: int) -> Optional[Tuple[int, int, int]]:
        """Determine LED color based on rainbow pattern.
        
        Note: In rainbow mode, we track vehicle positions but don't use them for display.
        The rainbow animation overrides all LED colors.
        """
        # Return None as we don't want to set individual vehicle colors
        return None
    
    def process_vehicle(self, vehicle_data: Dict[str, Any]) -> None:
        """Update rainbow animation and track vehicle positions.
        
        Override process_vehicle to handle the animation while still tracking vehicles.
        """
        # First let the base class handle vehicle position tracking
        super().process_vehicle(vehicle_data)
        
        # Then update the rainbow animation
        for i in range(self.led_count):
            color = self.wheel((i * RAINBOW_WHEEL_POSITIONS // self.led_count + self.rainbow_position) & COLOR_MAX)
            self.led_colors[i] = color
        
        # Move the rainbow
        self.rainbow_position = (self.rainbow_position + self.rainbow_speed) % RAINBOW_WHEEL_POSITIONS
    
    def get_color_key(self) -> List[Tuple[int, int, int]]:
        """Return rainbow colors for the color key."""
        return [
            self.wheel(0),                      # Red
            self.wheel(RAINBOW_WHEEL_SEGMENT_1),  # Green
            self.wheel(RAINBOW_WHEEL_SEGMENT_2)   # Blue
        ]
    
    def clear_vehicle(self, vehicle_data: Dict[str, Any]) -> None:
        """Override clear_vehicle to do nothing.
        
        Rainbow mode doesn't track individual vehicles.
        """
        pass
    
    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """Update the mode's settings.
        
        Args:
            new_settings: Dictionary containing new settings
        """
        self.settings = new_settings
        # Rainbow mode doesn't need to reprocess vehicles since it uses animation 