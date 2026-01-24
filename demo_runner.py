#!/usr/bin/env python3
"""
Demo Runner - Lightweight version of the rural infrastructure planning system.

This demo shows the regional analysis features without requiring heavy geospatial dependencies.
"""

import asyncio
import sys
from datetime import datetime
from typing import Dict, Any, List

# Mock the heavy dependencies for demo purposes
class MockCoordinate:
    def __init__(self, latitude: float, longitude: float, elevation: float = None):
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
    
    def to_dict(self):
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'elevation': self.elevation
        }

class MockAPI_Client:
    def __init__(self, prefer_local_for_testing=True):
        self.prefer_local = prefer_local_for_testing
    
    async def get_weather_data(self, coordinate):
        # Mock weather data
        return {
            'temperature': 15.0,
            'precipitation': 2.0,
            'wind_speed': 12.0,
            'humidity': 65.0,
            'visibility': 8.0,
            'cached': False
        }

# Import the regional analyzer (this should work without heavy dependencies)
try:
    from rural_infrastructure_planning.config.regional_config import UttarkashiAnalyzer, TerrainType, ConstructionSeason
    REGIONAL_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Regional config not available: {e}")
    REGIONAL_AVAILABLE = False

async def demo_regional_analysis():
    """Demonstrate the regional analysis features."""
    print("🏔️  Rural Infrastructure Planning - Regional Analysis Demo")
    print("=" * 70)
    
    if not REGIONAL_AVAILABLE:
        print("❌ Regional analysis not available. Please check imports.")
        return False
    
    # Test coordinates in Uttarkashi region
    coordinates = [
        MockCoordinate(30.7268, 78.4354, 1158),  # Uttarkashi town
        MockCoordinate(30.8500, 78.5500, 1800),  # Higher elevation
        MockCoordinate(30.9000, 78.6000, 2500),  # Mid-hills
        MockCoordinate(31.0000, 78.7000, 3500),  # High hills
        MockCoordinate(31.1000, 78.8000, 4500),  # Alpine zone
    ]
    
    locations = [
        "Uttarkashi Town",
        "Village Access Road",
        "Mid-Hills Settlement",
        "High-Altitude Village",
        "Alpine Research Station"
    ]
    
    # Initialize regional analyzer
    api_client = MockAPI_Client()
    analyzer = UttarkashiAnalyzer(api_client)
    
    print(f"📍 Analyzing {len(coordinates)} locations in Uttarkashi region:")
    print()
    
    for i, (coord, location) in enumerate(zip(coordinates, locations)):
        print(f"🎯 Location {i+1}: {location}")
        print(f"   Coordinates: {coord.latitude:.4f}°N, {coord.longitude:.4f}°E")
        print(f"   Elevation: {coord.elevation}m")
        
        # Test different slope scenarios
        slopes = [5.0, 15.0, 25.0, 35.0]  # Different terrain difficulties
        
        for slope in slopes:
            # Terrain classification
            terrain_type = analyzer.classify_terrain_type(coord, slope)
            print(f"   Slope {slope:4.1f}°: {terrain_type.value}")
            
            # Construction difficulty
            difficulty = analyzer.calculate_construction_difficulty(coord, slope, terrain_type)
            print(f"              Difficulty: {difficulty:.1f}/100")
        
        # Seasonal analysis
        seasonal_info = analyzer.get_optimal_construction_season(coord)
        current_season = seasonal_info['current_season']
        print(f"   Current season: {current_season.value if hasattr(current_season, 'value') else current_season}")
        print(f"   Elevation adjusted: {seasonal_info['elevation_adjusted']}")
        print(f"   Next optimal month: {seasonal_info['next_optimal_month']}")
        
        # Real-time weather factors
        weather_factors = await analyzer.get_real_time_weather_factors(coord)
        print(f"   Weather risk: {weather_factors['weather_risk_score']:.2f}")
        print(f"   Temperature: {weather_factors['temperature_c']:.1f}°C")
        print(f"   Altitude adjusted: {weather_factors['altitude_adjusted_temperature']:.1f}°C")
        print(f"   Data source: {weather_factors['data_source']}")
        
        # Cost estimation
        base_cost = 500000  # $500k base cost
        cost_analysis = analyzer.calculate_regional_cost_estimate(base_cost, coord)
        print(f"   Base cost: ${base_cost:,.0f}")
        print(f"   Regional cost: ${cost_analysis['total_cost']:,.0f}")
        print(f"   Cost multiplier: {cost_analysis['cost_increase_factor']:.2f}x")
        print(f"   Elevation zone: {cost_analysis['elevation_zone']}")
        
        # Geological hazards
        hazard_assessment = analyzer.assess_geological_hazards(coord, 20.0)  # 20° slope
        print(f"   Geological risk: {hazard_assessment['risk_category']}")
        print(f"   Overall risk score: {hazard_assessment['overall_risk_score']:.2f}")
        
        hazards = hazard_assessment['hazards']
        if hazards:
            print(f"   Active hazards: {', '.join(hazards.keys())}")
            for hazard_name, hazard_info in hazards.items():
                risk_level = hazard_info.get('risk_level', 0)
                print(f"     - {hazard_name}: {risk_level:.2f} risk level")
        
        recommendations = hazard_assessment.get('mitigation_recommendations', [])
        if recommendations:
            print(f"   Recommendations: {len(recommendations)} items")
            for rec in recommendations[:2]:  # Show first 2
                print(f"     • {rec}")
        
        print()
    
    # Summary analysis
    print("📊 Regional Analysis Summary:")
    print("=" * 50)
    
    # Elevation zones analysis
    elevation_zones = {}
    for coord in coordinates:
        zone = analyzer._get_elevation_zone(coord.elevation or 1000)
        elevation_zones[zone] = elevation_zones.get(zone, 0) + 1
    
    print("Elevation zones covered:")
    for zone, count in elevation_zones.items():
        print(f"  • {zone}: {count} location(s)")
    
    # Seasonal recommendations
    print(f"\nSeasonal construction recommendations:")
    current_month = datetime.now().month
    if current_month in [10, 11, 12, 1, 2, 3]:
        print("  ✅ Current season: OPTIMAL for construction")
        print("  📅 Recommended: Maximize construction activities")
    elif current_month in [4, 5, 9]:
        print("  ⚠️  Current season: FEASIBLE for construction")
        print("  📅 Recommended: Monitor weather conditions closely")
    elif current_month in [6, 7, 8]:
        print("  🚨 Current season: CHALLENGING (monsoon)")
        print("  📅 Recommended: Limit to essential activities only")
    
    # Cost analysis summary
    total_base_cost = len(coordinates) * 500000
    total_regional_cost = sum(
        analyzer.calculate_regional_cost_estimate(500000, coord)['total_cost']
        for coord in coordinates
    )
    
    print(f"\nCost analysis for {len(coordinates)} projects:")
    print(f"  Base cost total: ${total_base_cost:,.0f}")
    print(f"  Regional cost total: ${total_regional_cost:,.0f}")
    print(f"  Regional premium: ${total_regional_cost - total_base_cost:,.0f}")
    print(f"  Average multiplier: {total_regional_cost / total_base_cost:.2f}x")
    
    print(f"\n🎉 Regional analysis demo completed successfully!")
    return True

async def demo_simple_route_planning():
    """Demonstrate simple route planning concepts."""
    print("\n🛣️  Simple Route Planning Demo")
    print("=" * 50)
    
    if not REGIONAL_AVAILABLE:
        print("❌ Regional analysis not available.")
        return False
    
    # Define a simple route
    start = MockCoordinate(30.7268, 78.4354, 1158)  # Uttarkashi
    end = MockCoordinate(30.8500, 78.5500, 1800)    # Destination
    
    print(f"Route planning from Uttarkashi to mountain village:")
    print(f"  Start: {start.latitude:.4f}°N, {start.longitude:.4f}°E ({start.elevation}m)")
    print(f"  End: {end.latitude:.4f}°N, {end.longitude:.4f}°E ({end.elevation}m)")
    
    # Calculate basic route metrics
    import math
    
    # Distance calculation (simplified)
    lat_diff = end.latitude - start.latitude
    lon_diff = end.longitude - start.longitude
    distance_km = math.sqrt(lat_diff**2 + lon_diff**2) * 111  # Rough conversion
    
    elevation_gain = end.elevation - start.elevation
    avg_slope = math.degrees(math.atan2(elevation_gain, distance_km * 1000))
    
    print(f"\nRoute characteristics:")
    print(f"  Distance: {distance_km:.2f} km")
    print(f"  Elevation gain: {elevation_gain:.0f} m")
    print(f"  Average slope: {avg_slope:.1f}°")
    
    # Regional analysis for route
    analyzer = UttarkashiAnalyzer(MockAPI_Client())
    
    # Analyze start point
    start_difficulty = analyzer.calculate_construction_difficulty(start, avg_slope)
    start_cost = analyzer.calculate_regional_cost_estimate(distance_km * 100000, start)
    
    print(f"\nConstruction analysis:")
    print(f"  Difficulty score: {start_difficulty:.1f}/100")
    print(f"  Estimated cost: ${start_cost['total_cost']:,.0f}")
    print(f"  Cost per km: ${start_cost['total_cost']/distance_km:,.0f}")
    
    # Seasonal planning
    seasonal = analyzer.get_optimal_construction_season(start)
    print(f"\nSeasonal planning:")
    print(f"  Current season: {seasonal['current_season'].value if hasattr(seasonal['current_season'], 'value') else seasonal['current_season']}")
    print(f"  Next optimal: Month {seasonal['next_optimal_month']}")
    
    recommendations = seasonal.get('recommendations', [])
    if recommendations:
        print(f"  Recommendations:")
        for rec in recommendations[:3]:
            print(f"    • {rec}")
    
    return True

def main():
    """Run the demo."""
    print("🚀 Starting Rural Infrastructure Planning Demo")
    print("This demo works without heavy geospatial dependencies")
    print()
    
    try:
        # Run regional analysis demo
        success1 = asyncio.run(demo_regional_analysis())
        
        # Run simple route planning demo
        success2 = asyncio.run(demo_simple_route_planning())
        
        if success1 and success2:
            print("\n✅ All demos completed successfully!")
            print("\n💡 Next steps:")
            print("   1. Install full dependencies for complete functionality")
            print("   2. Try the web API: python -m rural_infrastructure_planning.api.main")
            print("   3. Run the full example: python examples/route_generator_example.py")
            return True
        else:
            print("\n⚠️  Some demos had issues, but core functionality works!")
            return False
            
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)