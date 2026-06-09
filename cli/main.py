#!/usr/bin/env python3
"""CharlieBoard terminal CLI for managing display settings without the web UI."""
import argparse
import sys

from config.settings import SettingsManager
from cli import settings_cmd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='charlieboard',
        description='Manage CharlieBoard display settings from the terminal.',
    )
    parser.add_argument(
        '--env',
        default='.env',
        help='Path to .env settings file (default: .env in project root)',
    )
    
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    subparsers.add_parser('show', help='Show current settings')
    
    set_parser = subparsers.add_parser('set', help='Update a setting')
    set_sub = set_parser.add_subparsers(dest='setting', required=True)
    
    route_parser = set_sub.add_parser('route', help='Set MBTA route (restarts services)')
    route_parser.add_argument(
        'route',
        help='Route name (e.g. Red, Orange, Green-B)',
    )
    
    mode_parser = set_sub.add_parser('mode', help='Set display mode')
    mode_parser.add_argument(
        'mode',
        choices=['vehicles', 'occupancy', 'speed', 'rainbow'],
        help='Display mode',
    )
    
    power_parser = set_sub.add_parser('power', help='Turn display on or off')
    power_parser.add_argument(
        'state',
        choices=['on', 'off'],
        help='Power state',
    )
    
    bedtime_parser = set_sub.add_parser('bedtime', help='Set bedtime window (HH:MM)')
    bedtime_parser.add_argument(
        '--start',
        metavar='HH:MM',
        help='Bedtime start (display off)',
    )
    bedtime_parser.add_argument(
        '--end',
        metavar='HH:MM',
        help='Bedtime end (display on)',
    )
    
    color_parser = set_sub.add_parser('color', help='Set a legend color (RGB)')
    color_parser.add_argument(
        'name',
        help='Color name (e.g. stopped, incoming, max_occupancy)',
    )
    color_parser.add_argument(
        'value',
        help='Color as #RRGGBB, R,G,B, or R G B',
    )
    
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    
    settings_manager = SettingsManager(env_file=args.env)
    
    if args.command == 'show':
        return settings_cmd.cmd_show(settings_manager)
    
    if args.command == 'set':
        if args.setting == 'route':
            return settings_cmd.cmd_set_route(settings_manager, args.route)
        if args.setting == 'mode':
            return settings_cmd.cmd_set_mode(settings_manager, args.mode)
        if args.setting == 'power':
            return settings_cmd.cmd_set_power(settings_manager, args.state)
        if args.setting == 'bedtime':
            return settings_cmd.cmd_set_bedtime(
                settings_manager,
                args.start,
                args.end,
            )
        if args.setting == 'color':
            return settings_cmd.cmd_set_color(
                settings_manager,
                args.name,
                args.value,
            )
    
    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
