"""
Command-line interface for the AI-Powered Rural Infrastructure Planning System.

This module provides CLI commands for system management, data processing,
and route generation tasks.
"""

import click
import asyncio
import json
from pathlib import Path
from typing import Optional

from .main import initialize_system, health_check
from .config.settings import config
from .utils.logging import get_logger

logger = get_logger(__name__)


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.option('--log-level', default='INFO', help='Set logging level')
def cli(debug: bool, log_level: str):
    """AI-Powered Rural Infrastructure Planning System CLI."""
    
    # Update config for CLI usage
    config.debug_mode = debug
    config.log_level = log_level
    
    # Initialize system
    initialize_system()


@cli.command()
def init():
    """Initialize the system and check configuration."""
    
    click.echo("Initializing Rural Infrastructure Planning System...")
    
    # Run health check
    health = asyncio.run(health_check())
    
    click.echo(f"System Status: {health['status']}")
    
    if health['warnings']:
        click.echo("\nWarnings:")
        for warning in health['warnings']:
            click.echo(f"  - {warning}")
    
    click.echo("\nComponent Status:")
    for component, status in health['components'].items():
        status_icon = "✓" if status['status'] == 'healthy' else "✗"
        click.echo(f"  {status_icon} {component}: {status['status']}")
        
        if status['status'] != 'healthy' and 'error' in status:
            click.echo(f"    Error: {status['error']}")


@cli.command()
@click.option('--format', 'output_format', default='json', type=click.Choice(['json', 'table']))
def status(output_format: str):
    """Show system status and health information."""
    
    health = asyncio.run(health_check())
    
    if output_format == 'json':
        click.echo(json.dumps(health, indent=2))
    else:
        # Table format
        click.echo(f"System Status: {health['status']}")
        click.echo(f"Timestamp: {health['timestamp']}")
        
        click.echo("\nComponents:")
        for component, status in health['components'].items():
            click.echo(f"  {component}: {status['status']}")


@cli.command()
@click.option('--clear-all', is_flag=True, help='Clear all cached data')
@click.option('--show-stats', is_flag=True, help='Show cache statistics')
def cache(clear_all: bool, show_stats: bool):
    """Manage system cache."""
    
    from .utils.cache import get_global_cache
    
    cache_instance = get_global_cache()
    
    if clear_all:
        cache_instance.clear()
        click.echo("Cache cleared successfully")
    
    if show_stats or not clear_all:
        stats = cache_instance.get_stats()
        click.echo("Cache Statistics:")
        click.echo(f"  Total entries: {stats.get('total_entries', 0)}")
        click.echo(f"  Total size: {stats.get('total_size_mb', 0):.2f} MB")
        click.echo(f"  Expired entries: {stats.get('expired_entries', 0)}")
        click.echo(f"  Cache directory: {stats.get('cache_dir', 'Unknown')}")
        
        if 'sources' in stats:
            click.echo("  Data sources:")
            for source, count in stats['sources'].items():
                click.echo(f"    {source}: {count} entries")


@cli.command()
@click.argument('start_lat', type=float)
@click.argument('start_lon', type=float)
@click.argument('end_lat', type=float)
@click.argument('end_lon', type=float)
@click.option('--output', '-o', help='Output file path for results')
@click.option('--format', 'output_format', default='json', type=click.Choice(['json', 'geojson', 'kml']))
def generate_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    output: Optional[str],
    output_format: str
):
    """Generate route between two coordinates."""
    
    click.echo(f"Generating route from ({start_lat}, {start_lon}) to ({end_lat}, {end_lon})")
    
    # TODO: Implement route generation when components are ready
    click.echo("Route generation will be implemented in subsequent tasks")
    
    if output:
        click.echo(f"Results will be saved to: {output}")


@cli.command()
@click.option('--api-keys', is_flag=True, help='Check API key configuration')
@click.option('--data-dirs', is_flag=True, help='Check data directory availability')
@click.option('--aws', is_flag=True, help='Check AWS configuration')
def check_config(api_keys: bool, data_dirs: bool, aws: bool):
    """Check system configuration."""
    
    if api_keys or not any([api_keys, data_dirs, aws]):
        click.echo("API Configuration:")
        api_status = {
            'OpenWeatherMap': bool(config.api.openweathermap_api_key),
            'NASA SRTM': True,  # No key required
            'IMD': bool(config.api.imd_api_key),
            'Google Places': bool(config.api.google_places_api_key),
            'Sentinel Hub': bool(config.api.sentinel_hub_api_key),
        }
        
        for api, configured in api_status.items():
            status_icon = "✓" if configured else "✗"
            click.echo(f"  {status_icon} {api}")
    
    if data_dirs or not any([api_keys, data_dirs, aws]):
        click.echo("\nData Directories:")
        directories = [
            ('DEM', config.data.dem_directory),
            ('OSM', config.data.osm_directory),
            ('Rainfall', config.data.rainfall_directory),
            ('Flood', config.data.flood_directory),
            ('Maps', config.data.maps_directory),
        ]
        
        for name, directory in directories:
            full_path = config.data.data_root / directory
            exists = full_path.exists()
            status_icon = "✓" if exists else "✗"
            click.echo(f"  {status_icon} {name}: {full_path}")
    
    if aws or not any([api_keys, data_dirs, aws]):
        click.echo("\nAWS Configuration:")
        aws_configured = bool(config.aws.aws_access_key_id and config.aws.aws_secret_access_key)
        status_icon = "✓" if aws_configured else "✗"
        click.echo(f"  {status_icon} Bedrock Access: {config.aws.aws_region}")
        click.echo(f"  Model: {config.aws.bedrock_model_id}")


@cli.command()
def test():
    """Run system tests."""
    
    import subprocess
    import sys
    
    click.echo("Running system tests...")
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            'tests/',
            '-v',
            '--tb=short'
        ], capture_output=True, text=True)
        
        click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)
        
        if result.returncode == 0:
            click.echo("✓ All tests passed")
        else:
            click.echo("✗ Some tests failed")
            sys.exit(result.returncode)
            
    except FileNotFoundError:
        click.echo("pytest not found. Install test dependencies with: pip install -e .[dev]")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == '__main__':
    main()