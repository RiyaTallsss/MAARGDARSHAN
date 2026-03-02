# MAARGDARSHAN - UI Wireframe

## Main Interface Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  MAARGDARSHAN - Rural Infrastructure Planning                   │
│  [Logo]                                    [User] [Settings] [?]│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────┐  ┌────────────────────────┐│
│  │                                 │  │  Route Planning        ││
│  │                                 │  │  ─────────────────     ││
│  │                                 │  │                        ││
│  │      SATELLITE MAP              │  │  Start Location:       ││
│  │      (Leaflet/MapBox)           │  │  [Uttarkashi Town   ▼] ││
│  │                                 │  │                        ││
│  │  • Route A (Red)                │  │  End Location:         ││
│  │  • Route B (Blue)               │  │  [Mountain Village  ▼] ││
│  │  • Route C (Green)              │  │                        ││
│  │                                 │  │  Constraints:          ││
│  │  [Risk Zones Overlay]           │  │  ☐ Avoid Flood Zones   ││
│  │  [Terrain Contours]             │  │  ☐ Minimize Cost       ││
│  │  [Settlements]                  │  │  ☐ Shortest Distance   ││
│  │                                 │  │                        ││
│  │  [Zoom +/-] [Layers] [Measure]  │  │  [Generate Routes]     ││
│  │                                 │  │                        ││
│  └─────────────────────────────────┘  └────────────────────────┘│
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Route Comparison & AI Analysis                                 │
│  ────────────────────────────────────────────────────────────   │
│                                                                 │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │   Metric     │   Route A    │   Route B    │   Route C    │  │
│  ├──────────────┼──────────────┼──────────────┼──────────────┤  │
│  │ Distance     │   17.6 km    │   17.5 km    │   18.1 km    │  │
│  │ Cost         │   $4.96M     │   $8.05M     │   $6.17M     │  │
│  │ Difficulty   │   41.3/100   │   56.7/100   │   38.4/100   │  │
│  │ Risk Score   │   35.2/100   │   52.8/100   │   28.9/100   │  │
│  │ Flood Risk   │   Low        │   High       │   Medium     │  │
│  │ Terrain Risk │   Medium     │   High       │   Low        │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
│                                                                 │
│  🤖 AI Recommendation (Amazon Bedrock):                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Route C (Scenic Route) is recommended for this project.     ││
│  │                                                             ││
│  │ Rationale:                                                  ││
│  │ • Lowest construction difficulty (38.4/100) and risk score  ││
│  │ • Follows valley terrain, reducing landslide exposure       ││
│  │ • Moderate cost ($6.17M) balances budget and safety         ││
│  │ • Accessible during monsoon season (June-September)         ││
│  │                                                             ││
│  │ Trade-offs:                                                 ││
│  │ • Slightly longer distance (+0.5 km vs Route B)             ││
│  │ • Medium flood risk requires 2 culverts at river crossings  ││
│  │                                                             ││
│  │ Recommended Actions:                                        ││
│  │ 1. Install drainage systems at km 8.2 and km 14.5           ││
│  │ 2. Schedule construction: October-March (dry season)        ││
│  │ 3. Budget additional $200K for flood mitigation             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  [Export GeoJSON] [Export KML] [Generate PDF Report] [Share]    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key UI Components

### 1. **Map Panel (Left, 60% width)**
- Satellite imagery base layer
- Multiple map layer options (Satellite, Street, Topographic)
- Route overlays with distinct colors
- Risk zone visualization (semi-transparent colored areas)
- Interactive markers for start/end points
- Click-to-view route segment details
- Zoom, pan, and measurement tools

### 2. **Control Panel (Right, 40% width)**
- Location selection dropdowns
- Constraint checkboxes
- Generate routes button
- Real-time progress indicator

### 3. **Comparison Table (Bottom)**
- Side-by-side route metrics
- Color-coded risk indicators
- Sortable columns

### 4. **AI Explanation Panel**
- Natural language recommendation
- Structured rationale with bullet points
- Trade-off analysis
- Actionable recommendations
- Data source indicators (API vs local data)

### 5. **Export Options**
- Multiple format support (GeoJSON, KML, Shapefile, PDF)
- Share functionality
- Print-friendly reports

## User Flow

```
1. User selects start/end locations
   ↓
2. User sets constraints (optional)
   ↓
3. Click "Generate Routes"
   ↓
4. System processes (shows loading indicator)
   ↓
5. Map displays 3 route alternatives
   ↓
6. Comparison table shows metrics
   ↓
7. AI explanation appears
   ↓
8. User clicks route to see details
   ↓
9. User exports preferred route
```

## Color Scheme

- **Route A (Safest)**: Red solid line
- **Route B (Direct)**: Blue dashed line
- **Route C (Scenic)**: Green dotted line
- **Flood Risk Zones**: Blue semi-transparent
- **Landslide Risk Zones**: Red semi-transparent
- **High Altitude Risk**: Orange semi-transparent
- **Start Marker**: Green pin
- **End Marker**: Red pin

## Responsive Design

- Desktop: Full layout as shown
- Tablet: Stacked layout (map on top, controls below)
- Mobile: Single column, collapsible panels

## Accessibility

- Keyboard navigation support
- Screen reader compatible
- High contrast mode option
- Text size adjustment
