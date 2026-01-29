# Bill of Materials

Complete parts list for building The CharlieBoard.

## Cost Summary

| Category | Cost |
|----------|------|
| Electronics | ~$165 |
| Hardware & Enclosure | ~$12 |
| **Total** | **~$177** |

*Most of the cost is the custom PCB (5-board minimum). Using LED strips instead brings total to ~$50.*

---

## Electronics

| Component | Qty | Price | Notes |
|-----------|-----|-------|-------|
| Raspberry Pi Zero 2W | 1 | $15 | Main controller |
| MicroSD Card (16GB+) | 1 | $8 | For OS and software |
| Custom PCB | 5 | $120 | With 47 WS2812B LEDs (assembled, min order 5) |
| 5V 4A USB-C Power Supply | 1 | $12 | Powers Pi and LEDs |
| USB-C to Wire Connector | 1 | $3 | Power connection |
| 1N5819 Schottky Diode | 1 | $0.25 | Protects GPIO pin |
| 3-pin JST Connectors | 2 | $1.50 | PCB power connection |
| Misc Wires | 1 set | $3 | Hookup wire |
| Heat Shrink Tubing | 1 set | $2 | Wire insulation |

## Hardware & Enclosure

| Component | Qty | Price | Notes |
|-----------|-----|-------|-------|
| 8"×10" Picture Frame | 1 | $10 | Display enclosure (remove glass) |
| 3D Printed Pi Case | 1 | $0.50 | ~15g PLA |
| M2.5×12mm Screws | 4 | $0.60 | Pi mounting |
| M2.5 Nuts | 4 | $0.40 | Pi mounting |

---

## Component Notes

### Raspberry Pi Zero 2W
Tested on Zero 2W, should work on Pi 3/4/5. Purchase from [Adafruit](https://www.adafruit.com/), [PiShop](https://www.pishop.us/), or [CanaKit](https://www.canakit.com/).

### Custom PCB
- Design files in `hardware/PCB Production/`
- Recommended: [JLCPCB](https://jlcpcb.com/) with assembly service
- WS2812B-2020 LEDs require baking before assembly—see [datasheet](https://www.mouser.com/pdfDocs/WS2812B-2020_V10_EN_181106150240761.pdf)

### 1N5819 Schottky Diode
Protects GPIO from backflow current. Critical for safe operation.

### Picture Frame
8"×10" works for Red Line PCB. Remove glass; modify back panel for JST connector clearance.

### 3D Printed Case
STL files in `hardware/RPI Case/`. Print at home or order from Craftcloud, Shapeways, etc.

---

## Budget Build (~$50)

Skip the custom PCB for a minimal working system:

| Component | Price |
|-----------|-------|
| Raspberry Pi Zero 2W | $15 |
| MicroSD Card | $8 |
| WS2812B LED Strip | $12 |
| 5V Power Supply | $10 |
| Misc Electronics | $5 |

**Trade-off:** Not geographically accurate, requires custom mounting.

---

## Self-Assembly PCB Option

Order bare PCBs (~$2–5 each) and hand-solder components.
- **Savings:** ~$60–80 per board
- **Difficulty:** High—WS2812B-2020 LEDs are 2mm × 2mm, requires reflow oven

---

## Bulk Orders

Custom PCB cost drops significantly with quantity. At 5 boards, cost is ~$24/board, bringing total build cost to ~$80 if the boards are split between 5 people.

---

## Where to Buy

| Category | Suppliers |
|----------|-----------|
| Electronics | Adafruit, DigiKey, Mouser, Amazon |
| PCB Manufacturing | JLCPCB (recommended), PCBWay, OSH Park |
| 3D Printing | Local maker spaces, Craftcloud, Shapeways |

---

## Not Included

- Soldering equipment (iron, solder, flux)
- Tools (wire strippers, screwdrivers, multimeter)
- Prices are estimates and vary by region/supplier
