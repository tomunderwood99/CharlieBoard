# Complete Setup Guide

This guide walks through setting up the MBTA LED Controller on a fresh Raspberry Pi Zero 2W. For most users, the [Quick Start Guide](../deployment/quick_start/QUICK_START_GUIDE.md) is faster.

**Note:** This covers software setup only. For hardware assembly, see the [Hardware Assembly Guide](hardware_assembly_guide.md) first.

## Table of Contents

1. [Prepare Your Raspberry Pi](#step-1-prepare-your-raspberry-pi)
2. [System Update and Core Tools](#step-2-system-update-and-core-tools)
3. [Clone the Repository](#step-3-clone-the-repository)
4. [Set Up Python Environment](#step-4-set-up-python-environment)
5. [Install Dependencies](#step-5-install-dependencies)
6. [Configure Timezone](#step-6-configure-timezone)
7. [Set Up Raspberry Pi Connect (Optional)](#step-7-set-up-raspberry-pi-connect-optional)
8. [Create Configuration File](#step-8-create-configuration-file)
9. [Configure LED Mappings (Optional)](#step-9-configure-led-mappings-optional)
10. [Test LED Hardware](#step-10-test-led-hardware)
11. [Test Full Application](#step-11-test-full-application)
12. [Configure Systemd Services](#step-12-configure-systemd-services)
13. [Install and Enable Services](#step-13-install-and-enable-services)
14. [Verify Services](#step-14-verify-services)
15. [Set Up Status Command (Optional)](#step-15-set-up-status-command-optional)
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

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-pip python3-venv

# Verify installations
git --version && python3 --version
```

## Step 3: Clone the Repository

```bash
cd ~
git clone https://github.com/tomunderwood99/CharlieBoard.git
cd mbta_led_controller

# Optional: Remove hardware folder to save space
rm -rf hardware/
echo "hardware/" >> .git/info/exclude
```

## Step 4: Set Up Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Verify: should show /home/pi/mbta_led_controller/venv/bin/python
which python
```

## Step 5: Install Dependencies

```bash
pip install -e .

# Verify key packages
pip list | grep -E "Flask|neopixel|rpi-ws281x"
```

## Step 6: Configure Timezone

```bash
# Set timezone (adjust for your location)
sudo timedatectl set-timezone America/New_York

# Verify
timedatectl

# Other US timezones: America/Chicago, America/Denver, America/Los_Angeles
```

## Step 7: Set Up Raspberry Pi Connect (Optional but Recommended)

[Raspberry Pi Connect](https://www.raspberrypi.com/documentation/services/connect.html) provides secure remote access via web browser—no port forwarding or VPN needed. Manage your display from anywhere.

```bash
sudo apt install rpi-connect
rpi-connect signin
```

Visit the displayed URL to complete sign-in with your [Raspberry Pi ID](https://id.raspberrypi.com). After setup, access your Pi at [connect.raspberrypi.com](https://connect.raspberrypi.com).

## Step 8: Create Configuration File

Create `.env` in the project root:

```bash
nano .env
```

Add:
```bash
MBTA_API_KEY=your_api_key_here
ROUTE=Red
BRIGHTNESS=0.5
POWER_SWITCH=on
BEDTIME_START=22:00
BEDTIME_END=06:00
DISPLAY_MODE=vehicles
SHOW_DEBUGGER_OPTIONS=false
```

Get your free API key at [api-v3.mbta.com](https://api-v3.mbta.com/).

## Step 9: Configure LED Mappings (Optional)

If customizing LED positions:
```bash
nano config/station_led_maps.py
nano config/station_id_maps.py
```

## Step 10: Test LED Hardware

```bash
cd ~/mbta_led_controller
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
cd ~/mbta_led_controller
source venv/bin/activate
sudo venv/bin/python runtime/startup.py
```

This starts the web interface (port 8000) and LED controller. Verify at `http://mbta-display.local:8000`.

Press Ctrl+C to stop.

## Step 12: Configure Systemd Services

Update paths in service files (if using non-default username):

```bash
nano deployment/systemd/mbta_display.service
nano deployment/systemd/mbta_monitor.service
nano deployment/systemd/daily_reboot.service
```

Verify paths like `/home/pi/mbta_led_controller` match your setup.

## Step 13: Install and Enable Services

```bash
cd ~/mbta_led_controller
mkdir -p logs

# Copy service files
sudo cp deployment/systemd/mbta_display.service /etc/systemd/system/
sudo cp deployment/systemd/mbta_monitor.service /etc/systemd/system/
sudo cp deployment/systemd/daily_reboot.service /etc/systemd/system/
sudo cp deployment/systemd/daily_reboot.timer /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable mbta_display.service mbta_monitor.service daily_reboot.timer
sudo systemctl start mbta_display.service mbta_monitor.service
```

## Step 14: Verify Services

```bash
sudo systemctl status mbta_display.service
sudo systemctl status mbta_monitor.service

# View live logs
sudo journalctl -u mbta_display -f
```

All services should show "active (running)".

## Step 15: Set Up Status Command (Optional)

```bash
echo 'alias display_status="python3 ~/mbta_led_controller/runtime/status_check.py"' >> ~/.bashrc
source ~/.bashrc

# Now you can run:
display_status
```

## Step 16: Access Web Interface

Open in your browser:
```
http://mbta-display.local:8000
```

Or use your Pi's IP: `http://192.168.1.xxx:8000`

**Features:**
- Switch display modes (vehicles, occupancy, speed, rainbow)
- Adjust brightness
- Change routes
- Configure bedtime hours
- Monitor system health

**Optional:** Set up [nginx reverse proxy](nginx_reverse_proxy_setup.md) to access at `http://mbta-display.local` without the port number.

## Troubleshooting

See [Operations & Troubleshooting](operations_and_troubleshooting.md) for common issues and solutions.
