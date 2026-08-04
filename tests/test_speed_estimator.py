#!/usr/bin/env python3
"""Unit tests for display.speed_estimator (no live MBTA API)."""

from __future__ import annotations

import math
import os
import sys
import unittest
from datetime import datetime, timezone

# Add project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.constants import MS_TO_MPH, SPEED_EMA_ALPHA, SPEED_SPIKE_FACTOR
from display.speed_estimator import (
    SpeedEstimator,
    haversine_meters,
    line_max_speed_mph,
    parse_updated_at,
)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _vehicle(
    vehicle_id: str = "v1",
    *,
    lat=None,
    lon=None,
    t: float = 1_700_000_000.0,
    status: str = "IN_TRANSIT_TO",
    speed=None,
):
    attrs = {
        "current_status": status,
        "updated_at": _iso(t),
        "speed": speed,
    }
    if lat is not None:
        attrs["latitude"] = lat
    if lon is not None:
        attrs["longitude"] = lon
    return {"id": vehicle_id, "attributes": attrs}


class HaversineTests(unittest.TestCase):
    def test_one_degree_latitude_approx_111km(self):
        # 1° latitude ≈ 111.19 km near the equator / mid-latitudes for great-circle
        d = haversine_meters(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(d, 111_194.9, delta=50.0)

    def test_zero_distance(self):
        self.assertEqual(haversine_meters(42.36, -71.06, 42.36, -71.06), 0.0)


class ParseUpdatedAtTests(unittest.TestCase):
    def test_parses_iso_with_offset(self):
        ts = parse_updated_at("2024-01-15T12:34:56-05:00")
        self.assertIsNotNone(ts)
        self.assertIsInstance(ts, float)

    def test_none_and_invalid(self):
        self.assertIsNone(parse_updated_at(None))
        self.assertIsNone(parse_updated_at("not-a-date"))


class LineMaxSpeedTests(unittest.TestCase):
    def test_known_routes(self):
        self.assertEqual(line_max_speed_mph("Orange"), 55)
        self.assertEqual(line_max_speed_mph("Red"), 50)
        self.assertEqual(line_max_speed_mph("Blue"), 50)
        self.assertEqual(line_max_speed_mph("Green-B"), 50)

    def test_unknown_falls_back(self):
        self.assertEqual(line_max_speed_mph("Commuter"), 50)


class SpeedEstimatorTests(unittest.TestCase):
    def setUp(self):
        self.est = SpeedEstimator()

    def test_stopped_at_forces_zero(self):
        t0 = 1_700_000_000.0
        # Seed a moving estimate first
        self.est.resolve(
            _vehicle(lat=42.3600, lon=-71.0580, t=t0, status="IN_TRANSIT_TO"),
            "Red",
            wall_time=t0,
        )
        # ~50 mph over 5s along latitude (~111 m per 0.001°)
        # 0.001° lat ≈ 111.2 m; in 5s → 22.24 m/s ≈ 49.7 mph
        moved = self.est.resolve(
            _vehicle(
                lat=42.3610,
                lon=-71.0580,
                t=t0 + 5.0,
                status="IN_TRANSIT_TO",
            ),
            "Red",
            wall_time=t0 + 5.0,
        )
        self.assertIsNotNone(moved)
        self.assertGreater(moved, 40.0)

        stopped = self.est.resolve(
            _vehicle(
                lat=42.3610,
                lon=-71.0580,
                t=t0 + 10.0,
                status="STOPPED_AT",
            ),
            "Red",
            wall_time=t0 + 10.0,
        )
        self.assertEqual(stopped, 0.0)

    def test_departure_after_stop_seeds_raw_not_blend_from_zero(self):
        """After STOPPED_AT, first accepted GPS estimate should jump to raw mph."""
        t0 = 1_700_000_000.0
        self.est.resolve(
            _vehicle(lat=42.3600, lon=-71.0580, t=t0, status="STOPPED_AT"),
            "Red",
            wall_time=t0,
        )
        # Baseline refresh while still stopped (position may nudge)
        self.est.resolve(
            _vehicle(lat=42.3600, lon=-71.0580, t=t0 + 3.0, status="STOPPED_AT"),
            "Red",
            wall_time=t0 + 3.0,
        )
        # Depart: 0.001° lat ≈ 111.2 m in 5s → ~49.7 mph
        departed = self.est.resolve(
            _vehicle(
                lat=42.3610,
                lon=-71.0580,
                t=t0 + 8.0,
                status="IN_TRANSIT_TO",
            ),
            "Red",
            wall_time=t0 + 8.0,
        )
        self.assertIsNotNone(departed)
        # Must be full raw (~50), not 0.35 * raw (~17)
        self.assertGreater(departed, 40.0)
        blended_from_zero = 0.35 * departed
        self.assertGreater(departed, blended_from_zero * 2)

    def test_green_uses_api_conversion_not_gps(self):
        t0 = 1_700_000_000.0
        api_ms = 10.0  # → ~22.37 mph
        first = self.est.resolve(
            _vehicle(
                lat=42.3600,
                lon=-71.0580,
                t=t0,
                status="IN_TRANSIT_TO",
                speed=api_ms,
            ),
            "Green-B",
            wall_time=t0,
        )
        self.assertAlmostEqual(first, api_ms * MS_TO_MPH, places=5)

        # Large GPS jump that would estimate ~100+ mph — Green must ignore it
        second = self.est.resolve(
            _vehicle(
                lat=42.3700,
                lon=-71.0580,
                t=t0 + 5.0,
                status="IN_TRANSIT_TO",
                speed=api_ms,
            ),
            "Green-B",
            wall_time=t0 + 5.0,
        )
        self.assertAlmostEqual(second, api_ms * MS_TO_MPH, places=5)

    def test_green_null_api_returns_none(self):
        t0 = 1_700_000_000.0
        result = self.est.resolve(
            _vehicle(lat=42.36, lon=-71.06, t=t0, speed=None),
            "Green-D",
            wall_time=t0,
        )
        self.assertIsNone(result)

    def test_red_estimates_from_two_samples(self):
        t0 = 1_700_000_000.0
        self.assertIsNone(
            self.est.resolve(
                _vehicle(lat=42.3600, lon=-71.0580, t=t0),
                "Red",
                wall_time=t0,
            )
        )
        # 0.001° lat ≈ 111.2 m in 5s → ~49.7 mph; first accepted sample seeds EMA
        mph = self.est.resolve(
            _vehicle(lat=42.3610, lon=-71.0580, t=t0 + 5.0),
            "Red",
            wall_time=t0 + 5.0,
        )
        self.assertIsNotNone(mph)
        self.assertGreater(mph, 40.0)
        self.assertLess(mph, 60.0)

    def test_dt_out_of_range_keeps_prior_ema(self):
        t0 = 1_700_000_000.0
        self.est.resolve(
            _vehicle(lat=42.3600, lon=-71.0580, t=t0),
            "Red",
            wall_time=t0,
        )
        seeded = self.est.resolve(
            _vehicle(lat=42.3610, lon=-71.0580, t=t0 + 5.0),
            "Red",
            wall_time=t0 + 5.0,
        )
        # Δt = 1s < min_dt → keep prior
        skipped = self.est.resolve(
            _vehicle(lat=42.3620, lon=-71.0580, t=t0 + 6.0),
            "Red",
            wall_time=t0 + 6.0,
        )
        self.assertEqual(skipped, seeded)

    def test_spike_rejected_keeps_prior_ema(self):
        t0 = 1_700_000_000.0
        self.est.resolve(
            _vehicle(lat=42.3600, lon=-71.0580, t=t0),
            "Blue",
            wall_time=t0,
        )
        seeded = self.est.resolve(
            _vehicle(lat=42.3605, lon=-71.0580, t=t0 + 5.0),
            "Blue",
            wall_time=t0 + 5.0,
        )
        # Huge jump in 3s → well above Blue max * spike factor
        spiked = self.est.resolve(
            _vehicle(lat=42.3800, lon=-71.0580, t=t0 + 8.0),
            "Blue",
            wall_time=t0 + 8.0,
        )
        self.assertEqual(spiked, seeded)
        # Confirm raw would have been a spike
        raw_m = haversine_meters(42.3605, -71.0580, 42.3800, -71.0580)
        raw_mph = (raw_m / 3.0) * MS_TO_MPH
        self.assertGreater(raw_mph, 50.0 * SPEED_SPIKE_FACTOR)

    def test_ema_converges_toward_new_samples(self):
        est = SpeedEstimator(ema_alpha=SPEED_EMA_ALPHA)
        t0 = 1_700_000_000.0
        # Seed with ~25 mph: 0.0005° lat ≈ 55.6 m in 5s → ~24.9 mph
        est.resolve(
            _vehicle(lat=42.3600, lon=-71.0580, t=t0),
            "Orange",
            wall_time=t0,
        )
        first = est.resolve(
            _vehicle(lat=42.3605, lon=-71.0580, t=t0 + 5.0),
            "Orange",
            wall_time=t0 + 5.0,
        )
        # Next pairs hold ~50 mph
        mph = first
        lat = 42.3605
        for i in range(1, 8):
            lat += 0.001  # ≈111 m
            t = t0 + 5.0 + i * 5.0
            mph = est.resolve(
                _vehicle(lat=lat, lon=-71.0580, t=t),
                "Orange",
                wall_time=t,
            )
        self.assertIsNotNone(mph)
        self.assertGreater(mph, first)
        self.assertGreater(mph, 35.0)

    def test_forget_drops_history(self):
        t0 = 1_700_000_000.0
        self.est.resolve(
            _vehicle("abc", lat=42.36, lon=-71.06, t=t0),
            "Red",
            wall_time=t0,
        )
        self.est.forget("abc")
        # After forget, first sighting again has no prior → None
        result = self.est.resolve(
            _vehicle("abc", lat=42.361, lon=-71.06, t=t0 + 5.0),
            "Red",
            wall_time=t0 + 5.0,
        )
        self.assertIsNone(result)

    def test_heavy_rail_uses_api_when_present(self):
        t0 = 1_700_000_000.0
        mph = self.est.resolve(
            _vehicle(
                lat=42.36,
                lon=-71.06,
                t=t0,
                speed=20.0,  # m/s
            ),
            "Red",
            wall_time=t0,
        )
        self.assertAlmostEqual(mph, 20.0 * MS_TO_MPH, places=5)


class SpeedModeColorTests(unittest.TestCase):
    """Smoke-test SpeedMode color branching without LEDs."""

    def test_none_vs_zero_colors(self):
        from display.modes.speed_mode import SpeedMode

        settings = {
            "route": "Red",
            "min_speed_color": [0, 255, 0],
            "max_speed_color": [255, 0, 0],
            "null_speed_color": [0, 0, 255],
        }
        mode = SpeedMode(
            led_count=10,
            station_maps={"outbound": {}, "inbound": {}},
            station_id_map={},
            settings=settings,
        )
        unknown = {"attributes": {"_display_speed_mph": None}}
        stopped = {"attributes": {"_display_speed_mph": 0}}
        moving = {"attributes": {"_display_speed_mph": 25.0}}

        self.assertEqual(mode.set_vehicle_led_color(unknown, 0), (0, 0, 255))
        self.assertEqual(mode.set_vehicle_led_color(stopped, 0), (0, 255, 0))
        color = mode.set_vehicle_led_color(moving, 0)
        self.assertIsNotNone(color)
        # Halfway to max on Red (50 mph) → midway RGB toward red
        self.assertEqual(color, (127, 127, 0))  # int lerp of green→red at 0.5


if __name__ == "__main__":
    unittest.main()
