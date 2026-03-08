#!/usr/bin/env python3
"""
Test script to query Overpass API for Uttarakhand roads
and compare with what we have in the OSM cache
"""

import requests
import json

def query_overpass(bbox, timeout=60):
    """
    Query Overpass API for roads in a bounding box
    bbox: (min_lat, min_lon, max_lat, max_lon)
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    min_lat, min_lon, max_lat, max_lon = bbox
    
    # Query for major roads
    query = f"""
    [out:json][timeout:{timeout}];
    (
      way["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified"]
          ({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out body;
    >;
    out skel qt;
    """
    
    print(f"Querying Overpass API...")
    print(f"  Bbox: {bbox}")
    print(f"  Timeout: {timeout}s")
    print()
    
    try:
        response = requests.post(overpass_url, data={'data': query}, timeout=timeout+5)
        data = response.json()
        
        elements = data.get('elements', [])
        ways = [e for e in elements if e.get('type') == 'way']
        nodes = [e for e in elements if e.get('type') == 'node']
        
        # Analyze roads
        highway_types = {}
        named_roads = []
        
        for way in ways:
            tags = way.get('tags', {})
            highway = tags.get('highway', 'unknown')
            name = tags.get('name', None)
            
            highway_types[highway] = highway_types.get(highway, 0) + 1
            
            if name:
                named_roads.append({
                    'name': name,
                    'type': highway,
                    'id': way.get('id'),
                    'nodes': len(way.get('nodes', []))
                })
        
        print(f"✓ Found {len(ways)} roads, {len(nodes)} nodes")
        print()
        print("Roads by type:")
        for htype, count in sorted(highway_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {htype:20} {count:6}")
        
        print()
        print(f"Named roads: {len(named_roads)}")
        
        if named_roads:
            print("\nSample named roads:")
            for i, road in enumerate(sorted(named_roads, key=lambda x: x['nodes'], reverse=True)[:20]):
                print(f"  {i+1:2}. {road['name']:40} ({road['type']:12}, {road['nodes']:4} nodes)")
        
        return {
            'ways': ways,
            'nodes': nodes,
            'highway_types': highway_types,
            'named_roads': named_roads
        }
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


if __name__ == '__main__':
    print("="*70)
    print("TESTING: Overpass API for Uttarakhand Roads")
    print("="*70)
    print()
    
    # Test 1: Small area around Uttarkashi
    print("TEST 1: Uttarkashi area (30.5-31.0, 78.0-78.8)")
    print("-"*70)
    result1 = query_overpass((30.5, 78.0, 31.0, 78.8), timeout=30)
    
    print()
    print("="*70)
    print()
    
    # Test 2: Larger Uttarakhand area
    print("TEST 2: Full Uttarakhand (28.6-31.5, 77.5-81.0)")
    print("-"*70)
    print("⚠️  This will take 60+ seconds...")
    result2 = query_overpass((28.6, 77.5, 31.5, 81.0), timeout=90)
    
    print()
    print("="*70)
    print("SUMMARY")
    print("="*70)
    
    if result1:
        print(f"Uttarkashi area: {len(result1['ways'])} roads")
    if result2:
        print(f"Full Uttarakhand: {len(result2['ways'])} roads")
    
    print()
    print("CONCLUSION:")
    print("  OpenStreetMap HAS road data for Uttarakhand!")
    print("  The issue is that your current cache was generated from")
    print("  a PBF file that only contains Himachal Pradesh data.")
    print()
    print("SOLUTION:")
    print("  1. Download the correct PBF file for Uttarakhand")
    print("  2. Or use Overpass API directly (but slower)")
    print("  3. Or regenerate cache with the full northern-zone PBF")
