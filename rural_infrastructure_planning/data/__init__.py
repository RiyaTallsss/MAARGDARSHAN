"""
Data processing and API integration module.

This module provides classes and utilities for fetching and processing data
from multiple sources including external APIs and local fallback files.
"""

from .api_client import (
    API_Client,
    BoundingBox,
    Coordinate,
    DateRange,
    ElevationData,
    OSMData,
    WeatherData,
    FloodRiskData
)

from .dem_processor import (
    DEM_Processor,
    DEMData,
    SlopeData,
    ElevationProfile,
    CostSurface
)

from .osm_parser import (
    OSM_Parser,
    RoadNetwork,
    Settlement,
    Infrastructure
)

__all__ = [
    'API_Client',
    'BoundingBox',
    'Coordinate', 
    'DateRange',
    'ElevationData',
    'OSMData',
    'WeatherData',
    'FloodRiskData',
    'DEM_Processor',
    'DEMData',
    'SlopeData',
    'ElevationProfile',
    'CostSurface',
    'OSM_Parser',
    'RoadNetwork',
    'Settlement',
    'Infrastructure'
]