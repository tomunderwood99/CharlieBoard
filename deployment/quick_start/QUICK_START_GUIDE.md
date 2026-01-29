# Quick Start Guide

Get your MBTA LED display running in under 10 minutes with the automated setup script.

## Prerequisites

1. Raspberry Pi with Raspberry Pi OS installed and booted
2. WiFi/network configured
3. SSH access to your Pi
4. Hardware connected (WS2812B LEDs, 5V power supply, common ground)

---

## Installation

### Step 1: Clone Repository

```bash
sudo apt update && sudo apt install -y git python3-pip
cd ~
git clone https://github.com/tomunderwood99/CharlieBoard.git
cd mbta_led_controller

# Optional: Remove hardware folder to save space
rm -rf hardware/
echo "hardware/" >> .git/info/exclude
```

### Step 2: Run Setup Script

```bash
chmod +x deployment/quick_start/setup_mbta_controller.sh
sudo ./deployment/quick_start/setup_mbta_controller.sh
```

### Step 3: Answer Prompts

| Prompt | Required | Default | Notes |
|--------|----------|---------|-------|
| MBTA API Key | Yes | — | Free at [api-v3.mbta.com](https://api-v3.mbta.com/) |
| Line | No | Red | Red, Blue, Orange, or Green |
| Timezone | No | Eastern | Select from menu |
| Bedtime Start/End | No | 22:00/06:00 | Auto-off hours |
| Brightness | No | 0.5 | 0.0–1.0 |
| LED Test | No | Yes | Tests hardware |
| Start Services | No | Yes | Start immediately |

### Step 4: Done!

Access web interface at `http://your-hostname.local:8000`

### Optional Enhancements

**Raspberry Pi Connect** – Secure remote access from anywhere via web browser:
```bash
sudo apt install rpi-connect
rpi-connect signin
```
Then access your Pi at [connect.raspberrypi.com](https://connect.raspberrypi.com). See [official docs](https://www.raspberrypi.com/documentation/services/connect.html).

**nginx Reverse Proxy** – Access at `http://hostname.local` without the port number. See [nginx setup guide](../../docs/nginx_reverse_proxy_setup.md).

---

## What the Script Does

1. Updates system and installs packages
2. Creates Python virtual environment
3. Installs dependencies
4. Creates `.env` configuration
5. Configures and installs systemd services
6. Sets up convenience commands (`display_status`, `display_reboot`)
7. Optionally tests LED hardware

---

## After Setup

### Quick Commands

```bash
source ~/.bashrc        # Load aliases (first time)
display_status          # Check system status
display_reboot          # Restart services
```

### Service Management

```bash
sudo systemctl status mbta_display.service
sudo systemctl restart mbta_display.service
sudo journalctl -u mbta_display -f    # Live logs
```

### Change Configuration

Use the web interface (easiest) or edit directly:
```bash
nano ~/mbta_led_controller/.env
sudo systemctl restart mbta_display.service
```

---

## Troubleshooting

For detailed troubleshooting, see [Operations & Troubleshooting](../../docs/operations_and_troubleshooting.md).

### Quick Checks

| Issue | Command |
|-------|---------|
| LED test | `sudo -E venv/bin/python tests/red_test.py` |
| Service status | `sudo systemctl status mbta_display.service` |
| View logs | `sudo journalctl -u mbta_display -n 100` |
| Find IP | `hostname -I` |
| Test API | `curl "https://api-v3.mbta.com/vehicles?api_key=YOUR_KEY"` |

### Common Issues
- **LEDs don't light**: Check wiring (GPIO 18, common ground)
- **Service won't start**: Check `.env` exists and API key is valid
- **Can't access web**: Try IP address instead of hostname

---

## What Gets Installed

### System Packages
- python3, python3-pip, python3-venv, python3-dev, git

### Python Packages (in venv)
- Flask, requests, sseclient, rpi-ws281x, adafruit-blinka, adafruit-circuitpython-neopixel, pytz

### Systemd Services
- `mbta_display.service` - Main display and web interface
- `mbta_monitor.service` - Health monitoring (auto-restarts main service)
- `daily_reboot.timer` - Daily 3 AM reboot for stability

### Files Created
- `~/mbta_led_controller/.env` - Configuration
- `~/mbta_led_controller/venv/` - Python environment
- `~/mbta_led_controller/logs/` - Application logs

---

## For Developers: Script Architecture

### Design Philosophy

Only 3 critical inputs required:
1. **MBTA API Key** - Cannot function without
2. **Line** - Which line to display (default: Red)
3. **Timezone** - For scheduling (default: Eastern)

All other settings have defaults and can be changed via web interface.

### Path Detection

```bash
ACTUAL_USER=${SUDO_USER:-$USER}
PROJECT_DIR=$(pwd)
VENV_PATH="$PROJECT_DIR/venv"
```

Service files updated dynamically via `sed`:
```bash
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" deployment/systemd/*.service
```

### Why sudo Required
- Installs system packages
- Modifies timezone
- Copies files to `/etc/systemd/system/`
- Services need GPIO access

### Customization Points
- **Venv name**: Modify `VENV_NAME` variable
- **Defaults**: Change `${VAR:-default}` patterns
- **Validation**: Enhance with regex/pattern matching

---

## Additional Resources

- [Complete Setup Guide](../../docs/complete_setup_guide.md) - Manual setup
- [Operations & Troubleshooting](../../docs/operations_and_troubleshooting.md)
- [Hardware Assembly](../../docs/hardware_assembly_guide.md)
- [MBTA API Docs](https://api-v3.mbta.com/)
- [GPIO Pinout](https://pinout.xyz/)
