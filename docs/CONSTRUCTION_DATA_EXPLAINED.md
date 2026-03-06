# Construction Data Calculations - Technical Documentation

## Overview
MAARGDARSHAN now generates construction-ready outputs for field engineers. This document explains how we calculate gradient and cut/fill volumes.

---

## 1. Gradient Analysis (Slope Percentage)

### Formula
```
Gradient (%) = (Elevation Change / Horizontal Distance) × 100
```

### Example
- Point A: Elevation 2000m
- Point B: Elevation 2050m (50m away horizontally)
- Gradient = (2050 - 2000) / 50 × 100 = **100%** (very steep!)

### IRC Standards (Indian Roads Congress)
- **Maximum gradient for hilly terrain**: 10% (IRC SP 73:2018)
- **Preferred gradient**: 6-8%
- **Exceptional cases**: Up to 12% for short stretches

### What This Means
- **5% gradient**: Road rises 5m for every 100m horizontal distance
- **10% gradient**: Road rises 10m for every 100m (maximum allowed)
- **>10% gradient**: Requires switchbacks or tunnels

---

## 2. Cut/Fill Volume Calculations

### What is Cut/Fill?
- **CUT**: Remove earth where ground is higher than road design level
- **FILL**: Add earth where ground is lower than road design level

### Our Calculation Method

#### Step 1: Determine Design Elevation
```
Design Elevation = Smoothed profile respecting max gradient (10%)
```

We interpolate linearly from start to end, ensuring the road doesn't exceed 10% gradient.

#### Step 2: Calculate Cut/Fill Depth
```
Cut/Fill Depth = Ground Elevation - Design Elevation
```

- **Positive value** = CUT (remove earth)
- **Negative value** = FILL (add earth)

#### Step 3: Calculate Cross-Sectional Area

**For CUT (trapezoidal section):**
```
Area = (Road Width + Side Slope × Depth) × Depth
```
- Road Width = 5.5m (single lane with shoulders)
- Side Slope = 1.5:1 (1.5 horizontal : 1 vertical)

**Example CUT:**
- Depth = 3m
- Area = (5.5 + 1.5 × 3) × 3 = (5.5 + 4.5) × 3 = **30 m²**

**For FILL (trapezoidal section):**
```
Area = (Road Width + Side Slope × Depth) × Depth
```
- Road Width = 5.5m
- Side Slope = 2:1 (2 horizontal : 1 vertical, gentler for stability)

**Example FILL:**
- Depth = 2m
- Area = (5.5 + 2 × 2) × 2 = (5.5 + 4) × 2 = **19 m²**

#### Step 4: Calculate Volume for Each Segment
```
Volume (m³) = Cross-Sectional Area × Length
```

For 50m segment:
- CUT volume = 30 m² × 50m = **1,500 m³**
- FILL volume = 19 m² × 50m = **950 m³**

#### Step 5: Total Earthwork
```
Total CUT = Sum of all CUT volumes
Total FILL = Sum of all FILL volumes
Balance = Total CUT - Total FILL
```

### Earthwork Balance Status
- **Balanced**: |Balance| < 1,000 m³ (ideal - reuse cut material for fill)
- **Excess Cut**: Balance > 1,000 m³ (need to dispose extra earth)
- **Excess Fill**: Balance < -1,000 m³ (need to borrow earth from elsewhere)

---

## 3. Real Data Integration

### Data Sources Used

#### DEM (Digital Elevation Model)
- **Source**: SRTM 30m resolution
- **Usage**: Ground elevation at every GPS point
- **Accuracy**: ±10m vertical, ±20m horizontal

#### Rivers GeoJSON
- **Source**: HydroRIVERS v1.0
- **Features**: 1,955 rivers in Uttarkashi
- **Usage**: 
  - Bridge location detection
  - Flood risk assessment (proximity to rivers)
  - Cost estimation (bridges add ₹1 crore each)

#### Settlements GeoJSON
- **Source**: OpenStreetMap
- **Features**: 5,388 villages/towns in Uttarkashi
- **Usage**:
  - Connectivity analysis
  - Labor availability
  - Material sourcing locations

#### Rainfall Data
- **Source**: IMD (India Meteorological Department)
- **Usage**: Seasonal risk assessment
- **Uttarkashi**: ~1,500mm/year

---

## 4. Construction-Ready Outputs

### GPS Waypoints (Every 50m)
```json
{
  "chainage_m": 0,
  "lat": 30.726800,
  "lon": 78.435400,
  "ground_elevation_m": 2175,
  "design_elevation_m": 2175,
  "cut_fill_depth_m": 0.0,
  "cut_fill_type": "balanced",
  "cut_fill_volume_m3": 0.0,
  "gradient_percent": 0.0
}
```

### Downloadable Formats

#### KML (Google Earth)
- Open in Google Earth to visualize 3D route
- Shows elevation profile
- Includes cut/fill volumes in description

#### GPX (GPS Devices)
- Load into Garmin, Trimble, or other GPS units
- Navigate to exact waypoints in the field
- Mark with survey pegs

#### GeoJSON (GIS Software)
- Import into QGIS, ArcGIS, or AutoCAD Civil 3D
- Perform detailed analysis
- Generate construction drawings

### Field Instructions
```json
{
  "surveying": "Use GPS device to navigate to each chainage point. Mark with survey pegs every 50m.",
  "leveling": "Use dumpy level or total station to set formation level at design elevation.",
  "earthwork": "Cut 45,000 m³ and fill 38,000 m³. Excess cut.",
  "gradient_control": "Maximum gradient: 8.5%. Ensure proper drainage."
}
```

---

## 5. Bridge Detection

### Algorithm
1. For each route segment (50m)
2. Check if any river crosses the segment
3. Use bounding box intersection test
4. Record river name and location

### Output
```json
{
  "lat": 30.8234,
  "lon": 78.5678,
  "river_name": "Bhagirathi River",
  "bridge_required": true,
  "estimated_span_m": 30
}
```

### Cost Impact
- Each bridge adds **₹1 crore** (~$120,000 USD)
- Construction time: **30 days per bridge**

---

## 6. Nearby Settlements

### Algorithm
1. For each waypoint
2. Find settlements within 5km radius
3. Calculate distance using Haversine formula
4. Sort by proximity

### Output
```json
{
  "name": "Gangotri",
  "type": "town",
  "lat": 30.9993,
  "lon": 78.9394,
  "distance_from_route_km": 0.5,
  "population": "Unknown"
}
```

### Usage
- **Labor sourcing**: Hire workers from nearby villages
- **Material supply**: Aggregate, sand, cement from local sources
- **Connectivity**: Prioritize routes connecting more settlements

---

## 7. Accuracy & Limitations

### Strengths
✅ Uses real DEM data for elevations
✅ Detects actual river crossings
✅ Identifies real settlements
✅ Follows IRC standards for gradients
✅ Generates industry-standard formats (KML, GPX, GeoJSON)

### Limitations
⚠️ Simplified routing (not full pathfinding algorithm)
⚠️ Cut/fill assumes uniform soil (doesn't account for rock vs soil)
⚠️ Bridge spans are estimates (need detailed survey)
⚠️ Doesn't account for land acquisition costs
⚠️ No geotechnical analysis (soil bearing capacity, etc.)

### For Production Use
For actual construction, you would need:
1. Detailed topographic survey (1:1000 scale)
2. Geotechnical investigation (soil testing)
3. Hydrological study (flood levels, drainage)
4. Environmental impact assessment
5. Land acquisition and forest clearance
6. Detailed design by licensed civil engineer

---

## 8. Cost Estimation Formula

```
Total Cost = Base Cost + Terrain Factor + Bridge Cost

Where:
- Base Cost = Distance (km) × ₹50 lakh/km
- Terrain Factor = Base Cost × (Terrain Risk / 200)
- Bridge Cost = Number of Bridges × ₹1 crore
```

### Example
- Distance: 60 km
- Terrain Risk: 70/100
- Bridges: 3

```
Base Cost = 60 × 50,00,000 = ₹30 crore
Terrain Factor = 30 × (70/200) = ₹10.5 crore
Bridge Cost = 3 × 1 = ₹3 crore
Total = ₹43.5 crore (~$5.2 million USD)
```

---

## 9. Timeline Estimation Formula

```
Total Days = Base Days + Terrain Factor + Bridge Days

Where:
- Base Days = Distance (km) × 15 days/km
- Terrain Factor = Base Days × (Terrain Risk / 300)
- Bridge Days = Number of Bridges × 30 days
```

### Example
- Distance: 60 km
- Terrain Risk: 70/100
- Bridges: 3

```
Base Days = 60 × 15 = 900 days
Terrain Factor = 900 × (70/300) = 210 days
Bridge Days = 3 × 30 = 90 days
Total = 1,200 days (~3.3 years)
```

---

## References

1. **IRC SP 73:2018** - Manual for Survey, Investigation and Preparation of Road Projects
2. **IRC 52:2019** - Guidelines for Geometric Design of Rural (Non-Urban) Highways
3. **SRTM DEM** - Shuttle Radar Topography Mission
4. **HydroRIVERS** - Global River Network Database
5. **OpenStreetMap** - Collaborative mapping project

---

**Generated by MAARGDARSHAN v2.0**
*AI-Powered Rural Infrastructure Planning for Bharat*
