#!/usr/bin/env python3
"""
Test OSM routing between Dehradun and Rishikesh (should work - major highway)
"""

import sys
import time
from osm_routing.parser import OSMParser
from osm_routing.calculator import RouteCalculator

# Coordinates
DEHRADUN = (30.3165, 78.0322)
RISHIKESH = (30.0869, 78.2676)

print("="*70)
print("Testing OSM Routing: Dehradun to Rishikesh")
print("="*70)
print()

# Load the cache
print("Loading OSM cache...")
start = time.time()
parser = OSMParser()
network = parser.load_from_cache('osm_cache_uttarakhand.json.gz')
print(f"✓ Loaded in {time.time()-start:.1f}s")
print(f"  Nodes: {len(network.nodes):,}")
print(f"  Edges: {len(network.edges):,}")
print()

# Initialize calculator
calc = RouteCalculator(network)

# Find snap points
print(f"Finding snap points...")
start_snap = calc.find_snap_point(DEHRADUN[0], DEHRADUN[1], max_distance_m=2000)
end_snap = calc.find_snap_point(RISHIKESH[0], RISHIKESH[1], max_distance_m=2000)

if not start_snap:
    print(f"✗ No road found near Dehradun within 2km")
    sys.exit(1)
    
if not end_snap:
    print(f"✗ No road found near Rishikesh within 2km")
    sys.exit(1)

print(f"✓ Start snap: {start_snap.lat:.4f}, {start_snap.lon:.4f} (node {start_snap.id})")
print(f"✓ End snap: {end_snap.lat:.4f}, {end_snap.lon:.4f} (node {end_snap.id})")
print()

# Try to find a route
print("Calculating route...")
start = time.time()

try:
    routes = calc.calculate_routes(DEHRADUN, RISHIKESH, settlements=[])
    elapsed = time.time() - start
    
    if routes:
        print(f"✓ Found {len(routes)} routes in {elapsed:.1f}s")
        print()
        for i, route in enumerate(routes[:2]):
            print(f"Route {i+1}: {route.name}")
            print(f"  Distance: {route.total_distance_km:.1f} km")
            print(f"  Waypoints: {len(route.waypoints)}")
            print(f"  Segments: {len(route.segments)}")
    else:
        print(f"✗ No routes found (took {elapsed:.1f}s)")
        
except Exception as e:
    elapsed = time.time() - start
    print(f"✗ Error after {elapsed:.1f}s: {e}")
    import traceback
    traceback.print_exc()
