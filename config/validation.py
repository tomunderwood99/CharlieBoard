"""Lightweight validation utilities for the MBTA LED Controller."""
from typing import Dict, List, Any, Optional
import re
import logging
from .constants import (
    COLOR_MIN,
    COLOR_MAX,
    RGB_CHANNELS,
    BRIGHTNESS_MIN,
    BRIGHTNESS_MAX,
    DEFAULT_BRIGHTNESS,
)

logger = logging.getLogger(__name__)

# Valid values for settings
# Note: Green-All is included for future use but requires custom station/LED maps to be implemented
VALID_ROUTES = {'Red', 'Blue', 'Orange', 'Green-All', 'Green-B', 'Green-C', 'Green-D', 'Green-E'}
VALID_DISPLAY_MODES = {'vehicles', 'occupancy', 'speed', 'rainbow'}
VALID_POWER_STATES = {'on', 'off'}
TIME_PATTERN = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')

# Default settings used when no defaults are provided
DEFAULT_SETTINGS = {
    'route': 'Red',
    'display_mode': 'vehicles',
    'power_switch': 'off',
    'brightness': 1.0,
    'bedtime_start': '22:00',
    'bedtime_end': '07:00',
    'transit_color': [150, 150, 150],
    'incoming_color': [255, 75, 75],
    'stopped_color': [255, 0, 0],
    'min_speed_color': [0, 255, 0],
    'max_speed_color': [255, 0, 0],
    'null_speed_color': [0, 0, 255],
    'min_occupancy_color': [0, 255, 0],
    'max_occupancy_color': [255, 0, 0],
    'null_occupancy_color': [0, 0, 255],
    'mbta_api_key': None,
    'debugger': [],
    'show_debugger_options': False,
    'save_error_data': False  # When True, saves problematic API data to logs/error_data/ for debugging
}


def validate_vehicle_data(data: Dict) -> Dict:
    """Validate incoming vehicle data from MBTA API.
    
    Only rejects vehicles that don't have an ID. Returns the data as-is
    since downstream code handles missing/malformed fields defensively.
    """
    if not data or not isinstance(data, dict) or not data.get('id'):
        raise ValueError("Vehicle data must have a valid ID")
    return data


def validate_color(color: Any, default: List[int]) -> List[int]:
    """Validate a color list [R, G, B]. Returns default if invalid."""
    if not isinstance(color, list) or len(color) != RGB_CHANNELS:
        return default
    try:
        validated = [max(COLOR_MIN, min(COLOR_MAX, int(c))) for c in color]
        return validated
    except (TypeError, ValueError):
        return default


def validate_time(time_str: Any, default: str) -> str:
    """Validate HH:MM time format. Returns default if invalid."""
    if not isinstance(time_str, str) or not TIME_PATTERN.match(time_str):
        return default
    return time_str


def validate_brightness(value: Any, default: float = DEFAULT_BRIGHTNESS) -> float:
    """Validate brightness (0.0-1.0). Returns default if invalid."""
    try:
        brightness = float(value)
        return max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, brightness))
    except (TypeError, ValueError):
        return default


def validate_settings(settings: Dict, defaults: Optional[Dict] = None) -> Dict:
    """Validate display settings, falling back to defaults for invalid values.
    
    Args:
        settings: User-provided settings dictionary
        defaults: Default settings to fall back to (uses DEFAULT_SETTINGS if not provided)
        
    Returns:
        Validated settings dictionary
    """
    if defaults is None:
        defaults = DEFAULT_SETTINGS
    validated = defaults.copy()
    
    # Route validation
    route = settings.get('route')
    if route in VALID_ROUTES:
        validated['route'] = route
    
    # Display mode validation
    mode = settings.get('display_mode')
    if mode in VALID_DISPLAY_MODES:
        validated['display_mode'] = mode
    
    # Power switch validation
    power = settings.get('power_switch')
    if power in VALID_POWER_STATES:
        validated['power_switch'] = power
    
    # Brightness validation
    if 'brightness' in settings:
        validated['brightness'] = validate_brightness(settings['brightness'], defaults['brightness'])
    
    # Time validations
    if 'bedtime_start' in settings:
        validated['bedtime_start'] = validate_time(settings['bedtime_start'], defaults['bedtime_start'])
    if 'bedtime_end' in settings:
        validated['bedtime_end'] = validate_time(settings['bedtime_end'], defaults['bedtime_end'])
    
    # Color validations
    color_keys = [
        'transit_color', 'incoming_color', 'stopped_color',
        'min_speed_color', 'max_speed_color', 'null_speed_color',
        'min_occupancy_color', 'max_occupancy_color', 'null_occupancy_color'
    ]
    for key in color_keys:
        if key in settings:
            validated[key] = validate_color(settings[key], defaults[key])
    
    # Pass through other fields
    if 'mbta_api_key' in settings:
        validated['mbta_api_key'] = settings['mbta_api_key']
    if 'debugger' in settings:
        validated['debugger'] = settings.get('debugger', [])
    if 'show_debugger_options' in settings:
        validated['show_debugger_options'] = bool(settings.get('show_debugger_options', False))
    if 'save_error_data' in settings:
        validated['save_error_data'] = bool(settings.get('save_error_data', False))
    
    return validated
