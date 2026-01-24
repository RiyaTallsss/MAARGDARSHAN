#!/usr/bin/env python3
"""
Simple test script to verify OSM_Parser implementation.
This script tests the basic functionality without running full test suites.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from rural_infrastructure_planning.data.osm_parser import OSM_Parser, BoundingBox


async def test_osm_parser():
    """Test basic OSM_Parser functionality."""
    print("Testing OSM_Parser implementation...")
    
    # Create test bounds for Uttarkashi region
    test_bounds = BoundingBox(
        north=30.8,
        south=30.6,
        east=78.6,
        west=78.4
    )
    
    async with OSM_Parser() as parser:
        print(f"✓ OSM_Parser initialized successfully")
        
        # Test 1: Parse OSM data with mock fallback
        print("Testing OSM data parsing...")
        try:
            osm_data = await parser.parse_osm_data(
                bounds=test_bounds,
                features=['roads', 'settlements', 'infrastructure'],
                use_local_fallback=True
            )
            
            print(f"✓ OSM data parsed successfully")
            print(f"  - Source: {osm_data.source}")
            print(f"  - Roads found: {len(osm_data.roads)}")
            print(f"  - Settlements found: {len(osm_data.settlements)}")
            print(f"  - Infrastructure found: {len(osm_data.infrastructure)}")
            print(f"  - Freshness: {osm_data.freshness_info.get_freshness_indicator() if osm_data.freshness_info else 'Unknown'}")
            
        except Exception as e:
            print(f"✗ OSM data parsing failed: {e}")
            return False
        
        # Test 2: Extract road network
        print("Testing road network extraction...")
        try:
            # Create mock OSM data for road network test
            mock_osm_data = parser._create_mock_osm_data(test_bounds)
            road_network = parser.extract_road_network(mock_osm_data, test_bounds)
            
            print(f"✓ Road network extracted successfully")
            print(f"  - Nodes: {len(road_network.nodes)}")
            print(f"  - Edges: {len(road_network.edges)}")
            print(f"  - Total length: {road_network.total_length_km:.2f} km")
            print(f"  - Road types: {road_network.road_types}")
            
        except Exception as e:
            print(f"✗ Road network extraction failed: {e}")
            return False
        
        # Test 3: Find settlements
        print("Testing settlement identification...")
        try:
            settlements = parser.find_settlements(mock_osm_data, test_bounds)
            
            print(f"✓ Settlements identified successfully")
            print(f"  - Total settlements: {len(settlements)}")
            for settlement in settlements[:3]:  # Show first 3
                print(f"    - {settlement.name} ({settlement.place_type})")
            
        except Exception as e:
            print(f"✗ Settlement identification failed: {e}")
            return False
        
        # Test 4: Get infrastructure (will use mock data due to API limitations)
        print("Testing infrastructure extraction...")
        try:
            infrastructure = await parser.get_existing_infrastructure(
                bounds=test_bounds,
                infrastructure_types=['school', 'hospital', 'market']
            )
            
            print(f"✓ Infrastructure extracted successfully")
            print(f"  - Total infrastructure: {len(infrastructure)}")
            for infra in infrastructure[:3]:  # Show first 3
                print(f"    - {infra.name} ({infra.infrastructure_type})")
            
        except Exception as e:
            print(f"✗ Infrastructure extraction failed: {e}")
            return False
    
    print("\n🎉 All OSM_Parser tests passed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_osm_parser())
    sys.exit(0 if success else 1)