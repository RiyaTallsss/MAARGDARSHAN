# Quick Fix: Show Existing Roads on Map

## Goal
Display existing OSM roads as a gray overlay so users can see the road network context.

## Implementation (30 minutes)

### Step 1: Add OSM Tile Layer
The easiest approach is to use OpenStreetMap's road overlay:

```javascript
// Add to frontend/app.js after map initialization

// Add OSM roads as a separate layer (can be toggled)
const osmRoadsLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    opacity: 0.3,  // Make it semi-transparent
    maxZoom: 18,
    minZoom: 7
});

// Add layer control
const baseLayers = {
    "Satellite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Esri'
    }),
    "Street Map": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap'
    })
};

const overlays = {
    "Existing Roads": osmRoadsLayer
};

L.control.layers(baseLayers, overlays).addTo(map);
```

### Step 2: Add Legend
```javascript
// Add legend to explain colors
const legend = L.control({position: 'bottomright'});

legend.onAdd = function (map) {
    const div = L.DomUtil.create('div', 'info legend');
    div.innerHTML = `
        <h4>Route Legend</h4>
        <div><span style="color: #3b82f6;">━━</span> Shortest Route (Proposed)</div>
        <div><span style="color: #10b981;">━━</span> Safest Route (Proposed)</div>
        <div><span style="color: #f97316;">━━</span> Budget Route (Proposed)</div>
        <div><span style="color: #a855f7;">━━</span> Social Impact (Proposed)</div>
        <div><span style="color: #999;">━━</span> Existing Roads</div>
    `;
    return div;
};

legend.addTo(map);
```

### Step 3: Add CSS
```css
/* Add to frontend/index.html */
.info.legend {
    padding: 10px;
    background: white;
    border-radius: 5px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    font-size: 12px;
    line-height: 1.5;
}

.info.legend h4 {
    margin: 0 0 5px;
    font-size: 14px;
}

.info.legend div {
    margin: 3px 0;
}
```

## Alternative: Load Roads from GeoJSON

If you want more control, extract roads from OSM and load as GeoJSON:

```python
# Python script to extract roads
import osmium
import json

class RoadHandler(osmium.SimpleHandler):
    def __init__(self):
        osmium.SimpleHandler.__init__(self)
        self.roads = []
    
    def way(self, w):
        if 'highway' in w.tags:
            coords = [[n.lon, n.lat] for n in w.nodes]
            self.roads.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': coords
                },
                'properties': {
                    'highway': w.tags['highway'],
                    'name': w.tags.get('name', 'Unnamed')
                }
            })

handler = RoadHandler()
handler.apply_file('Maps/northern-zone-260121.osm.pbf')

with open('roads.geojson', 'w') as f:
    json.dump({
        'type': 'FeatureCollection',
        'features': handler.roads
    }, f)
```

Then load in frontend:
```javascript
fetch('roads.geojson')
    .then(response => response.json())
    .then(data => {
        L.geoJSON(data, {
            style: {
                color: '#999',
                weight: 2,
                opacity: 0.5
            }
        }).addTo(map);
    });
```

## Recommendation

**For hackathon**: Use Step 1 (OSM tile layer) - it's instant and requires no data processing.

**For production**: Use Alternative (GeoJSON) - gives you full control over styling and filtering.

---

**Time Required**: 30 minutes for quick fix, 2-3 hours for GeoJSON approach
