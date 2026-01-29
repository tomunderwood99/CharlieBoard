#!/usr/bin/env python3
"""System health and maintenance service for MBTA LED Controller."""
import time
import logging
import subprocess
import requests
from datetime import datetime, timedelta
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