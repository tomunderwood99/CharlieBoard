# Hardware Assembly Guide

Assembly instructions for your MBTA LED display.

## Safety

- Work in ventilated area when soldering
- Disconnect power before making connections
- Double-check polarity (+5V and Ground) before powering on

## Tools Required

**Essential:**
- Soldering iron (300–350°C)
- Solder (60/40 or 63/37 rosin core)
- Wire strippers (22–24 AWG)
- Wire cutters
- Screwdriver

**Recommended:**
- Helping hands/third hand
- Heat shrink tubing
- Multimeter

## Components

See [Bill of Materials](bill_of_materials.md) for complete list.

**Core:**
- Raspberry Pi Zero 2W
- MicroSD card (16GB+)
- WS2812B LED strip OR custom PCB
- 5V 4A USB-C power supply
- Wires (22–24 AWG for data, 18–20 AWG for power)

**Optional:**
- Picture frame or enclosure
- JST connectors
- 1N5819 Schottky diode
- 3D printed Pi case

---

## Assembly Options

### Option 1: LED Strip (Cheapest)
- **Pros:** Quick, cheap, beginner-friendly
- **Cons:** Less professional appearance
- **Best for:** First builds, prototyping, tight budgets

### Option 2: Custom PCB (Professional)
- **Pros:** Clean look, exact LED placement
- **Cons:** Higher cost, requires PCB fabrication
- **Best for:** Permanent installations

---

## Option 1: LED Strip Assembly

### Step 1: Prepare LED Strip

**LED counts per line:**
| Line | LEDs Needed |
|------|-------------|
| Red | 47 |
| Blue | 27 |
| Orange | 43 |
| Green (combined) | 131 |

Cut strip at marked cut points. Note data flow direction (arrows on strip).

### Step 2: Wire Connections

See [wiring diagram](../hardware/rpi_zero2w_ws2812b2020_wiring.pdf).

1. **Data:** GPIO 18 (pin 12) → LED strip DIN
2. **Ground:** Pi ground → LED strip ground AND power supply ground (**all grounds must be common**)
3. **Power:** 5V supply → LED strip 5V (**not from Pi's 5V pin**)

Use heat shrink on all solder joints.

### Step 3: Mount & Test

Mount LEDs to your display (poster, frame, etc.), then test with software.

---

## Option 2: Custom PCB Assembly

### Step 1: Order PCB

**Manufacturing files** in `hardware/PCB Production/`:
- `gerber_files.zip` - PCB fabrication
- `bom.csv` - Bill of materials
- `pos.csv` - Pick-and-place

**Recommended:** [JLCPCB](https://jlcpcb.com/) with assembly service (WS2812B-2020 LEDs are 2mm × 2mm).

**Specs:** 2-layer, 1.6mm thickness, 1oz copper, ENIG or HASL finish.

### Step 2: Inspect PCB

Check for:
- Cold solder joints
- Solder bridges
- Correct LED orientation

### Step 3: Connect to Pi

Create cable with:
- JST connector (PCB side)
- Dupont connectors (Pi GPIO side)
- Schottky diode (1N5819) on 5V line to protect Pi

**Connections:**
- Data → GPIO 18 (pin 12)
- Ground → Any ground pin
- 5V → Pin 2 or 4 (through diode)

### Step 4: Final Assembly

1. Remove front glass from picture frame
2. Mount PCB with push tabs, screws, or adhesive
3. Position Pi accessibly but hidden
4. Connect power supply

---

## Testing

```bash
cd ~/mbta_led_controller
source venv/bin/activate
sudo -E venv/bin/python tests/red_test.py
```

All LEDs should turn red. Press Ctrl+C to exit.

---

## Common Mistakes

| Mistake | Result | Fix |
|---------|--------|-----|
| No common ground | LEDs don't work | Connect Pi ground to LED power supply ground |
| Wrong LED direction | LEDs don't light | Check arrows on strip, data flows one direction |
| Insufficient power | Flickering | Use adequate supply (5V 3A+ for ~50 LEDs) |
| Powering LEDs from Pi | Dim/no light | Use separate 5V supply for LEDs |
| Wrong GPIO pin | No data | Use GPIO 18 (PWM-capable) |

---

## Next Steps

If software not installed, see [Quick Start Guide](../deployment/quick_start/QUICK_START_GUIDE.md).

For troubleshooting, see [Operations & Troubleshooting](operations_and_troubleshooting.md).
