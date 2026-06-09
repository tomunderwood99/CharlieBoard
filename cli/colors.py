"""Parse RGB color values from CLI arguments."""
import re
from typing import List

from config.constants import COLOR_MAX, COLOR_MIN, RGB_CHANNELS

_HEX_PATTERN = re.compile(r'^#?([0-9a-fA-F]{6})$')


def parse_color(value: str) -> List[int]:
    """Parse a color from #RRGGBB, R,G,B, or 'R G B' format.
    
    Args:
        value: Color string from the command line
        
    Returns:
        List of three integers [R, G, B]
        
    Raises:
        ValueError: If the color cannot be parsed
    """
    value = value.strip()
    
    hex_match = _HEX_PATTERN.match(value)
    if hex_match:
        hex_str = hex_match.group(1)
        return [
            int(hex_str[0:2], 16),
            int(hex_str[2:4], 16),
            int(hex_str[4:6], 16),
        ]
    
    if ',' in value:
        parts = [p.strip() for p in value.split(',')]
    else:
        parts = value.split()
    
    if len(parts) != RGB_CHANNELS:
        raise ValueError(
            f"Expected 3 color components, got {len(parts)}. "
            "Use #RRGGBB, R,G,B, or 'R G B'."
        )
    
    try:
        rgb = [int(p) for p in parts]
    except ValueError as e:
        raise ValueError(f"Color components must be integers: {e}") from e
    
    for channel in rgb:
        if channel < COLOR_MIN or channel > COLOR_MAX:
            raise ValueError(
                f"Color values must be {COLOR_MIN}-{COLOR_MAX}, got {channel}"
            )
    
    return rgb


def format_color(rgb: List[int]) -> str:
    """Format an RGB list for display."""
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"
