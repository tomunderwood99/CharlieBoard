# Complete Setup Guide

This guide walks through setting up **CharlieBoard** on a fresh Raspberry Pi Zero 2W manually. For most users, the [Quick Start Guide](../deployment/quick_start/QUICK_START_GUIDE.md) or the automated installer (below) is faster.

**Automated setup (recommended):** From the repository root on the Pi, run:

```bash
cd ~/CharlieBoard   # or your clone directory
chmod +x deployment/quick_start/setup_mbta_controller.sh
sudo ./deployment/quick_start/setup_mbta_controller.sh
```

That script performs the same stages as this document: system packages, timezone, virtualenv, `pip install -e .`, `.env` creation, systemd unit path patching, log directory, service install, optional LED test, and `display_status` / `display_reboot` aliases in `~/.bashrc`. Use this guide if you need to install or debug step by step.

**Note:** This covers software setup only. For hardware assembly, see the [Hardware Assembly Guide](hardware_assembly_guide.md) first.

## Table of Contents

1. [Prepare Your Raspberry Pi](#step-1-prepare-your-raspberry-pi)
2. [System Update and Core Tools](#step-2-system-update-and-core-tools)
3. [Clone the Repository](#step-3-clone-the-repository)
4. [Configure Timezone](#step-4-configure-timezone)
5. [Set Up Python Environment](#step-5-set-up-python-environment)
6. [Install Dependencies](#step-6-install-dependencies)
7. [Set Up Raspberry Pi Connect (Optional)](#step-7-set-up-raspberry-pi-connect-optional)
8. [Create Configuration File](#step-8-create-configuration-file)
9. [Configure LED Mappings (Optional)](#step-9-configure-led-mappings-optional)
10. [Test LED Hardware](#step-10-test-led-hardware)
11. [Test Full Application](#step-11-test-full-application)
12. [Patch Paths in Systemd Unit Files](#step-12-patch-paths-in-systemd-unit-files)
13. [Install and Enable Services](#step-13-install-and-enable-services)
14. [Verify Services](#step-14-verify-services)
15. [Set Up Convenience Aliases (Optional)](#step-15-set-up-convenience-aliases-optional)
16. [Access Web Interface](#step-16-access-web-interface)

## Step 1: Prepare Your Raspberry Pi

1. **Flash Raspberry Pi OS** using [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   - Choose **Raspberry Pi OS Lite (64-bit)**
   - Configure WiFi and SSH in imager settings
   - Set hostname (e.g., `mbta-display`)
   - Set username and password

2. **Connect via SSH:**
   ```bash
   ssh pi@mbta-display.local
   # or: ssh pi@192.168.1.xxx
   ```

## Step 2: System Update and Core Tools

The automated installer runs `apt-get update` and installs the packages below (it does not run a full `dist-upgrade`). Match that set for manual setup:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev git
# Optional but recommended for a new image:
# sudo apt upgrade -y
```

Verify:

```bash
git --version && python3 --version
```

Python 3.7+ is required (`timedatectl` and `systemctl` are expected on Raspberry Pi OS).

## Step 3: Clone the Repository

```bash
cd ~
git clone https://github.com/tomunderwood99/CharlieBoard.git
cd CharlieBoard

# Optional: Remove hardware folder to save space
rm -rf hardware/
echo "hardware/" >> .git/info/exclude
```

The installer expects to be run from the directory that contains `runtime/startup.py` and `setup.py` (repository root).

## Step 4: Configure Timezone

The setup script configures timezone **before** creating the virtualenv. Set yours explicitly:

```bash
sudo timedatectl set-timezone America/New_York
timedatectl
```

Other US examples: `America/Chicago`, `America/Denver`, `America/Los_Angeles`.

## Step 5: Set Up Python Environment

```bash
cd ~/CharlieBoard
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Verify: should show .../CharlieBoard/venv/bin/python (path depends on user and clone location)
which python
```

The installer creates the venv as your normal user (`SUDO_USER`), not as root.

## Step 6: Install Dependencies

```bash
pip install -e .
```

Verify key packages:

```bash
pip list | grep -E "Flask|neopixel|rpi-ws281x"
```

If installation fails, the installer suggests:

```bash
sudo apt install -y build-essential python3-dev
# For some rpi_ws281x build issues:
sudo apt install -y scons swig
```

Then retry `pip install -e .` (or `pip install -e . -v` for verbose output).

## Step 7: Set Up Raspberry Pi Connect (Optional but Recommended)

[Raspberry Pi Connect](https://www.raspberrypi.com/documentation/services/connect.html) provides secure remote access via web browser—no port forwarding or VPN needed. Manage your display from anywhere.

```bash
sudo apt install rpi-connect
rpi-connect signin
```

Visit the displayed URL to complete sign-in with your [Raspberry Pi ID](https://id.raspberrypi.com). After setup, access your Pi at [connect.raspberrypi.com](https://connect.raspberrypi.com).

## Step 8: Create Configuration File

Create `.env` in the project root (`~/CharlieBoard/.env`). The installer writes this template (adjust values as needed):

```bash
nano .env
```

Contents (same fields as the setup script):

```bash
# CharlieBoard / MBTA configuration

MBTA_API_KEY=your_api_key_here

# Display settings
ROUTE=Red
BRIGHTNESS=0.5
POWER_SWITCH=on
BEDTIME_START=22:00
BEDTIME_END=06:00
DISPLAY_MODE=vehicles

# Color settings (RGB values)
STOPPED_COLOR=[255, 0, 0]
INCOMING_COLOR=[255, 75, 75]
TRANSIT_COLOR=[150, 150, 150]
MIN_SPEED_COLOR=[0, 255, 0]
MAX_SPEED_COLOR=[255, 0, 0]
NULL_SPEED_COLOR=[0, 0, 255]
MIN_OCCUPANCY_COLOR=[0, 255, 0]
MAX_OCCUPANCY_COLOR=[255, 0, 0]
NULL_OCCUPANCY_COLOR=[0, 0, 255]

# Debug settings
SHOW_DEBUGGER_OPTIONS=false
DEBUGGER=[]
```

Get a free API key at [api-v3.mbta.com](https://api-v3.mbta.com/). For `ROUTE`, the installer offers Red, Blue, Orange, Green-All, Green-B, Green-C, Green-D, and Green-E.

## Step 9: Configure LED Mappings (Optional)

If customizing LED positions:

```bash
nano config/station_led_maps.py
nano config/station_id_maps.py
```

## Step 10: Test LED Hardware

```bash
cd ~/CharlieBoard
source venv/bin/activate

# Edit LED_COUNT in test script if needed
nano tests/red_test.py

# Run test (requires sudo for GPIO)
sudo -E venv/bin/python tests/red_test.py
```

All LEDs should turn red. Press Ctrl+C to exit.

**If LEDs don't light up**, check:

- Data wire → GPIO 18 (physical pin 12)
- Ground shared between Pi and LED power supply
- LEDs have adequate 5V power

## Step 11: Test Full Application

```bash
cd ~/CharlieBoard
source venv/bin/activate
sudo venv/bin/python runtime/startup.py
```

This starts the web interface (port 8000) and LED controller. Verify at `http://mbta-display.local:8000` (or `/$(hostname).local:8000`).

Press Ctrl+C to stop.

## Step 12: Patch Paths in Systemd Unit Files

Checked-in unit files under `deployment/systemd/` use placeholder paths. The installer **`sed`-replaces** them so `WorkingDirectory`, `Environment=PROJECT_ROOT`, `Environment=VENV_PATH`, `ExecStart` (and the `daily_reboot` log line) point at your clone. From the repository root, run the same substitutions (adjust directory if your clone is not `~/CharlieBoard`):

```bash
cd ~/CharlieBoard
PROJECT_DIR="$(pwd)"
VENV_PATH="$PROJECT_DIR/venv"

sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" deployment/systemd/mbta_display.service
sed -i "s|Environment=PROJECT_ROOT=.*|Environment=PROJECT_ROOT=$PROJECT_DIR|g" deployment/systemd/mbta_display.service
sed -i "s|Environment=VENV_PATH=.*|Environment=VENV_PATH=$VENV_PATH|g" deployment/systemd/mbta_display.service
sed -i "s|ExecStart=.*|ExecStart=$VENV_PATH/bin/python $PROJECT_DIR/runtime/startup.py|g" deployment/systemd/mbta_display.service

sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" deployment/systemd/mbta_monitor.service
sed -i "s|Environment=PROJECT_ROOT=.*|Environment=PROJECT_ROOT=$PROJECT_DIR|g" deployment/systemd/mbta_monitor.service
sed -i "s|Environment=VENV_PATH=.*|Environment=VENV_PATH=$VENV_PATH|g" deployment/systemd/mbta_monitor.service
sed -i "s|ExecStart=.*|ExecStart=$VENV_PATH/bin/python -u $PROJECT_DIR/monitoring/health_monitor.py|g" deployment/systemd/mbta_monitor.service

sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" deployment/systemd/daily_reboot.service
sed -i "s|ExecStartPre=.*|ExecStartPre=/bin/sh -c 'echo \"\$(date): Initiating scheduled daily reboot\" >> $PROJECT_DIR/logs/daily_reboot.log'|g" deployment/systemd/daily_reboot.service
```

If you prefer editing by hand, ensure those fields match your `PROJECT_DIR` and `VENV_PATH`. The monitor unit keeps `ExecStartPre=/bin/sleep 15` as in the template.

## Step 13: Install and Enable Services

```bash
cd ~/CharlieBoard
mkdir -p logs

sudo cp deployment/systemd/mbta_display.service /etc/systemd/system/
sudo cp deployment/systemd/mbta_monitor.service /etc/systemd/system/
sudo cp deployment/systemd/daily_reboot.service /etc/systemd/system/
sudo cp deployment/systemd/daily_reboot.timer /etc/systemd/system/

sudo systemctl daemon-reload
```

Enable **the timer** for scheduled reboots (do not enable `daily_reboot.service` directly—it is triggered by the timer), matching the installer:

```bash
sudo systemctl enable mbta_display.service mbta_monitor.service daily_reboot.timer
sudo systemctl start mbta_display.service mbta_monitor.service
```

Daily reboot is scheduled by `daily_reboot.timer` (installer messaging refers to a 3 AM reboot). Inspect with:

```bash
sudo systemctl list-timers daily_reboot.timer
```

## Step 14: Verify Services

```bash
sudo systemctl status mbta_display.service
sudo systemctl status mbta_monitor.service

# View live logs
sudo journalctl -u mbta_display -f
```

All services should show "active (running)".

## Step 15: Set Up Convenience Aliases (Optional)

The installer appends these to `~/.bashrc` using the **venv’s** `python3` and absolute project paths (same effect as below):

```bash
echo '' >> ~/.bashrc
echo '# CharlieBoard quick status command' >> ~/.bashrc
echo "alias display_status='$HOME/CharlieBoard/venv/bin/python3 $HOME/CharlieBoard/runtime/status_check.py'" >> ~/.bashrc
echo '# CharlieBoard quick reboot command' >> ~/.bashrc
echo "alias display_reboot='sudo systemctl restart mbta_display.service && sudo systemctl restart mbta_monitor.service && echo \"Services restarted successfully\"'" >> ~/.bashrc
source ~/.bashrc
```

If your clone directory is not `~/CharlieBoard`, replace both path fragments in the `display_status` line (the installer uses the actual `PROJECT_DIR` from when you ran it).

Test the status script without the alias:

```bash
"$HOME/CharlieBoard/venv/bin/python3" "$HOME/CharlieBoard/runtime/status_check.py"
```

## Step 16: Access Web Interface

Open in your browser:

```
http://mbta-display.local:8000
```

Or use your Pi’s IP: `http://192.168.1.xxx:8000`

**Features:**

- Switch display modes (vehicles, occupancy, speed, rainbow)
- Adjust brightness
- Change routes
- Configure bedtime hours
- Monitor system health

**Optional:** Set up [nginx reverse proxy](nginx_reverse_proxy_setup.md) to access at `http://mbta-display.local` without the port number.

## Troubleshooting

See [Operations & Troubleshooting](operations_and_troubleshooting.md) for common issues and solutions.
