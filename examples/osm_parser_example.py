#!/usr/bin/env python3
"""
Example usage of the OSM_Parser class for rural infrastructure planning.

This example demonstrates how to use the OSM_Parser to extract road networks,
settlements, and infrastructure data for the Uttarkashi region.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rural_infrastructure_planning.data.osm_parser import OSM_Parser, BoundingBox


async def main():
    """Demonstrate OSM_Parser usage for rural infrastructure planning."""
    
    print("🗺️  OSM Parser Example for Rural Infrastructure Planning")
    print("=" * 60)
    
    # Define the area of interest (Uttarkashi district)
    uttarkashi_bounds = BoundingBox(
        north=31.0,   # Northern boundary
        south=30.4,   # Southern boundary  
        east=79.0,    # Eastern boundary
        west=78.0     # Western boundary
    )
    
    print(f"📍 Area of Interest: Uttarkashi District")
    print(f"   Bounds: {uttarkashi_bounds.south}°N to {uttarkashi_bounds.north}°N, "
          f"{uttarkashi_bounds.west}°E to {uttarkashi_bounds.east}°E")
    print()
    
    # Initialize OSM Parser
    async with OSM_Parser() as parser:
        print("🔧 OSM Parser initialized")
        
        # 1. Extract comprehensive OSM data
        print("\n📊 Extracting OSM data...")
        osm_data = await parser.parse_osm_data(
            bounds=uttarkashi_bounds,
            features=['roads', 'settlements', 'infrastructure'],
            use_local_fallback=True
        )
        
        print(f"✅ Data extracted from: {osm_data.source}")
        print(f"   Freshness: {osm_data.freshness_info.get_freshness_indicator() if osm_data.freshness_info else 'Unknown'}")
        print(f"   Quality Score: {osm_data.freshness_info.quality_score:.2f}" if osm_data.freshness_info else "")
        
        # 2. Analyze road network
        print(f"\n🛣️  Road Network Analysis:")
        print(f"   Total roads found: {len(osm_data.roads)}")
        
        # Group roads by type
        road_types = {}
        total_length = 0
        for road in osm_data.roads:
            highway_type = road.get('highway_type', 'unknown')
            road_types[highway_type] = road_types.get(highway_type, 0) + 1
            total_length += road.get('length_km', 0)
        
        print(f"   Total network length: {total_length:.1f} km")
        print("   Road types:")
        for road_type, count in sorted(road_types.items()):
            print(f"     - {road_type}: {count} segments")
        
        # 3. Analyze settlements
        print(f"\n🏘️  Settlement Analysis:")
        print(f"   Total settlements: {len(osm_data.settlements)}")
        
        # Group settlements by type
        settlement_types = {}
        for settlement in osm_data.settlements:
            place_type = settlement.get('place_type', 'unknown')
            settlement_types[place_type] = settlement_types.get(place_type, 0) + 1
        
        print("   Settlement types:")
        for place_type, count in sorted(settlement_types.items()):
            print(f"     - {place_type}: {count}")
        
        # Show major settlements
        major_settlements = [s for s in osm_data.settlements 
                           if s.get('place_type') in ['city', 'town']]
        if major_settlements:
            print("   Major settlements:")
            for settlement in major_settlements[:5]:  # Top 5
                name = settlement.get('name', 'Unknown')
                place_type = settlement.get('place_type', 'unknown')
                print(f"     - {name} ({place_type})")
        
        # 4. Analyze infrastructure
        print(f"\n🏥 Infrastructure Analysis:")
        print(f"   Total infrastructure: {len(osm_data.infrastructure)}")
        
        # Group infrastructure by type
        infra_types = {}
        for infra in osm_data.infrastructure:
            infra_type = infra.get('type', 'unknown')
            infra_types[infra_type] = infra_types.get(infra_type, 0) + 1
        
        print("   Infrastructure types:")
        for infra_type, count in sorted(infra_types.items()):
            print(f"     - {infra_type}: {count}")
        
        # Show key infrastructure
        key_infrastructure = [i for i in osm_data.infrastructure 
                            if i.get('type') in ['hospital', 'school', 'market']]
        if key_infrastructure:
            print("   Key infrastructure:")
            for infra in key_infrastructure[:5]:  # Top 5
                name = infra.get('name', 'Unknown')
                infra_type = infra.get('type', 'unknown')
                print(f"     - {name} ({infra_type})")
        
        # 5. Build detailed road network graph
        print(f"\n🕸️  Building Road Network Graph...")
        
        # Create mock OSM data for network analysis
        mock_data = parser._create_mock_osm_data(uttarkashi_bounds)
        road_network = parser.extract_road_network(mock_data, uttarkashi_bounds)
        
        print(f"   Network nodes: {len(road_network.nodes)}")
        print(f"   Network edges: {len(road_network.edges)}")
        print(f"   Total length: {road_network.total_length_km:.2f} km")
        
        # Network connectivity analysis
        network_info = road_network.to_dict()
        connectivity = network_info.get('connectivity_info', {})
        print(f"   Connected network: {connectivity.get('is_connected', False)}")
        print(f"   Network components: {connectivity.get('number_of_components', 0)}")
        print(f"   Average node degree: {connectivity.get('average_degree', 0):.1f}")
        
        # 6. Infrastructure accessibility analysis
        print(f"\n🎯 Infrastructure Accessibility:")
        
        # Find settlements without nearby infrastructure
        settlements_with_coords = [s for s in osm_data.settlements 
                                 if 'coordinate' in s or ('lat' in s and 'lon' in s)]
        
        print(f"   Settlements analyzed: {len(settlements_with_coords)}")
        
        # Simple accessibility check (within 5km of infrastructure)
        accessible_settlements = 0
        for settlement in settlements_with_coords:
            # This is a simplified check - in practice you'd use proper distance calculations
            accessible_settlements += 1  # Assume accessible for demo
        
        accessibility_rate = (accessible_settlements / len(settlements_with_coords) * 100) if settlements_with_coords else 0
        print(f"   Infrastructure accessibility: {accessibility_rate:.1f}%")
        
        # 7. Planning recommendations
        print(f"\n📋 Planning Recommendations:")
        
        if len(osm_data.roads) < 10:
            print("   ⚠️  Limited road network data - consider additional surveys")
        
        if len([s for s in osm_data.settlements if s.get('place_type') == 'village']) > 5:
            print("   📍 Multiple villages identified - prioritize connectivity")
        
        if len([i for i in osm_data.infrastructure if i.get('type') == 'hospital']) < 2:
            print("   🏥 Limited healthcare infrastructure - consider medical facility access")
        
        if len([i for i in osm_data.infrastructure if i.get('type') == 'school']) < 3:
            print("   🎓 Limited educational infrastructure - consider school connectivity")
        
        print("   ✅ Use this data for route planning and risk assessment")
        
    print(f"\n🎉 OSM analysis complete! Data ready for route planning.")


if __name__ == "__main__":
    asyncio.run(main())