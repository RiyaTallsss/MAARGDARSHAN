#!/usr/bin/env python3
"""
Demonstration of API_Client functionality.

This script shows how to use the API_Client class to fetch data from multiple
sources with intelligent fallbacks.
"""

import asyncio
from datetime import datetime, timedelta
from rural_infrastructure_planning.data import (
    API_Client,
    BoundingBox,
    Coordinate,
    DateRange
)


async def main():
    """Demonstrate API_Client functionality."""
    print("🌟 API_Client Demonstration")
    print("=" * 50)
    
    # Define test area (Uttarkashi region)
    bounds = BoundingBox(
        north=30.8,
        south=30.7,
        east=78.5,
        west=78.4
    )
    
    coordinate = Coordinate(latitude=30.75, longitude=78.45)
    date_range = DateRange(
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now()
    )
    
    async with API_Client() as client:
        print(f"📍 Test Area: {bounds.south}°S to {bounds.north}°N, {bounds.west}°W to {bounds.east}°E")
        print(f"📍 Test Coordinate: {coordinate.latitude}°, {coordinate.longitude}°")
        print()
        
        # 1. Fetch elevation data
        print("🏔️  Fetching elevation data...")
        elevation_data = await client.fetch_elevation_data(bounds)
        print(f"   ✓ Source: {elevation_data.source}")
        print(f"   ✓ Resolution: {elevation_data.resolution}m")
        print(f"   ✓ Data points: {len(elevation_data.elevations)}")
        if elevation_data.elevations:
            print(f"   ✓ Elevation range: {min(elevation_data.elevations):.1f}m - {max(elevation_data.elevations):.1f}m")
        print()
        
        # 2. Query OSM data
        print("🗺️  Querying OpenStreetMap data...")
        osm_data = await client.query_osm_data(bounds, ['roads', 'settlements', 'infrastructure'])
        print(f"   ✓ Source: {osm_data.source}")
        print(f"   ✓ Roads: {len(osm_data.roads)}")
        print(f"   ✓ Settlements: {len(osm_data.settlements)}")
        print(f"   ✓ Infrastructure: {len(osm_data.infrastructure)}")
        print()
        
        # 3. Get weather data
        print("🌦️  Getting weather data...")
        weather_data = await client.get_weather_data(coordinate, date_range)
        print(f"   ✓ Source: {weather_data.data_source}")
        print(f"   ✓ Current temperature: {weather_data.current_conditions['temperature']}°C")
        print(f"   ✓ Current humidity: {weather_data.current_conditions['humidity']}%")
        print(f"   ✓ Rainfall history: {len(weather_data.rainfall_history)} months")
        if weather_data.rainfall_history:
            avg_rainfall = sum(weather_data.rainfall_history) / len(weather_data.rainfall_history)
            print(f"   ✓ Average monthly rainfall: {avg_rainfall:.1f}mm")
        print()
        
        # 4. Check flood risk
        print("🌊 Checking flood risk...")
        flood_data = await client.check_flood_risk(bounds)
        print(f"   ✓ Source: {flood_data.source}")
        print(f"   ✓ Flood zones: {len(flood_data.flood_zones)}")
        print(f"   ✓ Risk areas: {len(flood_data.risk_levels)}")
        if flood_data.risk_levels:
            max_risk = max(flood_data.risk_levels.values())
            print(f"   ✓ Maximum risk level: {max_risk}/100")
        print()
        
        # 5. Get comprehensive infrastructure data
        print("🏗️  Getting infrastructure data...")
        infrastructure_data = await client.get_infrastructure_data(bounds)
        print(f"   ✓ Data sources: {infrastructure_data['data_sources']}")
        print(f"   ✓ Infrastructure points: {len(infrastructure_data['infrastructure'])}")
        print(f"   ✓ Settlements: {len(infrastructure_data['settlements'])}")
        print()
        
        # 6. Show API status
        print("📊 API Status:")
        status = client.get_api_status()
        print(f"   ✓ APIs tracked: {len(status['api_availability'])}")
        
        cache_stats = status['cache_stats']
        print(f"   ✓ Cache entries: {cache_stats['total_entries']}")
        print(f"   ✓ Cache size: {cache_stats['total_size_mb']:.2f} MB")
        print(f"   ✓ Data sources in cache: {list(cache_stats['sources'].keys())}")
        print()
        
        # 7. Demonstrate caching
        print("⚡ Testing cache performance...")
        start_time = datetime.now()
        elevation_data_cached = await client.fetch_elevation_data(bounds)
        cache_time = (datetime.now() - start_time).total_seconds()
        print(f"   ✓ Cached request completed in {cache_time:.3f} seconds")
        print(f"   ✓ Same data source: {elevation_data_cached.source == elevation_data.source}")
        print()
        
        print("🎉 API_Client demonstration completed successfully!")
        print("\n📋 Summary:")
        print(f"   • Elevation data: {elevation_data.source}")
        print(f"   • OSM data: {osm_data.source}")
        print(f"   • Weather data: {weather_data.data_source}")
        print(f"   • Flood data: {flood_data.source}")
        print(f"   • Infrastructure: {infrastructure_data['data_sources']}")
        print(f"   • Cache performance: {cache_time:.3f}s for cached request")


if __name__ == "__main__":
    asyncio.run(main())