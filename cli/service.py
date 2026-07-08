"""Systemd service control for CharlieBoard."""
import subprocess
import sys

_DISPLAY_SERVICE = 'mbta_display.service'
_MONITOR_SERVICE = 'mbta_monitor.service'


def restart_display_services() -> bool:
    """Restart display and monitor services (same as display_reboot alias).
    
    Returns:
        True if both services restarted successfully, False otherwise
    """
    commands = [
        ['systemctl', 'restart', _DISPLAY_SERVICE],
        ['systemctl', 'restart', _MONITOR_SERVICE],
    ]
    
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip() or result.stdout.strip()
                print(
                    f"Failed to run {' '.join(cmd)}: {stderr}",
                    file=sys.stderr,
                )
                print(
                    "Route was saved. Restart manually with: "
                    "sudo systemctl restart mbta_display.service "
                    "&& sudo systemctl restart mbta_monitor.service",
                    file=sys.stderr,
                )
                return False
        except FileNotFoundError:
            print(
                "systemctl not found. Route was saved; restart services manually.",
                file=sys.stderr,
            )
            return False
        except PermissionError:
            print(
                "Permission denied restarting services. Try: "
                f"sudo systemctl restart {_DISPLAY_SERVICE}",
                file=sys.stderr,
            )
            return False
    
    print("Services restarted successfully.")
    return True
