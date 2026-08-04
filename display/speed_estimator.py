"""Estimate display speed (mph) from MBTA vehicle updates.

Green Line uses API attributes.speed (m/s → mph). Red/Blue/Orange typically
lack API speed, so successive lat/lon samples are turned into mph via haversine
distance / Δt, then smoothed with an EMA. STOPPED_AT always forces 0 mph.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from config.constants import (
    LINE_MAX_SPEED_MPH,
    MAX_VEHICLE_SPEED_MPH,
    MS_TO_MPH,
    SPEED_EMA_ALPHA,
    SPEED_ESTIMATE_MAX_DT_S,
    SPEED_ESTIMATE_MIN_DT_S,
    SPEED_SPIKE_FACTOR,
)

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


def line_max_speed_mph(route: str) -> float:
    """Return the color-ceiling / spike cap for a route."""
    return float(LINE_MAX_SPEED_MPH.get(route, MAX_VEHICLE_SPEED_MPH))


def is_green_route(route: str) -> bool:
    return route.startswith("Green")


@dataclass
class _PositionSample:
    lat: float
    lon: float
    t: float  # preferred Δt clock (updated_at when present)
    wall_t: float  # wall clock when we processed this sample (SSE fallback)


@dataclass
class _VehicleState:
    last_sample: Optional[_PositionSample] = None
    ema_mph: Optional[float] = None


# Ignore haversine noise / identical GPS between updates (meters)
_MIN_MOVE_M = 5.0


class SpeedEstimator:
    """Per-vehicle speed resolution with optional GPS/EMA for heavy rail."""

    def __init__(
        self,
        min_dt: float = SPEED_ESTIMATE_MIN_DT_S,
        max_dt: float = SPEED_ESTIMATE_MAX_DT_S,
        ema_alpha: float = SPEED_EMA_ALPHA,
        spike_factor: float = SPEED_SPIKE_FACTOR,
    ):
        self.min_dt = min_dt
        self.max_dt = max_dt
        self.ema_alpha = ema_alpha
        self.spike_factor = spike_factor
        self._state: Dict[str, _VehicleState] = {}

    def forget(self, vehicle_id: str) -> None:
        """Drop history for a vehicle that left the stream."""
        self._state.pop(vehicle_id, None)

    def clear(self) -> None:
        """Drop all vehicle history (e.g. quiet-hours wipe)."""
        self._state.clear()

    def _dt_for_pair(self, prev: _PositionSample, curr: _PositionSample) -> Optional[float]:
        """Prefer updated_at Δt; fall back to wall clock when that is out of window.

        MBTA often re-emits vehicle SSE events with the same updated_at (Δt ≤ 0)
        while wall time has advanced — without a wall fallback we never estimate.
        """
        dt = curr.t - prev.t
        if self.min_dt <= dt <= self.max_dt:
            return dt
        wall_dt = curr.wall_t - prev.wall_t
        if self.min_dt <= wall_dt <= self.max_dt:
            return wall_dt
        return None

    def resolve(self, vehicle_data: dict, route: str, wall_time: Optional[float] = None) -> Optional[float]:
        """Return display speed in mph, or None if unknown.

        Args:
            vehicle_data: MBTA vehicle JSON:API object
            route: Active board route (e.g. 'Red', 'Green-B')
            wall_time: Optional clock override for tests; defaults to time.time()
        """
        now = wall_time if wall_time is not None else time.time()
        vehicle_id = vehicle_data.get("id")
        attrs = vehicle_data.get("attributes") or {}
        if not vehicle_id:
            return None

        state = self._state.setdefault(vehicle_id, _VehicleState())
        status = attrs.get("current_status")
        api_speed_ms = attrs.get("speed")
        lat = attrs.get("latitude")
        lon = attrs.get("longitude")
        sample_t = parse_updated_at(attrs.get("updated_at")) or now

        sample: Optional[_PositionSample] = None
        if lat is not None and lon is not None:
            try:
                sample = _PositionSample(
                    lat=float(lat), lon=float(lon), t=sample_t, wall_t=now
                )
            except (TypeError, ValueError):
                sample = None

        # Always force stopped trains to 0; still refresh position baseline.
        if status == "STOPPED_AT":
            if sample is not None:
                state.last_sample = sample
            state.ema_mph = 0.0
            return 0.0

        # Green Line: API speed only (m/s → mph). No GPS fallback.
        if is_green_route(route):
            if sample is not None:
                state.last_sample = sample
            if api_speed_ms is None:
                return None
            try:
                mph = float(api_speed_ms) * MS_TO_MPH
            except (TypeError, ValueError):
                return None
            state.ema_mph = mph
            return mph

        # Heavy rail: prefer rare API speed when present, else GPS estimate.
        if api_speed_ms is not None:
            try:
                mph = float(api_speed_ms) * MS_TO_MPH
            except (TypeError, ValueError):
                mph = None
            if mph is not None:
                if sample is not None:
                    state.last_sample = sample
                state.ema_mph = mph
                return mph

        if sample is None:
            return state.ema_mph

        prev = state.last_sample
        state.last_sample = sample

        if prev is None:
            return state.ema_mph

        dt = self._dt_for_pair(prev, sample)
        if dt is None:
            return state.ema_mph

        distance_m = haversine_meters(prev.lat, prev.lon, sample.lat, sample.lon)
        if distance_m < _MIN_MOVE_M:
            # Identical / jitter-only GPS — keep prior EMA (don't invent 0 mph)
            return state.ema_mph

        raw_mph = (distance_m / dt) * MS_TO_MPH

        max_mph = line_max_speed_mph(route)
        if raw_mph > max_mph * self.spike_factor:
            # Reject GPS jitter spike; keep prior EMA if any.
            return state.ema_mph

        if state.ema_mph is None or state.ema_mph == 0.0:
            # First estimate, or first move after STOPPED_AT: seed at raw so
            # departures aren't lagged by blending up from zero.
            state.ema_mph = raw_mph
        else:
            state.ema_mph = (
                self.ema_alpha * raw_mph + (1.0 - self.ema_alpha) * state.ema_mph
            )
        return state.ema_mph
