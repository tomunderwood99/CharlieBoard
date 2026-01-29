#!/usr/bin/env python3
import subprocess
import sys
import os
import signal
import time
import logging
import traceback
import json
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

# Add project root to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from config.constants import (
    LOG_FILE_MAX_BYTES,
    LOG_FILE_BACKUP_COUNT,
    MAX_REBOOTS,
    REBOOT_DELAY_SECONDS,
    REBOOT_WINDOW_HOURS,
    DEFAULT_LED_COUNT,
    LED_COUNT_ADJUSTMENT,
    SAFE_MODE_BRIGHTNESS,
    SAFE_MODE_COLOR,
    SAFE_MODE_REFRESH_INTERVAL_SECONDS,
    WEB_INTERFACE_STARTUP_DELAY_SECONDS,
    LED_CONTROLLER_STARTUP_DELAY_SECONDS,
    PROCESS_TERMINATE_TIMEOUT_SECONDS,
    MONITOR_LOOP_INTERVAL_SECONDS,
)

# Configure logging
# Note: No StreamHandler - when running via systemd, stdout is captured by journalctl
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'logs/startup.log',
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)

# Reboot loop protection file path
REBOOT_COUNTER_FILE = 'logs/reboot_counter.json'


def get_reboot_count() -> int:
    """Get the current reboot count from the counter file.
    
    Returns:
        int: Number of reboots within the time window, or 0 if counter is stale/missing
    """
    try:
        if not os.path.exists(REBOOT_COUNTER_FILE):
            return 0
        
        with open(REBOOT_COUNTER_FILE, 'r') as f:
            data = json.load(f)
        
        # Check if the counter is within the time window
        last_reboot_time = datetime.fromisoformat(data.get('last_reboot_time', ''))
        if datetime.now() - last_reboot_time > timedelta(hours=REBOOT_WINDOW_HOURS):
            # Counter is stale, reset it
            logger.info(f"Reboot counter expired (last reboot was {last_reboot_time}), resetting to 0")
            reset_reboot_count()
            return 0
        
        return data.get('count', 0)
    except Exception as e:
        logger.warning(f"Failed to read reboot counter: {e}")
        return 0


def increment_reboot_count() -> int:
    """Increment the reboot counter and return the new count.
    
    Returns:
        int: The new reboot count after incrementing
    """
    try:
        current_count = get_reboot_count()
        new_count = current_count + 1
        
        data = {
            'count': new_count,
            'last_reboot_time': datetime.now().isoformat()
        }
        
        with open(REBOOT_COUNTER_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Reboot counter incremented to {new_count}/{MAX_REBOOTS}")
        return new_count
    except Exception as e:
        logger.error(f"Failed to increment reboot counter: {e}")
        return MAX_REBOOTS + 1  # Return high value to trigger safe mode on error


def reset_reboot_count() -> None:
    """Reset the reboot counter to 0."""
    try:
        if os.path.exists(REBOOT_COUNTER_FILE):
            os.remove(REBOOT_COUNTER_FILE)
            logger.info("Reboot counter reset")
    except Exception as e:
        logger.warning(f"Failed to reset reboot counter: {e}")


def set_leds_blue_fallback() -> None:
    """Set all LEDs to blue as a fallback when max reboots reached.
    
    This function attempts to directly control the LEDs without going through
    the full application stack, as a visual indicator that safe mode is active.
    """
    try:
        import board
        import neopixel
        
        # Try to determine LED count from config, fallback to reasonable default
        led_count = DEFAULT_LED_COUNT  # Default fallback
        try:
            from config.station_led_maps import station_led_maps
            # Get LED count from Red line as default
            outbound_map, inbound_map = station_led_maps.get('Red', (lambda: ({}, {})))()
            if outbound_map or inbound_map:
                led_count = max(
                    max(outbound_map.values()) if outbound_map else 0,
                    max(inbound_map.values()) if inbound_map else 0
                ) + LED_COUNT_ADJUSTMENT  # +1 for 0-indexing, +3 for color key
        except Exception:
            pass  # Use default LED count
        
        logger.info(f"Setting {led_count} LEDs to blue (safe mode indicator)")
        
        pixels = neopixel.NeoPixel(
            board.D18,
            led_count,
            brightness=SAFE_MODE_BRIGHTNESS,  # Lower brightness for safe mode
            auto_write=False,
            pixel_order=neopixel.GRB
        )
        
        # Set all LEDs to blue
        pixels.fill(SAFE_MODE_COLOR)
        pixels.show()
        
        logger.info("LEDs set to blue successfully")
    except Exception as e:
        logger.error(f"Failed to set LEDs to blue: {e}")


def safe_mode_wait() -> None:
    """Enter safe mode: set LEDs blue and wait indefinitely.
    
    This prevents reboot loops by stopping all restart attempts and
    providing a visual indicator (blue LEDs) that intervention is needed.
    """
    logger.critical(f"SAFE MODE: Maximum reboots ({MAX_REBOOTS}) reached within {REBOOT_WINDOW_HOURS} hour(s)")
    logger.critical("System is in safe mode. Manual intervention required.")
    logger.critical("To exit safe mode: 1) Fix the issue, 2) Delete logs/reboot_counter.json, 3) Reboot manually")
    
    set_leds_blue_fallback()
    
    # Wait indefinitely - system will stay in this state until manual intervention
    logger.info("Entering infinite wait. System requires manual reboot after fixing the issue.")
    while True:
        time.sleep(SAFE_MODE_REFRESH_INTERVAL_SECONDS)
        # Periodically refresh the blue LEDs in case they reset
        set_leds_blue_fallback()


def log_detailed_error(name: str, process, error: Exception = None) -> None:
    """Log detailed error information including process output and stack trace."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_log_path = f'logs/error_{timestamp}.log'
        
        with open(error_log_path, 'w') as f:
            # Write error header
            f.write(f"=== Error Report for {name} ===\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Process: {name}\n")
            if process:
                f.write(f"PID: {process.pid}\n")
                f.write(f"Return Code: {process.poll()}\n\n")
            
            # Write exception info if available
            if error:
                f.write("=== Exception Details ===\n")
                f.write(f"Error Type: {type(error).__name__}\n")
                f.write(f"Error Message: {str(error)}\n")
                f.write("Stack Trace:\n")
                f.write(traceback.format_exc())
                f.write("\n")
            
            # Write process output
            if process:
                f.write("=== Process Output ===\n")
                f.write("STDOUT:\n")
                stdout, stderr = process.communicate()
                if stdout:
                    f.write(stdout)
                f.write("\nSTDERR:\n")
                if stderr:
                    f.write(stderr)
        
        logger.error(f"Detailed error log written to {error_log_path}")
    except Exception as e:
        logger.error(f"Failed to write detailed error log: {e}")

def system_reboot() -> bool:
    """Initiate system reboot with loop protection.
    
    Checks the reboot counter before rebooting. If max reboots reached,
    enters safe mode instead.
    
    Returns:
        bool: True if reboot was initiated, False if safe mode was entered
    """
    # Check reboot counter first
    reboot_count = increment_reboot_count()
    
    if reboot_count > MAX_REBOOTS:
        logger.warning(f"Reboot count ({reboot_count}) exceeds maximum ({MAX_REBOOTS})")
        safe_mode_wait()
        return False  # Will never reach here due to infinite loop in safe_mode_wait
    
    # Delay before reboot to prevent rapid reboot loops
    logger.info(f"Waiting {REBOOT_DELAY_SECONDS} seconds before reboot (attempt {reboot_count}/{MAX_REBOOTS})...")
    time.sleep(REBOOT_DELAY_SECONDS)
    
    try:
        logger.info("Initiating system reboot...")
        # Check if running as root
        if os.geteuid() == 0:
            subprocess.run(['shutdown', '-r', 'now'], check=True)
        else:
            subprocess.run(['sudo', 'shutdown', '-r', 'now'], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to initiate reboot: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during reboot: {e}")
        return False

def start_process(command, name):
    """Start a process and return its subprocess.Popen object."""
    try:
        # Get the directory of the current script and its parent
        startup_script_dir = os.path.dirname(os.path.abspath(__file__))
        startup_project_dir = os.path.dirname(startup_script_dir)
        
        # Start the process
        process = subprocess.Popen(
            command,
            cwd=startup_project_dir,  # Run from project root directory
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,  # Line buffered
            # Add these for better process management
            preexec_fn=os.setsid,  # Create new process group
            close_fds=True
        )
        
        logger.info(f"Started {name} (PID: {process.pid})")
        return process
    except Exception as e:
        logger.error(f"Failed to start {name}: {e}")
        log_detailed_error(name, None, e)
        return None

def monitor_output(process, name, quiet_mode=False):
    """Monitor a process's output in a non-blocking way."""
    try:
        # Use non-blocking reads with timeout
        import select
        
        # Check stdout
        if process.stdout and select.select([process.stdout], [], [], 0.0)[0]:
            line = process.stdout.readline()
            if line:
                # In quiet mode, only log important messages
                if not quiet_mode or any(keyword in line.lower() for keyword in ['error', 'warning', 'critical', 'failed', 'exception']):
                    logger.info(f"{name} output: {line.strip()}")
        
        # Check stderr
        if process.stderr and select.select([process.stderr], [], [], 0.0)[0]:
            line = process.stderr.readline()
            if line:
                # Filter out routine INFO messages that aren't actual errors
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in ['error', 'warning', 'critical', 'failed', 'exception', 'traceback']):
                    logger.error(f"{name} error: {line.strip()}")
                elif any(keyword in line_lower for keyword in ['settings loaded successfully', 'settings saved successfully', 'settings file modified', 'forcing settings reload', 'updated bedtime']):
                    # These are routine INFO messages, not errors - log at debug level or skip
                    if not quiet_mode:
                        logger.debug(f"{name} info: {line.strip()}")
                elif any(keyword in line_lower for keyword in ['serving flask app', 'development server', 'production deployment', 'werkzeug', 'flask']):
                    # These are Flask startup messages, not errors - log at debug level or skip
                    if not quiet_mode:
                        logger.debug(f"{name} flask: {line.strip()}")
                else:
                    # Other stderr messages - log as warnings in case they're important
                    if not quiet_mode:
                        logger.warning(f"{name} stderr: {line.strip()}")
    except Exception as e:
        logger.warning(f"Error monitoring {name} output: {e}")

def check_process_health(process, name):
    """Check if a process is healthy without blocking."""
    if process.poll() is not None:
        return False, f"Process {name} has stopped (return code: {process.poll()})"
    
    # Check if process is responsive by sending a signal 0
    try:
        os.kill(process.pid, 0)
        return True, None
    except OSError:
        return False, f"Process {name} is not responding"

def cleanup_processes(processes):
    """Cleanup processes on shutdown."""
    for name, process in processes.items():
        if process and process.poll() is None:  # If process is still running
            logger.info(f"Stopping {name}...")
            process.terminate()
            try:
                process.wait(timeout=PROCESS_TERMINATE_TIMEOUT_SECONDS)  # Wait up to 5 seconds
            except subprocess.TimeoutExpired:
                logger.warning(f"{name} didn't terminate, forcing...")
                process.kill()  # Force kill if it doesn't terminate
            logger.info(f"Stopped {name}")

def main():
    """Main function to start and monitor all processes."""
    processes = {}
    startup_complete = False
    
    try:
        # Start web interface
        web_process = start_process(
            [sys.executable, 'web_interface/app.py'],
            'Web Interface'
        )
        if web_process:
            processes['Web Interface'] = web_process
        else:
            raise Exception("Failed to start Web Interface")
        
        # Give web interface a moment to start
        time.sleep(WEB_INTERFACE_STARTUP_DELAY_SECONDS)
        
        # Start LED controller
        controller_process = start_process(
            [sys.executable, 'main/mbta_stream.py'],
            'LED Controller'
        )
        if controller_process:
            processes['LED Controller'] = controller_process
        else:
            raise Exception("Failed to start LED Controller")
        
        # Wait a bit more for initial startup messages
        time.sleep(LED_CONTROLLER_STARTUP_DELAY_SECONDS)
        
        # Mark startup as complete and start quiet mode
        startup_complete = True
        logger.info("Startup complete - entering quiet mode (only errors and warnings will be logged)")
        
        # Reset reboot counter after successful startup
        # This indicates the system is stable and any previous issues are resolved
        reset_reboot_count()
        
        # Monitor processes
        while True:
            # Check if either process has ended
            for name, process in processes.items():
                # Use the new health check function
                is_healthy, error_msg = check_process_health(process, name)
                if not is_healthy:
                    logger.error(error_msg)
                    log_detailed_error(name, process)
                    cleanup_processes(processes)
                    logger.info("Initiating system reboot...")
                    system_reboot()
                    sys.exit(1)  # Exit in case reboot fails
                
                # Monitor output (non-blocking) - use quiet mode after startup
                monitor_output(process, name, quiet_mode=startup_complete)
            
            time.sleep(MONITOR_LOOP_INTERVAL_SECONDS)  # Check every second instead of every 0.1 seconds
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal...")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        # Log detailed error for the failed process
        for name, process in processes.items():
            if process.poll() is not None:
                log_detailed_error(name, process, e)
        cleanup_processes(processes)
        logger.info("Initiating system reboot...")
        system_reboot()
        sys.exit(1)  # Exit in case reboot fails
    finally:
        cleanup_processes(processes)
        logger.info("Shutdown complete")

if __name__ == "__main__":
    # Handle SIGTERM gracefully
    signal.signal(signal.SIGTERM, lambda signo, frame: sys.exit(0))
    main() 
