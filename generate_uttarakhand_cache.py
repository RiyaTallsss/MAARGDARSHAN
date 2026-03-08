#!/usr/bin/env python3
"""
Generate OSM cache for Uttarakhand only (much smaller and faster)

This filters the northern-zone PBF to only include roads within Uttarakhand's
bounding box, making parsing and graph building much faster.
"""

import sys
import time
import boto3
import tempfile
import logging
from osm_routing.parser import OSMParser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
S3_BUCKET = 'maargdarshan-data'
OSM_PBF_PATH = 'Maps/uttarakhand-latest.osm.pbf'  # 31MB Uttarakhand-specific file
OSM_CACHE_S3_KEY = 'osm/cache/road_network.json.gz'

# Uttarakhand bounding box (original, optimized for Lambda)
# Expanded snap radius (2000m) compensates for sparse coverage
UTTARAKHAND_BBOX = (28.6, 77.5, 31.5, 81.0)  # (min_lat, min_lon, max_lat, max_lon)

def main():
    print("=" * 60)
    print("OSM Cache Generator for Uttarakhand (Filtered)")
    print("=" * 60)
    print()
    print(f"Bounding box: {UTTARAKHAND_BBOX}")
    print("This will be MUCH faster than the full northern zone!")
    print()
    
    # Initialize S3 client
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Step 1: Parse PBF file with bounding box filter
    print(f"Step 1: Parsing PBF file with Uttarakhand filter: {OSM_PBF_PATH}")
    print("Expected time: 2-5 minutes")
    print()
    
    start_time = time.time()
    parser = OSMParser()
    
    try:
        network = parser.parse_pbf(OSM_PBF_PATH, bbox=UTTARAKHAND_BBOX)
        parse_time = time.time() - start_time
        
        print(f"✓ Parsed in {parse_time:.1f}s")
        print(f"  Nodes: {len(network.nodes):,}")
        print(f"  Edges: {len(network.edges):,}")
        print()
        
    except Exception as e:
        print(f"✗ Error parsing PBF: {e}")
        return 1
    
    # Step 2: Build spatial index
    print("Step 2: Building spatial index...")
    start_time = time.time()
    
    try:
        network.build_spatial_index()
        index_time = time.time() - start_time
        
        print(f"✓ Built spatial index in {index_time:.1f}s")
        print()
        
    except Exception as e:
        print(f"✗ Error building index: {e}")
        return 1
    
    # Step 3: Save to cache file
    print("Step 3: Saving to compressed cache file...")
    start_time = time.time()
    
    try:
        cache_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json.gz')
        parser.save_to_cache(network, cache_file.name)
        save_time = time.time() - start_time
        
        # Get file size
        import os
        cache_size_mb = os.path.getsize(cache_file.name) / 1024 / 1024
        
        print(f"✓ Saved cache in {save_time:.1f}s")
        print(f"  File size: {cache_size_mb:.2f} MB")
        print()
        
    except Exception as e:
        print(f"✗ Error saving cache: {e}")
        return 1
    
    # Step 4: Upload to S3
    print(f"Step 4: Uploading to S3: s3://{S3_BUCKET}/{OSM_CACHE_S3_KEY}")
    start_time = time.time()
    
    try:
        s3.upload_file(cache_file.name, S3_BUCKET, OSM_CACHE_S3_KEY)
        upload_time = time.time() - start_time
        
        print(f"✓ Uploaded in {upload_time:.1f}s")
        print()
        
    except Exception as e:
        print(f"✗ Error uploading to S3: {e}")
        return 1
    
    # Summary
    print("=" * 60)
    print("SUCCESS! Uttarakhand OSM cache generated and uploaded")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Lambda will now load the cache instantly (< 5 seconds)")
    print("2. Test the API:")
    print()
    print("   curl -X POST https://pma49s9qy8.execute-api.us-east-1.amazonaws.com/prod/routes \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"start\": {\"lat\": 30.7268, \"lon\": 78.4354}, \"end\": {\"lat\": 30.9993, \"lon\": 78.9394}}'")
    print()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
