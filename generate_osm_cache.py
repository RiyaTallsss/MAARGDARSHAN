#!/usr/bin/env python3
"""
Generate OSM road network cache file locally and upload to S3

This script:
1. Parses the northern-zone PBF file locally (takes 2-3 minutes)
2. Builds the road network graph
3. Saves compressed cache to S3
4. Lambda will then load the cache instantly instead of parsing PBF
"""

import sys
import time
import boto3
import tempfile
import logging
from osm_routing.parser import OSMParser

# Set up logging to show progress
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
S3_BUCKET = 'maargdarshan-data'
OSM_PBF_PATH = 'Maps/northern-zone-260121.osm.pbf'
OSM_CACHE_S3_KEY = 'osm/cache/road_network.json.gz'

def main():
    print("=" * 60)
    print("OSM Cache Generator for MAARGDARSHAN")
    print("=" * 60)
    print()
    
    # Initialize S3 client
    s3 = boto3.client('s3', region_name='us-east-1')
    
    # Step 1: Parse PBF file
    print(f"Step 1: Parsing PBF file: {OSM_PBF_PATH}")
    print("This may take 10-20 minutes for the 208MB file...")
    print("Progress will be shown every 10,000 ways processed")
    print()
    
    start_time = time.time()
    parser = OSMParser()
    
    try:
        network = parser.parse_pbf(OSM_PBF_PATH)
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
    print("SUCCESS! OSM cache generated and uploaded")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Lambda will now load the cache instantly (< 5 seconds)")
    print("2. No more PBF parsing needed")
    print("3. Test the API:")
    print()
    print("   curl -X POST https://pma49s9qy8.execute-api.us-east-1.amazonaws.com/prod/routes \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{\"start\": {\"lat\": 30.7268, \"lon\": 78.4354}, \"end\": {\"lat\": 30.9993, \"lon\": 78.9394}}'")
    print()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
