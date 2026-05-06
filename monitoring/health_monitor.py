#!/usr/bin/env python3
"""System health and maintenance service for MBTA LED Controller."""
import time
import logging
import subprocess
import requests
from datetime import datetime, timedelta
from typing import Optional
import os
import sys
from logging.handlers import RotatingFileHandler

# Add project root to path for imports when run as a script
def _get_project_root():
    """Get the project root directory based on this script's location."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)

_project_root = _get_project_root()
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from config.bedtime import is_mbta_quiet_hours
from config.constants import (
    LOG_FILE_MAX_BYTES_SMALL,
    LOG_FILE_BACKUP_COUNT_SMALL,
    NETWORK_REQUEST_TIMEOUT_SECONDS,
    UNHEALTHY_REBOOT_THRESHOLD_MINUTES,
    UNHEALTHY_REBOOT_THRESHOLD_FAILURES,
    DISPLAY_SERVICE_MAX_WAIT_SECONDS,
    DISPLAY_SERVICE_CHECK_INTERVAL_SECONDS,
    HEALTH_CHECK_INTERVAL_SECONDS,
    HEALTH_MONITOR_ERROR_SLEEP_SECONDS,
    WEB_SERVER_PORT,
)

# Wi-Fi interface monitored both here and in monitoring/network_monitor.py.
# Kept in sync because the helper integration is wlan0-specific.
WIFI_IFACE = "wlan0"

# Public connectivity-check endpoints used to distinguish "MBTA is down" from
# "the whole Internet is unreachable from this Wi-Fi network". We accept any
# 2xx/3xx response; both URLs below are designed for this purpose and return
# tiny payloads (Google's `generate_204` and Firefox's portal-detection page).
# Crucially, NONE of these endpoints are MBTA — if the MBTA API is down for
# its own reasons we must NOT classify that as a Wi-Fi problem and wipe the
# user's saved network.
INTERNET_PROBE_URLS = (
    "https://www.gstatic.com/generate_204",
    "https://detectportal.firefox.com/canonical.html",
)

# Name of the headless_wifi_helper systemd unit. We only delete the active
# Wi-Fi connection profile to break a blackhole loop when this unit is
# installed — without the helper, deleting the connection would orphan the
# Pi (no way to re-enter credentials without a console / SD-card re-flash).
WIFI_HELPER_UNIT = "wifi_configurator.service"

# Configure logging with smaller file size
# Note: No StreamHandler - when running via systemd, stdout is captured by journalctl
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'logs/system_health.log',
            maxBytes=LOG_FILE_MAX_BYTES_SMALL,  # 512KB instead of 1MB
            backupCount=LOG_FILE_BACKUP_COUNT_SMALL,      # Keep fewer backups
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)


def _wifi_helper_installed() -> bool:
    """Return True if headless_wifi_helper's systemd unit is installed.

    We check `list-unit-files` rather than `is-enabled` because a hand-disabled
    unit is still a recovery target — its presence implies the user has the
    helper repo on disk and can re-enable it from the captive portal. We do
    NOT require the unit to be active right now (it's expected to be inactive
    once boot has succeeded).
    """
    try:
        result = subprocess.run(
            ["systemctl", "list-unit-files", WIFI_HELPER_UNIT, "--no-legend"],
            capture_output=True, text=True,
            timeout=NETWORK_REQUEST_TIMEOUT_SECONDS,
        )
        # Output is e.g. "wifi_configurator.service enabled enabled" when present,
        # empty string when absent.
        return WIFI_HELPER_UNIT in result.stdout
    except Exception as e:
        logger.debug("Could not query systemctl for %s: %s", WIFI_HELPER_UNIT, e)
        return False


def _active_wifi_connection_name() -> Optional[str]:
    """Return the active NetworkManager connection NAME on wlan0, or None.

    Uses the terse `-t` output and field selection to avoid parsing column
    widths. The NAME field can contain literal colons (rare for SSIDs but
    legal), so we rely on DEVICE being the trailing field — `nmcli -t` escapes
    any embedded colons within a field with a backslash, so a real `:wlan0`
    suffix unambiguously separates the device from the (possibly colon-
    containing) name.
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
            capture_output=True, text=True,
            timeout=NETWORK_REQUEST_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            return None
        suffix = ":" + WIFI_IFACE
        for line in result.stdout.splitlines():
            if line.endswith(suffix):
                # Unescape `\:` back to `:` in the NAME portion (nmcli -t
                # escapes embedded colons inside fields).
                name = line[: -len(suffix)].replace(r"\:", ":")
                return name or None
        return None
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.debug("nmcli connection lookup failed: %s", e)
        return None


def _internet_reachable() -> bool:
    """Return True if at least one public connectivity-check probe succeeds.

    Used to distinguish MBTA-side outages (don't touch Wi-Fi) from Wi-Fi-side
    blackholes (associated to a SSID with no working WAN, e.g. wrong upstream
    password or captive portal). Any 2xx or 3xx counts; we deliberately do
    not care about response bodies.
    """
    for url in INTERNET_PROBE_URLS:
        try:
            resp = requests.get(url, timeout=NETWORK_REQUEST_TIMEOUT_SECONDS)
            if 200 <= resp.status_code < 400:
                return True
        except Exception:
            continue
    return False


class SystemHealthService:
    """Service to monitor system health and perform maintenance."""
    
    def __init__(self):
        """Initialize the system health service."""
        self.health_url = f'http://localhost:{WEB_SERVER_PORT}/health'
        self.last_reboot = datetime.now()
        self.unhealthy_since = None
        self.consecutive_failures = 0
    
    def check_health(self) -> bool:
        """Check system health status.
        
        Returns:
            bool: True if system is healthy
        """
        try:
            response = requests.get(self.health_url, timeout=NETWORK_REQUEST_TIMEOUT_SECONDS)
            health_data = response.json()
            
            if response.status_code == 200 and health_data.get('healthy', False):
                # Log recovery if we were previously unhealthy
                if self.unhealthy_since is not None:
                    recovery_time = datetime.now() - self.unhealthy_since
                    logger.info(
                        f"System recovered to healthy state after {recovery_time.total_seconds():.1f}s "
                        f"({self.consecutive_failures} failed checks)"
                    )
                self.unhealthy_since = None
                self.consecutive_failures = 0
                return True
            
            # System is unhealthy
            if self.unhealthy_since is None:
                self.unhealthy_since = datetime.now()
            self.consecutive_failures += 1
            
            # Log unhealthy state with key diagnostic info only
            api_status = "OK" if health_data.get('api_healthy') else "FAIL"
            led_status = "OK" if health_data.get('led_healthy') else "FAIL"
            vehicles = health_data.get('active_vehicles', 0)
            quiet_hours = " (quiet hours)" if health_data.get('is_quiet_hours') else ""
            
            logger.warning(
                f"System unhealthy{quiet_hours}: API={api_status}, LED={led_status}, "
                f"vehicles={vehicles}, consecutive_failures={self.consecutive_failures}"
            )
            
            return False
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.consecutive_failures += 1
            return False
    
    def should_reboot(self) -> bool:
        """Determine if system should be rebooted.
        
        Returns:
            bool: True if system should be rebooted
        """
        if self.unhealthy_since is None:
            return False
        
        # Never reboot during MBTA quiet hours (12 AM - 6 AM ET)
        # The API naturally has minimal/no data during these hours
        if is_mbta_quiet_hours():
            logger.info("System unhealthy during MBTA quiet hours - deferring reboot decision")
            return False
        
        # Reboot if unhealthy for more than 5 minutes
        unhealthy_duration = datetime.now() - self.unhealthy_since
        if unhealthy_duration > timedelta(minutes=UNHEALTHY_REBOOT_THRESHOLD_MINUTES):
            return True
        
        # Reboot if too many consecutive failures
        if self.consecutive_failures > UNHEALTHY_REBOOT_THRESHOLD_FAILURES:  # 5 minutes at 10-second intervals
            return True
        
        return False
    
    def wait_for_display_service(self, max_wait: int = DISPLAY_SERVICE_MAX_WAIT_SECONDS, check_interval: int = DISPLAY_SERVICE_CHECK_INTERVAL_SECONDS) -> bool:
        """Wait for the display service to become available.
        
        Args:
            max_wait: Maximum seconds to wait for service
            check_interval: Seconds between checks
            
        Returns:
            bool: True if service became available, False if timeout
        """
        logger.info(f"Waiting up to {max_wait}s for display service to be ready...")
        waited = 0
        
        while waited < max_wait:
            try:
                response = requests.get(self.health_url, timeout=NETWORK_REQUEST_TIMEOUT_SECONDS)
                if response.status_code in (200, 503):  # 503 is unhealthy but reachable
                    logger.info(f"Display service is ready after {waited}s")
                    return True
            except requests.exceptions.ConnectionError:
                # Service not yet available, this is expected during startup
                pass
            except Exception as e:
                logger.debug(f"Waiting for display service: {e}")
            
            time.sleep(check_interval)
            waited += check_interval
        
        logger.warning(f"Display service not available after {max_wait}s, starting monitoring anyway")
        return False
    
    def _force_portal_recovery_if_blackholed(self) -> None:
        """Break an associated-but-no-Internet reboot loop before rebooting.

        Triggered just before we issue `shutdown -r now`. If we are about to
        reboot because our /health endpoint has been failing AND we detect
        that wlan0 is associated to a Wi-Fi network whose wider Internet is
        unreachable (a "blackholed" association — bad upstream link, captive
        portal we can't authenticate against, ISP outage on that SSID, …),
        we delete the active NM connection profile so that on the next boot
        the headless_wifi_helper sees no STA association and surfaces its
        captive portal at 192.168.4.1.

        Safety conditions — we only blow away the saved network when ALL of:
          1. wifi_configurator.service is installed on this system. Without
             the helper, deleting the connection would orphan the Pi.
          2. wlan0 has an active NM connection (we can identify the saved
             profile to delete).
          3. None of our public Internet probes succeed. We deliberately do
             not rely on the MBTA API here — if MBTA itself is down that's
             not a reason to touch the user's Wi-Fi config.

        Any failure path here is non-fatal: we always fall through to the
        normal reboot below so a probe / nmcli failure can never block
        recovery.
        """
        try:
            if not _wifi_helper_installed():
                # Without the helper, we have no recovery path post-delete.
                return

            connection_name = _active_wifi_connection_name()
            if not connection_name:
                # Either NM is not active (we'll just reboot and let
                # network_monitor's iproute2 path do its thing on next boot),
                # or wlan0 is already disconnected — either way, the helper
                # will catch us on the next boot without our intervention.
                return

            if _internet_reachable():
                # Internet works — this is an MBTA-side or local-service
                # problem. Don't touch the Wi-Fi config; just reboot.
                return

            logger.warning(
                "Wi-Fi appears blackholed (associated to '%s' but no public "
                "endpoint reachable). Deleting NM connection before reboot "
                "so headless_wifi_helper can surface the captive portal on "
                "next boot.",
                connection_name,
            )
            result = subprocess.run(
                ["nmcli", "connection", "delete", "id", connection_name],
                capture_output=True, text=True,
                timeout=NETWORK_REQUEST_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                logger.error(
                    "nmcli connection delete '%s' failed (rc=%s): %s",
                    connection_name, result.returncode, result.stderr.strip(),
                )
            else:
                logger.warning(
                    "Deleted NM connection '%s'. The next boot will land in "
                    "the captive portal at http://192.168.4.1.",
                    connection_name,
                )
        except Exception as e:
            # Never block reboot on a recovery-helper failure.
            logger.error(
                "Pre-reboot blackhole recovery raised %s: %s — proceeding "
                "with reboot anyway.",
                type(e).__name__, e,
            )

    def run(self) -> None:
        """Run the system health service."""
        logger.info("Starting system health service...")
        
        # Wait for the display service to be ready before starting health checks
        self.wait_for_display_service()
        
        while True:
            try:
                # Check health
                is_healthy = self.check_health()
                
                # Check if should reboot when unhealthy
                if not is_healthy and self.should_reboot():
                    logger.warning("System unhealthy, initiating reboot...")
                    # Best-effort: if we're stuck on a Wi-Fi network with no
                    # working Internet, hand the next boot off to
                    # headless_wifi_helper's captive portal instead of
                    # silently re-associating to the same dead network.
                    self._force_portal_recovery_if_blackholed()
                    subprocess.run(['sudo', 'shutdown', '-r', 'now'])
                    break
                
                time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)  # Check every 30 seconds instead of 10
                
            except KeyboardInterrupt:
                logger.info("System health service stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in system health service: {e}")
                time.sleep(HEALTH_MONITOR_ERROR_SLEEP_SECONDS)  # Wait longer on error

if __name__ == "__main__":
    service = SystemHealthService()
    service.run() 