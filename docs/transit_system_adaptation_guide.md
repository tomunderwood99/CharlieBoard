# Transit System Adaptation Guide

How to adapt The CharlieBoard for transit systems other than the MBTA.

**Disclaimer:** This guide was written with AI assistance and hasn't been fully tested. If you complete an adaptation, please share your experience!

## Overview

### What's MBTA-Specific

| Component | File | Change Required |
|-----------|------|-----------------|
| API Integration | `main/mbta_stream.py` | Yes |
| Station ID Maps | `config/station_id_maps.py` | Yes |
| Station LED Maps | `config/station_led_maps.py` | Yes |
| PCB/Map Design | `hardware/` | Yes |

### What's Reusable As-Is

- LED Controller (`display/controller/`)
- Display Modes (`display/modes/`)
- Web Interface (`web_interface/`)
- Monitoring (`monitoring/`)
- System Services (`deployment/systemd/`)

## Prerequisites

- Python proficiency
- Understanding of REST APIs
- Your transit system's API documentation and credentials
- Geographic data for your transit system (OpenStreetMap, local GIS)
- QGIS or similar for map creation

## Step 1: Research Your Transit API

### Common API Standards
- **GTFS Realtime** - North American and European systems
- **SIRI** - Common in Europe
- **Custom REST** - TfL, NYC MTA, etc.

### Required Data
   - ✅ Real-time vehicle positions
   - ✅ Vehicle direction/destination
   - ✅ Station/stop associations
- ⚠️ Occupancy (optional)
- ⚠️ Speed (optional)

### API Resources by Region

| Region | Resources |
|--------|-----------|
| **US** | [NYC OpenData](https://opendata.cityofnewyork.us/), [Chicago Data Portal](https://data.cityofchicago.org/) |
| **UK** | [TfL Open Data](https://tfl.gov.uk/info-for/open-data-users/) |
| **Europe** | [Île-de-France Mobilités](https://data.iledefrance-mobilites.fr/), [Berlin Open Data](https://daten.berlin.de/) |
| **General** | [OpenStreetMap](https://www.openstreetmap.org/) |

## Step 2: Create Station ID Maps

Maps API station identifiers to human-readable names.

```python
# config/station_id_maps.py

def your_line_map():
    return {
        'API_STATION_ID_1': 'Station Name',
        'API_STATION_ID_2': 'Station Name',
        # Multiple IDs can map to same station (platforms, directions)
        'station_platform_1': 'Central Station',
        'station_platform_2': 'Central Station',
    }

station_id_maps = {
    "YourLine": your_line_map,
}
```

**Tip:** Create a discovery script to find all station IDs from your API:
```python
import requests
response = requests.get("https://api.yourtransit.com/vehicles")
station_ids = set(v['stop_id'] for v in response.json()['vehicles'])
for sid in sorted(station_ids):
    print(f"'{sid}': 'STATION_NAME',")
```

## Step 3: Create Station LED Maps

Maps station names to physical LED positions.

```python
# config/station_led_maps.py

def your_line_led_map():
    return (
        # Direction 1 (e.g., outbound)
        {
            "Start Station": 0,
            "Station 2": 1,
            "Station 3": 2,
            "End Station": 3,
        },
        # Direction 2 (e.g., inbound) - typically reverse order
        {
            "End Station": 7,
            "Station 3": 6,
            "Station 2": 5,
            "Start Station": 4,
        }
    )

station_led_maps = {
    "YourLine": your_line_led_map,
}
```

**LED Count:** `(stations × 2) + branches`

## Step 4: Modify API Integration

Modify `main/mbta_stream.py` for your API:

### Key Changes Needed

1. **API endpoint and authentication**
2. **Field name mapping** (your API → internal format)
3. **Streaming method** (SSE, WebSocket, or polling)

### Data Format Mapping

| Internal Field | Common API Variants |
|---------------|---------------------|
| `id` | `vehicle_id`, `trip_id`, `label` |
| `current_status` | `status`, `state`, `position_status` |
| `direction_id` | `direction`, `route_direction_name` |
| `stop_id` | `station_id`, `current_stop` |

### Example: Polling-Based API

```python
class YourTransitStream:
    def poll_vehicles(self):
        response = requests.get(
            f"{self.api_base}/vehicles",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        for vehicle in response.json()['data']:
            self.mode_manager.process_vehicle({
                'id': vehicle['vehicleId'],
                'stop_id': vehicle['currentStop']['id'],
                'current_status': self.map_status(vehicle['status']),
                'direction_id': 0 if vehicle['direction'] == 'outbound' else 1,
            })
        time.sleep(5)  # Poll interval
```

### Status Mapping

```python
def map_status(self, api_status):
    return {
        'APPROACHING': 'INCOMING_AT',
        'AT_STOP': 'STOPPED_AT',
        'DEPARTED': 'IN_TRANSIT_TO',
        'EN_ROUTE': 'IN_TRANSIT_TO',
    }.get(api_status, 'IN_TRANSIT_TO')
```

## Step 5: Create Your Map

Follow [Map Making with QGIS](map_making_with_qgis.md), substituting your region’s data and CRS. An example project (layers, QGIS project file, and PDF) is available in the [QGIS Example Google Drive folder](https://drive.google.com/drive/folders/1vFNIh-ThJNZXUUT2JSJMrOyUVWq9bhA2?usp=drive_link).

### Coordinate Reference System (CRS)

| City | CRS |
|------|-----|
| London | EPSG:27700 |
| NYC | EPSG:2263 |
| Paris | EPSG:27572 |
| Berlin | EPSG:25833 |
| Tokyo | EPSG:6677 |
| Sydney | EPSG:7856 |

### Official Line Colors

| System | Line | Hex |
|--------|------|-----|
| London Underground | Central | `#DC241F` |
| NYC Subway | 1/2/3 | `#EE352E` |
| Paris Métro | M1 | `#FFCD00` |
| Berlin U-Bahn | U1 | `#55A030` |

## Step 6: Testing

### Validate Station Mappings

```python
from config.station_id_maps import station_id_maps
from config.station_led_maps import station_led_maps

def validate(line):
    id_map = station_id_maps[line]()
    outbound, inbound = station_led_maps[line]()
    
    id_stations = set(id_map.values())
    led_stations = set(outbound.keys())
    
    missing = id_stations - led_stations
    extra = led_stations - id_stations
    
    if missing: print(f"Missing in LED map: {missing}")
    if extra: print(f"Extra in LED map: {extra}")
    if not missing and not extra: print("✓ All stations mapped")

validate("YourLine")
```

### Test API Connection

```bash
curl -H "Authorization: Bearer YOUR_KEY" https://api.yourtransit.com/vehicles
```

### Test LEDs

   ```bash
sudo -E venv/bin/python tests/red_test.py
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Station not found" | Unknown ID from API | Add ID to station_id_maps.py |
| Wrong station lights up | Name mismatch | Check spelling/capitalization in both maps |
| No vehicles appear | API issue or wrong line name | Check API response, verify line identifier |
| Wrong direction | Direction mapping inverted | Swap outbound/inbound maps |
| Rate limiting | Polling too fast | Increase poll interval |

## Time Estimate

| Task | Hours |
|------|-------|
| API research | 2–4 |
| Station ID mapping | 1–2 |
| LED position mapping | 2–3 |
| API integration code | 4–8 |
| Map creation (QGIS) | 3–6 |
| PCB design | 8–16 |
| Testing | 4–8 |
| **Total** | **24–47** |

## Contributing

If you adapt this for another transit system, consider contributing:
- Station maps (config files)
- API integration code
- PCB design files
- Documentation of challenges faced

**Good luck!** If you build displays for other systems, please share with the community.
