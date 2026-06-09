"""Show and set handlers for CharlieBoard settings."""
import sys
from typing import Dict, Any, Optional

from config.settings import SettingsManager
from config.validation import (
    VALID_ROUTES,
    VALID_DISPLAY_MODES,
    VALID_POWER_STATES,
)
from cli.colors import parse_color, format_color
from cli.service import restart_display_services

# CLI color name -> settings dict key
COLOR_NAME_MAP = {
    'stopped': 'stopped_color',
    'incoming': 'incoming_color',
    'transit': 'transit_color',
    'min_speed': 'min_speed_color',
    'max_speed': 'max_speed_color',
    'null_speed': 'null_speed_color',
    'min_occupancy': 'min_occupancy_color',
    'max_occupancy': 'max_occupancy_color',
    'null_occupancy': 'null_occupancy_color',
}

MODE_COLORS = {
    'vehicles': ['stopped_color', 'incoming_color', 'transit_color'],
    'speed': ['min_speed_color', 'max_speed_color', 'null_speed_color'],
    'occupancy': ['min_occupancy_color', 'max_occupancy_color', 'null_occupancy_color'],
    'rainbow': [],
}


def _color_label(settings_key: str) -> str:
    for name, key in COLOR_NAME_MAP.items():
        if key == settings_key:
            return name
    return settings_key


def cmd_show(settings_manager: SettingsManager) -> int:
    """Print current settings."""
    settings = settings_manager.load_settings()
    
    print(f"Route:        {settings.get('route', 'unknown')}")
    print(f"Display mode: {settings.get('display_mode', 'unknown')}")
    print(f"Power:        {settings.get('power_switch', 'unknown')}")
    print(f"Bedtime:      {settings.get('bedtime_start')} - {settings.get('bedtime_end')}")
    print(f"Brightness:   {settings.get('brightness')}")
    print()
    
    mode = settings.get('display_mode', 'vehicles')
    color_keys = MODE_COLORS.get(mode, [])
    if color_keys:
        print(f"Colors ({mode}):")
        for key in color_keys:
            rgb = settings.get(key, [0, 0, 0])
            label = _color_label(key)
            print(f"  {label:16} {format_color(rgb)}")
    elif mode == 'rainbow':
        print("Colors: (rainbow mode uses animated colors)")
    
    print()
    print("All colors:")
    for name, key in sorted(COLOR_NAME_MAP.items()):
        rgb = settings.get(key, [0, 0, 0])
        print(f"  {name:16} {format_color(rgb)}")
    
    print()
    print(f"Settings file: {settings_manager.env_file}")
    return 0


def _save_and_report(
    settings_manager: SettingsManager,
    updates: Dict[str, Any],
    *,
    preserve_route: bool = True,
    message: str,
) -> int:
    if not settings_manager.patch_settings(updates, preserve_route=preserve_route):
        print("Failed to save settings.", file=sys.stderr)
        return 1
    print(message)
    if preserve_route:
        print("Running display will pick up changes on the next stream event.")
    return 0


def cmd_set_route(settings_manager: SettingsManager, route: str) -> int:
    if route not in VALID_ROUTES:
        print(
            f"Invalid route '{route}'. Valid routes: {', '.join(sorted(VALID_ROUTES))}",
            file=sys.stderr,
        )
        return 1
    
    if not settings_manager.patch_settings(
        {'route': route},
        preserve_route=False,
    ):
        print("Failed to save route.", file=sys.stderr)
        return 1
    
    print(f"Route set to {route}.")
    if not restart_display_services():
        return 1
    return 0


def cmd_set_mode(settings_manager: SettingsManager, mode: str) -> int:
    if mode not in VALID_DISPLAY_MODES:
        print(
            f"Invalid mode '{mode}'. Valid modes: {', '.join(sorted(VALID_DISPLAY_MODES))}",
            file=sys.stderr,
        )
        return 1
    return _save_and_report(
        settings_manager,
        {'display_mode': mode},
        message=f"Display mode set to {mode}.",
    )


def cmd_set_power(settings_manager: SettingsManager, power: str) -> int:
    power = power.lower()
    if power not in VALID_POWER_STATES:
        print(
            f"Invalid power state '{power}'. Use 'on' or 'off'.",
            file=sys.stderr,
        )
        return 1
    return _save_and_report(
        settings_manager,
        {'power_switch': power},
        message=f"Power switch set to {power}.",
    )


def cmd_set_bedtime(
    settings_manager: SettingsManager,
    start: Optional[str],
    end: Optional[str],
) -> int:
    if start is None and end is None:
        print("Provide --start and/or --end (HH:MM).", file=sys.stderr)
        return 1
    
    updates = {}
    if start is not None:
        updates['bedtime_start'] = start
    if end is not None:
        updates['bedtime_end'] = end
    
    parts = []
    if start is not None:
        parts.append(f"start {start}")
    if end is not None:
        parts.append(f"end {end}")
    
    return _save_and_report(
        settings_manager,
        updates,
        message=f"Bedtime updated ({', '.join(parts)}).",
    )


def cmd_set_color(
    settings_manager: SettingsManager,
    color_name: str,
    color_value: str,
) -> int:
    color_name = color_name.lower().replace('-', '_')
    settings_key = COLOR_NAME_MAP.get(color_name)
    if settings_key is None:
        valid = ', '.join(sorted(COLOR_NAME_MAP.keys()))
        print(
            f"Unknown color '{color_name}'. Valid names: {valid}",
            file=sys.stderr,
        )
        return 1
    
    try:
        rgb = parse_color(color_value)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    
    return _save_and_report(
        settings_manager,
        {settings_key: rgb},
        message=f"Color {color_name} set to {format_color(rgb)}.",
    )
