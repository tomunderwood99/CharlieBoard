#!/usr/bin/env python3
"""
Network Monitor Classes for MBTA LED Controller

This module provides proactive network monitoring functionality that runs
independently of the main SSE stream. While the SSE stream handles its own
reconnection when it fails, this monitor provides:

1. Proactive detection: Identifies network issues before the SSE stream times out
2. LED feedback: Updates the LED display to show network status (red=disconnected)
3. WiFi recovery: Attempts to restart the wireless interface on connection loss

Design note: This runs as a separate thread polling every 30 seconds. On a Pi Zero 2W,
this overhead is minimal (brief network request). The proactive monitoring
improves user experience by providing immediate visual feedback when network issues
occur, rather than waiting for the SSE stream to timeout.

Wi-Fi backend handling:

Raspberry Pi OS Trixie ships NetworkManager (NM) as the default network
backend, and the optional headless_wifi_helper integration *requires* NM.
We detect NM at startup and bounce the link via `nmcli device disconnect/
connect wlan0` so we stay inside NM's data model — toggling `ifconfig` /
`ip link` out from under NM puts the device into the `unavailable` /
`disconnected` state for ~10–30s while NM re-evaluates, which races with
our retry loop. On older images (or any system where NM is not active),
we fall back to `ip link set wlan0 down/up` (the modern, default-installed
replacement for `ifconfig`, which lives in `net-tools` and is not on
minimal Trixie images).

Escalation path when WiFi cannot be restored in-process:

  in-process reconnect attempts (here, NETWORK_MAX_RETRIES of nmcli /
  `ip link` bounces, see _attempt_reconnect below)
       │  exhausted, network still down
       ▼
  monitoring/health_monitor.py keeps polling /health; once the system has
  been unhealthy past UNHEALTHY_REBOOT_THRESHOLD_MINUTES (or the consecutive-
  failure threshold) outside MBTA quiet hours, it issues `shutdown -r now`.
  If the helper is installed AND wlan0 is associated to a Wi-Fi network
  that has no Internet reachability (a "blackholed" association — bad
  upstream link, captive portal, etc.), the health monitor first deletes
  the active NM connection so the helper is guaranteed to surface its
  captive portal on next boot instead of silently re-associating to the
  same blackholed network and rebooting again.
       │
       ▼
  Next boot: if the headless_wifi_helper is installed alongside CharlieBoard
  (see deployment/quick_start/setup_mbta_controller.sh --with-wifi-helper),
  its `wifi_configurator.service` runs Before=network-online.target, waits
  ~30s for wlan0 to associate, and — if it cannot — brings up a captive-
  portal access point at 192.168.4.1 so the user can hand the Pi new WiFi
  credentials (and optionally a new MBTA API key) from a phone. CharlieBoard's
  services are After=network-online.target, so they wait until either WiFi
  is up or the user reconfigures via the portal.

This module does NOT call `systemctl start wifi_configurator.service` itself
at runtime; the captive portal is reached purely via the reboot path above.

If you want to disable this for lower resource usage, you can remove the NetworkMonitor
initialization from mbta_stream.py and handle network status purely based on SSE failures.
"""

import subprocess
import time
import logging
import threading
import requests
from typing import Optional, Callable
from datetime import datetime, timedelta
from config.constants import (
    NETWORK_MAX_RETRIES,
    NETWORK_CHECK_INTERVAL_SECONDS,
    NETWORK_REQUEST_TIMEOUT_SECONDS,
    WIFI_INTERFACE_DOWN_WAIT_SECONDS,
    WIFI_INTERFACE_UP_WAIT_SECONDS,
    WIFI_RECONNECTION_WAIT_SECONDS,
)

logger = logging.getLogger(__name__)

# Wi-Fi interface we manage. Hard-coded because the rest of the system
# (helper, NM auto-config on the Pi Zero 2W) is also wlan0-specific.
WIFI_IFACE = "wlan0"


def _network_manager_active() -> bool:
    """Return True if systemd reports NetworkManager.service as active.

    Detected lazily at the first reconnect attempt rather than at import
    time so unit tests / non-systemd environments don't have to mock it.
    """
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "NetworkManager.service"],
            timeout=NETWORK_REQUEST_TIMEOUT_SECONDS,
        )
        return result.returncode == 0
    except Exception:
        # Missing systemctl, sandbox, etc. — assume non-NM environment.
        return False

class NetworkMonitor:
    """Monitors network connectivity and handles reconnection attempts."""
    
    def __init__(self, 
                 on_disconnect: Optional[Callable] = None,
                 on_reconnect: Optional[Callable] = None,
                 max_retries: int = NETWORK_MAX_RETRIES,
                 check_interval: int = NETWORK_CHECK_INTERVAL_SECONDS):
        """Initialize the network monitor.
        
        Args:
            on_disconnect: Callback function when network disconnects
            on_reconnect: Callback function when network reconnects
            max_retries: Maximum number of reconnection attempts
            check_interval: Seconds between connectivity checks
        """
        self.on_disconnect = on_disconnect
        self.on_reconnect = on_reconnect
        self.max_retries = max_retries
        self.check_interval = check_interval
        
        self._is_connected = True
        self._last_connected = datetime.now()
        self._retry_count = 0
        self._should_run = True
        self._lock = threading.Lock()

        # Cache the network backend on first reconnect attempt so we don't
        # shell out to `systemctl is-active` on every retry.
        self._uses_network_manager: Optional[bool] = None

        # Start monitoring thread
        self._monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
        self._monitor_thread.start()
    
    def _check_connection(self) -> bool:
        """Check if network is connected.
        
        Returns:
            bool: True if connected
        """
        try:
            # Try to reach a reliable endpoint
            response = requests.get("https://api-v3.mbta.com/", timeout=NETWORK_REQUEST_TIMEOUT_SECONDS)
            return response.status_code == 200
        except Exception:
            return False

    def _bounce_wifi_via_nmcli(self) -> bool:
        """Cycle wlan0 by asking NetworkManager to disconnect/reconnect it.

        We deliberately avoid `nmcli networking off/on` (too disruptive — it
        also drops Ethernet, USB-gadget, etc.) and avoid `ip link` here
        (NM treats out-of-band link toggles as user-initiated and parks the
        device in `disconnected` for tens of seconds). `device disconnect`
        followed by `device connect` is the cheapest reset that stays in
        NM's data model.

        Returns:
            bool: True if both nmcli invocations exited cleanly. A True
            return does NOT imply Internet reachability — the caller must
            re-check via `_check_connection`.
        """
        try:
            disc = subprocess.run(
                ["nmcli", "device", "disconnect", WIFI_IFACE],
                timeout=NETWORK_REQUEST_TIMEOUT_SECONDS,
                capture_output=True,
                text=True,
            )
            if disc.returncode != 0:
                logger.warning(
                    "nmcli device disconnect %s failed (rc=%s): %s",
                    WIFI_IFACE, disc.returncode, disc.stderr.strip(),
                )
                # Don't bail — `device connect` below can still recover an
                # already-disconnected device.
            time.sleep(WIFI_INTERFACE_DOWN_WAIT_SECONDS)

            conn = subprocess.run(
                ["nmcli", "device", "connect", WIFI_IFACE],
                timeout=NETWORK_REQUEST_TIMEOUT_SECONDS,
                capture_output=True,
                text=True,
            )
            if conn.returncode != 0:
                logger.warning(
                    "nmcli device connect %s failed (rc=%s): %s",
                    WIFI_IFACE, conn.returncode, conn.stderr.strip(),
                )
                return False
            return True
        except FileNotFoundError:
            # nmcli not installed despite NM appearing active — extremely
            # unusual, but fall through to ip-link path on next attempt.
            logger.warning("nmcli not found; will retry with `ip link` fallback.")
            self._uses_network_manager = False
            return False
        except Exception as e:
            logger.warning("nmcli reconnect raised %s: %s", type(e).__name__, e)
            return False

    def _bounce_wifi_via_ip_link(self) -> bool:
        """Bring wlan0 down and back up via iproute2 (no NetworkManager).

        Used when NetworkManager is not the active backend. `ip link` is
        part of iproute2 and is installed by default on every modern Pi
        OS image — unlike `ifconfig`, which lives in the optional
        `net-tools` package.
        """
        try:
            subprocess.run(
                ["ip", "link", "set", WIFI_IFACE, "down"],
                timeout=NETWORK_REQUEST_TIMEOUT_SECONDS,
            )
            time.sleep(WIFI_INTERFACE_DOWN_WAIT_SECONDS)
            subprocess.run(
                ["ip", "link", "set", WIFI_IFACE, "up"],
                timeout=NETWORK_REQUEST_TIMEOUT_SECONDS,
            )
            time.sleep(WIFI_INTERFACE_UP_WAIT_SECONDS)
            return True
        except Exception as e:
            logger.warning("ip-link reconnect raised %s: %s", type(e).__name__, e)
            return False

    def _attempt_reconnect(self) -> bool:
        """Attempt to reconnect to WiFi.

        Returns:
            bool: True if reconnection successful (verified by re-checking
            connectivity to the MBTA endpoint).
        """
        if self._uses_network_manager is None:
            self._uses_network_manager = _network_manager_active()
            logger.info(
                "Wi-Fi recovery backend: %s",
                "NetworkManager (nmcli)" if self._uses_network_manager else "iproute2 (ip link)",
            )

        # Each backend handles its own settle-time internally:
        #   - `nmcli device connect` blocks until NM marks the device
        #     activated, so no further sleep is needed here.
        #   - `ip link set wlan0 up` returns immediately, so the iproute2
        #     path sleeps WIFI_INTERFACE_UP_WAIT_SECONDS for DHCP / link
        #     negotiation before returning.
        # The outer retry loop in `_monitor_connection` adds its own
        # WIFI_RECONNECTION_WAIT_SECONDS pause between attempts.
        if self._uses_network_manager:
            bounced = self._bounce_wifi_via_nmcli()
        else:
            bounced = self._bounce_wifi_via_ip_link()

        if not bounced:
            return False
        return self._check_connection()
    
    def _monitor_connection(self) -> None:
        """Monitor network connection and handle reconnection."""
        while self._should_run:
            is_connected = self._check_connection()
            
            with self._lock:
                if is_connected and not self._is_connected:
                    # Network restored
                    logger.info("Network connection restored")
                    self._is_connected = True
                    self._last_connected = datetime.now()
                    self._retry_count = 0
                    if self.on_reconnect:
                        self.on_reconnect()
                
                elif not is_connected and self._is_connected:
                    # Network lost
                    logger.warning("Network connection lost")
                    self._is_connected = False
                    if self.on_disconnect:
                        self.on_disconnect()
                    
                    # Attempt reconnection
                    while (not self._is_connected and 
                           self._retry_count < self.max_retries and 
                           self._should_run):
                        logger.info(f"Attempting reconnection (attempt {self._retry_count + 1}/{self.max_retries})")
                        if self._attempt_reconnect():
                            self._is_connected = True
                            self._last_connected = datetime.now()
                            if self.on_reconnect:
                                self.on_reconnect()
                            break
                        self._retry_count += 1
                        time.sleep(WIFI_RECONNECTION_WAIT_SECONDS)  # Wait between attempts
            
            time.sleep(self.check_interval)
    
    def is_connected(self) -> bool:
        """Check if network is currently connected.
        
        Returns:
            bool: True if connected
        """
        with self._lock:
            return self._is_connected
    
    def get_status(self) -> dict:
        """Get current network status.
        
        Returns:
            dict: Network status information
        """
        with self._lock:
            return {
                'connected': self._is_connected,
                'last_connected': self._last_connected.isoformat(),
                'retry_count': self._retry_count
            }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self._should_run = False
        if self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
