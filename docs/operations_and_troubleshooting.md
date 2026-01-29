# Operations and Troubleshooting Guide

Day-to-day operations and troubleshooting for the MBTA LED Controller.

## Service Management

### Control Commands

```bash
sudo systemctl <command> mbta_display.service
sudo systemctl <command> mbta_monitor.service
```

| Command | Description |
|---------|-------------|
| `start` | Start service |
| `stop` | Stop service |
| `restart` | Restart (use after config changes) |
| `status` | Check if running |
| `enable` | Auto-start on boot |
| `disable` | Disable auto-start |

### Viewing Logs

```bash
# Live logs
sudo journalctl -u mbta_display -f

# Last 100 lines
sudo journalctl -u mbta_display -n 100

# Today's logs
sudo journalctl -u mbta_display --since today

# Errors only
sudo journalctl -u mbta_display -p err

# Application logs
tail -f ~/mbta_led_controller/logs/mbta_display.log
```

### Configuration Changes

```bash
nano ~/mbta_led_controller/.env
sudo systemctl restart mbta_display.service
```

Most settings can also be changed via the web interface without restart.

---

## Troubleshooting

### LEDs Don't Light Up

**1. Test with red_test.py:**
```bash
cd ~/mbta_led_controller
source venv/bin/activate
sudo -E venv/bin/python tests/red_test.py
```

**2. Check wiring:**
- Data wire → GPIO 18 (physical pin 12)
- Ground from Pi → LED power supply ground (shared ground required)
- LEDs have 5V power supply (not from Pi's 5V pin)
- Data wire is first in chain (check LED strip direction arrows)

**3. Check settings:**
- Power not set to "off" in web interface
- Not in bedtime hours
- Brightness not set to 0

**Note on logic level shifters:** Generally not needed for WS2812B-2020 LEDs with shared power supply. See [Adafruit NeoPixel Guide](https://learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels) for details.

### Service Won't Start

```bash
# Check status for error details
sudo systemctl status mbta_display.service

# View recent logs
sudo journalctl -u mbta_display -n 50
```

**Common causes:**
- Wrong paths in service file (verify username/paths match)
- Missing `.env` file in project root
- Invalid MBTA API key

### Network/API Issues

```bash
# Test API connectivity (replace YOUR_API_KEY)
curl -s "https://api-v3.mbta.com/vehicles?api_key=YOUR_API_KEY&filter[route]=Red" | head -c 200

# Check for connection errors
sudo journalctl -u mbta_display -p err
```

### Web Interface Not Accessible

```bash
# Check service status
sudo systemctl status mbta_display.service

# Check if port 8000 is listening
sudo netstat -tlnp | grep 8000

# Test locally
curl http://localhost:8000
```

**Also verify:**
- You're on the same network as the Pi
- Try IP address instead of hostname: `http://192.168.x.x:8000`

### Settings Not Saving

```bash
# Check .env file location and permissions
ls -la ~/mbta_led_controller/.env

# View application logs for errors
tail -f ~/mbta_led_controller/logs/*.log
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Check status | `display_status` or `sudo systemctl status mbta_display` |
| Restart display | `sudo systemctl restart mbta_display.service` |
| View live logs | `sudo journalctl -u mbta_display -f` |
| Edit config | `nano ~/mbta_led_controller/.env` |
| Test LEDs | `sudo -E venv/bin/python tests/red_test.py` |
| Find Pi's IP | `hostname -I` |

---

## Additional Resources

- [Complete Setup Guide](complete_setup_guide.md) - Full installation instructions
- [Hardware Assembly Guide](hardware_assembly_guide.md) - Wiring and assembly
- [FAQ](FAQ.md) - Common questions
- [GitHub Issues](https://github.com/tomunderwood99/CharlieBoard/issues) - Report bugs
