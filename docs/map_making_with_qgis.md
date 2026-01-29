# Map Making with QGIS

Create custom transit maps using QGIS and MassGIS data for PCB design or display visualizations.

> **System Requirements:** QGIS is computationally intensive. Recommended: 16GB+ RAM, dedicated GPU, SSD. Minimum: 8GB RAM, modern multi-core processor.

## Overview

1. [Install QGIS](#install-qgis)
2. [Download Data](#download-data)
3. [Set Up Project](#set-up-project)
4. [Add & Style Layers](#add--style-layers)
5. [Create Print Layout](#create-print-layout)
6. [Export](#export)

---

## Install QGIS

Download the **Long Term Release (LTR)** from [qgis.org/download](https://qgis.org/download/).

---

## Download Data

MassGIS provides free geographic data: [mass.gov/info-details/massgis-data-layers](https://www.mass.gov/info-details/massgis-data-layers)

**Recommended layers:**
- [MassDOT Roads](https://www.mass.gov/info-details/massgis-data-massgis-massdot-roads)
- [Hydrography 25k](https://www.mass.gov/info-details/massgis-data-massdep-hydrography-125000)
- [MBTA Rapid Transit](https://www.mass.gov/info-details/massgis-data-mbta-rapid-transit)
- [Open Space](https://www.mass.gov/info-details/massgis-data-protected-and-recreational-openspace)

---

## Set Up Project

1. `Project > New`, then `Project > Save As` (e.g., "MBTA_RedLine_Map.qgz")
2. Set CRS: `Project > Properties > CRS` → **EPSG:26986** (Massachusetts State Plane NAD83)

**Tip:** Keep downloaded data in the same folder as your project file.

---

## Add & Style Layers

### Adding Layers

In the Browser panel, navigate to your data folder and double-click layers to add:
- Use POLY.shp files for filled areas (parks, water)
- For MBTA: import both ARC (tracks) and NODES (stations)
- For roads: EOTMAJROADS_ARC and EOTMINROADS_ARC

### Layer Order (top to bottom)

1. MBTA Nodes
2. MBTA Arc
3. Roads (Major)
4. Roads (Minor)
5. Water Bodies
6. Parks/Open Space

### Fix Water Layer Boundaries

Remove internal boundary lines in water layer:
1. `Processing > Toolbox` → "Fix Geometry" → Run on water layer
2. `Processing > Toolbox` → "Dissolve" → Run on fixed layer (leave dissolve fields empty)
3. Delete old water layers

### Styling Examples

**Water (Blue):** Right-click → Properties > Symbology → Simple fill
- Fill: #A5BFDD, Stroke: #000000 (0.2mm)

**Parks (Green):** Simple fill
- Fill: #C7E9C0, Stroke: #31A354 (0.1mm)

**Roads:** Categorized by "CLASS" field
- Class 1: 1.0mm, Class 2: 0.5mm, Class 3: 0.3mm, Color: #000000

**MBTA Lines:** Categorized by "LINE" field
- Red: #DA291C, Orange: #ED8B00, Blue: #003DA5, Green: #00843D
- Width: 1–3mm

**Station Labels:** Properties > Labels > Single Labels
- Select station name field, 8–10pt font, white buffer (1mm)

---

## Create Print Layout

1. `Project > New Print Layout` → Name it
2. Set page size in Item Properties
3. `Add Item > Add Map` → Draw rectangle
4. Configure in Item Properties:
   - Set scale (1:100k works for Red Line on 8"×10")
   - Use "Move Item Content" to position
   - Add 0.25–0.5" margins
   - Lock map when done
5. Add: Scale bar, North arrow, Title (`Add Item` menu)

---

## Export

### For PCB Design (SVG)

1. `Layout > Export as SVG`
2. Open in Illustrator/Inkscape
3. Simplify paths, adjust positions
4. Convert to black/white (KiCad sees only filled/not-filled)
5. Use Minus Front/Cropping for proper rendering
6. Save as plain SVG
7. Import to KiCad, place LEDs, connect, manufacture

**Tip:** For PCB design help, use online tutorials and LLMs. I was entirely self-taught this way!

### For General Display

Export as PNG or PDF at 300 DPI. PDFs maintain vector quality.

---

## Tips

### Performance
- Simplify geometries: `Vector > Geometry Tools > Simplify` (10–50m tolerance)
- Create spatial indexes: Layer Properties > Source
- Use scale-dependent rendering
- Clip data to your area of interest

### PCB Considerations
- Exact geographic accuracy isn't always practical—consider schematic positioning
- Print at 100% scale on paper to verify LED placement

### Attribution

Include in documentation:
```
Map data provided by MassGIS. Data is provided "as is" and may not be accurate or current.
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Layer won't load | Ensure all shapefile components (.shp, .shx, .dbf, .prj) are together |
| Map distorted | Verify all layers use EPSG:26986 |
| QGIS slow/crashes | Close unnecessary layers, filter features, restart periodically |
| Roads too cluttered | Filter to Class 1 only, use scale-dependent rendering |

---

## Resources

- [QGIS Documentation](https://docs.qgis.org/)
- [QGIS Tutorials](https://www.qgistutorials.com/)
- MassGIS Contact: massgismail@mass.gov
