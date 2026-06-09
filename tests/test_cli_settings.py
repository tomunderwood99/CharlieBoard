"""Tests for CharlieBoard CLI color parsing and settings patching."""
import os
import tempfile
import unittest

from cli.colors import parse_color, format_color
from config.settings import SettingsManager
from config.validation import DEFAULT_SETTINGS


class TestParseColor(unittest.TestCase):
    def test_hex_with_hash(self):
        self.assertEqual(parse_color('#ff0000'), [255, 0, 0])

    def test_hex_without_hash(self):
        self.assertEqual(parse_color('00ff00'), [0, 255, 0])

    def test_comma_separated(self):
        self.assertEqual(parse_color('255,128,0'), [255, 128, 0])

    def test_space_separated(self):
        self.assertEqual(parse_color('10 20 30'), [10, 20, 30])

    def test_invalid_component_count(self):
        with self.assertRaises(ValueError):
            parse_color('255,0')

    def test_out_of_range(self):
        with self.assertRaises(ValueError):
            parse_color('256,0,0')

    def test_non_integer(self):
        with self.assertRaises(ValueError):
            parse_color('red,0,0')


class TestFormatColor(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_color([255, 0, 0]), 'rgb(255, 0, 0)')


class TestPatchSettings(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.env_path = os.path.join(self.temp_dir, '.env')
        with open(self.env_path, 'w') as f:
            f.write('ROUTE=Red\n')
            f.write('DISPLAY_MODE=vehicles\n')
            f.write('POWER_SWITCH=off\n')
            f.write('BEDTIME_START=22:00\n')
            f.write('BEDTIME_END=07:00\n')
            f.write('BRIGHTNESS=1.0\n')
            f.write('STOPPED_COLOR=[255,0,0]\n')
            f.write('INCOMING_COLOR=[255,75,75]\n')
            f.write('TRANSIT_COLOR=[150,150,150]\n')
            f.write('MIN_SPEED_COLOR=[0,255,0]\n')
            f.write('MAX_SPEED_COLOR=[255,0,0]\n')
            f.write('NULL_SPEED_COLOR=[0,0,255]\n')
            f.write('MIN_OCCUPANCY_COLOR=[0,255,0]\n')
            f.write('MAX_OCCUPANCY_COLOR=[255,0,0]\n')
            f.write('NULL_OCCUPANCY_COLOR=[0,0,255]\n')
        self.manager = SettingsManager(env_file=self.env_path)

    def test_patch_power_preserves_route(self):
        self.assertTrue(self.manager.patch_settings({'power_switch': 'on'}))
        settings = self.manager.load_settings()
        self.assertEqual(settings['power_switch'], 'on')
        self.assertEqual(settings['route'], 'Red')

    def test_patch_route_changes_route(self):
        self.assertTrue(
            self.manager.patch_settings({'route': 'Orange'}, preserve_route=False)
        )
        settings = self.manager.load_settings()
        self.assertEqual(settings['route'], 'Orange')

    def test_patch_bedtime_partial(self):
        self.assertTrue(self.manager.patch_settings({'bedtime_start': '23:30'}))
        settings = self.manager.load_settings()
        self.assertEqual(settings['bedtime_start'], '23:30')
        self.assertEqual(settings['bedtime_end'], '07:00')

    def test_patch_invalid_time_falls_back(self):
        self.assertTrue(self.manager.patch_settings({'bedtime_start': 'invalid'}))
        settings = self.manager.load_settings()
        self.assertEqual(settings['bedtime_start'], DEFAULT_SETTINGS['bedtime_start'])


if __name__ == '__main__':
    unittest.main()
