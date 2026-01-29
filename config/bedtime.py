from datetime import datetime, time
from zoneinfo import ZoneInfo
import logging
from .constants import (
    MBTA_QUIET_HOURS_START,
    MBTA_QUIET_HOURS_END,
    DEFAULT_BEDTIME_START_HOUR,
    DEFAULT_BEDTIME_START_MINUTE,
    DEFAULT_BEDTIME_END_HOUR,
    DEFAULT_BEDTIME_END_MINUTE,
)

logger = logging.getLogger(__name__)


def is_mbta_quiet_hours() -> bool:
    """Check if current time is during MBTA quiet hours.
    
    The MBTA API typically returns empty data or minimal updates during
    late night/early morning hours when trains are not running. This is
    normal behavior and should not be considered unhealthy.
    
    Quiet hours are 12:00 AM to 6:00 AM ET when most MBTA services
    are not operating. Uses Eastern Time regardless of device's local timezone.
    
    Returns:
        bool: True if current time is during MBTA quiet hours
    """
    # Get current time in Eastern Time
    eastern = ZoneInfo("America/New_York")
    current_time_et = datetime.now(eastern).time()
    quiet_start = time(MBTA_QUIET_HOURS_START, 0)  # 12:00 AM ET
    quiet_end = time(MBTA_QUIET_HOURS_END, 0)      # 6:00 AM ET
    
    # Quiet hours are within the same day (12 AM to 6 AM ET)
    return quiet_start <= current_time_et < quiet_end

class BedtimeManager:
    """Manages display bedtime functionality."""
    
    def __init__(self, bedtime_start: str = "22:00", bedtime_end: str = "06:00"):
        """Initialize the bedtime manager.
        
        Args:
            bedtime_start: Time to turn off display (24-hour format "HH:MM")
            bedtime_end: Time to turn on display (24-hour format "HH:MM")
        """
        self.update_bedtime(bedtime_start, bedtime_end)
    
    def update_bedtime(self, bedtime_start: str, bedtime_end: str) -> None:
        """Update bedtime hours.
        
        Args:
            bedtime_start: Time to turn off display (24-hour format "HH:MM")
            bedtime_end: Time to turn on display (24-hour format "HH:MM")
        """
        try:
            # Parse bedtime strings into time objects
            self.bedtime_start = datetime.strptime(bedtime_start, "%H:%M").time()
            self.bedtime_end = datetime.strptime(bedtime_end, "%H:%M").time()
        except ValueError as e:
            logger.error(f"Invalid bedtime format: {e}")
            # Set default values
            self.bedtime_start = time(DEFAULT_BEDTIME_START_HOUR, DEFAULT_BEDTIME_START_MINUTE)  # 10 PM
            self.bedtime_end = time(DEFAULT_BEDTIME_END_HOUR, DEFAULT_BEDTIME_END_MINUTE)        # 6 AM
    
    def is_bedtime(self) -> bool:
        """Check if current time is within bedtime hours.
        
        Returns:
            bool: True if current time is within bedtime hours
        """
        current_time = datetime.now().time()
        
        # Handle cases where bedtime crosses midnight
        if self.bedtime_start >= self.bedtime_end:
            # Complex case: bedtime crosses midnight
            # e.g., 23:00 to 07:00 means we're in bedtime from 23:00 to 23:59:59 and 00:00 to 06:59:59
            is_bedtime = current_time >= self.bedtime_start or current_time < self.bedtime_end
        else:
            # Simple case: bedtime within same day
            # e.g., 02:00 to 09:00 means we're in bedtime from 02:00 to 08:59:59
            is_bedtime = self.bedtime_start <= current_time < self.bedtime_end
        
        return is_bedtime 