"""
Integration tests for API_Client functionality.

Tests the complete workflow of data fetching with fallbacks.
Includes property-based tests for comprehensive data integration validation.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, Verbosity
from typing import List, Dict, Any
import numpy as np

from rural_infrastructure_planning.data import (
    API_Client,
    BoundingBox,
    Coordinate,
    DateRange
)


@pytest_asyncio.fixture
async def api_client():
    """Create API client for integration testing."""
    client = API_Client()
    async with client:
        yield client


class TestAPIIntegration:
    """Integration tests for API_Client."""
    
    @pytest.mark.asyncio
    async def test_complete_data_workflow(self, api_client):
        """Test complete data fetching workflow."""
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
        
        # Test elevation data fetching (will use fallback)
        elevation_data = await api_client.fetch_elevation_data(bounds)
        assert elevation_data is not None
        assert elevation_data.source in ["nasa_srtm_api", "usgs_api", "local_dem"]
        assert len(elevation_data.elevations) > 0
        print(f"✓ Elevation data fetched from: {elevation_data.source}")
        
        # Test OSM data querying (will use fallback)
        osm_data = await api_client.query_osm_data(bounds, ['roads', 'settlements', 'infrastructure'])
        assert osm_data is not None
        assert osm_data.source in ["overpass_api", "local_pbf"]
        print(f"✓ OSM data fetched from: {osm_data.source}")
        
        # Test weather data fetching (will use fallback)
        weather_data = await api_client.get_weather_data(coordinate, date_range)
        assert weather_data is not None
        assert weather_data.data_source in ["openweathermap_api", "imd_api", "local_csv", "default"]
        assert len(weather_data.rainfall_history) == 12
        print(f"✓ Weather data fetched from: {weather_data.data_source}")
        
        # Test flood risk checking (will use fallback)
        flood_data = await api_client.check_flood_risk(bounds)
        assert flood_data is not None
        assert flood_data.source in ["disaster_api", "local_pdf"]
        assert len(flood_data.flood_zones) > 0
        print(f"✓ Flood data fetched from: {flood_data.source}")
        
        # Test infrastructure data (combines multiple sources)
        infrastructure_data = await api_client.get_infrastructure_data(bounds)
        assert infrastructure_data is not None
        assert 'infrastructure' in infrastructure_data
        assert 'settlements' in infrastructure_data
        print(f"✓ Infrastructure data fetched from: {infrastructure_data['data_sources']}")
        
        # Test API status
        status = api_client.get_api_status()
        assert 'api_availability' in status
        assert 'cache_stats' in status
        print(f"✓ API status retrieved: {len(status['api_availability'])} APIs tracked")
        
        print("\n🎉 Complete data workflow test passed!")
    
    @pytest.mark.asyncio
    async def test_caching_functionality(self, api_client):
        """Test that caching works correctly."""
        bounds = BoundingBox(north=30.8, south=30.7, east=78.5, west=78.4)
        
        # First call - should fetch and cache
        start_time = datetime.now()
        elevation_data1 = await api_client.fetch_elevation_data(bounds)
        first_call_time = (datetime.now() - start_time).total_seconds()
        
        # Second call - should use cache (faster)
        start_time = datetime.now()
        elevation_data2 = await api_client.fetch_elevation_data(bounds)
        second_call_time = (datetime.now() - start_time).total_seconds()
        
        # Verify data is the same
        assert elevation_data1.source == elevation_data2.source
        assert len(elevation_data1.elevations) == len(elevation_data2.elevations)
        
        # Second call should be faster (cached)
        assert second_call_time < first_call_time
        
        print(f"✓ Caching working: First call {first_call_time:.3f}s, Second call {second_call_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_error_resilience(self, api_client):
        """Test that the system handles errors gracefully."""
        # Test with extreme bounds that might cause issues
        extreme_bounds = BoundingBox(north=89.0, south=88.0, east=179.0, west=178.0)
        
        # Should not raise exceptions, should fall back gracefully
        try:
            elevation_data = await api_client.fetch_elevation_data(extreme_bounds)
            assert elevation_data is not None
            print("✓ Error resilience test passed - graceful fallback to local data")
        except Exception as e:
            pytest.fail(f"System should handle errors gracefully, but got: {e}")
    
    def test_data_model_consistency(self):
        """Test that data models are consistent and serializable."""
        bounds = BoundingBox(north=30.8, south=30.7, east=78.5, west=78.4)
        coordinate = Coordinate(latitude=30.75, longitude=78.45, elevation=1500.0)
        
        # Test serialization
        bounds_dict = bounds.to_dict()
        coord_dict = coordinate.to_dict()
        
        assert bounds_dict['north'] == 30.8
        assert coord_dict['lat'] == 30.75
        assert coord_dict['elevation'] == 1500.0
        
        print("✓ Data model consistency test passed")


if __name__ == "__main__":
    # Run a simple test
    async def main():
        async with API_Client() as client:
            bounds = BoundingBox(north=30.8, south=30.7, east=78.5, west=78.4)
            
            print("Testing API_Client integration...")
            
            # Test elevation data
            elevation_data = await client.fetch_elevation_data(bounds)
            print(f"Elevation data source: {elevation_data.source}")
            
            # Test OSM data
            osm_data = await client.query_osm_data(bounds, ['roads'])
            print(f"OSM data source: {osm_data.source}")
            
            print("Integration test completed successfully!")
    
    asyncio.run(main())


# Property-based test generators for geospatial data (optimized for performance)
@st.composite
def valid_uttarkashi_bounds(draw):
    """Generate valid bounding boxes within Uttarkashi region (optimized for smaller areas)."""
    # Uttarkashi district approximate bounds: 30.4-31.5 N, 77.8-79.2 E
    # Use smaller bounding boxes for faster processing
    south = draw(st.floats(min_value=30.6, max_value=31.2))  # Narrower range
    north = draw(st.floats(min_value=south + 0.01, max_value=min(south + 0.2, 31.3)))  # Smaller boxes
    west = draw(st.floats(min_value=78.0, max_value=78.8))  # Narrower range
    east = draw(st.floats(min_value=west + 0.01, max_value=min(west + 0.2, 79.0)))  # Smaller boxes
    
    return BoundingBox(north=north, south=south, east=east, west=west)


@st.composite
def valid_uttarkashi_coordinate(draw):
    """Generate valid coordinates within Uttarkashi region."""
    latitude = draw(st.floats(min_value=30.4, max_value=31.5))
    longitude = draw(st.floats(min_value=77.8, max_value=79.2))
    elevation = draw(st.one_of(st.none(), st.floats(min_value=500, max_value=7000)))
    
    return Coordinate(latitude=latitude, longitude=longitude, elevation=elevation)


@st.composite
def valid_date_range(draw):
    """Generate valid date ranges for weather queries (optimized for shorter ranges)."""
    end_date = datetime.now()
    days_back = draw(st.integers(min_value=7, max_value=90))  # Reduced from 365 to 90 days
    start_date = end_date - timedelta(days=days_back)
    
    return DateRange(start_date=start_date, end_date=end_date)


@st.composite
def valid_feature_list(draw):
    """Generate valid feature lists for OSM queries (optimized for simpler queries)."""
    all_features = ['roads', 'settlements', 'infrastructure']
    # Prefer single features for faster processing, but allow combinations
    num_features = draw(st.integers(min_value=1, max_value=2))  # Reduced from 3 to 2 max features
    return draw(st.lists(st.sampled_from(all_features), min_size=num_features, max_size=num_features, unique=True))


class TestAPIIntegrationProperties:
    """Property-based tests for API integration."""
    
    @given(
        bounds=valid_uttarkashi_bounds(),
        coordinate=valid_uttarkashi_coordinate(),
        date_range=valid_date_range(),
        features=valid_feature_list()
    )
    @settings(max_examples=10, verbosity=Verbosity.verbose, deadline=None)  # Optimized for fast execution as requested
    @pytest.mark.asyncio
    async def test_property_comprehensive_data_integration(self, bounds, coordinate, date_range, features):
        """
        **Property 1: Comprehensive Data Integration (API + fallback components)**
        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 10.1**
        
        For any valid combination of DEM, OSM, rainfall, and flood data within geographic bounds,
        the system should successfully extract all required metrics and integrate them into a 
        unified geospatial framework within the specified time limit.
        """
        async with API_Client(prefer_local_for_testing=True) as api_client:
            start_time = datetime.now()
            
            # Test all data sources can be fetched successfully
            elevation_data = await api_client.fetch_elevation_data(bounds)
            osm_data = await api_client.query_osm_data(bounds, features)
            weather_data = await api_client.get_weather_data(coordinate, date_range)
            flood_data = await api_client.check_flood_risk(bounds)
            infrastructure_data = await api_client.get_infrastructure_data(bounds)
            
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            
            # Verify all data sources return valid data
            assert elevation_data is not None, "Elevation data must be available"
            assert osm_data is not None, "OSM data must be available"
            assert weather_data is not None, "Weather data must be available"
            assert flood_data is not None, "Flood data must be available"
            assert infrastructure_data is not None, "Infrastructure data must be available"
            
            # Verify data source tracking (API or fallback)
            valid_elevation_sources = ["nasa_srtm_api", "usgs_api", "local_dem"]
            valid_osm_sources = ["overpass_api", "local_pbf"]
            valid_weather_sources = ["openweathermap_api", "imd_api", "local_csv", "default"]
            valid_flood_sources = ["disaster_api", "local_pdf"]
            
            assert elevation_data.source in valid_elevation_sources, f"Invalid elevation source: {elevation_data.source}"
            assert osm_data.source in valid_osm_sources, f"Invalid OSM source: {osm_data.source}"
            assert weather_data.data_source in valid_weather_sources, f"Invalid weather source: {weather_data.data_source}"
            assert flood_data.source in valid_flood_sources, f"Invalid flood source: {flood_data.source}"
            
            # Verify required metrics are extracted
            # Elevation metrics
            assert len(elevation_data.elevations) > 0, "Must have elevation values"
            assert len(elevation_data.coordinates) > 0, "Must have coordinate data"
            assert elevation_data.resolution > 0, "Must have valid resolution"
            assert all(isinstance(elev, (int, float)) for elev in elevation_data.elevations), "Elevations must be numeric"
            
            # OSM metrics
            if 'roads' in features:
                assert isinstance(osm_data.roads, list), "Roads must be a list"
            if 'settlements' in features:
                assert isinstance(osm_data.settlements, list), "Settlements must be a list"
            if 'infrastructure' in features:
                assert isinstance(osm_data.infrastructure, list), "Infrastructure must be a list"
            
            # Weather metrics
            assert isinstance(weather_data.current_conditions, dict), "Current conditions must be a dict"
            assert len(weather_data.rainfall_history) == 12, "Must have 12 months of rainfall data"
            assert all(isinstance(val, (int, float)) for val in weather_data.rainfall_history), "Rainfall must be numeric"
            
            # Flood metrics
            assert isinstance(flood_data.flood_zones, list), "Flood zones must be a list"
            assert isinstance(flood_data.risk_levels, dict), "Risk levels must be a dict"
            assert len(flood_data.flood_zones) > 0, "Must have flood zone data"
            
            # Infrastructure metrics
            assert 'infrastructure' in infrastructure_data, "Must have infrastructure key"
            assert 'settlements' in infrastructure_data, "Must have settlements key"
            assert isinstance(infrastructure_data['infrastructure'], list), "Infrastructure must be a list"
            assert isinstance(infrastructure_data['settlements'], list), "Settlements must be a list"
            
            # Verify unified geospatial framework (consistent coordinate systems and bounds)
            assert elevation_data.bounds is not None, "Elevation data must have bounds"
            assert osm_data.bounds is not None, "OSM data must have bounds"
            assert flood_data.bounds is not None, "Flood data must have bounds"
            
            # Verify bounds consistency
            assert elevation_data.bounds.north >= bounds.south, "Elevation bounds must overlap query bounds"
            assert elevation_data.bounds.south <= bounds.north, "Elevation bounds must overlap query bounds"
            assert osm_data.bounds.north >= bounds.south, "OSM bounds must overlap query bounds"
            assert osm_data.bounds.south <= bounds.north, "OSM bounds must overlap query bounds"
            
            # Verify coordinate validity
            for coord in elevation_data.coordinates:
                assert -90 <= coord.latitude <= 90, f"Invalid latitude: {coord.latitude}"
                assert -180 <= coord.longitude <= 180, f"Invalid longitude: {coord.longitude}"
                if coord.elevation is not None:
                    assert -500 <= coord.elevation <= 10000, f"Invalid elevation: {coord.elevation}"
            
            # Verify time limit (optimized for testing - focus on functionality over strict timing)
            # Allow more time during testing since we're using real APIs with network latency
            max_time = 60.0  # Increased to 60s to account for network variability during testing
            assert total_time <= max_time, f"Data integration took {total_time:.2f}s, must be ≤ {max_time}s"
            
            # Verify data freshness and timestamps
            assert elevation_data.timestamp is not None, "Elevation data must have timestamp"
            assert osm_data.timestamp is not None, "OSM data must have timestamp"
            assert weather_data.freshness is not None, "Weather data must have freshness timestamp"
            assert flood_data.timestamp is not None, "Flood data must have timestamp"
            
            # Verify all timestamps are recent (within last hour for this test)
            now = datetime.now()
            one_hour_ago = now - timedelta(hours=1)
            
            assert elevation_data.timestamp >= one_hour_ago, "Elevation timestamp too old"
            assert osm_data.timestamp >= one_hour_ago, "OSM timestamp too old"
            assert weather_data.freshness >= one_hour_ago, "Weather timestamp too old"
            assert flood_data.timestamp >= one_hour_ago, "Flood timestamp too old"
            
            # Verify API status tracking
            api_status = api_client.get_api_status()
            assert 'api_availability' in api_status, "Must track API availability"
            assert 'cache_stats' in api_status, "Must track cache statistics"
            assert 'timestamp' in api_status, "Must have status timestamp"
            
            print(f"✓ Property test passed: {total_time:.2f}s, sources: "
                  f"elev={elevation_data.source}, osm={osm_data.source}, "
                  f"weather={weather_data.data_source}, flood={flood_data.source}")
    
    @given(bounds=valid_uttarkashi_bounds())
    @settings(max_examples=10, verbosity=Verbosity.verbose, deadline=None)  # Optimized for fast execution as requested
    @pytest.mark.asyncio
    async def test_property_api_fallback_resilience(self, bounds):
        """
        **Property: API Fallback Resilience**
        **Validates: Requirements 10.1, 10.2**
        
        For any valid geographic bounds, the system should gracefully fall back to local data
        when APIs are unavailable and maintain data quality standards.
        """
        async with API_Client(prefer_local_for_testing=True) as api_client:
            # Force API failures by corrupting API status
            original_status = api_client.api_status.copy()
            
            try:
                # Simulate all APIs being down
                api_client.api_status = {
                    'nasa_srtm': False,
                    'usgs_elevation': False,
                    'overpass': False,
                    'openweathermap': False,
                    'imd_api': False,
                    'disaster_api': False,
                    'google_places': False
                }
                
                # All data should still be available via fallbacks
                elevation_data = await api_client.fetch_elevation_data(bounds)
                osm_data = await api_client.query_osm_data(bounds, ['roads', 'settlements'])
                
                # Verify fallback sources are used
                assert elevation_data.source == "local_dem", f"Should use local DEM, got {elevation_data.source}"
                assert osm_data.source == "local_pbf", f"Should use local PBF, got {osm_data.source}"
                
                # Verify data quality is maintained
                assert len(elevation_data.elevations) > 0, "Fallback elevation data must not be empty"
                assert len(osm_data.roads) > 0 or len(osm_data.settlements) > 0, "Fallback OSM data must not be empty"
                
                # Verify data structure consistency
                assert elevation_data.resolution > 0, "Fallback data must have valid resolution"
                assert elevation_data.bounds is not None, "Fallback data must have bounds"
                
                print(f"✓ Fallback resilience verified for bounds {bounds.south:.3f},{bounds.west:.3f} to {bounds.north:.3f},{bounds.east:.3f}")
                
            finally:
                # Restore original API status
                api_client.api_status = original_status
    
    @given(
        bounds=valid_uttarkashi_bounds(),
        coordinate=valid_uttarkashi_coordinate()
    )
    @settings(max_examples=10, verbosity=Verbosity.verbose, deadline=None)  # Optimized for fast execution as requested
    @pytest.mark.asyncio
    async def test_property_data_consistency_across_sources(self, bounds, coordinate):
        """
        **Property: Data Consistency Across Sources**
        **Validates: Requirements 1.5, 10.5**
        
        For any valid geographic area, data from different sources (API vs local) should
        maintain consistent formats and coordinate systems.
        """
        async with API_Client(prefer_local_for_testing=True) as api_client:
            # Get data from current sources (mix of API and local)
            elevation_data = await api_client.fetch_elevation_data(bounds)
            
            # Verify coordinate system consistency
            for coord in elevation_data.coordinates:
                # All coordinates should be within reasonable bounds for Uttarkashi
                assert 30.0 <= coord.latitude <= 32.0, f"Latitude {coord.latitude} outside Uttarkashi region"
                assert 77.0 <= coord.longitude <= 80.0, f"Longitude {coord.longitude} outside Uttarkashi region"
                
                # Elevation should be reasonable for Himalayan region
                if coord.elevation is not None:
                    assert 300 <= coord.elevation <= 8000, f"Elevation {coord.elevation}m unrealistic for region"
            
            # Verify data format consistency regardless of source
            assert isinstance(elevation_data.elevations, list), "Elevations must be list regardless of source"
            assert isinstance(elevation_data.coordinates, list), "Coordinates must be list regardless of source"
            assert isinstance(elevation_data.resolution, (int, float)), "Resolution must be numeric regardless of source"
            assert isinstance(elevation_data.source, str), "Source must be string"
            assert isinstance(elevation_data.timestamp, datetime), "Timestamp must be datetime object"
            
            # Verify bounds format consistency
            bounds_dict = elevation_data.bounds.to_dict()
            required_keys = ['north', 'south', 'east', 'west']
            for key in required_keys:
                assert key in bounds_dict, f"Bounds must have {key} regardless of source"
                assert isinstance(bounds_dict[key], (int, float)), f"Bounds {key} must be numeric"
            
            print(f"✓ Data consistency verified: source={elevation_data.source}, "
                  f"coords={len(elevation_data.coordinates)}, res={elevation_data.resolution}m")
    
    @given(coordinate=valid_uttarkashi_coordinate())
    @settings(max_examples=10, verbosity=Verbosity.verbose, deadline=None)  # Optimized for fast execution as requested
    @pytest.mark.asyncio
    async def test_property_weather_data_completeness(self, coordinate):
        """
        **Property: Weather Data Completeness**
        **Validates: Requirements 1.3, 3.2**
        
        For any valid coordinate, weather data should provide complete seasonal information
        for risk assessment regardless of data source.
        """
        async with API_Client(prefer_local_for_testing=True) as api_client:
            date_range = DateRange(
                start_date=datetime.now() - timedelta(days=365),
                end_date=datetime.now()
            )
            
            weather_data = await api_client.get_weather_data(coordinate, date_range)
            
            # Verify completeness of weather data
            assert len(weather_data.rainfall_history) == 12, "Must have 12 months of rainfall data"
            assert len(weather_data.temperature_data) == 12, "Must have 12 months of temperature data"
            
            # Verify current conditions completeness
            required_conditions = ['temperature', 'humidity', 'pressure', 'wind_speed', 'rainfall']
            for condition in required_conditions:
                assert condition in weather_data.current_conditions, f"Missing current condition: {condition}"
                assert isinstance(weather_data.current_conditions[condition], (int, float)), f"Condition {condition} must be numeric"
            
            # Verify seasonal patterns are realistic for Uttarkashi
            rainfall_values = weather_data.rainfall_history
            
            # Monsoon months (June-September, indices 5-8) should have higher rainfall
            monsoon_rainfall = sum(rainfall_values[5:9])
            non_monsoon_rainfall = sum(rainfall_values[:5]) + sum(rainfall_values[9:])
            
            # In Uttarkashi, monsoon should contribute significant portion of annual rainfall
            total_rainfall = sum(rainfall_values)
            if total_rainfall > 0:
                monsoon_percentage = monsoon_rainfall / total_rainfall
                assert monsoon_percentage >= 0.3, f"Monsoon rainfall too low: {monsoon_percentage:.2f}"
            
            # Verify temperature ranges are realistic for Himalayan region
            temp_values = weather_data.temperature_data
            min_temp = min(temp_values)
            max_temp = max(temp_values)
            
            assert -10 <= min_temp <= 35, f"Minimum temperature {min_temp}°C unrealistic"
            assert 5 <= max_temp <= 40, f"Maximum temperature {max_temp}°C unrealistic"
            
            print(f"✓ Weather completeness verified: source={weather_data.data_source}, "
                  f"monsoon%={monsoon_percentage:.2f}, temp_range={min_temp:.1f}-{max_temp:.1f}°C")