# Frontend Enhancement Plan

## Current State
- ✅ Shows 2 routes (Shortest, Safest)
- ✅ Shows basic metrics (distance, cost, risk)
- ❌ Does NOT show construction data (bridges, settlements, earthwork)
- ❌ Does NOT show download buttons (KML/GPX/GeoJSON)
- ❌ Does NOT consider existing roads

## Missing Features

### 1. Construction Data Display
**What to add:**
- Bridges required (count + locations on map)
- Nearby settlements (list with distances)
- Earthwork summary (cut/fill volumes)
- Download buttons for KML/GPX/GeoJSON
- Gradient profile chart

**Where to show:**
- Expand route cards with "Details" section
- Add bridge markers on map (🌉 icon)
- Add settlement markers on map (🏘️ icon)
- Add download panel below route cards

### 2. Additional Route Types
**Add 3rd route:**
- **Most Cost-Effective**: Uses existing roads where available
- Checks OSM data for existing highways/roads
- Calculates cost as:
  - New construction: ₹50 lakh/km
  - Upgrade existing: ₹15 lakh/km
  - Use existing: ₹0/km

### 3. Existing Road Integration
**Critical missing feature:**
- OSM data has `highway` tag for existing roads
- Types: motorway, trunk, primary, secondary, tertiary, unclassified, residential
- We should:
  1. Check if route passes near existing roads
  2. Calculate % of route using existing infrastructure
  3. Adjust cost accordingly
  4. Show "Existing Road Utilization: 45%" in UI

## Implementation Priority

### Phase 1: Show Construction Data (30 min)
1. Update frontend to display:
   - Bridges count in route card
   - Settlements count in route card
   - Earthwork summary (cut/fill)
   - Download buttons

### Phase 2: Add 3rd Route Type (1 hour)
1. Update Lambda to generate "Cost-Effective" route
2. This route considers existing roads from OSM
3. Calculate actual cost savings

### Phase 3: Existing Road Detection (2 hours)
1. Load OSM road network from S3
2. Check if route segments overlap with existing roads
3. Classify road quality (highway vs dirt road)
4. Adjust costs and construction time
5. Show on map with different colors:
   - Blue: New construction needed
   - Green: Existing road (use as-is)
   - Orange: Existing road (needs upgrade)

## Cost Calculation with Existing Roads

### Current (Wrong)
```
Total Cost = Distance × ₹50 lakh/km + Bridges × ₹1 crore
```

### Correct (With Existing Roads)
```
For each segment:
  - If no existing road: ₹50 lakh/km (new construction)
  - If existing highway: ₹0/km (use as-is)
  - If existing dirt road: ₹15 lakh/km (upgrade)
  - If existing damaged road: ₹25 lakh/km (reconstruct)

Total Cost = Sum of segment costs + Bridges × ₹1 crore
```

### Example
Route: 100 km total
- 40 km uses existing highway: 40 × ₹0 = ₹0
- 30 km needs upgrade: 30 × ₹15 lakh = ₹4.5 crore
- 30 km new construction: 30 × ₹50 lakh = ₹15 crore
- 2 bridges: 2 × ₹1 crore = ₹2 crore
- **Total: ₹21.5 crore** (vs ₹52 crore without existing roads!)

## OSM Road Data Structure

```json
{
  "type": "Feature",
  "geometry": {
    "type": "LineString",
    "coordinates": [[78.123, 30.456], ...]
  },
  "properties": {
    "highway": "primary",  // motorway, trunk, primary, secondary, tertiary
    "surface": "paved",    // paved, unpaved, gravel, dirt
    "width": "7",          // meters
    "lanes": "2",
    "condition": "good"    // good, fair, poor
  }
}
```

## UI Mockup

### Route Card (Enhanced)
```
┌─────────────────────────────────────┐
│ 🛣️ Most Cost-Effective Route       │
│ 💰 Medium Risk                      │
├─────────────────────────────────────┤
│ Distance: 85 km                     │
│ Elevation: 1200 m                   │
│ Cost: ₹28 crore (45% savings!)     │
│ Duration: 850 days                  │
├─────────────────────────────────────┤
│ 🌉 Bridges: 3 required              │
│ 🏘️ Settlements: 12 nearby           │
│ 🚧 Existing Road: 45% utilization   │
├─────────────────────────────────────┤
│ Earthwork:                          │
│ • Cut: 2.5M m³                      │
│ • Fill: 1.8M m³                     │
│ • Balance: Excess cut               │
├─────────────────────────────────────┤
│ [Download KML] [GPX] [GeoJSON]     │
└─────────────────────────────────────┘
```

## Next Steps

1. **Quick Win (Tonight)**: Update frontend to show bridges, settlements, earthwork
2. **Tomorrow**: Add existing road detection to Lambda
3. **Tomorrow**: Add 3rd route type (Cost-Effective)
4. **Tomorrow**: Update UI with download buttons and enhanced metrics

