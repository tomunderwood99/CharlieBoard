# The CharlieBoard

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Hardware: Raspberry Pi](https://img.shields.io/badge/hardware-Raspberry%20Pi%20Zero%202W-C51A4A.svg)](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/tomunderwood99/CharlieBoard/issues)

An open-source LED display system for the MBTA that runs on Raspberry Pi Zero 2W with WS2812B LEDs. Features real-time transit data visualization, web control interface, and geographically accurate station mapping.

![CharlieBoard Display](hardware/images/hardware_carousel.gif)

## Quick Start

**Prerequisites:** Raspberry Pi Zero 2W with Raspberry Pi OS, WiFi configured, SSH enabled, and an [MBTA API key](https://api-v3.mbta.com/).

```bash
sudo apt update && sudo apt install -y git python3-pip
cd ~
git clone --filter=blob:none --sparse https://github.com/tomunderwood99/CharlieBoard.git
cd mbta_led_controller
git sparse-checkout set --no-cone '/*' '!hardware'
chmod +x deployment/quick_start/setup_mbta_controller.sh
sudo ./deployment/quick_start/setup_mbta_controller.sh
```

> **Note:** The sparse-checkout excludes the `hardware/` directory (PCB design files) to speed up cloning. This setting persists across future `git pull` operations. If you need the hardware files, run: `git sparse-checkout disable`

The setup script will prompt for your MBTA API key and configure everything automatically. Access the web interface at `http://your-hostname.local:8000` when complete.

**Optional enhancements:**
- [nginx reverse proxy](docs/nginx_reverse_proxy_setup.md) – Access at `http://hostname.local` without the port
- [Raspberry Pi Connect](https://www.raspberrypi.com/documentation/services/connect.html) – Secure remote access from anywhere

## Features

- **Real-time Transit Data**: Live vehicle positions, occupancy, and speed data
- **Geographically Accurate**: Only LED display system with true geographic station mapping
- **Web Control Interface**: Remote control from any device on your network
- **Customizable Display**: Adjustable brightness, colors, and multiple display modes
- **Reliable Operation**: Automatic recovery, health monitoring, and daily maintenance

## Hardware

| Component | Notes |
|-----------|-------|
| Raspberry Pi Zero 2W | Main controller |
| WS2812B LEDs | Custom PCB (\~\$120 for 5) or LED strips (\~\$20) |
| 5V 4A Power Supply | Powers Pi and LEDs |
| MicroSD Card (16GB+) | For OS and software |
| Display Enclosure | Picture frame or custom case |

**Total Cost**: $50–177 depending on LED choice

Complete PCB design files (Gerber + KiCad) are available in `hardware/PCB Production/`. See the [Bill of Materials](docs/bill_of_materials.md) for detailed pricing and sourcing.

## Documentation

| Guide | Description |
|-------|-------------|
| [Quick Start Guide](deployment/quick_start/QUICK_START_GUIDE.md) | Step-by-step setup walkthrough |
| [Complete Setup Guide](docs/complete_setup_guide.md) | Detailed manual configuration |
| [Bill of Materials](docs/bill_of_materials.md) | Hardware pricing and sourcing |
| [Hardware Assembly](docs/hardware_assembly_guide.md) | PCB assembly instructions |
| [Operations & Troubleshooting](docs/operations_and_troubleshooting.md) | Maintenance and problem solving |
| [Transit System Adaptation](docs/transit_system_adaptation_guide.md) | Adapt for other transit systems |
| [Map Making with QGIS](docs/map_making_with_qgis.md) | Create custom transit maps |

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Test on Raspberry Pi Zero 2W hardware
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push and open a Pull Request

Follow existing code style, update documentation for new features, and add comments for complex logic.

## License

MIT License – See [LICENSE](LICENSE.txt) for details.

Copyright © 2025 Thomas Underwood

<details>
<summary>Disclaimers & Attributions</summary>

### AI Assistance
This project was developed with the assistance of AI coding tools. All code has been reviewed, tested, and validated on actual hardware.

### Data Sources
This project uses data from:
- **MBTA and MassDOT** – Transit data via [MBTA V3 API](https://api-v3.mbta.com/)
- **MassGIS** – Geographic and mapping data

All data is provided "as is" without warranties. This project is not affiliated with, endorsed by, or sponsored by MBTA, MassDOT, MassGIS, or the Commonwealth of Massachusetts.
</details>

## Support

- Check the [Operations and Troubleshooting Guide](docs/operations_and_troubleshooting.md)
- Review logs: `sudo journalctl -u mbta_display -n 100`
- Open an issue on GitHub with your Pi model, OS version, and error details
- [MBTA V3 API Documentation](https://api-v3.mbta.com/) · [Raspberry Pi GPIO Pinout](https://pinout.xyz/) · [Adafruit NeoPixel Guide](https://learn.adafruit.com/adafruit-neopixel-uberguide)
