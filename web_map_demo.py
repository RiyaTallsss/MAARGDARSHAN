#!/usr/bin/env python3
"""
Web Map Demo - Interactive satellite map with route visualization.

This creates a web interface showing satellite imagery with routes plotted
from one point to another, including risk zones and terrain analysis.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple
import webbrowser
import os
from pathlib import Path

# Try to import folium for mapping
try:
    import folium
    from folium import plugins
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# Mock classes for demo
class MockCoordinate:
    def __init__(self, latitude: float, longitude: float, elevation: float = None):
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
    
    def to_dict(self):
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'elevation': self.elevation
        }

class MockRouteSegment:
    def __init__(self, start: MockCoordinate, end: MockCoordinate, 
                 terrain_type: str, difficulty: float, cost: float, risk_factors: List[str]):
        self.start = start
        self.end = end
        self.terrain_type = terrain_type
        self.construction_difficulty = difficulty
        self.construction_cost = cost
        self.risk_factors = risk_factors
        self.length = self._calculate_distance()
        self.slope_grade = self._calculate_slope()
    
    def _calculate_distance(self):
        import math
        lat1, lon1 = math.radians(self.start.latitude), math.radians(self.start.longitude)
        lat2, lon2 = math.radians(self.end.latitude), math.radians(self.end.longitude)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return 6371000 * 2 * math.asin(math.sqrt(a))  # meters
    
    def _calculate_slope(self):
        import math
        elev_diff = (self.end.elevation or 0) - (self.start.elevation or 0)
        return math.degrees(math.atan2(abs(elev_diff), self.length)) if self.length > 0 else 0

class MockRoute:
    def __init__(self, route_id: str, waypoints: List[MockCoordinate], segments: List[MockRouteSegment]):
        self.id = route_id
        self.waypoints = waypoints
        self.segments = segments
        self.total_distance = sum(seg.length for seg in segments) / 1000  # km
        self.estimated_cost = sum(seg.construction_cost * seg.length for seg in segments)
        self.construction_difficulty = sum(seg.construction_difficulty * seg.length for seg in segments) / sum(seg.length for seg in segments)
        self.risk_score = self._calculate_risk_score()
    
    def _calculate_risk_score(self):
        risk_count = sum(len(seg.risk_factors) for seg in self.segments)
        return min(100, risk_count * 15 + self.construction_difficulty * 0.3)

def create_sample_routes() -> List[MockRoute]:
    """Create sample routes for Uttarkashi region."""
    
    # Define key locations in Uttarkashi
    uttarkashi_town = MockCoordinate(30.7268, 78.4354, 1158)
    village_1 = MockCoordinate(30.7500, 78.4600, 1400)
    village_2 = MockCoordinate(30.7800, 78.4800, 1650)
    mountain_village = MockCoordinate(30.8200, 78.5200, 2100)
    high_village = MockCoordinate(30.8500, 78.5500, 2500)
    
    routes = []
    
    # Route 1: Safest route (longer but easier terrain)
    safe_waypoints = [uttarkashi_town, village_1, village_2, mountain_village, high_village]
    safe_segments = []
    
    for i in range(len(safe_waypoints) - 1):
        segment = MockRouteSegment(
            safe_waypoints[i], safe_waypoints[i+1],
            terrain_type="gentle" if i < 2 else "moderate",
            difficulty=25 + i*10,
            cost=200 + i*50,
            risk_factors=["high_altitude"] if i > 2 else []
        )
        safe_segments.append(segment)
    
    routes.append(MockRoute("route_safest", safe_waypoints, safe_segments))
    
    # Route 2: Direct route (shorter but steeper)
    direct_waypoints = [uttarkashi_town, village_2, high_village]
    direct_segments = []
    
    for i in range(len(direct_waypoints) - 1):
        segment = MockRouteSegment(
            direct_waypoints[i], direct_waypoints[i+1],
            terrain_type="steep" if i == 1 else "moderate",
            difficulty=45 + i*20,
            cost=400 + i*100,
            risk_factors=["steep_terrain", "landslide_risk"] if i == 1 else ["high_altitude"]
        )
        direct_segments.append(segment)
    
    routes.append(MockRoute("route_direct", direct_waypoints, direct_segments))
    
    # Route 3: Scenic route (follows valley)
    scenic_waypoints = [uttarkashi_town, MockCoordinate(30.7400, 78.4700, 1300), 
                       MockCoordinate(30.7900, 78.5100, 1800), high_village]
    scenic_segments = []
    
    for i in range(len(scenic_waypoints) - 1):
        segment = MockRouteSegment(
            scenic_waypoints[i], scenic_waypoints[i+1],
            terrain_type="gentle" if i == 0 else "moderate",
            difficulty=20 + i*15,
            cost=250 + i*75,
            risk_factors=["flash_flood_risk"] if i == 1 else (["high_altitude"] if i > 1 else [])
        )
        scenic_segments.append(segment)
    
    routes.append(MockRoute("route_scenic", scenic_waypoints, scenic_segments))
    
    return routes

def create_interactive_map(routes: List[MockRoute]) -> str:
    """Create an interactive map with satellite imagery and route visualization."""
    
    if not FOLIUM_AVAILABLE:
        return create_simple_html_map(routes)
    
    # Center map on Uttarkashi
    center_lat, center_lon = 30.7768, 78.4854
    
    # Create map with satellite tiles
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles=None  # We'll add custom tiles
    )
    
    # Add different tile layers
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='Street Map',
        overlay=False,
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Topographic',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Color scheme for different routes
    route_colors = ['red', 'blue', 'green', 'purple', 'orange']
    route_styles = [
        {'color': 'red', 'weight': 4, 'opacity': 0.8, 'dashArray': ''},
        {'color': 'blue', 'weight': 4, 'opacity': 0.8, 'dashArray': '10,5'},
        {'color': 'green', 'weight': 4, 'opacity': 0.8, 'dashArray': '5,5'},
    ]
    
    # Add routes to map
    for i, route in enumerate(routes):
        color = route_colors[i % len(route_colors)]
        style = route_styles[i % len(route_styles)]
        
        # Create route line
        route_coords = [[wp.latitude, wp.longitude] for wp in route.waypoints]
        
        # Route line
        folium.PolyLine(
            locations=route_coords,
            **style,
            popup=f"""
            <div style='width: 300px'>
                <h4>{route.id.replace('_', ' ').title()}</h4>
                <b>Distance:</b> {route.total_distance:.2f} km<br>
                <b>Cost:</b> ${route.estimated_cost:,.0f}<br>
                <b>Difficulty:</b> {route.construction_difficulty:.1f}/100<br>
                <b>Risk Score:</b> {route.risk_score:.1f}/100<br>
                <b>Segments:</b> {len(route.segments)}
            </div>
            """,
            tooltip=f"{route.id.replace('_', ' ').title()} - {route.total_distance:.1f}km"
        ).add_to(m)
        
        # Add waypoint markers
        for j, waypoint in enumerate(route.waypoints):
            if j == 0:  # Start point
                icon = folium.Icon(color='green', icon='play', prefix='fa')
                popup_text = f"<b>START</b><br>Uttarkashi Town<br>Elevation: {waypoint.elevation}m"
            elif j == len(route.waypoints) - 1:  # End point
                icon = folium.Icon(color='red', icon='stop', prefix='fa')
                popup_text = f"<b>DESTINATION</b><br>Mountain Village<br>Elevation: {waypoint.elevation}m"
            else:  # Intermediate waypoints
                icon = folium.Icon(color='blue', icon='circle', prefix='fa')
                popup_text = f"<b>Waypoint {j}</b><br>Elevation: {waypoint.elevation}m"
            
            folium.Marker(
                location=[waypoint.latitude, waypoint.longitude],
                popup=popup_text,
                icon=icon
            ).add_to(m)
    
    # Add risk zones (example areas)
    risk_zones = [
        {
            'center': [30.7600, 78.4900],
            'radius': 800,
            'risk_type': 'Landslide Risk',
            'color': 'red'
        },
        {
            'center': [30.7900, 78.5100],
            'radius': 600,
            'risk_type': 'Flash Flood Risk',
            'color': 'blue'
        },
        {
            'center': [30.8300, 78.5300],
            'radius': 1000,
            'risk_type': 'High Altitude Risk',
            'color': 'orange'
        }
    ]
    
    for zone in risk_zones:
        folium.Circle(
            location=zone['center'],
            radius=zone['radius'],
            popup=f"<b>{zone['risk_type']}</b><br>Radius: {zone['radius']}m",
            color=zone['color'],
            fillColor=zone['color'],
            fillOpacity=0.2,
            weight=2
        ).add_to(m)
    
    # Add elevation contours (simplified)
    elevation_lines = [
        [[30.7200, 78.4200], [30.7300, 78.4300], [30.7400, 78.4400]],  # 1200m
        [[30.7400, 78.4500], [30.7500, 78.4600], [30.7600, 78.4700]],  # 1500m
        [[30.7700, 78.4800], [30.7800, 78.4900], [30.7900, 78.5000]],  # 1800m
    ]
    
    elevations = [1200, 1500, 1800]
    for i, line in enumerate(elevation_lines):
        folium.PolyLine(
            locations=line,
            color='brown',
            weight=1,
            opacity=0.6,
            dashArray='2,4',
            popup=f"Elevation: {elevations[i]}m"
        ).add_to(m)
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <h4>Route Legend</h4>
    <p><span style="color:red;">━━━</span> Safest Route</p>
    <p><span style="color:blue;">┅┅┅</span> Direct Route</p>
    <p><span style="color:green;">┄┄┄</span> Scenic Route</p>
    <p><span style="color:red;">●</span> Risk Zones</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add fullscreen button
    plugins.Fullscreen().add_to(m)
    
    # Add measure tool
    plugins.MeasureControl().add_to(m)
    
    return m._repr_html_()

def create_simple_html_map(routes: List[MockRoute]) -> str:
    """Create a simple HTML map using Leaflet (fallback when folium not available)."""
    
    # Generate route data for JavaScript
    routes_json = []
    for route in routes:
        route_data = {
            'id': route.id,
            'name': route.id.replace('_', ' ').title(),
            'waypoints': [[wp.latitude, wp.longitude] for wp in route.waypoints],
            'distance': route.total_distance,
            'cost': route.estimated_cost,
            'difficulty': route.construction_difficulty,
            'risk_score': route.risk_score,
            'color': ['red', 'blue', 'green'][routes.index(route) % 3]
        }
        routes_json.append(route_data)
    
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Rural Infrastructure Planning - Route Visualization</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>
            body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
            #map {{ height: 100vh; width: 100%; }}
            .info-panel {{
                position: absolute;
                top: 10px;
                right: 10px;
                background: white;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                z-index: 1000;
                max-width: 300px;
            }}
            .route-info {{
                margin: 10px 0;
                padding: 10px;
                border-left: 4px solid #ccc;
                background: #f9f9f9;
            }}
            .route-safest {{ border-left-color: red; }}
            .route-direct {{ border-left-color: blue; }}
            .route-scenic {{ border-left-color: green; }}
            .legend {{
                position: absolute;
                bottom: 30px;
                left: 30px;
                background: white;
                padding: 15px;
                border-radius: 5px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                z-index: 1000;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        
        <div class="info-panel">
            <h3>🏔️ Uttarkashi Route Planning</h3>
            <div id="route-details">
                <p>Click on a route to see details</p>
            </div>
        </div>
        
        <div class="legend">
            <h4>Legend</h4>
            <p><span style="color:red;">━━━</span> Safest Route</p>
            <p><span style="color:blue;">━━━</span> Direct Route</p>
            <p><span style="color:green;">━━━</span> Scenic Route</p>
            <p><span style="color:orange;">●</span> Risk Zones</p>
        </div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            // Initialize map centered on Uttarkashi
            var map = L.map('map').setView([30.7768, 78.4854], 12);

            // Add satellite tile layer
            var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: 'Tiles &copy; Esri',
                maxZoom: 18
            }});

            // Add street map layer
            var streets = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 18
            }});

            // Add topographic layer
            var topo = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: 'Tiles &copy; Esri',
                maxZoom: 18
            }});

            // Add satellite as default
            satellite.addTo(map);

            // Layer control
            var baseMaps = {{
                "Satellite": satellite,
                "Street Map": streets,
                "Topographic": topo
            }};
            L.control.layers(baseMaps).addTo(map);

            // Route data
            var routes = {json.dumps(routes_json, indent=12)};

            // Add routes to map
            routes.forEach(function(route) {{
                var polyline = L.polyline(route.waypoints, {{
                    color: route.color,
                    weight: 4,
                    opacity: 0.8
                }}).addTo(map);

                polyline.bindPopup(`
                    <div style="width: 250px">
                        <h4>${{route.name}}</h4>
                        <b>Distance:</b> ${{route.distance.toFixed(2)}} km<br>
                        <b>Cost:</b> $$${{route.cost.toLocaleString()}}<br>
                        <b>Difficulty:</b> ${{route.difficulty.toFixed(1)}}/100<br>
                        <b>Risk Score:</b> ${{route.risk_score.toFixed(1)}}/100
                    </div>
                `);

                polyline.on('click', function() {{
                    document.getElementById('route-details').innerHTML = `
                        <div class="route-info route-${{route.id.split('_')[1]}}">
                            <h4>${{route.name}}</h4>
                            <p><b>Distance:</b> ${{route.distance.toFixed(2)}} km</p>
                            <p><b>Cost:</b> $$${{route.cost.toLocaleString()}}</p>
                            <p><b>Difficulty:</b> ${{route.difficulty.toFixed(1)}}/100</p>
                            <p><b>Risk Score:</b> ${{route.risk_score.toFixed(1)}}/100</p>
                            <p><b>Waypoints:</b> ${{route.waypoints.length}}</p>
                        </div>
                    `;
                }});

                // Add start marker
                L.marker(route.waypoints[0], {{
                    icon: L.icon({{
                        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
                        iconSize: [25, 41],
                        iconAnchor: [12, 41]
                    }})
                }}).addTo(map).bindPopup('<b>START</b><br>Uttarkashi Town');

                // Add end marker
                L.marker(route.waypoints[route.waypoints.length - 1], {{
                    icon: L.icon({{
                        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
                        iconSize: [25, 41],
                        iconAnchor: [12, 41]
                    }})
                }}).addTo(map).bindPopup('<b>DESTINATION</b><br>Mountain Village');
            }});

            // Add risk zones
            var riskZones = [
                {{center: [30.7600, 78.4900], radius: 800, type: 'Landslide Risk', color: 'red'}},
                {{center: [30.7900, 78.5100], radius: 600, type: 'Flash Flood Risk', color: 'blue'}},
                {{center: [30.8300, 78.5300], radius: 1000, type: 'High Altitude Risk', color: 'orange'}}
            ];

            riskZones.forEach(function(zone) {{
                L.circle(zone.center, {{
                    color: zone.color,
                    fillColor: zone.color,
                    fillOpacity: 0.2,
                    radius: zone.radius
                }}).addTo(map).bindPopup(`<b>${{zone.type}}</b><br>Radius: ${{zone.radius}}m`);
            }});

            // Fit map to show all routes
            var group = new L.featureGroup();
            routes.forEach(function(route) {{
                route.waypoints.forEach(function(point) {{
                    group.addLayer(L.marker(point));
                }});
            }});
            map.fitBounds(group.getBounds().pad(0.1));
        </script>
    </body>
    </html>
    '''
    
    return html_content

def main():
    """Create and display the interactive map."""
    print("🗺️  Creating Interactive Route Visualization Map")
    print("=" * 60)
    
    # Create sample routes
    print("📍 Generating sample routes for Uttarkashi region...")
    routes = create_sample_routes()
    
    print(f"✅ Created {len(routes)} route alternatives:")
    for route in routes:
        print(f"   • {route.id.replace('_', ' ').title()}: {route.total_distance:.2f}km, "
              f"${route.estimated_cost:,.0f}, difficulty {route.construction_difficulty:.1f}/100")
    
    # Create interactive map
    print("\n🌍 Creating interactive satellite map...")
    
    if FOLIUM_AVAILABLE:
        print("   Using Folium for advanced mapping features")
        map_html = create_interactive_map(routes)
    else:
        print("   Using Leaflet for basic mapping (install folium for advanced features)")
        map_html = create_simple_html_map(routes)
    
    # Save map to file
    map_file = Path("route_visualization_map.html")
    with open(map_file, 'w', encoding='utf-8') as f:
        f.write(map_html)
    
    print(f"✅ Map saved to: {map_file.absolute()}")
    
    # Open in browser
    print("🌐 Opening map in your default browser...")
    webbrowser.open(f"file://{map_file.absolute()}")
    
    print("\n🎯 Map Features:")
    print("   • 🛰️  Satellite imagery view")
    print("   • 🗺️  Multiple map layers (satellite, street, topographic)")
    print("   • 🛤️  3 route alternatives with different colors")
    print("   • 📍 Start/end markers")
    print("   • ⚠️  Risk zones (landslide, flood, altitude)")
    print("   • 📊 Route details on click")
    print("   • 📏 Distance measurement tool")
    print("   • 🔍 Zoom and pan controls")
    
    print(f"\n💡 The map shows:")
    print(f"   • RED route: Safest (longer but easier terrain)")
    print(f"   • BLUE route: Direct (shorter but steeper)")
    print(f"   • GREEN route: Scenic (follows valley)")
    print(f"   • Risk zones: Landslide, flood, and altitude risks")
    
    print(f"\n🎉 Interactive map is now open in your browser!")
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            exit(1)
    except KeyboardInterrupt:
        print("\n👋 Map demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error creating map: {e}")
        print("💡 Try installing folium: pip install folium")
        exit(1)