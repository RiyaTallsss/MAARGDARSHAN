#!/usr/bin/env python3
"""
Test OSM routing locally with the northern-zone PBF file
"""

import sys
import time
from osm_routing.parser import OSMParser
from osm_routing.calculator import RouteCalculator

def test_osm_routing():
    """Test OSM routing end-to-end"""
    
    print("=" * 60)
    print("Testing OSM Road Network Routing Locally")
    print("=" * 60)
    print()
    
    # Test coordinates: Uttarkashi to Gangotri
    start_lat, start_lon = 30.7268, 78.4354
    end_lat, end_lon = 30.9993, 78.9394
    
    print(f"Route: Uttarkashi ({start_lat}, {start_lon}) -> Gangotri ({end_lat}, {end_lon})")
    print()
    
    # Step 1: Parse PBF file
    print("Step 1: Parsing OSM PBF file...")
    print("-" * 60)
    
    parser = OSMParser()
    pbf_path = "Maps/northern-zone-260121.osm.pbf"
    
    try:
        start_time = time.time()
        network = parser.parse_pbf(pbf_path)
        parse_time = time.time() - start_time
        
        print(f"✓ Parsed successfully in {parse_time:.2f}s")
        print(f"  - Nodes: {len(network.nodes):,}")
        print(f"  - Edges: {len(network.edges):,}")
        print()
        
    except Exception as e:
        print(f"✗ Failed to parse PBF: {e}")
        return False
    
    # Step 2: Build spatial index
    print("Step 2: Building spatial index...")
    print("-" * 60)
    
    try:
        start_time = time.time()
        network.build_spatial_index()
        index_time = time.time() - start_time
        
        print(f"✓ Spatial index built in {index_time:.2f}s")
        print()
        
    except Exception as e:
        print(f"✗ Failed to build spatial index: {e}")
        return False
    
    # Step 3: Initialize route calculator
    print("Step 3: Initializing route calculator...")
    print("-" * 60)
    
    try:
        calculator = RouteCalculator(network)
        print(f"✓ Route calculator initialized")
        print()
        
    except Exception as e:
        print(f"✗ Failed to initialize calculator: {e}")
        return False
    
    # Step 4: Find snap points
    print("Step 4: Finding snap points...")
    print("-" * 60)
    
    try:
        start_node = calculator.find_snap_point(start_lat, start_lon)
        end_node = calculator.find_snap_point(end_lat, end_lon)
        
        if start_node is None:
            print(f"✗ No road within 500m of start point")
            return False
        
        if end_node is None:
            print(f"✗ No road within 500m of end point")
            return False
        
        print(f"✓ Start snapped to node {start_node.id} at ({start_node.lat:.4f}, {start_node.lon:.4f})")
        print(f"✓ End snapped to node {end_node.id} at ({end_node.lat:.4f}, {end_node.lon:.4f})")
        print()
        
    except Exception as e:
        print(f"✗ Failed to find snap points: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 5: Calculate routes
    print("Step 5: Calculating 4 routes...")
    print("-" * 60)
    
    try:
        start_time = time.time()
        routes = calculator.calculate_routes(
            (start_lat, start_lon),
            (end_lat, end_lon),
            settlements=[]  # No settlements for this test
        )
        calc_time = time.time() - start_time
        
        print(f"✓ Calculated {len(routes)} routes in {calc_time:.2f}s")
        print()
        
        for i, route in enumerate(routes, 1):
            print(f"  Route {i}: {route.name}")
            print(f"    - Distance: {route.total_distance_km:.2f} km")
            print(f"    - Segments: {len(route.segments)}")
            print(f"    - Waypoints: {len(route.waypoints)}")
        
        print()
        
    except Exception as e:
        print(f"✗ Failed to calculate routes: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 6: Classify segments
    print("Step 6: Classifying route segments...")
    print("-" * 60)
    
    try:
        for route in routes:
            calculator.classify_segments(route)
        
        print(f"✓ Segments classified")
        print()
        
        for i, route in enumerate(routes, 1):
            stats = route.construction_stats
            print(f"  Route {i}: {route.name}")
            print(f"    - New construction: {stats.get('new_construction_km', 0):.2f} km")
            print(f"    - Upgrade existing: {stats.get('upgrade_existing_km', 0):.2f} km")
            print(f"    - Utilization: {stats.get('utilization_percent', 0):.1f}%")
            print(f"    - Cost: ${route.estimated_cost:,.0f}")
        
        print()
        
    except Exception as e:
        print(f"✗ Failed to classify segments: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("=" * 60)
    print("✓ ALL TESTS PASSED")
    print("=" * 60)
    print()
    print(f"Total time: {parse_time + index_time + calc_time:.2f}s")
    print(f"  - Parsing: {parse_time:.2f}s")
    print(f"  - Indexing: {index_time:.2f}s")
    print(f"  - Routing: {calc_time:.2f}s")
    print()
    
    return True

if __name__ == "__main__":
    success = test_osm_routing()
    sys.exit(0 if success else 1)
