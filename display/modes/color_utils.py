"""Shared color utilities for display modes."""
from typing import List, Tuple


def interpolate_color(
    value: float, 
    max_value: float, 
    min_color: List[int], 
    max_color: List[int]
) -> Tuple[int, int, int]:
    """Interpolate between two colors based on a value.
    
    Args:
        value: Current value (e.g., speed or occupancy)
        max_value: Maximum expected value for full intensity
        min_color: RGB color list for minimum value [R, G, B]
        max_color: RGB color list for maximum value [R, G, B]
        
    Returns:
        RGB color tuple interpolated between min and max colors
    """
    intensity = min(value / max_value, 1.0) if max_value > 0 else 0
    
    r = int(min_color[0] + (max_color[0] - min_color[0]) * intensity)
    g = int(min_color[1] + (max_color[1] - min_color[1]) * intensity)
    b = int(min_color[2] + (max_color[2] - min_color[2]) * intensity)
    
    return (r, g, b)

