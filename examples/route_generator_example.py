#!/usr/bin/env python3
"""
Route Generator Example

This example demonstrates how to use the Route_Generator class to generate
optimal route alignments for rural infrastructure planning in Uttarakhand.
"""

import asyncio
from rural_infrastructure_planning.routing.route_generator import (
    Route_Generator, RouteConstraints, Coordinate
)
from rural_infrastructure_planning.data.api_client import API_Client
from rural_infrastructure_planning.data.dem_processor import DEM_Processor
from rural_infrastructure_planning.data.osm_parser import OSM_Parser

async def main():
    """Demonstrate Route_Generator usage."""
    print("🛣️  Route Generator Example for Uttarakhand Infrastructure Planning")
    print("=" * 70)
    
    # Define route endpoints (Uttarkashi region)
    start = Coordinate(30.7268, 78.4354, elevation=1158)  # Uttarkashi town
    end = Coordinate(30.8500, 78.5500, elevation=1800)    # Higher elevation destination
    
    print(f"📍 Start: {start.latitude:.4f}°N, {start.longitude:.4f}°E (elevation: {start.elevation}m)")
    print(f"📍 End: {end.latitude:.4f}°N, {end.longitude:.4f}°E (elevation: {end.elevation}m)")
    
    # Initialize components with API integration
    api_client = API_Client(prefer_local_for_testing=True)
    dem_processor = DEM_Processor(api_client)
    osm_parser = OSM_Parser()
    
    # Create Route_Generator
    route_generator = Route_Generator(
        api_client=api_client,
        dem_processor=dem_processor,
        osm_parser=osm_parser
    )
    
    # Define routing constraints for Uttarakhand conditions
    constraints = RouteConstraints(
        max_slope_degrees=25.0,          # Conservative for mountain roads
        max_elevation_gain=1500.0,       # Reasonable for the region
        max_distance_km=30.0,            # Local connectivity
        avoid_flood_zones=True,          # Important for monsoon season
        prefer_existing_roads=True,      # Cost-effective approach
        construction_season="post_monsoon",  # Optimal timing
        priority_factors=["safety", "cost", "accessibility"]
    )
    
    print(f"\n⚙️  Routing Constraints:")
    print(f"   Max slope: {constraints.max_slope_degrees}°")
    print(f"   Max elevation gain: {constraints.max_elevation_gain}m")
    print(f"   Max distance: {constraints.max_distance_km}km")
    print(f"   Priorities: {', '.join(constraints.priority_factors)}")
    
    try:
        print(f"\n🔄 Generating route alternatives...")
        
        # Generate multiple route alternatives
        routes = await route_generator.generate_routes(
            start=start,
            end=end,
            constraints=constraints,
            num_alternatives=3
        )
        
        print(f"\n✅ Generated {len(routes)} route alternatives:")
        print("=" * 70)
        
        for i, route in enumerate(routes, 1):
            print(f"\n🛤️  Route {i}: {route.id}")
            print(f"   Strategy: {route.algorithm_used}")
            print(f"   Distance: {route.total_distance:.2f} km")
            print(f"   Elevation gain: {route.elevation_gain:.0f}m")
            print(f"   Elevation loss: {route.elevation_loss:.0f}m")
            print(f"   Construction cost: ${route.estimated_cost:,.0f}")
            print(f"   Construction time: {route.estimated_duration} days")
            print(f"   Difficulty: {route.construction_difficulty:.1f}/100")
            print(f"   Risk score: {route.risk_score:.1f}/100")
            print(f"   Waypoints: {len(route.waypoints)}")
            print(f"   Data sources: {', '.join(route.data_sources) if route.data_sources else 'Local data'}")
            
            # Calculate detailed metrics
            metrics = route_generator.calculate_route_metrics(route)
            print(f"   Accessibility: {metrics.accessibility_score:.1f}/100")
            print(f"   Sustainability: {metrics.sustainability_score:.1f}/100")
            print(f"   Max slope: {metrics.max_slope_degrees:.1f}°")
            print(f"   Avg slope: {metrics.avg_slope_degrees:.1f}°")
            
            # Show terrain breakdown
            terrain_types = {}
            for segment in route.segments:
                terrain_types[segment.terrain_type] = terrain_types.get(segment.terrain_type, 0) + 1
            
            print(f"   Terrain: {dict(terrain_types)}")
            
            # Show risk factors
            all_risks = set()
            for segment in route.segments:
                all_risks.update(segment.risk_factors)
            
            if all_risks:
                print(f"   Risk factors: {', '.join(all_risks)}")
        
        # Demonstrate route optimization
        if routes:
            print(f"\n🔧 Optimizing best route...")
            best_route = routes[0]  # Routes are sorted by composite score
            
            # Load cost surface for optimization
            from rural_infrastructure_planning.data.api_client import BoundingBox
            bounds = BoundingBox(
                north=max(start.latitude, end.latitude) + 0.02,
                south=min(start.latitude, end.latitude) - 0.02,
                east=max(start.longitude, end.longitude) + 0.02,
                west=min(start.longitude, end.longitude) - 0.02
            )
            
            dem_data = await dem_processor.load_elevation_data(bounds)
            cost_surface = await dem_processor.generate_cost_surface(dem_data)
            
            optimized_route = await route_generator.optimize_alignment(
                best_route, cost_surface, iterations=3
            )
            
            print(f"   Original cost: ${best_route.estimated_cost:,.0f}")
            print(f"   Optimized cost: ${optimized_route.estimated_cost:,.0f}")
            print(f"   Savings: ${best_route.estimated_cost - optimized_route.estimated_cost:,.0f}")
        
        print(f"\n🎯 Route Generation Summary:")
        print(f"   Total alternatives: {len(routes)}")
        print(f"   Best route distance: {routes[0].total_distance:.2f} km")
        print(f"   Best route cost: ${routes[0].estimated_cost:,.0f}")
        print(f"   Construction time: {routes[0].estimated_duration} days")
        
        print(f"\n💡 Recommendations:")
        best_route = routes[0]
        if best_route.construction_difficulty < 30:
            print("   ✅ Low construction difficulty - suitable for standard equipment")
        elif best_route.construction_difficulty < 60:
            print("   ⚠️  Moderate difficulty - may require specialized equipment")
        else:
            print("   🚨 High difficulty - requires careful planning and specialized equipment")
        
        if best_route.risk_score < 25:
            print("   ✅ Low risk - suitable for year-round construction")
        elif best_route.risk_score < 50:
            print("   ⚠️  Moderate risk - avoid monsoon season construction")
        else:
            print("   🚨 High risk - requires extensive mitigation measures")
        
        print(f"\n🏗️  Construction Planning:")
        print(f"   Recommended season: {constraints.construction_season or 'Post-monsoon (Oct-Nov)'}")
        print(f"   Estimated timeline: {best_route.estimated_duration} days")
        print(f"   Budget requirement: ${best_route.estimated_cost:,.0f}")
        
    except Exception as e:
        print(f"❌ Route generation failed: {e}")
        return False
    
    print(f"\n🎉 Route generation completed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        exit(1)