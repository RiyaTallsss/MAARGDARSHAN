#!/usr/bin/env python3
"""
Generate OSM cache in separate, resumable steps

This breaks the process into 4 steps that can be run independently:
1. Parse PBF → save parsed roads to pickle
2. Build graph → save network to pickle  
3. Build spatial index → save to pickle
4. Compress and upload to S3

Each step saves its output, so you can resume if something fails.
"""

import sys
import time
import boto3
import pickle
import gzip
import logging
import os
from osm_routing.parser import OSMParser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
S3_BUCKET = 'maargdarshan-data'
OSM_PBF_PATH = 'Maps/northern-zone-260121.osm.pbf'
OSM_CACHE_S3_KEY = 'osm/cache/road_network.json.gz'

# Intermediate files
PARSED_ROADS_FILE = '/tmp/osm_parsed_roads.pkl'
NETWORK_FILE = '/tmp/osm_network.pkl'
INDEXED_NETWORK_FILE = '/tmp/osm_network_indexed.pkl'
CACHE_FILE = '/tmp/road_network.json.gz'

def step1_parse_pbf():
    """Step 1: Parse PBF file and save roads"""
    print("=" * 60)
    print("STEP 1: Parse PBF File")
    print("=" * 60)
    print()
    
    if os.path.exists(PARSED_ROADS_FILE):
        print(f"✓ Already completed - {PARSED_ROADS_FILE} exists")
        print("  Delete this file to re-run this step")
        return True
    
    print(f"Parsing: {OSM_PBF_PATH}")
    print("This will take 1-2 minutes...")
    print()
    
    start_time = time.time()
    parser = OSMParser()
    
    try:
        # Just parse, don't build graph yet
        from osm_routing.parser import RoadHandler
        handler = RoadHandler()
        handler.apply_file(OSM_PBF_PATH, locations=True)
        
        parse_time = time.time() - start_time
        
        print(f"✓ Parsed in {parse_time:.1f}s")
        print(f"  Roads found: {len(handler.roads):,}")
        print()
        
        # Save to pickle
        print(f"Saving to: {PARSED_ROADS_FILE}")
        with open(PARSED_ROADS_FILE, 'wb') as f:
            pickle.dump({
                'roads': handler.roads,
                'nodes_used': handler.nodes_used,
                'data_quality_issues': handler.data_quality_issues
            }, f)
        
        file_size = os.path.getsize(PARSED_ROADS_FILE) / 1024 / 1024
        print(f"✓ Saved ({file_size:.1f} MB)")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def step2_build_graph():
    """Step 2: Build graph from parsed roads"""
    print("=" * 60)
    print("STEP 2: Build Graph")
    print("=" * 60)
    print()
    
    if not os.path.exists(PARSED_ROADS_FILE):
        print(f"✗ Error: {PARSED_ROADS_FILE} not found")
        print("  Run step 1 first")
        return False
    
    if os.path.exists(NETWORK_FILE):
        print(f"✓ Already completed - {NETWORK_FILE} exists")
        print("  Delete this file to re-run this step")
        return True
    
    print(f"Loading parsed roads from: {PARSED_ROADS_FILE}")
    with open(PARSED_ROADS_FILE, 'rb') as f:
        data = pickle.load(f)
    
    roads = data['roads']
    nodes_used = data['nodes_used']
    
    print(f"  Loaded {len(roads):,} roads")
    print()
    
    print("Building graph...")
    print("This will take 5-10 minutes for 393K roads...")
    print()
    
    start_time = time.time()
    parser = OSMParser()
    
    try:
        network = parser._build_graph(roads, nodes_used)
        build_time = time.time() - start_time
        
        print(f"✓ Built graph in {build_time:.1f}s")
        print(f"  Nodes: {len(network.nodes):,}")
        print(f"  Edges: {len(network.edges):,}")
        print()
        
        # Save to pickle
        print(f"Saving to: {NETWORK_FILE}")
        with open(NETWORK_FILE, 'wb') as f:
            pickle.dump(network, f)
        
        file_size = os.path.getsize(NETWORK_FILE) / 1024 / 1024
        print(f"✓ Saved ({file_size:.1f} MB)")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def step3_build_index():
    """Step 3: Build spatial index"""
    print("=" * 60)
    print("STEP 3: Build Spatial Index")
    print("=" * 60)
    print()
    
    if not os.path.exists(NETWORK_FILE):
        print(f"✗ Error: {NETWORK_FILE} not found")
        print("  Run step 2 first")
        return False
    
    if os.path.exists(INDEXED_NETWORK_FILE):
        print(f"✓ Already completed - {INDEXED_NETWORK_FILE} exists")
        print("  Delete this file to re-run this step")
        return True
    
    print(f"Loading network from: {NETWORK_FILE}")
    with open(NETWORK_FILE, 'rb') as f:
        network = pickle.load(f)
    
    print(f"  Loaded network with {len(network.nodes):,} nodes")
    print()
    
    print("Building spatial index...")
    print("This will take 1-2 minutes...")
    print()
    
    start_time = time.time()
    
    try:
        network.build_spatial_index()
        index_time = time.time() - start_time
        
        print(f"✓ Built index in {index_time:.1f}s")
        print()
        
        # Save to pickle
        print(f"Saving to: {INDEXED_NETWORK_FILE}")
        with open(INDEXED_NETWORK_FILE, 'wb') as f:
            pickle.dump(network, f)
        
        file_size = os.path.getsize(INDEXED_NETWORK_FILE) / 1024 / 1024
        print(f"✓ Saved ({file_size:.1f} MB)")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def step4_compress_and_upload():
    """Step 4: Compress to JSON and upload to S3"""
    print("=" * 60)
    print("STEP 4: Compress and Upload")
    print("=" * 60)
    print()
    
    if not os.path.exists(INDEXED_NETWORK_FILE):
        print(f"✗ Error: {INDEXED_NETWORK_FILE} not found")
        print("  Run step 3 first")
        return False
    
    print(f"Loading indexed network from: {INDEXED_NETWORK_FILE}")
    with open(INDEXED_NETWORK_FILE, 'rb') as f:
        network = pickle.load(f)
    
    print(f"  Loaded network with {len(network.nodes):,} nodes")
    print()
    
    # Save to compressed JSON
    print(f"Compressing to: {CACHE_FILE}")
    print("This will take 2-3 minutes...")
    print()
    
    start_time = time.time()
    parser = OSMParser()
    
    try:
        parser.save_to_cache(network, CACHE_FILE)
        compress_time = time.time() - start_time
        
        file_size = os.path.getsize(CACHE_FILE) / 1024 / 1024
        print(f"✓ Compressed in {compress_time:.1f}s ({file_size:.1f} MB)")
        print()
        
        # Upload to S3
        print(f"Uploading to: s3://{S3_BUCKET}/{OSM_CACHE_S3_KEY}")
        s3 = boto3.client('s3', region_name='us-east-1')
        
        start_time = time.time()
        s3.upload_file(CACHE_FILE, S3_BUCKET, OSM_CACHE_S3_KEY)
        upload_time = time.time() - start_time
        
        print(f"✓ Uploaded in {upload_time:.1f}s")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("OSM Cache Generator - Step-by-Step Mode")
    print("=" * 60)
    print()
    print("This breaks the process into 4 resumable steps:")
    print("  1. Parse PBF file (~1-2 min)")
    print("  2. Build graph (~5-10 min)")
    print("  3. Build spatial index (~1-2 min)")
    print("  4. Compress and upload (~2-3 min)")
    print()
    print("Each step saves progress, so you can resume if interrupted.")
    print()
    
    # Run all steps
    if not step1_parse_pbf():
        return 1
    
    if not step2_build_graph():
        return 1
    
    if not step3_build_index():
        return 1
    
    if not step4_compress_and_upload():
        return 1
    
    # Success!
    print("=" * 60)
    print("SUCCESS! All steps completed")
    print("=" * 60)
    print()
    print("OSM cache is now deployed and ready to use!")
    print()
    print("Test the API:")
    print("  curl -X POST https://pma49s9qy8.execute-api.us-east-1.amazonaws.com/prod/routes \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"start\": {\"lat\": 30.7268, \"lon\": 78.4354}, \"end\": {\"lat\": 30.9993, \"lon\": 78.9394}}'")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
