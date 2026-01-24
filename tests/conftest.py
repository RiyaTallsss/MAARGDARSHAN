"""
Pytest configuration and fixtures for the rural infrastructure planning system.

This module provides common fixtures and configuration for all tests,
including mock data, API clients, and test utilities.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
from typing import Dict, Any, Generator

from rural_infrastructure_planning.config.settings import SystemConfig, APIConfig, AWSConfig, CacheConfig, DataConfig
from rural_infrastructure_planning.utils.cache import SmartCache
from rural_infrastructure_planning.utils.rate_limiter import RateLimiter, RateLimitConfig


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_config(temp_dir: Path) -> SystemConfig:
    """Create a test configuration with temporary directories."""
    api_config = APIConfig(
        openweathermap_api_key="test_openweather_key",
        nasa_srtm_api_key="test_nasa_key",
        google_places_api_key="test_places_key",
    )
    
    aws_config = AWSConfig(
        aws_access_key_id="test_access_key",
        aws_secret_access_key="test_secret_key",
        aws_region="us-east-1",
    )
    
    cache_config = CacheConfig(
        cache_directory=temp_dir / "cache",
        cache_expiry_hours=1,
        max_cache_size_mb=10,
    )
    
    data_config = DataConfig(
        data_root=temp_dir,
        dem_directory=temp_dir / "dem",
        osm_directory=temp_dir / "osm",
        rainfall_directory=temp_dir / "rainfall",
        flood_directory=temp_dir / "flood",
    )
    
    return SystemConfig(
        api=api_config,
        aws=aws_config,
        cache=cache_config,
        data=data_config,
        debug_mode=True,
    )


@pytest.fixture
def test_cache(temp_dir: Path) -> SmartCache:
    """Create a test cache instance."""
    return SmartCache(
        cache_dir=temp_dir / "test_cache",
        max_size_mb=10,
        default_ttl_hours=1,
    )


@pytest.fixture
def test_rate_limiter() -> RateLimiter:
    """Create a test rate limiter with permissive limits."""
    limiter = RateLimiter()
    
    # Configure with high limits for testing
    test_limits = {
        'openweathermap': RateLimitConfig(requests_per_minute=1000),
        'nasa_srtm': RateLimitConfig(requests_per_minute=1000),
        'overpass': RateLimitConfig(requests_per_minute=1000),
        'google_places': RateLimitConfig(requests_per_minute=1000),
    }
    
    for service, config in test_limits.items():
        limiter.configure(service, config)
    
    return limiter


@pytest.fixture
def mock_dem_data() -> np.ndarray:
    """Create mock DEM data for testing."""
    # Create a 100x100 elevation grid with realistic values for Uttarkashi
    np.random.seed(42)  # For reproducible tests
    base_elevation = 2000  # Base elevation in meters
    elevation_data = base_elevation + np.random.normal(0, 500, (100, 100))
    
    # Add some terrain features
    # Create a valley (lower elevation in the middle)
    x, y = np.meshgrid(np.linspace(-1, 1, 100), np.linspace(-1, 1, 100))
    valley = -200 * np.exp(-(x**2 + y**2) / 0.5)
    elevation_data += valley
    
    # Add a ridge (higher elevation)
    ridge = 300 * np.exp(-((x - 0.5)**2 + (y - 0.3)**2) / 0.2)
    elevation_data += ridge
    
    return elevation_data.astype(np.float32)


@pytest.fixture
def mock_osm_data() -> Dict[str, Any]:
    """Create mock OSM data for testing."""
    return {
        'roads': [
            {
                'id': 'way_1',
                'type': 'primary',
                'coordinates': [(78.0, 30.5), (78.1, 30.6), (78.2, 30.7)],
                'tags': {'highway': 'primary', 'name': 'Test Highway'}
            },
            {
                'id': 'way_2', 
                'type': 'secondary',
                'coordinates': [(78.05, 30.45), (78.15, 30.55)],
                'tags': {'highway': 'secondary', 'name': 'Test Road'}
            }
        ],
        'settlements': [
            {
                'id': 'node_1',
                'name': 'Test Village',
                'coordinates': (78.1, 30.55),
                'population': 500,
                'tags': {'place': 'village'}
            }
        ],
        'infrastructure': [
            {
                'id': 'node_2',
                'type': 'school',
                'name': 'Test School',
                'coordinates': (78.12, 30.56),
                'tags': {'amenity': 'school'}
            },
            {
                'id': 'node_3',
                'type': 'hospital',
                'name': 'Test Hospital', 
                'coordinates': (78.08, 30.52),
                'tags': {'amenity': 'hospital'}
            }
        ]
    }


@pytest.fixture
def mock_weather_data() -> Dict[str, Any]:
    """Create mock weather data for testing."""
    return {
        'current': {
            'temperature': 15.5,
            'humidity': 65,
            'precipitation': 0.0,
            'wind_speed': 5.2,
            'conditions': 'clear'
        },
        'historical_rainfall': [
            {'month': 1, 'rainfall_mm': 45.2},
            {'month': 2, 'rainfall_mm': 38.7},
            {'month': 3, 'rainfall_mm': 52.1},
            {'month': 4, 'rainfall_mm': 28.9},
            {'month': 5, 'rainfall_mm': 15.3},
            {'month': 6, 'rainfall_mm': 125.8},  # Monsoon
            {'month': 7, 'rainfall_mm': 245.6},  # Peak monsoon
            {'month': 8, 'rainfall_mm': 198.4},  # Monsoon
            {'month': 9, 'rainfall_mm': 87.2},
            {'month': 10, 'rainfall_mm': 23.1},
            {'month': 11, 'rainfall_mm': 12.4},
            {'month': 12, 'rainfall_mm': 31.8}
        ],
        'monsoon_forecast': {
            'start_date': '2024-06-15',
            'end_date': '2024-09-30',
            'intensity': 'normal',
            'total_expected_mm': 650
        }
    }


@pytest.fixture
def mock_flood_data() -> Dict[str, Any]:
    """Create mock flood data for testing."""
    return {
        'flood_zones': [
            {
                'id': 'zone_1',
                'severity': 3,  # 1-5 scale
                'coordinates': [
                    (78.0, 30.5), (78.1, 30.5), (78.1, 30.6), (78.0, 30.6)
                ],
                'flood_frequency': 'once_in_5_years',
                'last_flood_year': 2020
            },
            {
                'id': 'zone_2',
                'severity': 2,
                'coordinates': [
                    (78.15, 30.45), (78.25, 30.45), (78.25, 30.55), (78.15, 30.55)
                ],
                'flood_frequency': 'once_in_10_years',
                'last_flood_year': 2018
            }
        ],
        'mitigation_strategies': [
            {
                'zone_id': 'zone_1',
                'strategies': ['elevated_construction', 'drainage_improvement', 'early_warning_system']
            },
            {
                'zone_id': 'zone_2', 
                'strategies': ['culvert_upgrade', 'slope_stabilization']
            }
        ]
    }


@pytest.fixture
def mock_api_responses():
    """Mock API responses for testing."""
    with patch('requests.get') as mock_get, \
         patch('aiohttp.ClientSession.get') as mock_async_get:
        
        # Configure mock responses
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'status': 'success', 'data': {}}
        
        mock_async_get.return_value.__aenter__.return_value.status = 200
        mock_async_get.return_value.__aenter__.return_value.json.return_value = {'status': 'success', 'data': {}}
        
        yield {
            'sync': mock_get,
            'async': mock_async_get
        }


@pytest.fixture
def mock_bedrock_client():
    """Mock AWS Bedrock client for testing."""
    with patch('boto3.client') as mock_boto_client:
        mock_client = Mock()
        mock_client.invoke_model.return_value = {
            'body': Mock(read=lambda: b'{"completion": "Test AI response"}')
        }
        mock_boto_client.return_value = mock_client
        yield mock_client


# Property-based testing configuration
@pytest.fixture
def hypothesis_settings():
    """Configure Hypothesis for property-based testing."""
    from hypothesis import settings, Verbosity
    
    return settings(
        max_examples=100,  # Minimum required iterations
        verbosity=Verbosity.verbose,
        deadline=None,  # No deadline for complex geospatial operations
        suppress_health_check=[],
    )


# Test data generators for property-based testing
@pytest.fixture
def coordinate_generator():
    """Generator for valid coordinates within Uttarkashi bounds."""
    from hypothesis import strategies as st
    
    return st.tuples(
        st.floats(min_value=77.8, max_value=79.2),  # Longitude
        st.floats(min_value=30.4, max_value=31.5),  # Latitude
    )


@pytest.fixture
def elevation_generator():
    """Generator for realistic elevation values."""
    from hypothesis import strategies as st
    
    return st.floats(min_value=500, max_value=7000)  # Uttarkashi elevation range


@pytest.fixture
def route_generator(coordinate_generator):
    """Generator for route data."""
    from hypothesis import strategies as st
    
    return st.tuples(
        coordinate_generator,  # Start coordinate
        coordinate_generator,  # End coordinate
    ).filter(lambda coords: coords[0] != coords[1])  # Ensure start != end