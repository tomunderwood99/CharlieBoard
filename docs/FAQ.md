# Frequently Asked Questions (FAQ)

## General

### What is this project?
An open-source LED display system showing real-time MBTA train locations on a geographically accurate map. Each LED represents a station, lighting up to show where trains are.

### Do I need programming experience?
No. The automated setup script handles everything. If you can SSH into a Raspberry Pi, you can build this.

### How much does it cost?
**$50–200 USD** depending on components:
- Raspberry Pi Zero 2W: ~$15
- MicroSD Card (16GB): ~$8
- WS2812B LED Strip (~$15) or Custom PCB ($25–120)
- Power Supply (5V 4A): ~$10
- Frame & mounting: ~$10–20

See [Bill of Materials](bill_of_materials.md) for detailed pricing.

### How long does it take to build?
- **Hardware assembly**: 1–3 hours
- **Software setup**: 15–30 minutes (automated)

## Compatibility

### Can I use a different Raspberry Pi?
Yes. Tested on Pi Zero 2W, but should work on Pi 3/4/5. The original Pi Zero W may work but is slower.

### Can I adapt this for other transit systems?
Yes, with code modifications. See [Transit System Adaptation Guide](transit_system_adaptation_guide.md).

### Can I use different LEDs?
Designed for **WS2812B** (NeoPixel) addressable RGB LEDs. Other addressable types may work with code changes. Regular non-addressable LEDs won't work.

## Hardware

### Do I need the custom PCB?
No. You can use a standard WS2812B LED strip (cheaper, good for prototyping) or order the custom PCB (cleaner look, geographically accurate).

### My LEDs aren't lighting up
See [Operations & Troubleshooting](operations_and_troubleshooting.md#leds-dont-light-up) for a complete checklist.

### Can I power Pi and LEDs from the same supply?
Yes. A 5V 4A USB-C supply can power both. Must share common ground.

## Software

### Does this need WiFi?
Yes—for API data streaming and SSH access.

### What happens if internet goes down?
Display shows all red LEDs indicating connection issue. Automatically reconnects when internet returns.

### Do I need an MBTA API key?
Yes, but it's **free**: [api-v3.mbta.com](https://api-v3.mbta.com/)

### Can I access the web interface remotely?
Not by default. Options:
1. **Raspberry Pi Connect** (easiest)
2. **VPN** (Tailscale, WireGuard)
3. **Reverse proxy** (Cloudflare Tunnel, ngrok)

### How do I update the software?
```bash
cd ~/mbta_led_controller
git pull
sudo systemctl restart mbta_display.service
```

## Display Modes

### What do the different modes show?
- **Vehicles**: Train positions (stopped, approaching, in transit)
- **Speed**: Train speeds (green=slow, red=fast) — data limited
- **Occupancy**: Crowding levels — data limited
- **Rainbow**: Animated rainbow for testing/decoration

### What is bedtime mode?
Automatically turns off display during specified hours (e.g., 10 PM – 6 AM). Configurable via web interface.

### How often does the display update?
Real-time via MBTA API stream—typically every few seconds.

## Troubleshooting

For detailed troubleshooting, see [Operations & Troubleshooting](operations_and_troubleshooting.md).

## Other

### Is this project maintained?
Check the GitHub repository for recent activity.

### Can I sell displays built with this?
Yes (MIT license). Please credit the project and respect MBTA's API terms of service.

### Does the MBTA endorse this?
No. This is an independent project using publicly available MBTA data.

### Can I share my build?
Absolutely! Tag and share on social media—I'd love to see your builds.

**Still have questions?** Open an issue on GitHub.
