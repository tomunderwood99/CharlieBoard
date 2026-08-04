#!/usr/bin/env python3
"""Estimate train speed from successive MBTA vehicle lat/lon samples.

Background
----------
SpeedMode currently reads attributes.speed from the MBTA API. That field is
populated for Green Line vehicles but is typically null on Red/Blue/Orange.
Latitude and longitude are provided for all subway lines, so successive GPS
samples can be turned into an estimated speed via the haversine formula.

This script polls GET /vehicles on a fixed interval (REST, not SSE), tracks
each vehicle's last known position, and reports:

  - estimated speed (mph and m/s) from Δdistance / Δtime
  - API-reported speed when present (MBTA documents this as meters/second)
  - summary stats: how often lat/lon exist, how often API speed is null,
    and (on Green) how estimated mph compares to API when both are available

Caveats (why this is an experiment, not production-ready yet)
------------------------------------------------------------
  - GPS jitter at short Δt produces noisy / spiked estimates
  - Position updates can be uneven; identical lat/lon between polls → 0 mph
  - Great-circle distance underestimates path length slightly vs track geometry
  - STOPPED_AT vehicles may still show tiny residual speeds from GPS noise
  - attributes.updated_at is preferred for Δt; wall clock is the fallback

Usage
-----
  python tests/speed_from_position_test.py
  python tests/speed_from_position_test.py --route Red --interval 5 --duration 120
  python tests/speed_from_position_test.py --route Green-B,Green-C,Green-D,Green-E

Requires MBTA_API_KEY in the environment (or --api-key). Get a free key at
https://api-v3.mbta.com/
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Add project root to Python path (same pattern as keepalive_test.py)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Shared estimator helpers (haversine / MS_TO_MPH). Fall back if display
# package is unavailable in a stripped checkout.
try:
    from display.speed_estimator import haversine_meters, parse_updated_at
    from config.constants import MS_TO_MPH, MAX_VEHICLE_SPEED_MPH
except Exception:
    MAX_VEHICLE_SPEED_MPH = 50
    MS_TO_MPH = 2.2369362921
    EARTH_RADIUS_M = 6_371_000.0

    def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance between two WGS84 points, in meters."""
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))

    def parse_updated_at(value: Optional[str]) -> Optional[float]:
        """Parse MBTA updated_at (ISO-8601) to a unix timestamp, or None."""
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except (TypeError, ValueError):
            return None

VEHICLES_URL = "https://api-v3.mbta.com/vehicles"


@dataclass
class PositionSample:
    lat: float
    lon: float
    t: float  # unix seconds used for Δt
    updated_at: Optional[str]
    api_speed_ms: Optional[float]
    status: Optional[str]
    label: Optional[str]


@dataclass
class SpeedEstimate:
    vehicle_id: str
    label: Optional[str]
    status: Optional[str]
    distance_m: float
    dt_s: float
    estimated_mph: float
    estimated_ms: float
    api_speed_ms: Optional[float]
    api_speed_mph: Optional[float]
    poll_time: float


@dataclass
class MonitorStats:
    polls: int = 0
    vehicle_sightings: int = 0
    with_latlon: int = 0
    with_api_speed: int = 0
    estimates: List[SpeedEstimate] = field(default_factory=list)
    skipped_same_timestamp: int = 0
    skipped_dt_out_of_range: int = 0
    skipped_no_movement_pair: int = 0


class SpeedFromPositionMonitor:
    """Poll MBTA vehicles and estimate speed from successive GPS samples."""

    def __init__(
        self,
        api_key: Optional[str],
        route: str,
        interval: float = 5.0,
        min_dt: float = 2.0,
        max_dt: float = 60.0,
        max_plausible_mph: float = MAX_VEHICLE_SPEED_MPH * 1.5,
        quiet: bool = False,
    ):
        self.api_key = api_key
        self.route = route
        self.interval = interval
        self.min_dt = min_dt
        self.max_dt = max_dt
        self.max_plausible_mph = max_plausible_mph
        self.quiet = quiet
        self.prev: Dict[str, PositionSample] = {}
        self.stats = MonitorStats()

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/vnd.api+json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def fetch_vehicles(self) -> List[dict]:
        params = urllib.parse.urlencode(
            {
                "filter[route]": self.route,
                "include": "trip,stop",
            }
        )
        request = urllib.request.Request(
            f"{VEHICLES_URL}?{params}",
            headers=self._headers(),
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def _sample_from_vehicle(
        self, vehicle: dict, wall_time: float
    ) -> Optional[Tuple[str, PositionSample]]:
        vehicle_id = vehicle.get("id")
        attrs = vehicle.get("attributes") or {}
        lat = attrs.get("latitude")
        lon = attrs.get("longitude")
        if vehicle_id is None or lat is None or lon is None:
            return None

        updated_at = attrs.get("updated_at")
        sample_t = parse_updated_at(updated_at) or wall_time
        sample = PositionSample(
            lat=float(lat),
            lon=float(lon),
            t=sample_t,
            updated_at=updated_at,
            api_speed_ms=attrs.get("speed"),
            status=attrs.get("current_status"),
            label=attrs.get("label"),
        )
        return vehicle_id, sample

    def _estimate(
        self, vehicle_id: str, prev: PositionSample, curr: PositionSample, poll_time: float
    ) -> Optional[SpeedEstimate]:
        dt = curr.t - prev.t
        if dt <= 0:
            self.stats.skipped_same_timestamp += 1
            return None
        if dt < self.min_dt or dt > self.max_dt:
            self.stats.skipped_dt_out_of_range += 1
            return None

        distance_m = haversine_meters(prev.lat, prev.lon, curr.lat, curr.lon)
        estimated_ms = distance_m / dt
        estimated_mph = estimated_ms * MS_TO_MPH

        api_ms = curr.api_speed_ms
        api_mph = (api_ms * MS_TO_MPH) if api_ms is not None else None

        return SpeedEstimate(
            vehicle_id=vehicle_id,
            label=curr.label,
            status=curr.status,
            distance_m=distance_m,
            dt_s=dt,
            estimated_mph=estimated_mph,
            estimated_ms=estimated_ms,
            api_speed_ms=api_ms,
            api_speed_mph=api_mph,
            poll_time=poll_time,
        )

    def process_poll(self, vehicles: List[dict], poll_time: float) -> List[SpeedEstimate]:
        self.stats.polls += 1
        estimates: List[SpeedEstimate] = []
        seen_ids = set()

        for vehicle in vehicles:
            self.stats.vehicle_sightings += 1
            parsed = self._sample_from_vehicle(vehicle, poll_time)
            if parsed is None:
                continue

            vehicle_id, sample = parsed
            self.stats.with_latlon += 1
            if sample.api_speed_ms is not None:
                self.stats.with_api_speed += 1
            seen_ids.add(vehicle_id)

            prev = self.prev.get(vehicle_id)
            if prev is None:
                self.stats.skipped_no_movement_pair += 1
            else:
                estimate = self._estimate(vehicle_id, prev, sample, poll_time)
                if estimate is not None:
                    estimates.append(estimate)
                    self.stats.estimates.append(estimate)

            self.prev[vehicle_id] = sample

        # Drop vehicles that disappeared so stale history doesn't poison Δt
        stale = [vid for vid in self.prev if vid not in seen_ids]
        for vid in stale:
            del self.prev[vid]

        return estimates

    def _format_estimate(self, est: SpeedEstimate) -> str:
        label = est.label or "?"
        status = (est.status or "?").replace("_", " ")
        flag = ""
        if est.estimated_mph > self.max_plausible_mph:
            flag = "  [SPIKE?]"

        api_part = "api=null"
        if est.api_speed_ms is not None:
            api_part = (
                f"api={est.api_speed_ms:5.2f} m/s ({est.api_speed_mph:5.1f} mph)"
            )

        return (
            f"  {est.vehicle_id:>12s} label={label:<6s} {status:<16s} "
            f"Δ={est.distance_m:6.1f}m Δt={est.dt_s:5.1f}s  "
            f"est={est.estimated_mph:5.1f} mph ({est.estimated_ms:5.2f} m/s)  "
            f"{api_part}{flag}"
        )

    def run(self, duration_seconds: float) -> None:
        print(f"\n{'=' * 78}")
        print("MBTA Speed-from-Position Monitor")
        print(f"{'=' * 78}")
        print(f"Route(s):     {self.route}")
        print(f"Poll interval:{self.interval:g} s")
        print(f"Duration:     {duration_seconds:g} s")
        print(f"Δt window:    {self.min_dt:g}–{self.max_dt:g} s")
        print(f"Start:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(
            "Note:         MBTA attributes.speed is meters/second when present; "
            "CharlieBoard SpeedMode historically treated the raw value as mph."
        )
        print(f"{'=' * 78}\n")

        start = time.time()
        next_poll = start
        poll_index = 0

        try:
            while True:
                now = time.time()
                if now - start >= duration_seconds:
                    break

                # Align to interval schedule so Duration is approx N * interval
                sleep_for = next_poll - time.time()
                if sleep_for > 0:
                    time.sleep(sleep_for)

                poll_time = time.time()
                poll_index += 1
                stamp = datetime.now().strftime("%H:%M:%S")

                try:
                    vehicles = self.fetch_vehicles()
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                    print(f"[{stamp}] Poll #{poll_index}: request failed: {exc}")
                    next_poll = start + poll_index * self.interval
                    continue

                estimates = self.process_poll(vehicles, poll_time)
                with_pos = sum(
                    1
                    for v in vehicles
                    if (v.get("attributes") or {}).get("latitude") is not None
                    and (v.get("attributes") or {}).get("longitude") is not None
                )
                with_speed = sum(
                    1
                    for v in vehicles
                    if (v.get("attributes") or {}).get("speed") is not None
                )

                print(
                    f"[{stamp}] Poll #{poll_index}: "
                    f"{len(vehicles)} vehicles, {with_pos} with lat/lon, "
                    f"{with_speed} with API speed, "
                    f"{len(estimates)} new estimates"
                )

                if not self.quiet:
                    for est in sorted(estimates, key=lambda e: e.vehicle_id):
                        print(self._format_estimate(est))

                next_poll = start + poll_index * self.interval

        except KeyboardInterrupt:
            print(f"\n{'=' * 78}")
            print("Stopped by user (Ctrl+C)")
            print(f"{'=' * 78}")

        self.print_statistics(time.time() - start)

    def print_statistics(self, duration: float) -> None:
        s = self.stats
        print(f"\n{'=' * 78}")
        print("STATISTICS")
        print(f"{'=' * 78}")
        print(f"Duration:              {duration:.1f} s ({duration / 60:.2f} min)")
        print(f"Polls:                 {s.polls}")
        print(f"Vehicle sightings:     {s.vehicle_sightings}")

        if s.vehicle_sightings:
            latlon_pct = 100.0 * s.with_latlon / s.vehicle_sightings
            api_pct = 100.0 * s.with_api_speed / s.vehicle_sightings
            print(
                f"With lat/lon:          {s.with_latlon} "
                f"({latlon_pct:.1f}% of sightings)"
            )
            print(
                f"With API speed:        {s.with_api_speed} "
                f"({api_pct:.1f}% of sightings)"
            )

        print(f"Speed estimates:       {len(s.estimates)}")
        print(f"Skipped (no prior):    {s.skipped_no_movement_pair}")
        print(f"Skipped (Δt ≤ 0):      {s.skipped_same_timestamp}")
        print(f"Skipped (Δt window):   {s.skipped_dt_out_of_range}")

        if not s.estimates:
            print("\nNo estimates produced — try a longer duration or shorter interval.")
            print(f"{'=' * 78}\n")
            return

        mph_values = [e.estimated_mph for e in s.estimates]
        moving = [e for e in s.estimates if e.estimated_mph >= 1.0]
        spikes = [e for e in s.estimates if e.estimated_mph > self.max_plausible_mph]
        stopped_status = [
            e for e in s.estimates if e.status == "STOPPED_AT" and e.estimated_mph >= 1.0
        ]

        print("\nEstimated speed (mph):")
        print(f"  n / mean / median:   {len(mph_values)} / "
              f"{_mean(mph_values):.1f} / {_median(mph_values):.1f}")
        print(f"  min / max:           {_min(mph_values):.1f} / {_max(mph_values):.1f}")
        print(f"  moving (≥1 mph):     {len(moving)} ({100 * len(moving) / len(mph_values):.1f}%)")
        print(f"  spikes (>{self.max_plausible_mph:g} mph): {len(spikes)}")
        print(f"  STOPPED_AT but ≥1:   {len(stopped_status)}")

        compared = [
            e for e in s.estimates
            if e.api_speed_ms is not None and e.estimated_mph <= self.max_plausible_mph
        ]
        if compared:
            # Compare in m/s — that is the documented API unit.
            abs_err_ms = [
                abs(e.estimated_ms - e.api_speed_ms)  # type: ignore[operator]
                for e in compared
            ]
            abs_err_mph = [err * MS_TO_MPH for err in abs_err_ms]
            print(f"\nAPI comparison (n={len(compared)}, speed in m/s):")
            print(f"  mean |est−api|:      {_mean(abs_err_ms):.2f} m/s "
                  f"({_mean(abs_err_mph):.1f} mph)")
            print(f"  median |est−api|:    {_median(abs_err_ms):.2f} m/s "
                  f"({_median(abs_err_mph):.1f} mph)")
            print("  (Use Green Line routes to get meaningful API comparison.)")
        else:
            print(
                "\nNo API speed values to compare against. "
                "Try --route Green-B,Green-C,Green-D,Green-E"
            )

        print(f"\n{'=' * 78}")
        print("READOUT")
        print(f"{'=' * 78}")
        if s.with_latlon == 0:
            print("Lat/lon were absent — estimation is not viable for this sample.")
        elif len(s.estimates) == 0:
            print("Lat/lon present but no valid successive pairs yet — run longer.")
        elif len(spikes) > 0.25 * len(s.estimates):
            print(
                "Many spike estimates — increase --interval or tighten --max-dt; "
                "GPS jitter may dominate at your current poll rate."
            )
        else:
            print(
                "Lat/lon-based estimation looks usable as a fallback when "
                "attributes.speed is null. Consider smoothing (e.g. EMA) and "
                "zeroing speeds for STOPPED_AT before wiring into SpeedMode."
            )
        print(f"{'=' * 78}\n")


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _median(values: List[float]) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _min(values: List[float]) -> float:
    return min(values) if values else float("nan")


def _max(values: List[float]) -> float:
    return max(values) if values else float("nan")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate MBTA train speeds from successive lat/lon samples "
            "(REST poll of /vehicles)."
        )
    )
    parser.add_argument(
        "--route",
        default="Red",
        help=(
            "MBTA route filter (default: Red). Comma-separate for multiple, "
            "e.g. Green-B,Green-C,Green-D,Green-E"
        ),
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between REST polls (default: 5)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=120.0,
        help="How long to run in seconds (default: 120)",
    )
    parser.add_argument(
        "--min-dt",
        type=float,
        default=2.0,
        help="Ignore pairs with Δt below this many seconds (default: 2)",
    )
    parser.add_argument(
        "--max-dt",
        type=float,
        default=60.0,
        help="Ignore pairs with Δt above this many seconds (default: 60)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="MBTA API key (default: MBTA_API_KEY env var)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print per-poll summaries only (no per-vehicle estimate lines)",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("MBTA_API_KEY")
    if not api_key:
        # Fall back to project .env via SettingsManager when available
        try:
            from config.settings import SettingsManager

            api_key = SettingsManager().load_settings().get("mbta_api_key")
        except Exception:
            api_key = None

    if not api_key:
        print("WARNING: No MBTA API key found.")
        print("  Set MBTA_API_KEY, pass --api-key, or configure .env.")
        print("  Get a free key at: https://api-v3.mbta.com/")
        print("  Continuing without a key (may be rate-limited).\n")

    if args.interval <= 0:
        parser.error("--interval must be positive")
    if args.duration <= 0:
        parser.error("--duration must be positive")

    monitor = SpeedFromPositionMonitor(
        api_key=api_key,
        route=args.route,
        interval=args.interval,
        min_dt=args.min_dt,
        max_dt=args.max_dt,
        quiet=args.quiet,
    )
    monitor.run(args.duration)


if __name__ == "__main__":
    main()
