"""
Configuration for data sources and fallback strategies.

This module provides configuration management for all data sources,
including API endpoints, fallback strategies, and cost optimization settings.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path


class DataSourceType(Enum):
    """Types of data sources."""
    API = "api"
    LOCAL_FILE = "local_file"
    HYBRID = "hybrid"


class CostTier(Enum):
    """Cost tiers for API services."""
    FREE = "free"
    LOW_COST = "low_cost"      # < $1/day
    MEDIUM_COST = "medium_cost"  # $1-5/day
    HIGH_COST = "high_cost"    # > $5/day


@dataclass
class APIEndpointConfig:
    """Configuration for an API endpoint."""
    name: str
    base_url: str
    api_key_env_var: Optional[str] = None
    rate_limit_per_minute: int = 60
    rate_limit_per_day: Optional[int] = None
    cost_per_request: float = 0.0
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)


@dataclass
class LocalDataConfig:
    """Configuration for local data sources."""
    name: str
    file_path: str
    file_type: str  # 'tiff', 'pbf', 'csv', 'pdf', 'json'
    last_updated: Optional[str] = None
    data_quality_score: float = 0.8
    coverage_area: Optional[Dict[str, float]] = None  # bounding box
    processing_required: bool = False


@dataclass
class FallbackConfig:
    """Configuration for fallback strategies."""
    primary_sources: List[str]
    fallback_sources: List[str]
    fallback_trigger_threshold: int = 3  # failures before fallback
    recovery_check_interval_minutes: int = 15
    max_fallback_duration_hours: int = 24
    quality_degradation_acceptable: bool = True


class DataSourceConfigurator:
    """
    Manages configuration for all data sources and fallback strategies.
    
    This class provides centralized configuration management for:
    - API endpoints and authentication
    - Local data file locations and metadata
    - Fallback strategies and thresholds
    - Cost optimization settings
    - Regional customizations
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file
        self.api_configs: Dict[str, APIEndpointConfig] = {}
        self.local_configs: Dict[str, LocalDataConfig] = {}
        self.fallback_configs: Dict[str, FallbackConfig] = {}
        
        # Initialize default configurations
        self._initialize_default_api_configs()
        self._initialize_default_local_configs()
        self._initialize_default_fallback_configs()
        
        # Load custom configurations if provided
        if config_file and Path(config_file).exists():
            self._load_custom_config(config_file)
    
    def _initialize_default_api_configs(self) -> None:
        """Initialize default API configurations."""
        
        # NASA SRTM Elevation API
        self.api_configs['nasa_srtm'] = APIEndpointConfig(
            name='nasa_srtm',
            base_url='https://cloud.sdsc.edu/v1/srtm',
            api_key_env_var='NASA_SRTM_API_KEY',
            rate_limit_per_minute=100,
            rate_limit_per_day=10000,
            cost_per_request=0.0,  # Free service
            timeout_seconds=30,
            headers={'Accept': 'application/json'}
        )
        
        # USGS Elevation API
        self.api_configs['usgs_elevation'] = APIEndpointConfig(
            name='usgs_elevation',
            base_url='https://nationalmap.gov/epqs/pqs.php',
            rate_limit_per_minute=100,
            rate_limit_per_day=5000,
            cost_per_request=0.0,  # Free service
            timeout_seconds=25,
            headers={'Accept': 'application/json'}
        )
        
        # Overpass API (OpenStreetMap)
        self.api_configs['overpass'] = APIEndpointConfig(
            name='overpass',
            base_url='https://overpass-api.de/api/interpreter',
            rate_limit_per_minute=10,  # Conservative limit
            cost_per_request=0.0,  # Free service
            timeout_seconds=60,  # OSM queries can be slow
            retry_attempts=2,  # Fewer retries for free service
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        # OpenWeatherMap API
        self.api_configs['openweathermap'] = APIEndpointConfig(
            name='openweathermap',
            base_url='https://api.openweathermap.org/data/2.5',
            api_key_env_var='OPENWEATHERMAP_API_KEY',
            rate_limit_per_minute=60,
            rate_limit_per_day=1000,  # Free tier limit
            cost_per_request=0.001,  # $0.001 per call after free tier
            timeout_seconds=15,
            headers={'Accept': 'application/json'}
        )
        
        # India Meteorological Department API
        self.api_configs['imd_api'] = APIEndpointConfig(
            name='imd_api',
            base_url='https://mausam.imd.gov.in/imd_latest/contents/api',
            rate_limit_per_minute=30,
            rate_limit_per_day=500,
            cost_per_request=0.0,  # Free government service
            timeout_seconds=45,  # Government APIs can be slow
            headers={'Accept': 'application/json'}
        )
        
        # India Disaster Management API
        self.api_configs['disaster_api'] = APIEndpointConfig(
            name='disaster_api',
            base_url='https://ndma.gov.in/api',
            rate_limit_per_minute=20,
            rate_limit_per_day=200,
            cost_per_request=0.0,  # Free government service
            timeout_seconds=60,
            headers={'Accept': 'application/json'}
        )
        
        # Google Places API
        self.api_configs['google_places'] = APIEndpointConfig(
            name='google_places',
            base_url='https://maps.googleapis.com/maps/api/place',
            api_key_env_var='GOOGLE_PLACES_API_KEY',
            rate_limit_per_minute=100,
            rate_limit_per_day=1000,
            cost_per_request=0.05,  # $0.05 per request
            timeout_seconds=10,
            headers={'Accept': 'application/json'}
        )
        
        # Sentinel Hub API (for satellite imagery)
        self.api_configs['sentinel_hub'] = APIEndpointConfig(
            name='sentinel_hub',
            base_url='https://services.sentinel-hub.com/api/v1',
            api_key_env_var='SENTINEL_HUB_API_KEY',
            rate_limit_per_minute=50,
            rate_limit_per_day=500,
            cost_per_request=0.02,  # $0.02 per request
            timeout_seconds=30,
            headers={'Accept': 'application/json'}
        )
    
    def _initialize_default_local_configs(self) -> None:
        """Initialize default local data configurations."""
        
        # Uttarkashi DEM file
        self.local_configs['local_dem'] = LocalDataConfig(
            name='local_dem',
            file_path='data/dem/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif',
            file_type='tiff',
            data_quality_score=0.85,
            coverage_area={
                'north': 31.0,
                'south': 30.0,
                'east': 79.0,
                'west': 78.0
            },
            processing_required=True
        )
        
        # Northern zone OSM PBF file
        self.local_configs['local_pbf'] = LocalDataConfig(
            name='local_pbf',
            file_path='data/osm/northern-zone-260121.osm.pbf',
            file_type='pbf',
            data_quality_score=0.80,
            coverage_area={
                'north': 35.0,
                'south': 28.0,
                'east': 82.0,
                'west': 74.0
            },
            processing_required=True
        )
        
        # Rainfall CSV data
        self.local_configs['local_csv'] = LocalDataConfig(
            name='local_csv',
            file_path='data/weather/Rainfall_2016_districtwise.csv',
            file_type='csv',
            data_quality_score=0.70,
            last_updated='2016-12-31'
        )
        
        # Flood hazard atlas PDFs
        self.local_configs['local_pdf'] = LocalDataConfig(
            name='local_pdf',
            file_path='data/flood/flood_hazard_atlas_uttarakhand.pdf',
            file_type='pdf',
            data_quality_score=0.75,
            processing_required=True
        )
        
        # PMGSY road data
        self.local_configs['local_pmgsy'] = LocalDataConfig(
            name='local_pmgsy',
            file_path='data/roads/pmgsy_uttarakhand.csv',
            file_type='csv',
            data_quality_score=0.85,
            coverage_area={
                'north': 31.5,
                'south': 29.0,
                'east': 81.0,
                'west': 77.5
            }
        )
    
    def _initialize_default_fallback_configs(self) -> None:
        """Initialize default fallback configurations."""
        
        # Elevation data fallback
        self.fallback_configs['elevation'] = FallbackConfig(
            primary_sources=['nasa_srtm', 'usgs_elevation'],
            fallback_sources=['local_dem'],
            fallback_trigger_threshold=2,
            recovery_check_interval_minutes=10,
            max_fallback_duration_hours=12
        )
        
        # OSM data fallback
        self.fallback_configs['osm'] = FallbackConfig(
            primary_sources=['overpass'],
            fallback_sources=['local_pbf'],
            fallback_trigger_threshold=1,  # Immediate fallback for free service
            recovery_check_interval_minutes=5,
            max_fallback_duration_hours=6
        )
        
        # Weather data fallback
        self.fallback_configs['weather'] = FallbackConfig(
            primary_sources=['openweathermap', 'imd_api'],
            fallback_sources=['local_csv'],
            fallback_trigger_threshold=3,
            recovery_check_interval_minutes=15,
            max_fallback_duration_hours=24,
            quality_degradation_acceptable=True
        )
        
        # Flood data fallback
        self.fallback_configs['flood'] = FallbackConfig(
            primary_sources=['disaster_api'],
            fallback_sources=['local_pdf'],
            fallback_trigger_threshold=2,
            recovery_check_interval_minutes=30,
            max_fallback_duration_hours=48
        )
        
        # Infrastructure data fallback
        self.fallback_configs['infrastructure'] = FallbackConfig(
            primary_sources=['overpass', 'google_places'],
            fallback_sources=['local_pbf', 'local_pmgsy'],
            fallback_trigger_threshold=2,
            recovery_check_interval_minutes=20,
            max_fallback_duration_hours=12
        )
    
    def get_api_config(self, source_name: str) -> Optional[APIEndpointConfig]:
        """Get API configuration for a source."""
        return self.api_configs.get(source_name)
    
    def get_local_config(self, source_name: str) -> Optional[LocalDataConfig]:
        """Get local data configuration for a source."""
        return self.local_configs.get(source_name)
    
    def get_fallback_config(self, data_type: str) -> Optional[FallbackConfig]:
        """Get fallback configuration for a data type."""
        return self.fallback_configs.get(data_type)
    
    def get_cost_tier(self, source_name: str) -> CostTier:
        """Get the cost tier for a source."""
        api_config = self.get_api_config(source_name)
        if not api_config:
            return CostTier.FREE
        
        daily_cost = api_config.cost_per_request * api_config.rate_limit_per_day if api_config.rate_limit_per_day else 0
        
        if daily_cost == 0:
            return CostTier.FREE
        elif daily_cost < 1.0:
            return CostTier.LOW_COST
        elif daily_cost < 5.0:
            return CostTier.MEDIUM_COST
        else:
            return CostTier.HIGH_COST
    
    def get_sources_by_cost_tier(self, tier: CostTier) -> List[str]:
        """Get all sources in a specific cost tier."""
        sources = []
        for source_name in self.api_configs.keys():
            if self.get_cost_tier(source_name) == tier:
                sources.append(source_name)
        return sources
    
    def get_regional_optimization_config(self, region: str = 'uttarakhand') -> Dict[str, Any]:
        """
        Get region-specific optimization configuration.
        
        This provides region-specific settings for Uttarakhand or other regions.
        """
        if region.lower() == 'uttarakhand':
            return {
                'preferred_sources': {
                    'elevation': ['nasa_srtm', 'local_dem'],  # NASA SRTM good for Himalayas
                    'weather': ['imd_api', 'openweathermap'],  # Prefer Indian sources
                    'flood': ['disaster_api', 'local_pdf'],   # Government data preferred
                    'osm': ['overpass', 'local_pbf']          # Standard OSM sources
                },
                'quality_thresholds': {
                    'elevation': 0.85,  # High accuracy needed for mountainous terrain
                    'weather': 0.70,    # Moderate accuracy acceptable
                    'flood': 0.80,      # High accuracy for safety
                    'osm': 0.75         # Good accuracy for infrastructure
                },
                'cost_limits': {
                    'daily_budget': 10.0,      # $10/day total
                    'per_source_limit': 5.0,   # $5/day per source
                    'emergency_budget': 25.0   # $25/day in emergencies
                },
                'performance_targets': {
                    'max_response_time_ms': 15000,  # 15 seconds max
                    'cache_hit_rate_target': 0.70,  # 70% cache hits
                    'availability_target': 0.95     # 95% availability
                },
                'regional_adjustments': {
                    'monsoon_season_caching': True,     # Increase caching during monsoon
                    'high_altitude_corrections': True,   # Apply altitude corrections
                    'local_time_zone': 'Asia/Kolkata',
                    'preferred_language': 'en'
                }
            }
        else:
            # Default configuration for other regions
            return {
                'preferred_sources': {
                    'elevation': ['nasa_srtm', 'usgs_elevation'],
                    'weather': ['openweathermap'],
                    'flood': ['disaster_api'],
                    'osm': ['overpass']
                },
                'quality_thresholds': {
                    'elevation': 0.80,
                    'weather': 0.70,
                    'flood': 0.75,
                    'osm': 0.75
                },
                'cost_limits': {
                    'daily_budget': 15.0,
                    'per_source_limit': 7.0,
                    'emergency_budget': 30.0
                },
                'performance_targets': {
                    'max_response_time_ms': 10000,
                    'cache_hit_rate_target': 0.65,
                    'availability_target': 0.90
                }
            }
    
    def validate_configuration(self) -> Dict[str, List[str]]:
        """
        Validate the current configuration and return any issues found.
        
        Returns:
            Dict with 'errors' and 'warnings' lists
        """
        errors = []
        warnings = []
        
        # Check API configurations
        for source_name, config in self.api_configs.items():
            # Check for required API keys
            if config.api_key_env_var and not os.getenv(config.api_key_env_var):
                warnings.append(f"API key not found for {source_name}: {config.api_key_env_var}")
            
            # Check rate limits
            if config.rate_limit_per_minute <= 0:
                errors.append(f"Invalid rate limit for {source_name}: {config.rate_limit_per_minute}")
            
            # Check URLs
            if not config.base_url.startswith(('http://', 'https://')):
                errors.append(f"Invalid base URL for {source_name}: {config.base_url}")
        
        # Check local data configurations
        for source_name, config in self.local_configs.items():
            file_path = Path(config.file_path)
            if not file_path.exists():
                warnings.append(f"Local data file not found for {source_name}: {config.file_path}")
            
            if config.data_quality_score < 0 or config.data_quality_score > 1:
                errors.append(f"Invalid quality score for {source_name}: {config.data_quality_score}")
        
        # Check fallback configurations
        for data_type, config in self.fallback_configs.items():
            # Check that primary sources exist
            for source in config.primary_sources:
                if source not in self.api_configs:
                    errors.append(f"Unknown primary source in {data_type} fallback: {source}")
            
            # Check that fallback sources exist
            for source in config.fallback_sources:
                if source not in self.local_configs:
                    errors.append(f"Unknown fallback source in {data_type} fallback: {source}")
        
        return {'errors': errors, 'warnings': warnings}
    
    def _load_custom_config(self, config_file: str) -> None:
        """Load custom configuration from a file."""
        # This would implement loading from JSON/YAML config file
        # For now, just log that custom config loading is not implemented
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Custom config loading from {config_file} not yet implemented")
    
    def export_config(self, output_file: str) -> None:
        """Export current configuration to a file."""
        import json
        
        config_data = {
            'api_configs': {name: {
                'name': cfg.name,
                'base_url': cfg.base_url,
                'api_key_env_var': cfg.api_key_env_var,
                'rate_limit_per_minute': cfg.rate_limit_per_minute,
                'rate_limit_per_day': cfg.rate_limit_per_day,
                'cost_per_request': cfg.cost_per_request,
                'timeout_seconds': cfg.timeout_seconds,
                'retry_attempts': cfg.retry_attempts,
                'retry_delay_seconds': cfg.retry_delay_seconds,
                'headers': cfg.headers,
                'query_params': cfg.query_params
            } for name, cfg in self.api_configs.items()},
            
            'local_configs': {name: {
                'name': cfg.name,
                'file_path': cfg.file_path,
                'file_type': cfg.file_type,
                'last_updated': cfg.last_updated,
                'data_quality_score': cfg.data_quality_score,
                'coverage_area': cfg.coverage_area,
                'processing_required': cfg.processing_required
            } for name, cfg in self.local_configs.items()},
            
            'fallback_configs': {name: {
                'primary_sources': cfg.primary_sources,
                'fallback_sources': cfg.fallback_sources,
                'fallback_trigger_threshold': cfg.fallback_trigger_threshold,
                'recovery_check_interval_minutes': cfg.recovery_check_interval_minutes,
                'max_fallback_duration_hours': cfg.max_fallback_duration_hours,
                'quality_degradation_acceptable': cfg.quality_degradation_acceptable
            } for name, cfg in self.fallback_configs.items()}
        }
        
        with open(output_file, 'w') as f:
            json.dump(config_data, f, indent=2)


# Global configurator instance
_global_configurator: Optional[DataSourceConfigurator] = None


def get_data_source_configurator() -> DataSourceConfigurator:
    """Get the global data source configurator instance."""
    global _global_configurator
    if _global_configurator is None:
        _global_configurator = DataSourceConfigurator()
    return _global_configurator