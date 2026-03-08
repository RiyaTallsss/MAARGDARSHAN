#!/usr/bin/env python3
"""
Diagnose OSM network connectivity issues
"""

import sys
from collections import deque
from osm_routing.parser import OSMParser
from osm_routing.calculator import RouteCalculator

print("="*70)
print("OSM Network Connectivity Diagnosis")
print("="*70)
print()

# Load cache
print("Loading cache...")
parser = OSMParser()
network = parser.load_from_cache('osm_cache_uttarakhand.json.gz')
print(f"✓ Loaded: {len(network.nodes):,} nodes, {len(network.edges):,} edges")
print()

# Test points
DEHRADUN = (30.3165, 78.0322)
RISHIKESH = (30.0869, 78.2676)

calc = RouteCalculator(network)

# Find snap points
print("Finding snap points...")
start_snap = calc.find_snap_point(DEHRADUN[0], DEHRADUN[1], max_distance_m=2000)
end_snap = calc.find_snap_point(RISHIKESH[0], RISHIKESH[1], max_distance_m=2000)

if not start_snap or not end_snap:
    print("✗ Could not find snap points")
    sys.exit(1)

print(f"Start: {start_snap.id} at ({start_snap.lat:.4f}, {start_snap.lon:.4f})")
print(f"End: {end_snap.id} at ({end_snap.lat:.4f}, {end_snap.lon:.4f})")
print()

# BFS to find connected component from start
print("Running BFS from start node to find connected component...")
visited = set()
queue = deque([start_snap.id])
visited.add(start_snap.id)

while queue and len(visited) < 100000:  # Limit to prevent infinite loop
    node_id = queue.popleft()
    
    # Explore neighbors
    for edge in network.get_outgoing_edges(node_id):
        neighbor = edge.target_node_id
        if neighbor not in visited:
            visited.add(neighbor)
            queue.append(neighbor)
    
    # Progress
    if len(visited) % 1000 == 0:
        print(f"  Visited {len(visited):,} nodes...")

print(f"✓ Connected component from start: {len(visited):,} nodes")
print()

# Check if end node is in the same component
if end_snap.id in visited:
    print("✓ END NODE IS REACHABLE from start node!")
    print("  The network IS connected between these points.")
    print("  The A* timeout is due to performance issues, not connectivity.")
else:
    print("✗ END NODE IS NOT REACHABLE from start node!")
    print("  The network is DISCONNECTED between these points.")
    print()
    
    # Find connected component from end
    print("Running BFS from end node...")
    visited_end = set()
    queue = deque([end_snap.id])
    visited_end.add(end_snap.id)
    
    while queue and len(visited_end) < 100000:
        node_id = queue.popleft()
        for edge in network.get_outgoing_edges(node_id):
            neighbor = edge.target_node_id
            if neighbor not in visited_end:
                visited_end.add(neighbor)
                queue.append(neighbor)
        
        if len(visited_end) % 1000 == 0:
            print(f"  Visited {len(visited_end):,} nodes...")
    
    print(f"✓ Connected component from end: {len(visited_end):,} nodes")
    print()
    
    print("Analysis:")
    print(f"  Total nodes in network: {len(network.nodes):,}")
    print(f"  Nodes reachable from start: {len(visited):,} ({len(visited)/len(network.nodes)*100:.1f}%)")
    print(f"  Nodes reachable from end: {len(visited_end):,} ({len(visited_end)/len(network.nodes)*100:.1f}%)")
    print(f"  Disconnected nodes: {len(network.nodes) - len(visited) - len(visited_end):,}")
    print()
    print("Conclusion:")
    print("  The major roads (motorway, trunk, primary, secondary) do NOT form")
    print("  a connected network between Dehradun and Rishikesh.")
    print("  You need to include tertiary roads to connect these cities.")

print()
print("="*70)
