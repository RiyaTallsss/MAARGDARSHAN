"""
Main application entry point for the AI-Powered Rural Infrastructure Planning System.

This module initializes the system, configures logging, sets up caching and rate limiting,
and provides the main application interface.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

from .config.settings import config
from .utils.logging import setup_logging, get_logger
from .utils.cache import get_global_cache
from .utils.rate_limiter import get_global_rate_limiter, configure_global_rate_limits, RateLimitConfig

logger = get_logger(__name__)


def initialize_system() -> None:
    """
    Initialize the rural infrastructure planning system.
    
    Sets up logging, caching, rate limiting, and validates configuration.
    """
    
    # Set up logging
    setup_logging(
        log_level=config.log_level,
        debug_mode=config.debug_mode
    )
    
    logger.info("Initializing AI-Powered Rural Infrastructure Planning System")
    
    # Initialize cache
    cache = get_global_cache()
    cache_stats = cache.get_stats()
    logger.info(f"Cache initialized: {cache_stats['cache_dir']} "
                f"(max: {cache_stats['max_size_mb']:.1f}MB)")
    
    # Configure rate limiting
    rate_limits = {
        'openweathermap': RateLimitConfig(
            requests_per_minute=config.api.rate_limits.get('openweathermap', 60),
            requests_per_day=1000  # Free tier limit
        ),
        'overpass': RateLimitConfig(
            requests_per_minute=config.api.rate_limits.get('overpass', 10)
        ),
        'nasa_srtm': RateLimitConfig(
            requests_per_minute=config.api.rate_limits.get('nasa_srtm', 100)
        ),
        'google_places': RateLimitConfig(
            requests_per_minute=config.api.rate_limits.get('google_places', 100)
        ),
        'sentinel_hub': RateLimitConfig(
            requests_per_minute=config.api.rate_limits.get('sentinel_hub', 20)
        ),
    }
    
    configure_global_rate_limits(rate_limits)
    logger.info("Rate limiting configured for all API services")
    
    # Validate data directories
    _validate_data_directories()
    
    # Check API key availability
    _check_api_configuration()
    
    logger.info("System initialization complete")


def _validate_data_directories() -> None:
    """Validate that required data directories exist."""
    
    directories_to_check = [
        config.data.dem_directory,
        config.data.osm_directory,
        config.data.rainfall_directory,
        config.data.flood_directory,
        config.data.maps_directory,
    ]
    
    missing_dirs = []
    for directory in directories_to_check:
        full_path = config.data.data_root / directory
        if not full_path.exists():
            missing_dirs.append(str(directory))
            logger.warning(f"Data directory not found: {full_path}")
    
    if missing_dirs:
        logger.warning(f"Missing data directories: {missing_dirs}. "
                      "System will rely on API data sources.")
    else:
        logger.info("All data directories found")


def _check_api_configuration() -> None:
    """Check API key configuration and availability."""
    
    api_status = {
        'OpenWeatherMap': bool(config.api.openweathermap_api_key),
        'NASA SRTM': True,  # No key required
        'IMD': bool(config.api.imd_api_key),
        'Google Places': bool(config.api.google_places_api_key),
        'Sentinel Hub': bool(config.api.sentinel_hub_api_key),
        'AWS Bedrock': bool(config.aws.aws_access_key_id and config.aws.aws_secret_access_key),
    }
    
    configured_apis = [name for name, configured in api_status.items() if configured]
    missing_apis = [name for name, configured in api_status.items() if not configured]
    
    logger.info(f"Configured APIs: {configured_apis}")
    if missing_apis:
        logger.warning(f"Missing API keys: {missing_apis}. "
                      "System will use local data fallbacks where available.")
    
    # Check critical APIs
    if not api_status['AWS Bedrock']:
        logger.error("AWS Bedrock credentials not configured. AI features will be unavailable.")
    
    if not any([api_status['OpenWeatherMap'], api_status['IMD']]):
        logger.warning("No weather API configured. Weather analysis will use local data only.")


async def health_check() -> dict:
    """
    Perform a system health check.
    
    Returns:
        Dictionary with system health status
    """
    
    health_status = {
        'status': 'healthy',
        'timestamp': None,
        'components': {},
        'warnings': []
    }
    
    import time
    health_status['timestamp'] = time.time()
    
    # Check cache
    try:
        cache = get_global_cache()
        cache_stats = cache.get_stats()
        health_status['components']['cache'] = {
            'status': 'healthy',
            'entries': cache_stats.get('total_entries', 0),
            'size_mb': cache_stats.get('total_size_mb', 0),
        }
    except Exception as e:
        health_status['components']['cache'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['warnings'].append('Cache system error')
    
    # Check data directories
    try:
        _validate_data_directories()
        health_status['components']['data_directories'] = {'status': 'healthy'}
    except Exception as e:
        health_status['components']['data_directories'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['warnings'].append('Data directory issues')
    
    # Check API configuration
    try:
        _check_api_configuration()
        health_status['components']['api_config'] = {'status': 'healthy'}
    except Exception as e:
        health_status['components']['api_config'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['warnings'].append('API configuration issues')
    
    # Overall status
    unhealthy_components = [
        name for name, component in health_status['components'].items()
        if component.get('status') != 'healthy'
    ]
    
    if unhealthy_components:
        health_status['status'] = 'degraded' if len(unhealthy_components) < len(health_status['components']) else 'unhealthy'
    
    return health_status


def main() -> None:
    """Main application entry point."""
    
    try:
        # Initialize system
        initialize_system()
        
        # Run health check
        health = asyncio.run(health_check())
        logger.info(f"System health check: {health['status']}")
        
        if health['warnings']:
            for warning in health['warnings']:
                logger.warning(warning)
        
        logger.info("Rural Infrastructure Planning System is ready")
        
    except KeyboardInterrupt:
        logger.info("System shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()