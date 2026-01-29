#!/usr/bin/env python3
"""
MBTA LED Controller Status Checker
Quick command to check system status and display information
"""

import sys
import os
import json
import time
from datetime import datetime

def get_project_root():
    """Get the project root directory based on this script's location."""
    # This script is in runtime/status_check.py, so go up one level to get project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    return project_root

# Add project root to path for imports
_project_root = get_project_root()
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from monitoring.system_utils import format_uptime
from config.constants import (
    METRICS_FILE_MAX_AGE_SECONDS,
    STATUS_DISPLAY_WIDTH,
    CPU_TEMPERATURE_HOT_THRESHOLD,
    CPU_TEMPERATURE_WARM_THRESHOLD,
    MEMORY_CRITICAL_THRESHOLD_PERCENT,
    MEMORY_HIGH_THRESHOLD_PERCENT,
)


def get_ascii_art():
    """Return the specified ASCII art."""
    return ""

def get_system_status():
    """Get current system status from metrics file directly."""
    try:
        project_root = get_project_root()
        
        # Read metrics file directly to avoid import issues
        metrics_file = os.path.join(project_root, 'logs', 'metrics.json')
        if not os.path.exists(metrics_file):
            return {
                'error': 'Metrics file not found - system may not be running',
                'healthy': False,
                'active_vehicles': 0,
                'display_mode': 'unknown',
                'uptime': 0
            }
        
        # Check if metrics file is stale (older than 2 minutes)
        file_age = time.time() - os.path.getmtime(metrics_file)
        metrics_stale = file_age > METRICS_FILE_MAX_AGE_SECONDS  # 2 minutes
        
        with open(metrics_file, 'r') as f:
            metrics_data = json.load(f)
        
        # Extract relevant information
        health_status = metrics_data.get('health', {})
        performance_metrics = metrics_data.get('performance', {})
        
        # Get current settings from .env file
        current_mode = 'unknown'
        last_settings_mod = 'unknown'
        env_file = os.path.join(project_root, '.env')
        if os.path.exists(env_file):
            try:
                # Get last modification time
                last_mod_time = os.path.getmtime(env_file)
                last_settings_mod = datetime.fromtimestamp(last_mod_time).strftime('%Y-%m-%d %H:%M:%S')
                
                # Read display mode
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('DISPLAY_MODE='):
                            current_mode = line.split('=', 1)[1].strip('"\'')
                            break
            except:
                pass
        
        return {
            'healthy': health_status.get('healthy', False),
            'active_vehicles': health_status.get('active_vehicles', 0),
            'display_mode': current_mode,
            'session_uptime': health_status.get('session_uptime_seconds', 0),
            'total_uptime': health_status.get('total_uptime_seconds', 0),
            'session_start_time': health_status.get('session_start_time', 'unknown'),
            'first_start_time': health_status.get('first_start_time', 'unknown'),
            'last_led_update': health_status.get('last_led_update', 'unknown'),
            'last_settings_mod': last_settings_mod,
            'api_healthy': health_status.get('api_healthy', False),
            'led_healthy': health_status.get('led_healthy', False),
            'metrics_stale': metrics_stale,
            'metrics_age_seconds': int(file_age),
            'memory_usage': health_status.get('memory_usage'),
            'cpu_temperature': health_status.get('cpu_temperature')
        }
    except Exception as e:
        return {
            'error': str(e),
            'healthy': False,
            'active_vehicles': 0,
            'display_mode': 'unknown',
            'session_uptime': 0,
            'total_uptime': 0
        }

def print_status():
    """Print the complete status information."""
    # Print ASCII art first
    print(get_ascii_art())
    print()
    
    # Get system status
    status = get_system_status()
    
    # Print status header
    print("=" * STATUS_DISPLAY_WIDTH)
    print("           MBTA LED CONTROLLER STATUS")
    print("=" * STATUS_DISPLAY_WIDTH)
    print()
    
    # Check for errors
    if 'error' in status:
        print(f"❌ ERROR: {status['error']}")
        print()
        return
    
    # Check for stale metrics and warn user
    if status.get('metrics_stale', False):
        print(f"⚠️  WARNING: Metrics file is stale ({status.get('metrics_age_seconds', 0)}s old)")
        print(f"⚠️  Display controller may not be running. Data below may be outdated.")
        print()
    
    # Print health status
    health_icon = "✅" if status['healthy'] else "❌"
    health_text = "HEALTHY" if status['healthy'] else "UNHEALTHY"
    print(f"{health_icon} System Status: {health_text}")
    
    # Print vehicle count and mode
    vehicle_icon = "🚇" if status['active_vehicles'] > 0 else "🚫"
    print(f"{vehicle_icon} Active Vehicles: {status['active_vehicles']}")
    print(f"🎭 Display Mode: {status['display_mode'].upper()}")
    
    # Print uptime
    session_uptime_text = format_uptime(status['session_uptime'])
    total_uptime_text = format_uptime(status['total_uptime'])
    print(f"⏱️  Session Uptime: {session_uptime_text} (since last reboot)")
    print(f"📅 Total Uptime: {total_uptime_text} (since first deployment)")
    
    # Print component health
    api_icon = "✅" if status['api_healthy'] else "❌"
    led_icon = "✅" if status['led_healthy'] else "❌"
    print(f"{api_icon} API Health: {'HEALTHY' if status['api_healthy'] else 'UNHEALTHY'}")
    print(f"{led_icon} LED Health: {'HEALTHY' if status['led_healthy'] else 'UNHEALTHY'}")
    
    # Print system resources
    print()
    print("System Resources:")
    
    # Memory usage
    memory = status.get('memory_usage')
    if memory and memory is not None:
        memory_icon = "💾"
        percent = memory.get('percent_used', 0)
        # Color code based on usage
        if percent > MEMORY_CRITICAL_THRESHOLD_PERCENT:
            memory_status = "⚠️  CRITICAL"
        elif percent > MEMORY_HIGH_THRESHOLD_PERCENT:
            memory_status = "⚠️  HIGH"
        else:
            memory_status = "✅"
        print(f"{memory_icon} Memory: {memory.get('used_mb', 'N/A')}MB / {memory.get('total_mb', 'N/A')}MB ({percent}%) {memory_status}")
    else:
        print(f"💾 Memory: Not available")
    
    # CPU temperature
    temp = status.get('cpu_temperature')
    if temp is not None:
        temp_icon = "🌡️"
        # Color code based on temperature
        if temp > CPU_TEMPERATURE_HOT_THRESHOLD:
            temp_status = "⚠️  HOT"
        elif temp > CPU_TEMPERATURE_WARM_THRESHOLD:
            temp_status = "⚠️  WARM"
        else:
            temp_status = "✅"
        print(f"{temp_icon} CPU Temperature: {temp}°C {temp_status}")
    else:
        print(f"🌡️  CPU Temperature: Not available")
    
    # Print timestamps section
    print()
    print("Timestamps:")
    
    # Print last update time
    if status['last_led_update'] != 'unknown':
        try:
            # Parse ISO timestamp and format like settings timestamp
            led_timestamp = datetime.fromisoformat(status['last_led_update'].replace('Z', '+00:00'))
            formatted_led_time = led_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            print(f"🔄 Last LED Update: {formatted_led_time}")
        except:
            # Fallback to original format if parsing fails
            print(f"🔄 Last LED Update: {status['last_led_update']}")
    
    # Print last settings modification
    if status['last_settings_mod'] != 'unknown':
        print(f"⚙️  Last Settings Change: {status['last_settings_mod']}")
    
    # Print start times
    if status.get('session_start_time') != 'unknown':
        try:
            session_start = datetime.fromisoformat(status['session_start_time'].replace('Z', '+00:00'))
            print(f"🔄 Session Started: {session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            pass
    
    if status.get('first_start_time') != 'unknown':
        try:
            first_start = datetime.fromisoformat(status['first_start_time'].replace('Z', '+00:00'))
            print(f"🚀 First Deployed: {first_start.strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            pass
    
    print()
    print("=" * STATUS_DISPLAY_WIDTH)

def main():
    """Main function."""
    try:
        print_status()
    except KeyboardInterrupt:
        print("\nStatus check interrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"Error during status check: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
