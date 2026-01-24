"""
Configuration settings for the AI-Powered Rural Infrastructure Planning System.

This module manages API keys, AWS credentials, and system configuration parameters
with support for environment variables and secure credential storage.
"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class APIConfig:
    """Configuration for external API integrations."""
    
    # Weather APIs
    openweathermap_api_key: Optional[str] = None
    imd_api_key: Optional[str] = None
    nasa_power_api_key: Optional[str] = None
    
    # Geospatial APIs
    nasa_srtm_api_key: Optional[str] = None
    usgs_elevation_api_key: Optional[str] = None
    mapbox_api_key: Optional[str] = None
    
    # Infrastructure APIs
    google_places_api_key: Optional[str] = None
    sentinel_hub_api_key: Optional[str] = None
    
    # Disaster Management APIs
    india_disaster_api_key: Optional[str] = None
    
    # Rate limiting settings (requests per minute)
    rate_limits: Dict[str, int] = None
    
    def __post_init__(self):
        if self.rate_limits is None:
            self.rate_limits = {
                'openweathermap': 60,  # Free tier: 1000/day
                'overpass': 10,        # Conservative rate limiting
                'nasa_srtm': 100,      # Generous for government API
                'google_places': 100,  # Paid tier
                'sentinel_hub': 20,    # Freemium tier
            }


@dataclass
class AWSConfig:
    """Configuration for AWS services."""
    
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    
    # Bedrock configuration
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    bedrock_max_tokens: int = 4000
    bedrock_temperature: float = 0.1
    
    # S3 configuration for data storage
    s3_bucket_name: Optional[str] = None
    s3_data_prefix: str = "rural-infrastructure-data/"


@dataclass
class CacheConfig:
    """Configuration for caching and performance optimization."""
    
    cache_directory: Path = Path("cache")
    cache_expiry_hours: int = 24
    max_cache_size_mb: int = 1000
    
    # API response caching
    enable_api_caching: bool = True
    api_cache_expiry_hours: int = 6
    
    # DEM data caching
    enable_dem_caching: bool = True
    dem_cache_expiry_hours: int = 168  # 1 week


@dataclass
class DataConfig:
    """Configuration for data sources and file paths."""
    
    # Local data directories
    data_root: Path = Path(".")
    dem_directory: Path = Path("Uttarkashi_Terrain")
    osm_directory: Path = Path("Roads")
    rainfall_directory: Path = Path("Rainfall")
    flood_directory: Path = Path("Floods")
    maps_directory: Path = Path("Maps")
    
    # Specific file paths
    uttarkashi_dem_file: str = "P5_PAN_CD_N30_000_E078_000_DEM_30m.tif"
    northern_zone_osm_file: str = "northern-zone-260121.osm.pbf"
    rainfall_csv_file: str = "Rainfall_2016_districtwise.csv"
    
    # Geographic bounds for Uttarkashi district
    uttarkashi_bounds: Dict[str, float] = None
    
    def __post_init__(self):
        if self.uttarkashi_bounds is None:
            self.uttarkashi_bounds = {
                'north': 31.5,
                'south': 30.4,
                'east': 79.2,
                'west': 77.8
            }


@dataclass
class SystemConfig:
    """Main system configuration combining all components."""
    
    api: APIConfig
    aws: AWSConfig
    cache: CacheConfig
    data: DataConfig
    
    # Performance settings
    max_concurrent_requests: int = 10
    request_timeout_seconds: int = 30
    max_route_alternatives: int = 5
    
    # Development settings
    debug_mode: bool = False
    log_level: str = "INFO"
    enable_profiling: bool = False


def load_config() -> SystemConfig:
    """
    Load configuration from environment variables and defaults.
    
    Returns:
        SystemConfig: Complete system configuration
    """
    
    # Load API configuration from environment
    api_config = APIConfig(
        openweathermap_api_key=os.getenv('OPENWEATHERMAP_API_KEY'),
        imd_api_key=os.getenv('IMD_API_KEY'),
        nasa_power_api_key=os.getenv('NASA_POWER_API_KEY'),
        nasa_srtm_api_key=os.getenv('NASA_SRTM_API_KEY'),
        usgs_elevation_api_key=os.getenv('USGS_ELEVATION_API_KEY'),
        mapbox_api_key=os.getenv('MAPBOX_API_KEY'),
        google_places_api_key=os.getenv('GOOGLE_PLACES_API_KEY'),
        sentinel_hub_api_key=os.getenv('SENTINEL_HUB_API_KEY'),
        india_disaster_api_key=os.getenv('INDIA_DISASTER_API_KEY'),
    )
    
    # Load AWS configuration from environment
    aws_config = AWSConfig(
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        aws_region=os.getenv('AWS_REGION', 'us-east-1'),
        bedrock_model_id=os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0'),
        s3_bucket_name=os.getenv('S3_BUCKET_NAME'),
    )
    
    # Load cache configuration
    cache_config = CacheConfig(
        cache_directory=Path(os.getenv('CACHE_DIRECTORY', 'cache')),
        cache_expiry_hours=int(os.getenv('CACHE_EXPIRY_HOURS', '24')),
        max_cache_size_mb=int(os.getenv('MAX_CACHE_SIZE_MB', '1000')),
    )
    
    # Load data configuration
    data_config = DataConfig(
        data_root=Path(os.getenv('DATA_ROOT', '.')),
    )
    
    # Create system configuration
    system_config = SystemConfig(
        api=api_config,
        aws=aws_config,
        cache=cache_config,
        data=data_config,
        debug_mode=os.getenv('DEBUG_MODE', 'false').lower() == 'true',
        log_level=os.getenv('LOG_LEVEL', 'INFO'),
    )
    
    return system_config


# Global configuration instance
config = load_config()