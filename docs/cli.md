# CharlieBoard terminal CLI

Manage display settings from SSH or Raspberry Pi Connect without using the web UI on port 8000.

Install with the project (`pip install -e .`). The setup script puts `venv/bin` on your PATH in `/etc/profile.d/mbta_led_controller.sh`, so `charlieboard` works in new SSH or Pi Connect sessions. In the same terminal window where you just ran setup, use the full path once: `~/CharlieBoard/venv/bin/charlieboard show`.

## Commands

### Show settings

```bash
charlieboard show
```

Prints route, display mode, power, bedtimes, brightness, and colors.

### Set display mode

```bash
charlieboard set mode vehicles    # vehicles | occupancy | speed | rainbow
```

Picked up by the running display on the next MBTA stream event (usually within seconds).

### Set power

```bash
charlieboard set power on
charlieboard set power off
```

### Set bedtimes

```bash
charlieboard set bedtime --start 22:00 --end 07:00
charlieboard set bedtime --start 23:30    # end unchanged
charlieboard set bedtime --end 06:00      # start unchanged
```

Times use 24-hour `HH:MM` format.

### Set colors (legend / color keys)

```bash
charlieboard set color stopped 255,0,0
charlieboard set color incoming #ff4b4b
charlieboard set color max_occupancy 255 128 0
```

**Color names**

| Mode | Names |
|------|--------|
| vehicles | `stopped`, `incoming`, `transit` |
| speed | `min_speed`, `max_speed`, `null_speed` |
| occupancy | `min_occupancy`, `max_occupancy`, `null_occupancy` |

**Color formats:** `#RRGGBB`, `R,G,B`, or `R G B` (0–255 per channel).

### Set route

```bash
sudo charlieboard set route Green-B
```

Valid routes: `Red`, `Blue`, `Orange`, `Green-All`, `Green-B`, `Green-C`, `Green-D`, `Green-E`.

Route changes require restarting services (station maps and the MBTA stream filter are set at startup). The CLI restarts `mbta_display` and `mbta_monitor` automatically after saving. Use `sudo` if `systemctl restart` needs elevated permissions.

### Custom .env path

```bash
charlieboard --env /path/to/.env show
```

## Web UI sync

- Settings are stored in `.env`; the web UI reads the same file on page load (`GET /get_settings`).
- Reload the browser after CLI changes to refresh the form.
- The web UI does not display route (setup-only); saving from the web will not overwrite a CLI route change.

## Related commands

| Command | Purpose |
|---------|---------|
| `display_status` | System health and metrics |
| `display_reboot` | Restart display + monitor services |
