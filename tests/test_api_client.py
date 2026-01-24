"""
Unit tests for the API_Client class.

Tests the multi-source data fetching functionality with API integration
and fallback mechanisms.
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp

from rural_infrastructure_planning.data import (
    API_Client,
    BoundingBox,
    Coordinate,
    DateRange,
    ElevationData,
    OSMData,
    WeatherData,
    FloodRiskData
)


@pytest.fixture
def sample_bounds():
    """Sample bounding box for Uttarkashi region."""
    return BoundingBox(
        north=30.8,
        south=30.7,
        east=78.5,
        west=78.4
    )


@pytest.fixture
def sample_coordinate():
    """Sample coordinate in Uttarkashi region."""
    return Coordinate(latitude=30.75, longitude=78.45)


@pytest.fixture
def sample_date_range():
    """Sample date range for weather queries."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    return DateRange(start_date=start_date, end_date=end_date)


@pytest_asyncio.fixture
async def api_client():
    """Create API client for testing."""
    client = API_Client()
    async with client:
        yield client


class TestAPIClient:
    """Test cases for API_Client class."""
    
    def test_bounding_box_creation(self, sample_bounds):
        """Test BoundingBox creation and methods."""
        assert sample_bounds.north == 30.8
        assert sample_bounds.south == 30.7
        assert sample_bounds.east == 78.5
        assert sample_bounds.west == 78.4
        
        # Test point containment
        assert sample_bounds.contains_point(30.75, 78.45)
        assert not sample_bounds.contains_point(31.0, 78.45)
        
        # Test dictionary conversion
        bounds_dict = sample_bounds.to_dict()
        assert bounds_dict['north'] == 30.8
        assert bounds_dict['south'] == 30.7
    
    def test_coordinate_creation(self, sample_coordinate):
        """Test Coordinate creation and methods."""
        assert sample_coordinate.latitude == 30.75
        assert sample_coordinate.longitude == 78.45
        assert sample_coordinate.elevation is None
        
        # Test with elevation
        coord_with_elevation = Coordinate(30.75, 78.45, 1500.0)
        assert coord_with_elevation.elevation == 1500.0
        
        # Test dictionary conversion
        coord_dict = sample_coordinate.to_dict()
        assert coord_dict['lat'] == 30.75
        assert coord_dict['lon'] == 78.45
    
    @pytest.mark.asyncio
    async def test_api_client_initialization(self, api_client):
        """Test API client initialization."""
        assert api_client.cache is not None
        assert api_client.rate_limiter is not None
        assert api_client.session is not None
        assert isinstance(api_client.api_status, dict)
    
    @pytest.mark.asyncio
    async def test_fetch_elevation_data_fallback(self, api_client, sample_bounds):
        """Test elevation data fetching with fallback to local data."""
        # Mock API failures to test fallback
        with patch.object(api_client, '_fetch_nasa_srtm_data', return_value=None), \
             patch.object(api_client, '_fetch_usgs_elevation_data', return_value=None), \
             patch.object(api_client, '_load_local_dem_data') as mock_local:
            
            # Mock local DEM data
            mock_elevation_data = ElevationData(
                elevations=[1500.0, 1520.0, 1480.0],
                coordinates=[
                    Coordinate(30.75, 78.45, 1500.0),
                    Coordinate(30.76, 78.46, 1520.0),
                    Coordinate(30.74, 78.44, 1480.0)
                ],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            assert result is not None
            assert result.source == "local_dem"
            assert len(result.elevations) == 3
            assert result.resolution == 30.0
            mock_local.assert_called_once_with(sample_bounds)
    
    @pytest.mark.asyncio
    async def test_query_osm_data_fallback(self, api_client, sample_bounds):
        """Test OSM data querying with fallback to local data."""
        features = ['roads', 'settlements', 'infrastructure']
        
        # Mock API failure to test fallback
        with patch.object(api_client, '_query_overpass_api', return_value=None), \
             patch.object(api_client, '_load_local_osm_data') as mock_local:
            
            # Mock local OSM data
            mock_osm_data = OSMData(
                roads=[{'id': 'test_road', 'highway_type': 'primary'}],
                settlements=[{'id': 'test_settlement', 'name': 'Test Village'}],
                infrastructure=[{'id': 'test_infra', 'type': 'school'}],
                bounds=sample_bounds,
                source="local_pbf",
                timestamp=datetime.now()
            )
            mock_local.return_value = mock_osm_data
            
            result = await api_client.query_osm_data(sample_bounds, features)
            
            assert result is not None
            assert result.source == "local_pbf"
            assert len(result.roads) == 1
            assert len(result.settlements) == 1
            assert len(result.infrastructure) == 1
            mock_local.assert_called_once_with(sample_bounds, features)
    
    @pytest.mark.asyncio
    async def test_get_weather_data_fallback(self, api_client, sample_coordinate, sample_date_range):
        """Test weather data fetching with fallback to local data."""
        # Mock API failures to test fallback
        with patch.object(api_client, '_fetch_openweathermap_data', return_value=None), \
             patch.object(api_client, '_fetch_imd_data', return_value=None), \
             patch.object(api_client, '_load_local_weather_data') as mock_local:
            
            # Mock local weather data
            mock_weather_data = WeatherData(
                current_conditions={'temperature': 20.0, 'humidity': 65.0},
                rainfall_history=[50.0] * 12,
                temperature_data=[20.0] * 12,
                location=sample_coordinate,
                data_source="local_csv",
                freshness=datetime.now()
            )
            mock_local.return_value = mock_weather_data
            
            result = await api_client.get_weather_data(sample_coordinate, sample_date_range)
            
            assert result is not None
            assert result.data_source == "local_csv"
            assert len(result.rainfall_history) == 12
            assert result.current_conditions['temperature'] == 20.0
            mock_local.assert_called_once_with(sample_coordinate, sample_date_range)
    
    @pytest.mark.asyncio
    async def test_check_flood_risk_fallback(self, api_client, sample_bounds):
        """Test flood risk checking with fallback to local data."""
        # Mock API failure to test fallback
        with patch.object(api_client, '_fetch_disaster_api_data', return_value=None), \
             patch.object(api_client, '_load_local_flood_data') as mock_local:
            
            # Mock local flood data
            mock_flood_data = FloodRiskData(
                flood_zones=[{'id': 'test_zone', 'risk_level': 'high'}],
                risk_levels={'test_zone': 75.0},
                seasonal_patterns={'monsoon': [10.0] * 12},
                bounds=sample_bounds,
                source="local_pdf",
                timestamp=datetime.now()
            )
            mock_local.return_value = mock_flood_data
            
            result = await api_client.check_flood_risk(sample_bounds)
            
            assert result is not None
            assert result.source == "local_pdf"
            assert len(result.flood_zones) == 1
            assert result.risk_levels['test_zone'] == 75.0
            mock_local.assert_called_once_with(sample_bounds)
    
    @pytest.mark.asyncio
    async def test_get_infrastructure_data(self, api_client, sample_bounds):
        """Test comprehensive infrastructure data fetching."""
        # Mock OSM data
        mock_osm_data = OSMData(
            roads=[],
            settlements=[{'id': 'settlement_1', 'name': 'Test Village'}],
            infrastructure=[{'id': 'infra_1', 'type': 'school', 'name': 'Test School'}],
            bounds=sample_bounds,
            source="overpass_api",
            timestamp=datetime.now()
        )
        
        with patch.object(api_client, 'query_osm_data', return_value=mock_osm_data), \
             patch.object(api_client, '_fetch_google_places_data', return_value=None):
            
            result = await api_client.get_infrastructure_data(sample_bounds)
            
            assert result is not None
            assert 'infrastructure' in result
            assert 'settlements' in result
            assert len(result['infrastructure']) == 1
            assert len(result['settlements']) == 1
            assert result['infrastructure'][0]['name'] == 'Test School'
    
    def test_get_api_status(self, api_client):
        """Test API status reporting."""
        status = api_client.get_api_status()
        
        assert 'api_availability' in status
        assert 'cache_stats' in status
        assert 'timestamp' in status
        assert isinstance(status['api_availability'], dict)
    
    @pytest.mark.asyncio
    async def test_caching_behavior(self, api_client, sample_bounds):
        """Test that API responses are properly cached."""
        # Mock successful API response
        mock_elevation_data = ElevationData(
            elevations=[1500.0],
            coordinates=[Coordinate(30.75, 78.45, 1500.0)],
            resolution=30.0,
            source="nasa_srtm_api",
            timestamp=datetime.now(),
            bounds=sample_bounds
        )
        
        with patch.object(api_client, '_fetch_nasa_srtm_data', return_value=mock_elevation_data) as mock_api:
            # First call should hit the API
            result1 = await api_client.fetch_elevation_data(sample_bounds)
            assert result1.source == "nasa_srtm_api"
            
            # Second call should use cache (API should not be called again)
            result2 = await api_client.fetch_elevation_data(sample_bounds)
            assert result2.source == "nasa_srtm_api"
            
            # API should only be called once due to caching
            mock_api.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, api_client, sample_bounds):
        """Test error handling in API calls."""
        # Test with invalid bounds that might cause errors
        invalid_bounds = BoundingBox(north=91.0, south=-91.0, east=181.0, west=-181.0)
        
        # Should not raise exceptions, should fall back gracefully
        result = await api_client.fetch_elevation_data(invalid_bounds)
        assert result is not None  # Should get fallback data
    
    def test_data_model_serialization(self, sample_bounds, sample_coordinate):
        """Test that data models can be serialized to dictionaries."""
        # Test ElevationData serialization
        elevation_data = ElevationData(
            elevations=[1500.0, 1520.0],
            coordinates=[sample_coordinate],
            resolution=30.0,
            source="test",
            timestamp=datetime.now(),
            bounds=sample_bounds
        )
        
        elevation_dict = elevation_data.to_dict()
        assert 'elevations' in elevation_dict
        assert 'coordinates' in elevation_dict
        assert 'resolution' in elevation_dict
        assert 'source' in elevation_dict
        
        # Test OSMData serialization
        osm_data = OSMData(
            roads=[{'id': 'test_road'}],
            settlements=[{'id': 'test_settlement'}],
            infrastructure=[{'id': 'test_infra'}],
            bounds=sample_bounds,
            source="test",
            timestamp=datetime.now()
        )
        
        osm_dict = osm_data.to_dict()
        assert 'roads' in osm_dict
        assert 'settlements' in osm_dict
        assert 'infrastructure' in osm_dict
        assert 'bounds' in osm_dict


class TestAPIResponseHandling:
    """Test API response handling and error scenarios."""
    
    @pytest.mark.asyncio
    async def test_successful_api_response_handling(self, api_client, sample_bounds):
        """Test handling of successful API responses."""
        # Mock successful NASA SRTM API response
        mock_response_data = {
            'elevations': [1500.0, 1520.0, 1480.0],
            'width': 2,
            'height': 2,
            'resolution': 30.0
        }
        
        with patch.object(api_client, '_fetch_nasa_srtm_data') as mock_fetch:
            mock_elevation_data = ElevationData(
                elevations=mock_response_data['elevations'],
                coordinates=[
                    Coordinate(30.75, 78.45, 1500.0),
                    Coordinate(30.76, 78.46, 1520.0),
                    Coordinate(30.74, 78.44, 1480.0)
                ],
                resolution=30.0,
                source="nasa_srtm_api",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_fetch.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            assert result is not None
            assert result.source == "nasa_srtm_api"
            assert len(result.elevations) == 3
            assert result.freshness_info is not None
            assert result.freshness_info.source_type == "api"
            assert result.freshness_info.is_real_time is True
    
    @pytest.mark.asyncio
    async def test_api_error_response_handling(self, api_client, sample_bounds):
        """Test handling of API error responses."""
        # Mock API returning None (error condition)
        with patch.object(api_client, '_fetch_nasa_srtm_data', return_value=None), \
             patch.object(api_client, '_fetch_usgs_elevation_data', return_value=None), \
             patch.object(api_client, '_load_local_dem_data') as mock_local:
            
            # Mock local fallback data
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            # Should fall back to local data
            assert result is not None
            assert result.source == "local_dem"
            assert result.freshness_info.source_type == "local"
            mock_local.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, api_client, sample_bounds):
        """Test handling of network timeouts."""
        with patch.object(api_client, '_make_resilient_request', side_effect=asyncio.TimeoutError()), \
             patch.object(api_client, '_load_local_dem_data') as mock_local:
            
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            # Should fall back to local data after timeout
            assert result is not None
            assert result.source == "local_dem"
            mock_local.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_http_error_status_handling(self, api_client, sample_bounds):
        """Test handling of HTTP error status codes."""
        # Mock HTTP 429 (rate limited) response
        mock_error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=429,
            message="Rate Limited"
        )
        
        with patch.object(api_client, '_make_resilient_request', side_effect=mock_error), \
             patch.object(api_client, '_load_local_dem_data') as mock_local:
            
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            # Should fall back to local data after HTTP error
            assert result is not None
            assert result.source == "local_dem"
            mock_local.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_malformed_api_response_handling(self, api_client, sample_bounds):
        """Test handling of malformed API responses."""
        # Mock API returning malformed data
        with patch.object(api_client, '_fetch_nasa_srtm_data', side_effect=KeyError("Missing required field")), \
             patch.object(api_client, '_load_local_dem_data') as mock_local:
            
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            # Should fall back to local data after parsing error
            assert result is not None
            assert result.source == "local_dem"
            mock_local.assert_called_once()


class TestFallbackMechanisms:
    """Test fallback mechanisms with mock API failures."""
    
    @pytest.mark.asyncio
    async def test_elevation_api_fallback_chain(self, api_client, sample_bounds):
        """Test the complete fallback chain for elevation APIs."""
        # Mock all APIs failing in sequence
        with patch.object(api_client, '_fetch_nasa_srtm_data', return_value=None), \
             patch.object(api_client, '_fetch_usgs_elevation_data', return_value=None), \
             patch.object(api_client, '_load_local_dem_data') as mock_local:
            
            mock_elevation_data = ElevationData(
                elevations=[1500.0, 1520.0],
                coordinates=[
                    Coordinate(30.75, 78.45, 1500.0),
                    Coordinate(30.76, 78.46, 1520.0)
                ],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            assert result is not None
            assert result.source == "local_dem"
            assert result.freshness_info.source_type == "local"
            assert len(result.elevations) == 2
            mock_local.assert_called_once_with(sample_bounds)
    
    @pytest.mark.asyncio
    async def test_weather_api_fallback_chain(self, api_client, sample_coordinate, sample_date_range):
        """Test the complete fallback chain for weather APIs."""
        # Mock all weather APIs failing
        with patch.object(api_client, '_fetch_openweathermap_data', return_value=None), \
             patch.object(api_client, '_fetch_imd_data', return_value=None), \
             patch.object(api_client, '_load_local_weather_data') as mock_local:
            
            mock_weather_data = WeatherData(
                current_conditions={'temperature': 15.0, 'humidity': 70.0},
                rainfall_history=[45.0] * 12,
                temperature_data=[15.0] * 12,
                location=sample_coordinate,
                data_source="local_csv",
                freshness=datetime.now()
            )
            mock_local.return_value = mock_weather_data
            
            result = await api_client.get_weather_data(sample_coordinate, sample_date_range)
            
            assert result is not None
            assert result.data_source == "local_csv"
            assert result.freshness_info.source_type == "local"
            assert len(result.rainfall_history) == 12
            mock_local.assert_called_once_with(sample_coordinate, sample_date_range)
    
    @pytest.mark.asyncio
    async def test_osm_api_fallback_with_timeout(self, api_client, sample_bounds):
        """Test OSM API fallback when Overpass API times out."""
        # Mock Overpass API timeout
        with patch.object(api_client, '_query_overpass_api', side_effect=asyncio.TimeoutError()), \
             patch.object(api_client, '_load_local_osm_data') as mock_local:
            
            mock_osm_data = OSMData(
                roads=[{'id': 'local_road_1', 'highway_type': 'primary'}],
                settlements=[{'id': 'local_settlement_1', 'name': 'Test Village'}],
                infrastructure=[{'id': 'local_infra_1', 'type': 'school'}],
                bounds=sample_bounds,
                source="local_pbf",
                timestamp=datetime.now()
            )
            mock_local.return_value = mock_osm_data
            
            result = await api_client.query_osm_data(sample_bounds, ['roads', 'settlements'])
            
            assert result is not None
            assert result.source == "local_pbf"
            assert len(result.roads) == 1
            assert len(result.settlements) == 1
            mock_local.assert_called_once_with(sample_bounds, ['roads', 'settlements'])
    
    @pytest.mark.asyncio
    async def test_flood_api_fallback_with_network_error(self, api_client, sample_bounds):
        """Test flood API fallback when disaster API has network errors."""
        # Mock network error
        network_error = aiohttp.ClientConnectorError(
            connection_key=MagicMock(),
            os_error=OSError("Network unreachable")
        )
        
        with patch.object(api_client, '_fetch_disaster_api_data', side_effect=network_error), \
             patch.object(api_client, '_load_local_flood_data') as mock_local:
            
            mock_flood_data = FloodRiskData(
                flood_zones=[{'id': 'local_zone_1', 'risk_level': 'medium'}],
                risk_levels={'local_zone_1': 60.0},
                seasonal_patterns={'monsoon': [20.0] * 12},
                bounds=sample_bounds,
                source="local_pdf",
                timestamp=datetime.now()
            )
            mock_local.return_value = mock_flood_data
            
            result = await api_client.check_flood_risk(sample_bounds)
            
            assert result is not None
            assert result.source == "local_pdf"
            assert len(result.flood_zones) == 1
            assert result.risk_levels['local_zone_1'] == 60.0
            mock_local.assert_called_once_with(sample_bounds)
    
    @pytest.mark.asyncio
    async def test_partial_api_failure_handling(self, api_client, sample_bounds):
        """Test handling when some APIs work and others fail."""
        # Mock NASA SRTM working but USGS failing
        mock_elevation_data = ElevationData(
            elevations=[1500.0, 1520.0],
            coordinates=[
                Coordinate(30.75, 78.45, 1500.0),
                Coordinate(30.76, 78.46, 1520.0)
            ],
            resolution=30.0,
            source="nasa_srtm_api",
            timestamp=datetime.now(),
            bounds=sample_bounds
        )
        
        with patch.object(api_client, '_fetch_nasa_srtm_data', return_value=mock_elevation_data), \
             patch.object(api_client, '_fetch_usgs_elevation_data', return_value=None):
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            # Should use the working API (NASA SRTM)
            assert result is not None
            assert result.source == "nasa_srtm_api"
            assert result.freshness_info.source_type == "api"
            assert result.freshness_info.is_real_time is True
    
    @pytest.mark.asyncio
    async def test_forced_fallback_mode(self, api_client, sample_bounds):
        """Test forced fallback mode functionality."""
        # Enable forced fallback mode
        api_client.force_fallback_mode(True)
        
        with patch.object(api_client, '_load_local_dem_data') as mock_local:
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            # Should use local data even if APIs would work
            assert result is not None
            assert result.source == "local_dem"
            mock_local.assert_called_once()
        
        # Disable forced fallback mode
        api_client.force_fallback_mode(False)


class TestCachingBehavior:
    """Test caching behavior and data freshness indicators."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_behavior(self, api_client, sample_bounds):
        """Test that cached data is returned on subsequent requests."""
        # Mock API response for first call
        mock_elevation_data = ElevationData(
            elevations=[1500.0, 1520.0],
            coordinates=[
                Coordinate(30.75, 78.45, 1500.0),
                Coordinate(30.76, 78.46, 1520.0)
            ],
            resolution=30.0,
            source="nasa_srtm_api",
            timestamp=datetime.now(),
            bounds=sample_bounds
        )
        
        with patch.object(api_client, '_fetch_nasa_srtm_data', return_value=mock_elevation_data) as mock_api:
            # First call should hit the API
            result1 = await api_client.fetch_elevation_data(sample_bounds)
            assert result1.source == "nasa_srtm_api"
            assert result1.freshness_info.cache_hit is False
            
            # Second call should use cache
            result2 = await api_client.fetch_elevation_data(sample_bounds)
            assert result2.source == "nasa_srtm_api"
            assert result2.freshness_info.cache_hit is True
            
            # API should only be called once
            mock_api.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_miss_behavior(self, api_client, sample_bounds):
        """Test cache miss behavior with different parameters."""
        # Different bounds should result in cache miss
        bounds1 = BoundingBox(north=30.8, south=30.7, east=78.5, west=78.4)
        bounds2 = BoundingBox(north=30.9, south=30.8, east=78.6, west=78.5)
        
        mock_elevation_data1 = ElevationData(
            elevations=[1500.0],
            coordinates=[Coordinate(30.75, 78.45, 1500.0)],
            resolution=30.0,
            source="nasa_srtm_api",
            timestamp=datetime.now(),
            bounds=bounds1
        )
        
        mock_elevation_data2 = ElevationData(
            elevations=[1600.0],
            coordinates=[Coordinate(30.85, 78.55, 1600.0)],
            resolution=30.0,
            source="nasa_srtm_api",
            timestamp=datetime.now(),
            bounds=bounds2
        )
        
        with patch.object(api_client, '_fetch_nasa_srtm_data', side_effect=[mock_elevation_data1, mock_elevation_data2]) as mock_api:
            # First call with bounds1
            result1 = await api_client.fetch_elevation_data(bounds1)
            assert result1.elevations[0] == 1500.0
            
            # Second call with bounds2 (different cache key)
            result2 = await api_client.fetch_elevation_data(bounds2)
            assert result2.elevations[0] == 1600.0
            
            # API should be called twice (cache miss)
            assert mock_api.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_expiry_behavior(self, api_client, sample_bounds):
        """Test cache expiry and refresh behavior."""
        # Mock cache that returns None (expired)
        with patch.object(api_client.cache, 'get', return_value=None), \
             patch.object(api_client.cache, 'set') as mock_cache_set, \
             patch.object(api_client, '_fetch_nasa_srtm_data') as mock_api:
            
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="nasa_srtm_api",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_api.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            # Should fetch from API and cache the result
            assert result.source == "nasa_srtm_api"
            mock_api.assert_called_once()
            mock_cache_set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_data_freshness_indicators(self, api_client, sample_bounds):
        """Test data freshness indicators for different sources."""
        # Test API data freshness
        mock_api_data = ElevationData(
            elevations=[1500.0],
            coordinates=[Coordinate(30.75, 78.45, 1500.0)],
            resolution=30.0,
            source="nasa_srtm_api",
            timestamp=datetime.now(),
            bounds=sample_bounds
        )
        
        with patch.object(api_client, '_fetch_nasa_srtm_data', return_value=mock_api_data):
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            assert result.freshness_info is not None
            assert result.freshness_info.source_type == "api"
            assert result.freshness_info.source_name == "nasa_srtm"
            assert result.freshness_info.is_real_time is True
            assert result.freshness_info.quality_score > 0.8
            assert "🟢" in result.freshness_info.get_freshness_indicator()
    
    @pytest.mark.asyncio
    async def test_cache_performance_metrics(self, api_client):
        """Test cache performance metrics tracking."""
        # Get initial cache stats
        initial_stats = api_client.cache.get_stats()
        
        # Make some requests to populate cache
        bounds = BoundingBox(north=30.8, south=30.7, east=78.5, west=78.4)
        
        with patch.object(api_client, '_fetch_nasa_srtm_data') as mock_api:
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="nasa_srtm_api",
                timestamp=datetime.now(),
                bounds=bounds
            )
            mock_api.return_value = mock_elevation_data
            
            # First call (cache miss)
            await api_client.fetch_elevation_data(bounds)
            
            # Second call (cache hit)
            await api_client.fetch_elevation_data(bounds)
        
        # Check that cache metrics are updated
        final_stats = api_client.cache.get_stats()
        assert isinstance(final_stats, dict)
        
        # Get API status which includes cache metrics
        status = api_client.get_api_status()
        assert 'cache_stats' in status
        assert 'cost_optimization' in status
        assert isinstance(status['cost_optimization']['cache_hit_rate'], float)


class TestRateLimiting:
    """Test rate limiting and cost optimization."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_configuration(self, api_client):
        """Test that rate limiting is properly configured."""
        # Check that rate limiter has configurations for expected services
        limiter = api_client.rate_limiter
        
        # Test that we can check rate limits (should not raise errors)
        can_make_request = limiter.can_make_request('openweathermap')
        assert isinstance(can_make_request, bool)
        
        wait_time = limiter.wait_time('openweathermap')
        assert isinstance(wait_time, (int, float))
        assert wait_time >= 0
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, api_client, sample_bounds):
        """Test that rate limits are enforced."""
        # Mock a source as rate limited
        api_client.data_sources['nasa_srtm'].requests_today = 1000
        api_client.data_sources['nasa_srtm'].daily_limit = 1000
        
        with patch.object(api_client, '_load_local_dem_data') as mock_local:
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            # Should fall back to local data due to rate limiting
            assert result.source == "local_dem"
            mock_local.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cost_optimization_thresholds(self, api_client, sample_bounds):
        """Test cost optimization thresholds."""
        # Set high daily cost to trigger cost optimization
        api_client.cost_metrics.total_cost_today = 30.0  # Above $25 limit
        
        # Mock expensive source
        api_client.data_sources['google_places'].cost_per_request = 0.05
        
        with patch.object(api_client, '_load_local_dem_data') as mock_local:
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            # Should skip expensive APIs when cost limit is approached
            result = await api_client.fetch_elevation_data(sample_bounds)
            assert result.source == "local_dem"
    
    @pytest.mark.asyncio
    async def test_cost_tracking_accuracy(self, api_client, sample_bounds):
        """Test that API costs are tracked accurately."""
        initial_cost = api_client.cost_metrics.total_cost_today
        
        # Mock API with known cost
        api_client.data_sources['openweathermap'].cost_per_request = 0.001
        
        mock_weather_data = WeatherData(
            current_conditions={'temperature': 20.0},
            rainfall_history=[50.0] * 12,
            temperature_data=[20.0] * 12,
            location=Coordinate(30.75, 78.45),
            data_source="openweathermap_api",
            freshness=datetime.now()
        )
        
        with patch.object(api_client, '_fetch_openweathermap_data', return_value=mock_weather_data):
            await api_client.get_weather_data(
                Coordinate(30.75, 78.45),
                DateRange(datetime.now() - timedelta(days=30), datetime.now())
            )
            
            # Cost should be tracked
            expected_cost = initial_cost + 0.001
            assert abs(api_client.cost_metrics.total_cost_today - expected_cost) < 0.0001
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_functionality(self, api_client, sample_bounds):
        """Test circuit breaker pattern for failing APIs."""
        # Simulate multiple failures to trigger circuit breaker
        source = api_client.data_sources['nasa_srtm']
        source.failure_count = 5  # Above threshold
        source.is_available = False
        
        with patch.object(api_client, '_load_local_dem_data') as mock_local:
            mock_elevation_data = ElevationData(
                elevations=[1500.0],
                coordinates=[Coordinate(30.75, 78.45, 1500.0)],
                resolution=30.0,
                source="local_dem",
                timestamp=datetime.now(),
                bounds=sample_bounds
            )
            mock_local.return_value = mock_elevation_data
            
            result = await api_client.fetch_elevation_data(sample_bounds)
            
            # Should use fallback due to circuit breaker
            assert result.source == "local_dem"
            mock_local.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_reset(self, api_client):
        """Test circuit breaker reset functionality."""
        # Set some sources as unavailable
        api_client.data_sources['nasa_srtm'].is_available = False
        api_client.data_sources['openweathermap'].is_available = False
        
        # Reset circuit breakers
        reset_results = api_client.reset_circuit_breakers()
        
        # Check that sources were reset
        assert reset_results['nasa_srtm'] is True
        assert reset_results['openweathermap'] is True
        assert api_client.data_sources['nasa_srtm'].is_available is True
        assert api_client.data_sources['openweathermap'].is_available is True
    
    @pytest.mark.asyncio
    async def test_api_usage_optimization_analysis(self, api_client):
        """Test API usage optimization analysis."""
        # Set up some usage data
        api_client.data_sources['openweathermap'].requests_today = 500
        api_client.data_sources['openweathermap'].cost_per_request = 0.001
        api_client.cost_metrics.total_cost_today = 2.5
        
        optimization_report = await api_client.optimize_api_usage()
        
        assert 'recommendations' in optimization_report
        assert 'cost_analysis' in optimization_report
        assert 'optimization_potential' in optimization_report
        assert isinstance(optimization_report['cost_analysis']['total_daily_cost'], float)
        assert isinstance(optimization_report['recommendations'], list)
    
    @pytest.mark.asyncio
    async def test_data_source_availability_scoring(self, api_client):
        """Test data source availability scoring."""
        # Set up different source conditions
        api_client.data_sources['nasa_srtm'].failure_count = 0
        api_client.data_sources['nasa_srtm'].response_time_ms = 1000.0
        
        api_client.data_sources['openweathermap'].failure_count = 3
        api_client.data_sources['openweathermap'].response_time_ms = 8000.0
        
        # Test availability scores
        nasa_score = api_client.data_sources['nasa_srtm'].get_availability_score()
        weather_score = api_client.data_sources['openweathermap'].get_availability_score()
        
        assert 0.0 <= nasa_score <= 1.0
        assert 0.0 <= weather_score <= 1.0
        assert nasa_score > weather_score  # NASA should score higher


class TestDataValidation:
    """Test data validation and edge cases."""
    
    def test_bounding_box_validation(self):
        """Test bounding box edge cases."""
        # Test valid bounding box
        valid_bounds = BoundingBox(north=30.8, south=30.7, east=78.5, west=78.4)
        assert valid_bounds.north > valid_bounds.south
        assert valid_bounds.east > valid_bounds.west
        
        # Test point containment edge cases
        assert valid_bounds.contains_point(30.75, 78.45)  # Inside
        assert valid_bounds.contains_point(30.8, 78.5)    # On boundary
        assert not valid_bounds.contains_point(30.9, 78.45)  # Outside
    
    def test_coordinate_validation(self):
        """Test coordinate edge cases."""
        # Test valid coordinates
        coord = Coordinate(latitude=30.75, longitude=78.45)
        assert -90 <= coord.latitude <= 90
        assert -180 <= coord.longitude <= 180
        
        # Test coordinate with elevation
        coord_with_elev = Coordinate(latitude=30.75, longitude=78.45, elevation=1500.0)
        assert coord_with_elev.elevation == 1500.0
    
    def test_date_range_validation(self, sample_date_range):
        """Test date range validation."""
        assert sample_date_range.start_date < sample_date_range.end_date
        
        # Test dictionary conversion
        date_dict = sample_date_range.to_dict()
        assert 'start' in date_dict
        assert 'end' in date_dict