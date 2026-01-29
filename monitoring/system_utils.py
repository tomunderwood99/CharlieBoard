"""Shared system utilities for monitoring and formatting."""
import subprocess
import logging
from typing import Dict, Optional
from datetime import timedelta

logger = logging.getLogger(__name__)


def get_memory_usage() -> Optional[Dict]:
    """Get memory usage statistics.
    
    Returns:
        Dictionary with memory stats or None if unavailable
    """
    try:
        result = subprocess.run(['free', '-m'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        memory = lines[1].split()
        
        # Calculate percentage used
        total = int(memory[1])
        used = int(memory[2])
        free = int(memory[3])
        percent_used = round((used / total) * 100, 1) if total > 0 else 0
        
        return {
            'total_mb': total,
            'used_mb': used,
            'free_mb': free,
            'percent_used': percent_used
        }
    except Exception as e:
        logger.debug(f"Failed to get memory usage: {e}")
        return None


def get_cpu_temperature() -> Optional[float]:
    """Get CPU temperature (Raspberry Pi specific).
    
    Returns:
        Temperature in Celsius or None if unavailable
    """
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
            return round(temp, 1)
    except Exception as e:
        logger.debug(f"Failed to get CPU temperature: {e}")
        return None


def format_uptime(seconds: int) -> str:
    """Format uptime in human-readable format.
    
    Args:
        seconds: Uptime in seconds
        
    Returns:
        Human-readable uptime string (e.g., "2d 5h 30m")
    """
    if seconds <= 0:
        return "Unknown"
    
    uptime = timedelta(seconds=seconds)
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m {secs}s"

