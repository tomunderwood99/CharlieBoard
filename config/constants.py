"""
Centralized constants for the MBTA LED Controller.

This module contains all magic numbers and configuration constants used throughout
the application. Grouping them here makes the codebase easier to maintain and tune.
"""

# =============================================================================
# TIME CONSTANTS
# =============================================================================

# MBTA quiet hours (when train service is minimal/stopped)
MBTA_QUIET_HOURS_START = 0   # 12:00 AM (midnight)
MBTA_QUIET_HOURS_END = 6     # 6:00 AM

# Default bedtime settings (when display turns off)
DEFAULT_BEDTIME_START_HOUR = 22  # 10:00 PM
DEFAULT_BEDTIME_START_MINUTE = 0
DEFAULT_BEDTIME_END_HOUR = 6     # 6:00 AM
DEFAULT_BEDTIME_END_MINUTE = 0

# =============================================================================
# COLOR CONSTANTS
# =============================================================================

# RGB color value bounds
COLOR_MIN = 0
COLOR_MAX = 255
RGB_CHANNELS = 3  # Number of color channels (R, G, B)

# LED off color
LED_OFF = (0, 0, 0)

# Network status indicator colors
NETWORK_DISCONNECTED_COLOR = (255, 0, 0)   # Red
NETWORK_RECONNECTING_COLOR = (0, 0, 255)   # Blue

# Safe mode indicator color (used when max reboots reached)
SAFE_MODE_COLOR = (0, 0, 255)  # Blue

# =============================================================================
# BRIGHTNESS CONSTANTS
# =============================================================================

BRIGHTNESS_MIN = 0.0
BRIGHTNESS_MAX = 1.0
DEFAULT_BRIGHTNESS = 1.0
SAFE_MODE_BRIGHTNESS = 0.3  # Lower brightness for safe mode indicator

# =============================================================================
# HARDWARE CONSTANTS
# =============================================================================

# GPIO pin for NeoPixel LED strip (Raspberry Pi)
LED_GPIO_PIN = 18  # board.D18

# Default fallback LED count (used when config unavailable)
DEFAULT_LED_COUNT = 100

# Color key LED count (LEDs at end of strip showing color legend)
COLOR_KEY_LED_COUNT = 3

# LED count adjustment for 0-indexing (+1) and color key (+3)
LED_COUNT_ADJUSTMENT = 4

# =============================================================================
# DISPLAY MODE CONSTANTS
# =============================================================================

# Rainbow mode animation
RAINBOW_ANIMATION_SPEED = 5
RAINBOW_WHEEL_POSITIONS = 256
RAINBOW_WHEEL_SEGMENT_1 = 85   # First color transition boundary
RAINBOW_WHEEL_SEGMENT_2 = 170  # Second color transition boundary
RAINBOW_WHEEL_MULTIPLIER = 3   # Color intensity multiplier

# Speed mode
MAX_VEHICLE_SPEED_MPH = 45  # Maximum expected train speed

# Occupancy mode
MAX_OCCUPANCY_PERCENTAGE = 100

# =============================================================================
# ERROR HANDLING CONSTANTS
# =============================================================================

# Maximum consecutive errors before suppressing detailed logs
MAX_CONSECUTIVE_ERRORS = 5

# Seconds between detailed error logs when errors persist
ERROR_LOG_COOLDOWN_SECONDS = 30

# Maximum age in days for error data files before cleanup
ERROR_FILE_MAX_AGE_DAYS = 7

# String preview lengths for error logging
ERROR_DATA_PREVIEW_LENGTH = 500   # Full error data preview
ERROR_LOG_PREVIEW_LENGTH = 100    # Short error preview in logs

# =============================================================================
# LOGGING BEHAVIOR CONSTANTS
# =============================================================================

# How often to log health status (every N events)
HEALTH_LOG_FREQUENCY = 10

# =============================================================================
# SSE STREAM CONSTANTS
# =============================================================================

# Chunk size for SSE client (handles large reset events)
SSE_CHUNK_SIZE = 65536  # 64KB

# =============================================================================
# HEALTH MONITORING CONSTANTS
# =============================================================================

# Timeout thresholds for health checks
HEALTH_CHECK_API_TIMEOUT_MINUTES = 2      # Normal hours
HEALTH_CHECK_LED_TIMEOUT_MINUTES = 2      # Normal hours
HEALTH_CHECK_QUIET_HOURS_TIMEOUT_HOURS = 7  # Extended timeout during quiet hours

# Time before vehicle data is considered stale during quiet hours
STALE_VEHICLE_DATA_SECONDS = 600  # 10 minutes

# Health monitor check interval
HEALTH_CHECK_INTERVAL_SECONDS = 30

# Minutes unhealthy before initiating reboot
UNHEALTHY_REBOOT_THRESHOLD_MINUTES = 5

# Consecutive health check failures before reboot
UNHEALTHY_REBOOT_THRESHOLD_FAILURES = 30

# Wait time for display service to become available
DISPLAY_SERVICE_MAX_WAIT_SECONDS = 60
DISPLAY_SERVICE_CHECK_INTERVAL_SECONDS = 5

# Sleep time after error in health monitor
HEALTH_MONITOR_ERROR_SLEEP_SECONDS = 60

# =============================================================================
# METRICS CONSTANTS
# =============================================================================

# History sizes for performance tracking (reduced for Pi memory efficiency)
API_LATENCY_HISTORY_SIZE = 20
UPDATE_TIMES_HISTORY_SIZE = 20
VALIDATION_TIMES_HISTORY_SIZE = 10

# System resource update interval
SYSTEM_RESOURCE_UPDATE_INTERVAL_SECONDS = 30

# Shared metrics file staleness threshold
METRICS_FILE_MAX_AGE_SECONDS = 120  # 2 minutes

# Metrics save timing
METRICS_INITIAL_SAVE_DELAY_SECONDS = 30
METRICS_SAVE_INTERVAL_SECONDS = 15

# =============================================================================
# NETWORK MONITOR CONSTANTS
# =============================================================================

# Network connectivity check settings
NETWORK_MAX_RETRIES = 5
NETWORK_CHECK_INTERVAL_SECONDS = 30
NETWORK_REQUEST_TIMEOUT_SECONDS = 5

# WiFi interface restart timing
WIFI_INTERFACE_DOWN_WAIT_SECONDS = 1
WIFI_INTERFACE_UP_WAIT_SECONDS = 5
WIFI_RECONNECTION_WAIT_SECONDS = 5

# =============================================================================
# REBOOT PROTECTION CONSTANTS
# =============================================================================

# Maximum reboots allowed within time window before entering safe mode
MAX_REBOOTS = 5

# Delay before initiating reboot (prevents rapid loops)
REBOOT_DELAY_SECONDS = 30

# Time window for reboot counter (resets if no reboots in this time)
REBOOT_WINDOW_HOURS = 1

# Safe mode refresh interval (periodic LED refresh)
SAFE_MODE_REFRESH_INTERVAL_SECONDS = 60

# =============================================================================
# PROCESS MANAGEMENT CONSTANTS
# =============================================================================

# Startup delays between processes
WEB_INTERFACE_STARTUP_DELAY_SECONDS = 2
LED_CONTROLLER_STARTUP_DELAY_SECONDS = 3

# Process termination timeout
PROCESS_TERMINATE_TIMEOUT_SECONDS = 5

# Main monitoring loop interval
MONITOR_LOOP_INTERVAL_SECONDS = 1.0

# Network disconnection retry wait
NETWORK_DISCONNECTION_WAIT_SECONDS = 5

# Stream error retry wait
STREAM_ERROR_RETRY_WAIT_SECONDS = 5

# =============================================================================
# LOGGING CONSTANTS
# =============================================================================

# Log file sizes
LOG_FILE_MAX_BYTES = 1024 * 1024        # 1MB
LOG_FILE_MAX_BYTES_SMALL = 512 * 1024   # 512KB for less critical logs
LOG_FILE_BACKUP_COUNT = 5
LOG_FILE_BACKUP_COUNT_SMALL = 3

# =============================================================================
# WEB INTERFACE CONSTANTS
# =============================================================================

# Minimum length for a valid API key
API_KEY_MIN_LENGTH = 32

# Web server port
WEB_SERVER_PORT = 8000

# =============================================================================
# STATUS CHECK CONSTANTS
# =============================================================================

# Terminal display width
STATUS_DISPLAY_WIDTH = 60

# Temperature thresholds (Celsius)
CPU_TEMPERATURE_HOT_THRESHOLD = 70
CPU_TEMPERATURE_WARM_THRESHOLD = 60

# Memory usage thresholds (percentage)
MEMORY_CRITICAL_THRESHOLD_PERCENT = 90
MEMORY_HIGH_THRESHOLD_PERCENT = 75
