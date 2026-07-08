#!/bin/bash

###############################################################################
# MBTA LED Controller - Automated Setup Script
# 
# This script automates the complete setup process for a fresh Raspberry Pi
# installation, from system configuration through service installation.
#
# Prerequisites:
#   - Raspberry Pi OS (headless) installed and booted
#   - Git and pip installed (sudo apt install -y git python3-pip)
#   - This repository cloned to the system
#   - Run from the repository root directory
#
# Usage:
#   sudo ./deployment/quick_start/setup_mbta_controller.sh
###############################################################################

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track what we've installed for cleanup purposes
CREATED_VENV=false
CREATED_ENV_FILE=false
INSTALLED_SERVICES=false
MODIFIED_BASHRC=false
INSTALLED_PROFILE_D=false
INSTALLED_WIFI_HELPER=false

# WiFi helper integration flags. INSTALL_WIFI_HELPER may be set to "true",
# "false", or left empty (the default), in which case the user is prompted
# interactively. AP_SSID/AP_PASSWORD/WIFI_HELPER_DIR are only used when the
# helper is actually installed; empty values fall through to the helper's
# own defaults.
INSTALL_WIFI_HELPER=""
WIFI_HELPER_DIR=""
AP_SSID=""
AP_PASSWORD=""
WIFI_HELPER_REPO_URL="https://github.com/tomunderwood99/headless_wifi_helper.git"

# Argument parsing for non-interactive WiFi helper configuration. We only
# parse a small set of flags that affect the helper integration; all other
# user-facing settings still come from the interactive prompts below.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-wifi-helper)
            INSTALL_WIFI_HELPER=true
            shift
            ;;
        --no-wifi-helper)
            INSTALL_WIFI_HELPER=false
            shift
            ;;
        --wifi-helper-dir)
            WIFI_HELPER_DIR="$2"
            shift 2
            ;;
        --ap-ssid)
            AP_SSID="$2"
            shift 2
            ;;
        --ap-password)
            AP_PASSWORD="$2"
            shift 2
            ;;
        -h|--help)
            cat <<'EOF'
Usage: sudo ./deployment/quick_start/setup_mbta_controller.sh [options]

Options:
  --with-wifi-helper          Install tomunderwood99/headless_wifi_helper so a
                              captive-portal AP appears on first boot when no
                              known WiFi is in range. The portal can also write
                              the MBTA API key into CharlieBoard's .env.

                              REQUIRES Raspberry Pi OS Trixie (NetworkManager
                              as the network backend). Older images using
                              dhcpcd / wpa_supplicant are NOT supported and
                              the helper's setup will fail. If you're not on
                              Trixie, pass --no-wifi-helper instead.
  --no-wifi-helper            Skip the WiFi helper prompt and do not install it.
  --wifi-helper-dir <path>    Where to clone the helper repo
                              (default: /home/<user>/headless_wifi_helper).
  --ap-ssid <ssid>            Override the captive-portal AP SSID
                              (forwarded to the helper's setup.sh).
  --ap-password <password>    Override the captive-portal AP password
                              (forwarded to the helper's setup.sh; must be
                              >= 12 chars per the helper's policy).
  -h, --help                  Show this message and exit.
EOF
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            echo "Run with --help to see available options." >&2
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

###############################################################################
# Error Handler and Cleanup
###############################################################################

cleanup_on_error() {
    local exit_code=$?
    local line_number=$1
    
    echo ""
    echo ""
    log_error "═══════════════════════════════════════════════════════"
    log_error "  Setup failed at line $line_number (exit code: $exit_code)"
    log_error "═══════════════════════════════════════════════════════"
    echo ""
    
    read -p "Would you like to rollback changes made so far? [Y/n]: " rollback
    rollback=${rollback:-Y}
    
    if [ "$rollback" = "y" ] || [ "$rollback" = "Y" ]; then
        echo ""
        log_info "Rolling back changes..."
        
        # Rollback in reverse order of installation
        if [ "$INSTALLED_WIFI_HELPER" = true ]; then
            log_info "Disabling and removing wifi_configurator.service..."
            systemctl disable --now wifi_configurator.service 2>/dev/null || true
            rm -f /etc/systemd/system/wifi_configurator.service
            systemctl daemon-reload
            # Note: we intentionally do NOT delete the cloned helper repo —
            # the user may have edited it, and `git clone` is cheap to redo.
            log_success "wifi_configurator.service removed (helper repo left in place)"
        fi

        if [ "$INSTALLED_SERVICES" = true ]; then
            log_info "Stopping and removing systemd services..."
            systemctl stop mbta_display.service 2>/dev/null || true
            systemctl stop mbta_monitor.service 2>/dev/null || true
            systemctl stop daily_reboot.timer 2>/dev/null || true
            systemctl disable mbta_display.service 2>/dev/null || true
            systemctl disable mbta_monitor.service 2>/dev/null || true
            systemctl disable daily_reboot.timer 2>/dev/null || true
            rm -f /etc/systemd/system/mbta_display.service
            rm -f /etc/systemd/system/mbta_monitor.service
            rm -f /etc/systemd/system/daily_reboot.service
            rm -f /etc/systemd/system/daily_reboot.timer
            systemctl daemon-reload
            log_success "Services removed"
        fi
        
        if [ "$INSTALLED_PROFILE_D" = true ]; then
            log_info "Removing profile.d PATH configuration..."
            rm -f /etc/profile.d/mbta_led_controller.sh
            log_success "profile.d configuration removed"
        fi

        if [ "$MODIFIED_BASHRC" = true ] && [ -n "$ACTUAL_USER" ]; then
            log_info "Removing .bashrc modifications..."
            BASHRC_FILE="/home/$ACTUAL_USER/.bashrc"
            if [ -f "$BASHRC_FILE" ]; then
                sed -i '/# MBTA LED Controller quick status command/d' "$BASHRC_FILE"
                sed -i '/alias display_status=/d' "$BASHRC_FILE"
                sed -i '/# MBTA LED Controller quick reboot command/d' "$BASHRC_FILE"
                sed -i '/alias display_reboot=/d' "$BASHRC_FILE"
                sed -i '/# MBTA LED Controller settings CLI/d' "$BASHRC_FILE"
                sed -i '/alias charlieboard=/d' "$BASHRC_FILE"
                log_success ".bashrc cleaned"
            fi
        fi
        
        if [ "$CREATED_ENV_FILE" = true ] && [ -n "$PROJECT_DIR" ]; then
            log_info "Removing configuration file..."
            rm -f "$PROJECT_DIR/.env"
            log_success "Configuration file removed"
        fi
        
        if [ "$CREATED_VENV" = true ] && [ -n "$VENV_PATH" ]; then
            log_info "Removing virtual environment..."
            rm -rf "$VENV_PATH"
            log_success "Virtual environment removed"
        fi
        
        echo ""
        log_success "Rollback complete"
    else
        log_info "Keeping partial installation for debugging"
    fi
    
    echo ""
    echo -e "${YELLOW}Troubleshooting Tips:${NC}"
    echo "  • Check the error message above for specific details"
    echo "  • For Python package errors, try manually:"
    echo -e "    ${BLUE}source venv/bin/activate && pip install -e .${NC}"
    echo "  • Ensure all system dependencies are installed:"
    echo -e "    ${BLUE}sudo apt-get install python3-dev build-essential${NC}"
    echo -e "  • Check system logs: ${BLUE}journalctl -xe${NC}"
    echo ""
    
    exit $exit_code
}

# Set up error trap
trap 'cleanup_on_error ${LINENO}' ERR

###############################################################################
# Pre-flight Checks
###############################################################################

print_header "MBTA LED Controller - Automated Setup"

log_info "Running pre-flight checks..."
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "This script must be run as root (use sudo)"
    echo "Usage: sudo ./deployment/quick_start/setup_mbta_controller.sh"
    exit 1
fi

# Check for required system commands
MISSING_DEPS=()
for cmd in python3 pip3 git timedatectl systemctl; do
    if ! command -v $cmd &> /dev/null; then
        MISSING_DEPS+=("$cmd")
    fi
done

if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    log_error "Missing required system dependencies: ${MISSING_DEPS[*]}"
    echo ""
    echo "Please install them first:"
    echo -e "  ${YELLOW}sudo apt-get update${NC}"
    echo -e "  ${YELLOW}sudo apt-get install -y python3 python3-pip git systemd${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 7 ]); then
    log_error "Python 3.7 or higher is required (found: $PYTHON_VERSION)"
    exit 1
fi

log_success "Python version check passed: $PYTHON_VERSION"

# Get the actual user (not root when using sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
if [ "$ACTUAL_USER" = "root" ]; then
    ACTUAL_USER="pi"  # Default to pi user
fi

log_success "Running as user: $ACTUAL_USER"

# Verify we're in the correct directory
if [ ! -f "runtime/startup.py" ] || [ ! -f "setup.py" ]; then
    log_error "Cannot find required files (runtime/startup.py, setup.py)"
    log_error "Please run this script from the mbta_led_controller root directory"
    exit 1
fi

PROJECT_DIR=$(pwd)
log_success "Project directory: $PROJECT_DIR"

###############################################################################
# Collect User Input
###############################################################################

print_header "Configuration Setup"

echo "This script will guide you through the initial setup."
echo "You'll need to provide a few key pieces of information."
echo ""

# Prompt for headless WiFi helper installation. We do this first so the
# MBTA API key prompt below can be made optional when the helper is being
# installed (the captive portal can also write the key into .env later).
# If --with-wifi-helper or --no-wifi-helper was passed, skip the prompt.
# Default is "no" — installing the helper pulls in NetworkManager, dnsmasq,
# and a separate cloned repo, so we keep the existing minimal install path
# unless the user explicitly opts in.
if [ -z "$INSTALL_WIFI_HELPER" ]; then
    echo "The headless WiFi helper (tomunderwood99/headless_wifi_helper) brings"
    echo "up a temporary access point on boot whenever no known WiFi network is"
    echo "in range, so you can reconfigure WiFi from a phone without re-flashing"
    echo "the Pi. The captive portal can also save your MBTA API key directly"
    echo "into this project's .env file."
    echo ""
    echo "REQUIRES Raspberry Pi OS Trixie (NetworkManager as the network backend)."
    echo "Older images using dhcpcd / wpa_supplicant are NOT supported."
    echo ""
    read -p "Install the headless WiFi helper? [y/N]: " install_helper
    install_helper=${install_helper:-N}
    if [ "$install_helper" = "y" ] || [ "$install_helper" = "Y" ]; then
        INSTALL_WIFI_HELPER=true
    else
        INSTALL_WIFI_HELPER=false
    fi
fi
if [ "$INSTALL_WIFI_HELPER" = true ]; then
    log_success "Headless WiFi helper will be installed"
else
    log_info "Headless WiFi helper will NOT be installed"
fi

# Prompt for MBTA API Key. When the WiFi helper is being installed, the user
# can leave this blank and enter the key later via the captive portal — the
# helper writes MBTA_API_KEY straight into CharlieBoard's .env on submit.
echo ""
if [ "$INSTALL_WIFI_HELPER" = true ]; then
    read -p "Enter your MBTA API Key (get one free at https://api-v3.mbta.com/) [leave blank to enter via the WiFi helper portal later]: " MBTA_API_KEY
    if [ -z "$MBTA_API_KEY" ]; then
        log_warning "API Key not provided — you can paste it into the captive portal on first connection."
        log_warning "The display services will start with an empty key and reconnect once the portal writes one."
    else
        log_success "API Key configured"
    fi
else
    while true; do
        read -p "Enter your MBTA API Key (get one free at https://api-v3.mbta.com/): " MBTA_API_KEY
        if [ -n "$MBTA_API_KEY" ]; then
            break
        else
            log_warning "API Key is required. Please enter a valid key."
        fi
    done
    log_success "API Key configured"
fi

# Prompt for MBTA Line/Route
echo ""
echo "Available MBTA Lines:"
echo "  1) Red"
echo "  2) Blue"
echo "  3) Orange"
echo "  4) Green-All (in development)"
echo "  5) Green-B"
echo "  6) Green-C"
echo "  7) Green-D"
echo "  8) Green-E"
while true; do
    read -p "Select MBTA Line [1-8] (default: 1 - Red): " route_choice
    route_choice=${route_choice:-1}
    case $route_choice in
        1) MBTA_ROUTE="Red"; break;;
        2) MBTA_ROUTE="Blue"; break;;
        3) MBTA_ROUTE="Orange"; break;;
        4) MBTA_ROUTE="Green-All"; break;;
        5) MBTA_ROUTE="Green-B"; break;;
        6) MBTA_ROUTE="Green-C"; break;;
        7) MBTA_ROUTE="Green-D"; break;;
        8) MBTA_ROUTE="Green-E"; break;;
        *) log_warning "Invalid selection. Please choose 1-8.";;
    esac
done
log_success "Route configured: $MBTA_ROUTE"

# Prompt for Timezone
echo ""
echo "Common US Timezones:"
echo "  1) America/New_York (Eastern)"
echo "  2) America/Chicago (Central)"
echo "  3) America/Denver (Mountain)"
echo "  4) America/Los_Angeles (Pacific)"
echo "  5) America/Anchorage (Alaska)"
echo "  6) Pacific/Honolulu (Hawaii)"
echo "  7) Custom (enter manually)"
while true; do
    read -p "Select Timezone [1-7] (default: 1 - Eastern): " tz_choice
    tz_choice=${tz_choice:-1}
    case $tz_choice in
        1) TIMEZONE="America/New_York"; break;;
        2) TIMEZONE="America/Chicago"; break;;
        3) TIMEZONE="America/Denver"; break;;
        4) TIMEZONE="America/Los_Angeles"; break;;
        5) TIMEZONE="America/Anchorage"; break;;
        6) TIMEZONE="Pacific/Honolulu"; break;;
        7) 
            read -p "Enter timezone (e.g., America/New_York): " TIMEZONE
            if [ -n "$TIMEZONE" ]; then
                break
            else
                log_warning "Timezone is required."
            fi
            ;;
        *) log_warning "Invalid selection. Please choose 1-7.";;
    esac
done
log_success "Timezone configured: $TIMEZONE"

# Optional: Bedtime hours
echo ""
read -p "Enter bedtime start hour (HH:MM, default: 22:00): " BEDTIME_START
BEDTIME_START=${BEDTIME_START:-22:00}
read -p "Enter bedtime end hour (HH:MM, default: 06:00): " BEDTIME_END
BEDTIME_END=${BEDTIME_END:-06:00}
log_success "Bedtime configured: $BEDTIME_START to $BEDTIME_END"

# Optional: Initial brightness
echo ""
read -p "Enter initial brightness (0.0-1.0, default: 0.5): " BRIGHTNESS
BRIGHTNESS=${BRIGHTNESS:-0.5}
log_success "Brightness: $BRIGHTNESS"

# Virtual environment name
VENV_NAME="venv"
VENV_PATH="$PROJECT_DIR/$VENV_NAME"

###############################################################################
# System Update and Package Installation
###############################################################################

print_header "System Update and Package Installation"

log_info "Updating package lists..."
if ! apt-get update -qq 2>&1 | grep -v "^Get:" | grep -v "^Hit:" | grep -v "^Reading" | grep -v "^Building" | grep -E "(E:|W:)" >&2; then
    log_success "Package lists updated"
else
    log_error "Failed to update package lists"
    exit 1
fi

log_info "Installing system dependencies (python3, python3-pip, python3-venv, python3-dev, git)..."
if apt-get install -y python3 python3-pip python3-venv python3-dev git 2>&1 | tee /tmp/apt_install.log | grep -E "(E:|cannot|failed)" >&2; then
    log_error "Failed to install system packages. Check /tmp/apt_install.log for details."
    exit 1
fi
log_success "System packages installed"

###############################################################################
# Set System Timezone
###############################################################################

print_header "System Configuration"

log_info "Setting system timezone to $TIMEZONE..."
timedatectl set-timezone "$TIMEZONE"
CURRENT_TZ=$(timedatectl | grep "Time zone" | awk '{print $3}')
log_success "Timezone set to: $CURRENT_TZ"

###############################################################################
# Python Virtual Environment Setup
###############################################################################

print_header "Python Environment Setup"

# Check if virtual environment already exists
if [ -d "$VENV_PATH" ]; then
    log_warning "Virtual environment already exists at $VENV_PATH"
    read -p "Remove and recreate? [y/N]: " recreate
    if [ "$recreate" = "y" ] || [ "$recreate" = "Y" ]; then
        log_info "Removing existing virtual environment..."
        rm -rf "$VENV_PATH"
    else
        log_info "Using existing virtual environment"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_PATH" ]; then
    log_info "Creating virtual environment at $VENV_PATH..."
    if sudo -u "$ACTUAL_USER" python3 -m venv "$VENV_PATH" 2>&1 | tee /tmp/venv_create.log | grep -iE "(error|failed|cannot)" >&2; then
        log_error "Failed to create virtual environment. Check /tmp/venv_create.log for details."
        exit 1
    fi
    CREATED_VENV=true
    log_success "Virtual environment created"
fi

# Upgrade pip in the virtual environment
log_info "Upgrading pip..."
if ! sudo -u "$ACTUAL_USER" "$VENV_PATH/bin/pip" install --upgrade pip >/dev/null 2>&1; then
    log_warning "Failed to upgrade pip (continuing anyway)"
else
    log_success "Pip upgraded"
fi

# Install Python dependencies
log_info "Installing Python dependencies (this may take several minutes)..."
echo "  Progress will be shown below as packages are installed..."
echo ""

# Run pip install with filtered output to show progress
sudo -u "$ACTUAL_USER" "$VENV_PATH/bin/pip" install -e "$PROJECT_DIR" 2>&1 | tee /tmp/pip_install.log | while IFS= read -r line; do
    # Show collecting packages (indicates what's being installed)
    if echo "$line" | grep -q "^Collecting"; then
        echo "  📦 $line"
    # Show when packages are successfully installed
    elif echo "$line" | grep -q "^Successfully installed"; then
        echo -e "  ${GREEN}✓${NC} $line"
    # Show building messages (for packages that compile)
    elif echo "$line" | grep -q "Building wheel"; then
        echo "  🔧 Building package..."
    # Show errors and warnings
    elif echo "$line" | grep -iqE "(error|warning|failed)"; then
        echo -e "  ${YELLOW}⚠${NC} $line"
    fi
done

# Check if pip install succeeded
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo ""
    log_error "Failed to install Python dependencies"
    log_error "Check /tmp/pip_install.log for full details"
    echo ""
    echo -e "${YELLOW}Common solutions:${NC}"
    echo -e "  • Install build dependencies: ${BLUE}sudo apt-get install -y build-essential python3-dev${NC}"
    echo -e "  • For rpi_ws281x issues: ${BLUE}sudo apt-get install -y scons swig${NC}"
    echo -e "  • Try manual install: ${BLUE}source $VENV_PATH/bin/activate && pip install -e . -v${NC}"
    exit 1
fi

echo ""
log_success "Python dependencies installed"

###############################################################################
# Create Configuration File
###############################################################################

print_header "Configuration File Creation"

ENV_FILE="$PROJECT_DIR/.env"

log_info "Creating configuration file at $ENV_FILE..."

cat > "$ENV_FILE" << EOF
# MBTA LED Controller Configuration
# Generated by setup script on $(date)

# MBTA API Configuration
MBTA_API_KEY=$MBTA_API_KEY

# Display Settings
ROUTE=$MBTA_ROUTE
BRIGHTNESS=$BRIGHTNESS
POWER_SWITCH=on
BEDTIME_START=$BEDTIME_START
BEDTIME_END=$BEDTIME_END
DISPLAY_MODE=vehicles

# Color Settings (RGB values)
STOPPED_COLOR=[255, 0, 0]
INCOMING_COLOR=[255, 75, 75]
TRANSIT_COLOR=[150, 150, 150]
MIN_SPEED_COLOR=[0, 255, 0]
MAX_SPEED_COLOR=[255, 0, 0]
NULL_SPEED_COLOR=[0, 0, 255]
MIN_OCCUPANCY_COLOR=[0, 255, 0]
MAX_OCCUPANCY_COLOR=[255, 0, 0]
NULL_OCCUPANCY_COLOR=[0, 0, 255]

# Debug Settings
SHOW_DEBUGGER_OPTIONS=false
DEBUGGER=[]
EOF

chown "$ACTUAL_USER:$ACTUAL_USER" "$ENV_FILE"
CREATED_ENV_FILE=true
log_success "Configuration file created"

###############################################################################
# Configure Systemd Service Files
###############################################################################

print_header "Systemd Service Configuration"

log_info "Updating service files with correct paths..."

# Update mbta_display.service
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" deployment/systemd/mbta_display.service
sed -i "s|Environment=PROJECT_ROOT=.*|Environment=PROJECT_ROOT=$PROJECT_DIR|g" deployment/systemd/mbta_display.service
sed -i "s|Environment=VENV_PATH=.*|Environment=VENV_PATH=$VENV_PATH|g" deployment/systemd/mbta_display.service
sed -i "s|ExecStart=.*|ExecStart=$VENV_PATH/bin/python $PROJECT_DIR/runtime/startup.py|g" deployment/systemd/mbta_display.service

# Update mbta_monitor.service
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" deployment/systemd/mbta_monitor.service
sed -i "s|Environment=PROJECT_ROOT=.*|Environment=PROJECT_ROOT=$PROJECT_DIR|g" deployment/systemd/mbta_monitor.service
sed -i "s|Environment=VENV_PATH=.*|Environment=VENV_PATH=$VENV_PATH|g" deployment/systemd/mbta_monitor.service
sed -i "s|ExecStart=.*|ExecStart=$VENV_PATH/bin/python -u $PROJECT_DIR/monitoring/health_monitor.py|g" deployment/systemd/mbta_monitor.service

# Update daily_reboot.service (timer-triggered)
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" deployment/systemd/daily_reboot.service
sed -i "s|ExecStartPre=.*|ExecStartPre=/bin/sh -c 'echo \"\$(date): Initiating scheduled daily reboot\" >> $PROJECT_DIR/logs/daily_reboot.log'|g" deployment/systemd/daily_reboot.service

log_success "Service files updated"

###############################################################################
# Create Log Directory
###############################################################################

log_info "Creating log directories..."
mkdir -p "$PROJECT_DIR/logs"
chown -R "$ACTUAL_USER:$ACTUAL_USER" "$PROJECT_DIR/logs"
log_success "Log directories created"

###############################################################################
# Install Systemd Services
###############################################################################

print_header "Installing Systemd Services"

log_info "Copying service and timer files to /etc/systemd/system/..."
cp deployment/systemd/mbta_display.service /etc/systemd/system/
cp deployment/systemd/mbta_monitor.service /etc/systemd/system/
cp deployment/systemd/daily_reboot.service /etc/systemd/system/
cp deployment/systemd/daily_reboot.timer /etc/systemd/system/
log_success "Service files copied"

log_info "Reloading systemd daemon..."
systemctl daemon-reload
log_success "Systemd daemon reloaded"

log_info "Enabling services to start on boot..."
systemctl enable mbta_display.service
systemctl enable mbta_monitor.service
systemctl enable daily_reboot.timer  # Enable timer, not the service directly
INSTALLED_SERVICES=true
log_success "Services and timer enabled"

###############################################################################
# Set Up Quick Status Command
###############################################################################

print_header "Convenience Commands Setup"

BASHRC_FILE="/home/$ACTUAL_USER/.bashrc"
PROFILE_D_FILE="/etc/profile.d/mbta_led_controller.sh"
log_info "Adding charlieboard to PATH for login shells..."
if [ -f "$PROFILE_D_FILE" ] && grep -q "$VENV_PATH/bin" "$PROFILE_D_FILE" 2>/dev/null; then
    log_warning "profile.d PATH entry already exists"
else
    cat > "$PROFILE_D_FILE" <<EOF
# MBTA LED Controller - charlieboard CLI and other venv console scripts
export PATH="$VENV_PATH/bin:\$PATH"
EOF
    chmod 644 "$PROFILE_D_FILE"
    INSTALLED_PROFILE_D=true
    log_success "charlieboard available on PATH for new login sessions"
fi

# Remove legacy charlieboard bash alias (PATH via profile.d replaces it)
if [ -f "$BASHRC_FILE" ] && grep -q "alias charlieboard=" "$BASHRC_FILE" 2>/dev/null; then
    sed -i '/# MBTA LED Controller settings CLI/d' "$BASHRC_FILE"
    sed -i '/alias charlieboard=/d' "$BASHRC_FILE"
    log_info "Removed legacy charlieboard alias from .bashrc (using PATH instead)"
fi

log_info "Setting up 'display_status' command alias..."

# Check if alias already exists
if grep -q "alias display_status=" "$BASHRC_FILE" 2>/dev/null; then
    log_warning "Display status alias already exists in .bashrc"
else
    echo "" >> "$BASHRC_FILE"
    echo "# MBTA LED Controller quick status command" >> "$BASHRC_FILE"
    echo "alias display_status='$VENV_PATH/bin/python3 $PROJECT_DIR/runtime/status_check.py'" >> "$BASHRC_FILE"
    chown "$ACTUAL_USER:$ACTUAL_USER" "$BASHRC_FILE"
    MODIFIED_BASHRC=true
    log_success "Display status command alias added to .bashrc"
fi

log_info "Setting up 'display_reboot' command alias..."

# Check if alias already exists
if grep -q "alias display_reboot=" "$BASHRC_FILE" 2>/dev/null; then
    log_warning "Display reboot alias already exists in .bashrc"
else
    echo "# MBTA LED Controller quick reboot command" >> "$BASHRC_FILE"
    echo "alias display_reboot='sudo systemctl restart mbta_display.service && sudo systemctl restart mbta_monitor.service && echo \"Services restarted successfully\"'" >> "$BASHRC_FILE"
    chown "$ACTUAL_USER:$ACTUAL_USER" "$BASHRC_FILE"
    MODIFIED_BASHRC=true
    log_success "Display reboot command alias added to .bashrc"
fi

echo ""
echo -e "${YELLOW}Note:${NC} ${BLUE}charlieboard${NC} is on your PATH after the next login (or run ${BLUE}source /etc/profile.d/mbta_led_controller.sh${NC} once in this shell)."
echo "The ${BLUE}display_status${NC} and ${BLUE}display_reboot${NC} shortcuts are in ~/.bashrc — use a new SSH session, or ${BLUE}source ~/.bashrc${NC} in the window where you ran setup."
echo ""
echo "Test now without reopening the terminal:"
echo -e "  ${BLUE}$VENV_PATH/bin/charlieboard show${NC}"
echo -e "  ${BLUE}$VENV_PATH/bin/python3 $PROJECT_DIR/runtime/status_check.py${NC}"

###############################################################################
# Headless WiFi Helper Installation (Optional)
###############################################################################

# This installs tomunderwood99/headless_wifi_helper alongside CharlieBoard.
# At boot, that project's wifi_configurator.service waits up to ~30s for wlan0
# to associate as a WiFi client. If it does not, the service brings up a
# captive-portal AP at 192.168.4.1 and blocks until the user submits new
# credentials and reboots. The helper's service is `Before=network-online.target`
# and CharlieBoard's services are `After=network-online.target`, so boot-time
# ordering is automatic — no edits to the mbta_*.service files are required.
# At runtime, if WiFi is lost long enough that mbta_monitor.service reboots
# the Pi, the helper picks up again on the next boot.

if [ "$INSTALL_WIFI_HELPER" = true ]; then
    print_header "Headless WiFi Helper Installation"

    # Default install location: a sibling of CharlieBoard in the user's home.
    HELPER_DIR_DEFAULT="/home/$ACTUAL_USER/headless_wifi_helper"
    HELPER_DIR="${WIFI_HELPER_DIR:-$HELPER_DIR_DEFAULT}"

    log_info "Helper directory: $HELPER_DIR"

    if [ ! -d "$HELPER_DIR" ]; then
        log_info "Cloning headless_wifi_helper from $WIFI_HELPER_REPO_URL..."
        if sudo -u "$ACTUAL_USER" git clone "$WIFI_HELPER_REPO_URL" "$HELPER_DIR" 2>&1 | tee /tmp/wifi_helper_clone.log | grep -iE "(error|failed|fatal)" >&2; then
            log_error "Failed to clone headless_wifi_helper. Check /tmp/wifi_helper_clone.log for details."
            exit 1
        fi
        log_success "headless_wifi_helper cloned"
    else
        log_warning "$HELPER_DIR already exists — using the existing checkout (not re-cloning)."
    fi

    # Build the helper's setup.sh argument list. We always pin the .env file
    # path to CharlieBoard's .env and the env key name to MBTA_API_KEY so the
    # captive portal writes the API key directly into our config. AP_SSID and
    # AP_PASSWORD are optional pass-throughs; when empty, the helper's own
    # defaults / autogeneration take over (see its setup.sh).
    HELPER_ARGS=(--env-file "$ENV_FILE" --env-key-name MBTA_API_KEY)
    if [ -n "$AP_SSID" ]; then
        HELPER_ARGS+=(--ap-ssid "$AP_SSID")
    fi
    if [ -n "$AP_PASSWORD" ]; then
        HELPER_ARGS+=(--ap-password "$AP_PASSWORD")
    fi

    log_info "Running headless_wifi_helper setup (this installs network-manager, dnsmasq, etc.)..."
    log_info "Helper setup args: ${HELPER_ARGS[*]}"
    echo ""

    # The helper's setup.sh requires root and is already idempotent enough for
    # re-runs; it streams its own colored progress to stdout, so we let it
    # through unfiltered.
    if (cd "$HELPER_DIR" && bash ./deployment/setup.sh "${HELPER_ARGS[@]}"); then
        INSTALLED_WIFI_HELPER=true
        log_success "headless_wifi_helper installed and wifi_configurator.service enabled"
    else
        log_error "headless_wifi_helper setup failed (see output above)"
        log_error "You can re-run it manually later: cd $HELPER_DIR && sudo ./deployment/setup.sh ${HELPER_ARGS[*]}"
        exit 1
    fi
fi

###############################################################################
# LED Hardware Test (Optional)
###############################################################################

print_header "Hardware Test"

echo ""
echo "Would you like to test your LED hardware now?"
echo "This will light up all LEDs in red to verify your wiring."
echo ""
read -p "Run LED test? [Y/n]: " run_test
run_test=${run_test:-Y}

if [ "$run_test" = "y" ] || [ "$run_test" = "Y" ]; then
    log_info "Running LED test (press Ctrl+C to stop)..."
    echo ""
    if [ -f "tests/red_test.py" ]; then
        sudo -E "$VENV_PATH/bin/python" tests/red_test.py || log_warning "LED test failed or was interrupted"
    else
        log_error "LED test script not found at tests/red_test.py"
    fi
else
    log_info "Skipping LED test"
fi

###############################################################################
# Final Steps
###############################################################################

print_header "Setup Complete!"

log_success "MBTA LED Controller has been successfully installed and configured"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Configuration Summary${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "  📍 Project Directory: $PROJECT_DIR"
echo "  👤 User: $ACTUAL_USER"
echo "  🐍 Virtual Environment: $VENV_PATH"
echo "  🚇 MBTA Route: $MBTA_ROUTE Line"
echo "  🌍 Timezone: $TIMEZONE"
echo "  🔆 Brightness: $BRIGHTNESS"
echo "  😴 Bedtime: $BEDTIME_START - $BEDTIME_END"
if [ "$INSTALLED_WIFI_HELPER" = true ]; then
    echo "  📶 WiFi Helper: installed at ${HELPER_DIR}"
fi
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "  1. Start the services now (or reboot to start automatically):"
echo -e "     ${YELLOW}sudo systemctl start mbta_display.service${NC}"
echo -e "     ${YELLOW}sudo systemctl start mbta_monitor.service${NC}"
echo ""
echo "  2. Check service status:"
echo -e "     ${YELLOW}sudo systemctl status mbta_display.service${NC}"
echo ""
echo "  3. View live logs:"
echo -e "     ${YELLOW}sudo journalctl -u mbta_display -f${NC}"
echo ""
echo "  4. Access the web interface:"
echo -e "     ${YELLOW}http://$(hostname).local:8000${NC}"
echo -e "     ${YELLOW}http://$(hostname -I | awk '{print $1}'):8000${NC}"
echo ""
echo "  5. Check system status:"
echo -e "     ${YELLOW}display_status${NC}  ${BLUE}# new SSH session, or: source ~/.bashrc${NC}"
echo ""
echo "  6. Change settings from the terminal (no web UI):"
echo -e "     ${YELLOW}charlieboard show${NC}  ${BLUE}# on PATH after login; or use full path above${NC}"
echo -e "     ${YELLOW}charlieboard set power on${NC}"
echo ""
echo "  7. Restart display services (if needed):"
echo -e "     ${YELLOW}display_reboot${NC}"
echo ""
echo -e "     ${BLUE}Tip:${NC} The aliases will work automatically in new terminal sessions"
echo ""

echo -e "${YELLOW}Important Notes:${NC}"
echo ""
echo "  • Services will auto-start on boot"
echo "  • Health monitor will restart main service if it fails"
echo "  • Daily reboot occurs at 3 AM (systemd timer-based)"
echo "  • Configuration file: $ENV_FILE"
echo "  • Logs location: $PROJECT_DIR/logs/"
echo "  • View reboot schedule: ${BLUE}sudo systemctl list-timers daily_reboot.timer${NC}"
echo ""

if [ "$INSTALLED_WIFI_HELPER" = true ]; then
    echo -e "${YELLOW}Headless WiFi Helper:${NC}"
    echo ""
    echo "  • If the Pi boots without a known WiFi network, a captive-portal"
    echo "    access point will appear so you can reconfigure WiFi (and the"
    echo "    MBTA API key) from a phone — no re-flashing required."
    echo "  • The helper waits ~30s for wlan0 to associate before starting"
    echo "    the AP. The MBTA services (After=network-online.target) will"
    echo "    wait until either WiFi is up or you reconfigure it via the portal."
    echo "  • Helper service: ${BLUE}systemctl status wifi_configurator.service${NC}"
    echo "  • Helper logs:    ${BLUE}sudo journalctl -u wifi_configurator.service -f${NC}"
    echo "  • Helper repo:    ${BLUE}$HELPER_DIR${NC}"
    echo "  • See $HELPER_DIR/README.md for AP SSID/password and customization."
    echo ""
fi

read -p "Would you like to start the services now? [Y/n]: " start_now
start_now=${start_now:-Y}

if [ "$start_now" = "y" ] || [ "$start_now" = "Y" ]; then
    echo ""
    log_info "Starting services..."
    
    if systemctl start mbta_display.service 2>&1 | tee /tmp/service_start.log | grep -iE "(failed|error)" >&2; then
        log_error "Failed to start mbta_display.service"
        log_error "Check logs with: sudo journalctl -u mbta_display.service -n 50"
        echo ""
        echo -e "${YELLOW}The setup is complete but the service failed to start.${NC}"
        echo "This may be due to hardware issues or configuration problems."
        echo "You can troubleshoot and start manually later."
    else
        log_success "mbta_display.service started"
    fi
    
    sleep 2
    
    if systemctl start mbta_monitor.service 2>&1 | tee -a /tmp/service_start.log | grep -iE "(failed|error)" >&2; then
        log_warning "Failed to start mbta_monitor.service (not critical)"
    else
        log_success "mbta_monitor.service started"
    fi
    
    echo ""
    log_info "Checking service status..."
    echo ""
    systemctl status mbta_display.service --no-pager -l || true
    
    echo ""
    if systemctl is-active --quiet mbta_display.service; then
        echo -e "${GREEN}✓ Setup complete! Your MBTA LED display is now running.${NC}"
        echo ""
        echo -e "Access the web interface at: ${YELLOW}http://$(hostname -I | awk '{print $1}'):8000${NC}"
    else
        echo -e "${YELLOW}⚠ Setup complete but service is not running.${NC}"
        echo -e "Check logs: ${BLUE}sudo journalctl -u mbta_display.service -n 50${NC}"
    fi
else
    echo ""
    log_info "Services not started. Start them manually when ready:"
    echo "  sudo systemctl start mbta_display.service"
    echo "  sudo systemctl start mbta_monitor.service"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Enjoy your MBTA LED display! 🚇✨${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""
