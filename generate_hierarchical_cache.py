#!/usr/bin/env python3
"""
Generate hierarchical OSM cache with spatial partitioning

Strategy:
1. Divide roads by hierarchy (L1: major highways, L2: regional, L3: local)
2. Divide Uttarakhand into grid cells (0.1° x 0.1° = ~11km x 11km)
3. Store each combination separately for fast loading

This allows:
- Load only L1 for long-distance routing (fast)
- Load L1+L2 for medium-distance (moderate)
- Load only relevant grid cells (spatial filtering)
"""

import sys
import json
import gzip
import time
import boto3
import logging
from collections import defaultdict
from osm_routing.parser import OSMParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
S3_BUCKET = 'maargdarshan-data'
OSM_PBF_PATH = 'Maps/uttarakhand-latest.osm.pbf'
UTTARAKHAND_BBOX = (28.6, 77.5, 31.5, 81.0)  # (min_lat, min_lon, max_lat, max_lon)

# Road hierarchy levels
ROAD_LEVELS = {
    'L1_major_highways': {'motorway', 'trunk', 'primary', 'motorway_link', 'trunk_link', 'primary_link'},
    'L2_regional_roads': {'secondary', 'tertiary', 'secondary_link', 'tertiary_link'},
    'L3_local_roads': {'unclassified', 'residential', 'service', 'track'}
}

# Grid configuration (0.1 degree = ~11km)
GRID_SIZE = 0.1

def get_grid_cell(lat, lon):
    """Get grid cell ID for a coordinate"""
    cell_lat = int(lat / GRID_SIZE) * GRID_SIZE
    cell_lon = int(lon / GRID_SIZE) * GRID_SIZE
    return f"{cell_lat:.1f}_{cell_lon:.1f}"

def main():
    print("="*70)
    print("Hierarchical OSM Cache Generator")
    print("="*70)
    print()
    print(f"Road Levels:")
    for level, types in ROAD_LEVELS.items():
        print(f"  {level}: {', '.join(sorted(types))}")
    print()
    print(f"Grid Size: {GRID_SIZE}° (~{GRID_SIZE * 111:.0f}km)")
    print()
    
    # Parse PBF file
    print("Step 1: Parsing PBF file...")
    parser = OSMParser()
    
    # Temporarily set to include ALL road types
    import osm_routing.parser as parser_module
    original_types = parser_module.HIGHWAY_TYPES.copy()
    parser_module.HIGHWAY_TYPES = set()
    for types in ROAD_LEVELS.values():
        parser_module.HIGHWAY_TYPES.update(types)
    
    start = time.time()
    network = parser.parse_pbf(OSM_PBF_PATH, bbox=UTTARAKHAND_BBOX)
    parse_time = time.time() - start
    
    # Restore original types
    parser_module.HIGHWAY_TYPES = original_types
    
    print(f"✓ Parsed in {parse_time:.1f}s")
    print(f"  Total roads: {len(network.roads):,}")
    print(f"  Total nodes: {len(network.nodes):,}")
    print(f"  Total edges: {len(network.edges):,}")
    print()
    
    # Organize roads by level and grid cell
    print("Step 2: Organizing roads by hierarchy and location...")
    
    roads_by_level = defaultdict(list)
    roads_by_grid = defaultdict(lambda: defaultdict(list))
    
    for road in network.roads:
        # Determine road level
        highway_type = road.highway_type
        level = None
        for lvl, types in ROAD_LEVELS.items():
            if highway_type in types:
                level = lvl
                break
        
        if not level:
            continue
        
        # Add to level
        roads_by_level[level].append(road)
        
        # Determine grid cells this road touches
        grid_cells = set()
        for node_id in road.node_ids:
            if node_id in network.nodes:
                node = network.nodes[node_id]
                cell = get_grid_cell(node.lat, node.lon)
                grid_cells.add(cell)
        
        # Add to each grid cell
        for cell in grid_cells:
            roads_by_grid[level][cell].append(road)
    
    print(f"✓ Organized roads:")
    for level in ['L1_major_highways', 'L2_regional_roads', 'L3_local_roads']:
        count = len(roads_by_level[level])
        cells = len(roads_by_grid[level])
        print(f"  {level}: {count:,} roads across {cells} grid cells")
    print()
    
    # Generate cache files
    print("Step 3: Generating cache files...")
    s3 = boto3.client('s3', region_name='us-east-1')
    
    cache_files = []
    
    # 1. Level 1 only (for long-distance routing)
    print("  Generating L1 (major highways) cache...")
    l1_network = parser._build_graph([r for r in roads_by_level['L1_major_highways']])
    l1_data = parser._serialize_network(l1_network)
    l1_json = json.dumps(l1_data).encode('utf-8')
    l1_compressed = gzip.compress(l1_json, compresslevel=9)
    
    l1_key = 'osm/cache/hierarchical/L1_major_highways.json.gz'
    s3.put_object(Bucket=S3_BUCKET, Key=l1_key, Body=l1_compressed)
    cache_files.append({
        'key': l1_key,
        'size_mb': len(l1_compressed) / 1024 / 1024,
        'roads': len(roads_by_level['L1_major_highways']),
        'nodes': len(l1_network.nodes),
        'edges': len(l1_network.edges)
    })
    print(f"    ✓ {l1_key}: {len(l1_compressed)/1024/1024:.2f} MB")
    
    # 2. Level 1+2 combined (for medium-distance routing)
    print("  Generating L1+L2 (highways + regional) cache...")
    l1_l2_roads = roads_by_level['L1_major_highways'] + roads_by_level['L2_regional_roads']
    l1_l2_network = parser._build_graph(l1_l2_roads)
    l1_l2_data = parser._serialize_network(l1_l2_network)
    l1_l2_json = json.dumps(l1_l2_data).encode('utf-8')
    l1_l2_compressed = gzip.compress(l1_l2_json, compresslevel=9)
    
    l1_l2_key = 'osm/cache/hierarchical/L1_L2_highways_regional.json.gz'
    s3.put_object(Bucket=S3_BUCKET, Key=l1_l2_key, Body=l1_l2_compressed)
    cache_files.append({
        'key': l1_l2_key,
        'size_mb': len(l1_l2_compressed) / 1024 / 1024,
        'roads': len(l1_l2_roads),
        'nodes': len(l1_l2_network.nodes),
        'edges': len(l1_l2_network.edges)
    })
    print(f"    ✓ {l1_l2_key}: {len(l1_l2_compressed)/1024/1024:.2f} MB")
    
    # 3. Grid cell index (metadata about which cells have roads)
    print("  Generating grid index...")
    grid_index = {}
    for level in ['L1_major_highways', 'L2_regional_roads', 'L3_local_roads']:
        grid_index[level] = {}
        for cell, roads in roads_by_grid[level].items():
            grid_index[level][cell] = {
                'road_count': len(roads),
                'cache_key': f'osm/cache/hierarchical/{level}/{cell}.json.gz'
            }
    
    grid_index_json = json.dumps(grid_index, indent=2).encode('utf-8')
    grid_index_key = 'osm/cache/hierarchical/grid_index.json'
    s3.put_object(Bucket=S3_BUCKET, Key=grid_index_key, Body=grid_index_json)
    print(f"    ✓ {grid_index_key}: {len(grid_index_json)/1024:.2f} KB")
    
    # 4. Generate top 10 densest grid cells for L2 and L3 (for demo)
    print("  Generating sample grid cell caches...")
    
    for level in ['L2_regional_roads', 'L3_local_roads']:
        # Sort cells by road count
        cells_sorted = sorted(
            roads_by_grid[level].items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        # Generate cache for top 10 cells
        for cell, roads in cells_sorted[:10]:
            cell_network = parser._build_graph(roads)
            cell_data = parser._serialize_network(cell_network)
            cell_json = json.dumps(cell_data).encode('utf-8')
            cell_compressed = gzip.compress(cell_json, compresslevel=9)
            
            cell_key = f'osm/cache/hierarchical/{level}/{cell}.json.gz'
            s3.put_object(Bucket=S3_BUCKET, Key=cell_key, Body=cell_compressed)
            print(f"    ✓ {cell_key}: {len(cell_compressed)/1024:.2f} KB ({len(roads)} roads)")
    
    print()
    print("="*70)
    print("SUCCESS! Hierarchical cache generated")
    print("="*70)
    print()
    print("Cache Structure:")
    print("  L1 (major highways): Fast loading for long-distance routing")
    print("  L1+L2 (highways + regional): Medium-distance routing")
    print("  Grid cells: Load only roads near your coordinates")
    print()
    print("Usage in Lambda:")
    print("  1. Always load L1 (fast, <2MB)")
    print("  2. If distance > 50km: Use L1 only")
    print("  3. If distance 10-50km: Load L1+L2")
    print("  4. If distance < 10km: Load L1 + relevant grid cells")
    print()
    print("Files generated:")
    for cf in cache_files:
        print(f"  {cf['key']}")
        print(f"    Size: {cf['size_mb']:.2f} MB")
        print(f"    Roads: {cf['roads']:,}")
        print(f"    Nodes: {cf['nodes']:,}")
        print(f"    Edges: {cf['edges']:,}")
        print()

if __name__ == '__main__':
    main()
