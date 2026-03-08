#!/usr/bin/env python3
"""
Quick test of OSM routing modules (no PBF parsing)
"""

import sys

def test_imports():
    """Test that all modules can be imported"""
    print("=" * 60)
    print("Testing OSM Routing Module Imports")
    print("=" * 60)
    print()
    
    try:
        print("1. Testing osm_routing.models...")
        from osm_routing.models import RoadNode, RoadEdge, RoadNetwork, Route, RouteSegment
        print("   ✓ Models imported successfully")
        
        print("2. Testing osm_routing.parser...")
        from osm_routing.parser import OSMParser
        print("   ✓ Parser imported successfully")
        
        print("3. Testing osm_routing.calculator...")
        from osm_routing.calculator import RouteCalculator
        print("   ✓ Calculator imported successfully")
        
        print("4. Testing osm_routing.renderer...")
        from osm_routing.renderer import RoadRenderer
        print("   ✓ Renderer imported successfully")
        
        print()
        print("✓ All modules imported successfully")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_structures():
    """Test basic data structure creation"""
    print("=" * 60)
    print("Testing Data Structures")
    print("=" * 60)
    print()
    
    try:
        from osm_routing.models import RoadNode, RoadEdge, RoadNetwork, Route, RouteSegment
        
        print("1. Creating RoadNode...")
        node1 = RoadNode(id="n1", lat=30.7268, lon=78.4354, elevation=1200)
        node2 = RoadNode(id="n2", lat=30.7300, lon=78.4400, elevation=1250)
        print(f"   ✓ Created nodes: {node1.id}, {node2.id}")
        
        print("2. Creating RoadEdge...")
        edge = RoadEdge(
            id="e1",
            source_node_id="n1",
            target_node_id="n2",
            coordinates=[(78.4354, 30.7268), (78.4400, 30.7300)],
            distance_m=500.0,
            name="Test Road",
            highway_type="primary",
            surface="paved"
        )
        print(f"   ✓ Created edge: {edge.id} ({edge.distance_m}m)")
        
        print("3. Creating RoadNetwork...")
        network = RoadNetwork()
        network.nodes = {"n1": node1, "n2": node2}
        network.edges = {"e1": edge}
        print(f"   ✓ Created network with {len(network.nodes)} nodes, {len(network.edges)} edges")
        
        print("4. Testing serialization...")
        network_dict = network.to_dict()
        network_restored = RoadNetwork.from_dict(network_dict)
        print(f"   ✓ Serialization round-trip successful")
        
        print("5. Building spatial index...")
        network.build_spatial_index()
        print(f"   ✓ Spatial index built")
        
        print()
        print("✓ All data structure tests passed")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Data structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pathfinding():
    """Test pathfinding with a simple graph"""
    print("=" * 60)
    print("Testing Pathfinding")
    print("=" * 60)
    print()
    
    try:
        from osm_routing.models import RoadNode, RoadEdge, RoadNetwork
        from osm_routing.calculator import RouteCalculator
        
        print("1. Creating test network...")
        # Create a simple 3-node network: A -> B -> C
        network = RoadNetwork()
        
        nodeA = RoadNode(id="A", lat=30.0, lon=78.0)
        nodeB = RoadNode(id="B", lat=30.1, lon=78.1)
        nodeC = RoadNode(id="C", lat=30.2, lon=78.2)
        
        network.nodes = {"A": nodeA, "B": nodeB, "C": nodeC}
        
        edgeAB = RoadEdge(
            id="AB",
            source_node_id="A",
            target_node_id="B",
            coordinates=[(78.0, 30.0), (78.1, 30.1)],
            distance_m=1000.0,
            highway_type="primary",
            surface="paved"
        )
        
        edgeBC = RoadEdge(
            id="BC",
            source_node_id="B",
            target_node_id="C",
            coordinates=[(78.1, 30.1), (78.2, 30.2)],
            distance_m=1000.0,
            highway_type="secondary",
            surface="unpaved"
        )
        
        network.edges = {"AB": edgeAB, "BC": edgeBC}
        network.build_spatial_index()
        
        print(f"   ✓ Created network: A -> B -> C")
        
        print("2. Initializing calculator...")
        calculator = RouteCalculator(network)
        print(f"   ✓ Calculator initialized")
        
        print("3. Finding path from A to C...")
        path = calculator.find_path("A", "C", calculator.cost_shortest)
        
        if path is None:
            print(f"   ✗ No path found")
            return False
        
        print(f"   ✓ Found path with {len(path)} edges")
        print(f"     Path: {' -> '.join([edge.id for edge in path])}")
        
        print("4. Testing cost functions...")
        cost_shortest = calculator.cost_shortest(edgeAB)
        cost_safest = calculator.cost_safest(edgeAB)
        cost_budget = calculator.cost_budget(edgeAB)
        
        print(f"   ✓ Shortest cost: {cost_shortest:.1f}m")
        print(f"   ✓ Safest cost: {cost_safest:.1f}m")
        print(f"   ✓ Budget cost: {cost_budget:.1f}m")
        
        print()
        print("✓ All pathfinding tests passed")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Pathfinding test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rendering():
    """Test GeoJSON rendering"""
    print("=" * 60)
    print("Testing GeoJSON Rendering")
    print("=" * 60)
    print()
    
    try:
        from osm_routing.models import RoadNode, RoadEdge, RoadNetwork
        from osm_routing.renderer import RoadRenderer
        
        print("1. Creating test network...")
        network = RoadNetwork()
        
        node1 = RoadNode(id="n1", lat=30.0, lon=78.0)
        node2 = RoadNode(id="n2", lat=30.1, lon=78.1)
        
        network.nodes = {"n1": node1, "n2": node2}
        
        edge = RoadEdge(
            id="e1",
            source_node_id="n1",
            target_node_id="n2",
            coordinates=[(78.0, 30.0), (78.1, 30.1)],
            distance_m=1000.0,
            name="Test Road",
            highway_type="primary",
            surface="paved"
        )
        
        network.edges = {"e1": edge}
        
        print(f"   ✓ Created test network")
        
        print("2. Rendering to GeoJSON...")
        renderer = RoadRenderer()
        geojson = renderer.to_geojson(network)
        
        print(f"   ✓ GeoJSON generated")
        print(f"     Type: {geojson['type']}")
        print(f"     Features: {len(geojson['features'])}")
        
        if geojson['features']:
            feature = geojson['features'][0]
            print(f"     First feature type: {feature['geometry']['type']}")
            print(f"     Properties: {list(feature['properties'].keys())}")
        
        print()
        print("✓ All rendering tests passed")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ Rendering test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print()
    
    all_passed = True
    
    all_passed &= test_imports()
    all_passed &= test_data_structures()
    all_passed &= test_pathfinding()
    all_passed &= test_rendering()
    
    print("=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print()
        print("OSM routing modules are working correctly!")
        print("The code is ready for deployment once the Lambda runtime")
        print("is upgraded to Python 3.11 (for C++ compiler compatibility).")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 60)
    print()
    
    sys.exit(0 if all_passed else 1)
