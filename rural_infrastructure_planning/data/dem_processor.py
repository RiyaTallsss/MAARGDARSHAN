"""
DEM (Digital Elevation Model) processing with API and local file support.

This module provides the DEM_Processor class that handles elevation data processing
from both API responses and local TIFF files, including slope calculation, elevation
profile extraction, and cost surface generation for route optimization.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds
from rasterio.transform import xy, rowcol
from rasterio.warp import reproject, Resampling
from rasterio.enums import Resampling as ResamplingEnum
import rasterio.features
from scipy import ndimage
from scipy.interpolate import interp1d
import geopandas as gpd
from shapely.geometry import Point, LineString
import tempfile
import os
from datetime import datetime

from .api_client import API_Client, BoundingBox, Coordinate, ElevationData, DataFreshnessInfo
from ..config.settings import config

logger = logging.getLogger(__name__)

# Optional GDAL import - fallback to numpy/scipy if not available
try:
    from osgeo import gdal, gdalconst
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False
    logger.warning("GDAL not available, using numpy/scipy fallback for slope calculations")


@dataclass
class DEMData:
    """Digital Elevation Model data structure."""
    elevation_array: np.ndarray
    slope_array: Optional[np.ndarray] = None
    aspect_array: Optional[np.ndarray] = None
    bounds: Optional[BoundingBox] = None
    resolution: float = 30.0  # meters per pixel
    coordinate_system: str = "EPSG:4326"  # WGS84
    transform: Optional[rasterio.Affine] = None
    nodata_value: Optional[float] = None
    source: str = "unknown"
    timestamp: Optional[datetime] = None
    freshness_info: Optional[DataFreshnessInfo] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            'elevation_shape': self.elevation_array.shape,
            'elevation_min': float(np.nanmin(self.elevation_array)),
            'elevation_max': float(np.nanmax(self.elevation_array)),
            'elevation_mean': float(np.nanmean(self.elevation_array)),
            'resolution': self.resolution,
            'coordinate_system': self.coordinate_system,
            'source': self.source,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'bounds': self.bounds.to_dict() if self.bounds else None,
            'nodata_value': self.nodata_value
        }
        
        if self.slope_array is not None:
            result.update({
                'slope_min': float(np.nanmin(self.slope_array)),
                'slope_max': float(np.nanmax(self.slope_array)),
                'slope_mean': float(np.nanmean(self.slope_array))
            })
        
        if self.freshness_info:
            result['freshness'] = {
                'source_type': self.freshness_info.source_type,
                'source_name': self.freshness_info.source_name,
                'data_age_hours': self.freshness_info.data_age_hours,
                'is_real_time': self.freshness_info.is_real_time,
                'quality_score': self.freshness_info.quality_score,
                'indicator': self.freshness_info.get_freshness_indicator(),
                'cache_hit': self.freshness_info.cache_hit
            }
        
        return result


@dataclass
class SlopeData:
    """Slope analysis results."""
    slope_degrees: np.ndarray
    slope_percent: np.ndarray
    aspect_degrees: Optional[np.ndarray] = None
    slope_classification: Optional[np.ndarray] = None
    bounds: Optional[BoundingBox] = None
    resolution: float = 30.0
    
    def get_slope_statistics(self) -> Dict[str, float]:
        """Get statistical summary of slope data."""
        return {
            'min_slope_degrees': float(np.nanmin(self.slope_degrees)),
            'max_slope_degrees': float(np.nanmax(self.slope_degrees)),
            'mean_slope_degrees': float(np.nanmean(self.slope_degrees)),
            'std_slope_degrees': float(np.nanstd(self.slope_degrees)),
            'min_slope_percent': float(np.nanmin(self.slope_percent)),
            'max_slope_percent': float(np.nanmax(self.slope_percent)),
            'mean_slope_percent': float(np.nanmean(self.slope_percent)),
            'std_slope_percent': float(np.nanstd(self.slope_percent))
        }


@dataclass
class TerrainDifficulty:
    """Terrain difficulty analysis results."""
    difficulty_scores: np.ndarray  # 0-100 scale difficulty scores
    terrain_types: np.ndarray  # Classified terrain types (0-5)
    construction_factors: np.ndarray  # Construction difficulty multipliers
    accessibility_scores: np.ndarray  # Accessibility scores (0-100)
    seasonal_factors: Optional[np.ndarray] = None  # Seasonal difficulty adjustments
    bounds: Optional[BoundingBox] = None
    resolution: float = 30.0
    source_freshness: Optional[DataFreshnessInfo] = None
    
    # Terrain type constants
    TERRAIN_FLAT = 0
    TERRAIN_GENTLE = 1
    TERRAIN_MODERATE = 2
    TERRAIN_STEEP = 3
    TERRAIN_VERY_STEEP = 4
    TERRAIN_EXTREME = 5
    
    TERRAIN_NAMES = {
        TERRAIN_FLAT: "flat",
        TERRAIN_GENTLE: "gentle", 
        TERRAIN_MODERATE: "moderate",
        TERRAIN_STEEP: "steep",
        TERRAIN_VERY_STEEP: "very_steep",
        TERRAIN_EXTREME: "extreme"
    }
    
    def get_difficulty_statistics(self) -> Dict[str, Any]:
        """Get statistical summary of terrain difficulty."""
        terrain_counts = {}
        for terrain_type in range(6):
            count = np.sum(self.terrain_types == terrain_type)
            terrain_counts[self.TERRAIN_NAMES[terrain_type]] = int(count)
        
        return {
            'difficulty_min': float(np.nanmin(self.difficulty_scores)),
            'difficulty_max': float(np.nanmax(self.difficulty_scores)),
            'difficulty_mean': float(np.nanmean(self.difficulty_scores)),
            'difficulty_std': float(np.nanstd(self.difficulty_scores)),
            'terrain_distribution': terrain_counts,
            'total_pixels': int(self.difficulty_scores.size),
            'construction_factor_mean': float(np.nanmean(self.construction_factors)),
            'accessibility_mean': float(np.nanmean(self.accessibility_scores))
        }
    
    def get_terrain_type_name(self, terrain_type: int) -> str:
        """Get human-readable name for terrain type."""
        return self.TERRAIN_NAMES.get(terrain_type, "unknown")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            'difficulty_shape': self.difficulty_scores.shape,
            'statistics': self.get_difficulty_statistics(),
            'bounds': self.bounds.to_dict() if self.bounds else None,
            'resolution': self.resolution
        }
        
        if self.source_freshness:
            result['freshness'] = {
                'source_type': self.source_freshness.source_type,
                'source_name': self.source_freshness.source_name,
                'data_age_hours': self.source_freshness.data_age_hours,
                'is_real_time': self.source_freshness.is_real_time,
                'quality_score': self.source_freshness.quality_score,
                'indicator': self.source_freshness.get_freshness_indicator(),
                'cache_hit': self.source_freshness.cache_hit
            }
        
        return result


@dataclass
class ElevationProfile:
    """Elevation profile along a route."""
    distances: List[float]  # Distance from start in meters
    elevations: List[float]  # Elevation in meters
    coordinates: List[Coordinate]  # Geographic coordinates
    total_distance: float  # Total distance in meters
    elevation_gain: float  # Total elevation gain in meters
    elevation_loss: float  # Total elevation loss in meters
    max_elevation: float  # Maximum elevation in meters
    min_elevation: float  # Minimum elevation in meters
    average_slope: float  # Average slope in degrees
    max_slope: float  # Maximum slope in degrees
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'distances': self.distances,
            'elevations': self.elevations,
            'coordinates': [coord.to_dict() for coord in self.coordinates],
            'total_distance': self.total_distance,
            'elevation_gain': self.elevation_gain,
            'elevation_loss': self.elevation_loss,
            'max_elevation': self.max_elevation,
            'min_elevation': self.min_elevation,
            'average_slope': self.average_slope,
            'max_slope': self.max_slope,
            'elevation_range': self.max_elevation - self.min_elevation
        }


@dataclass
class CostSurface:
    """Weighted cost surface for route optimization."""
    cost_array: np.ndarray  # Cost values for each pixel
    weights: Dict[str, float]  # Factor weights used in calculation
    bounds: BoundingBox
    resolution: float
    transform: rasterio.Affine
    coordinate_system: str = "EPSG:4326"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'cost_shape': self.cost_array.shape,
            'cost_min': float(np.nanmin(self.cost_array)),
            'cost_max': float(np.nanmax(self.cost_array)),
            'cost_mean': float(np.nanmean(self.cost_array)),
            'weights': self.weights,
            'bounds': self.bounds.to_dict(),
            'resolution': self.resolution,
            'coordinate_system': self.coordinate_system
        }


class DEM_Processor:
    """
    Digital Elevation Model processor with API and local file support.
    
    This class processes elevation data from APIs or local files to extract terrain
    metrics including slope calculation, elevation profiles, and cost surfaces for
    route optimization. It integrates with the API_Client for data fetching and
    provides fallback to local DEM files.
    
    Features:
    - Load elevation data from API responses or local TIFF files
    - Calculate slope and aspect using GDAL processing
    - Extract elevation profiles along routes
    - Generate weighted cost surfaces for pathfinding
    - NASA SRTM API integration with Uttarkashi DEM fallback
    - Uttarakhand-specific terrain analysis parameters
    """
    
    def __init__(self, api_client: Optional[API_Client] = None):
        """
        Initialize DEM processor.
        
        Args:
            api_client: Optional API client for fetching elevation data
        """
        self.api_client = api_client
        self.cache = {}  # Simple in-memory cache for processed DEM data
        
        # Uttarakhand-specific terrain parameters
        self.uttarakhand_params = {
            'slope_thresholds': {
                'flat': 5.0,        # 0-5 degrees
                'gentle': 15.0,     # 5-15 degrees  
                'moderate': 25.0,   # 15-25 degrees
                'steep': 35.0,      # 25-35 degrees
                'very_steep': 45.0, # 35-45 degrees
                # >45 degrees = extreme
            },
            'elevation_zones': {
                'valley': (500, 1000),      # 500-1000m
                'low_hills': (1000, 2000),  # 1000-2000m
                'mid_hills': (2000, 3000),  # 2000-3000m
                'high_hills': (3000, 4000), # 3000-4000m
                'alpine': (4000, 6000),     # 4000-6000m
            },
            'construction_difficulty': {
                'flat': 1.0,
                'gentle': 1.5,
                'moderate': 2.5,
                'steep': 4.0,
                'very_steep': 7.0,
                'extreme': 12.0
            }
        }
        
        logger.info("Initialized DEM_Processor with Uttarakhand-specific parameters")
    
    async def load_elevation_data(self, 
                                source: Union[BoundingBox, str, ElevationData],
                                force_local: bool = False) -> DEMData:
        """
        Load elevation data from API responses or local TIFF files.
        
        This method handles multiple input types:
        - BoundingBox: Fetch from API or local DEM file
        - str: Path to local TIFF file
        - ElevationData: Convert API response to DEMData
        
        Args:
            source: Data source (bounding box, file path, or API response)
            force_local: Force use of local data even if API is available
            
        Returns:
            DEMData: Processed elevation data with metadata
            
        Raises:
            ValueError: If source type is not supported
            FileNotFoundError: If local file doesn't exist
            RuntimeError: If data processing fails
        """
        cache_key = self._generate_cache_key(source)
        
        # Check cache first
        if cache_key in self.cache:
            logger.debug(f"Using cached DEM data for {cache_key}")
            return self.cache[cache_key]
        
        try:
            if isinstance(source, BoundingBox):
                # Fetch elevation data via API or local file
                dem_data = await self._load_from_bounds(source, force_local)
            elif isinstance(source, str):
                # Load from local TIFF file
                dem_data = await self._load_from_file(source)
            elif isinstance(source, ElevationData):
                # Convert API response to DEMData
                dem_data = await self._convert_api_response(source)
            else:
                raise ValueError(f"Unsupported source type: {type(source)}")
            
            # Cache the result
            self.cache[cache_key] = dem_data
            
            logger.info(f"Loaded DEM data: {dem_data.elevation_array.shape} "
                       f"from {dem_data.source} (resolution: {dem_data.resolution}m)")
            
            return dem_data
            
        except Exception as e:
            logger.error(f"Failed to load elevation data: {e}")
            raise RuntimeError(f"DEM data loading failed: {e}") from e
    
    async def calculate_slope(self, 
                            dem_data: DEMData,
                            algorithm: str = "gdal") -> SlopeData:
        """
        Calculate slope and aspect using GDAL DEMProcessing.
        
        This method computes slope gradients and optionally aspect (direction)
        from elevation data using GDAL's optimized algorithms.
        
        Args:
            dem_data: Input elevation data
            algorithm: Algorithm to use ("gdal", "numpy", or "scipy")
            
        Returns:
            SlopeData: Slope analysis results with statistics
            
        Raises:
            RuntimeError: If slope calculation fails
        """
        try:
            if algorithm == "gdal":
                slope_data = await self._calculate_slope_gdal(dem_data)
            elif algorithm == "numpy":
                slope_data = self._calculate_slope_numpy(dem_data)
            elif algorithm == "scipy":
                slope_data = self._calculate_slope_scipy(dem_data)
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            
            # Add Uttarakhand-specific slope classification
            slope_data.slope_classification = self._classify_slopes_uttarakhand(
                slope_data.slope_degrees
            )
            
            logger.info(f"Calculated slope data using {algorithm} algorithm: "
                       f"mean slope {slope_data.get_slope_statistics()['mean_slope_degrees']:.1f}°")
            
            return slope_data
            
        except Exception as e:
            logger.error(f"Slope calculation failed: {e}")
            raise RuntimeError(f"Slope calculation failed: {e}") from e
    
    async def extract_elevation_profile(self,
                                      start: Coordinate,
                                      end: Coordinate,
                                      dem_data: Optional[DEMData] = None,
                                      num_points: int = 100) -> ElevationProfile:
        """
        Extract elevation profile for route elevation analysis.
        
        This method samples elevation along a straight line between two points,
        providing detailed elevation profile information for route analysis.
        
        Args:
            start: Starting coordinate
            end: Ending coordinate  
            dem_data: Optional DEM data (will fetch if not provided)
            num_points: Number of sample points along the route
            
        Returns:
            ElevationProfile: Detailed elevation profile with statistics
            
        Raises:
            RuntimeError: If profile extraction fails
        """
        try:
            # Get DEM data if not provided
            if dem_data is None:
                bounds = BoundingBox(
                    north=max(start.latitude, end.latitude) + 0.01,
                    south=min(start.latitude, end.latitude) - 0.01,
                    east=max(start.longitude, end.longitude) + 0.01,
                    west=min(start.longitude, end.longitude) - 0.01
                )
                dem_data = await self.load_elevation_data(bounds)
            
            # Create line geometry
            line = LineString([(start.longitude, start.latitude), 
                             (end.longitude, end.latitude)])
            
            # Sample points along the line
            distances = np.linspace(0, line.length, num_points)
            coordinates = []
            elevations = []
            
            for i, distance in enumerate(distances):
                # Get point at distance along line
                point = line.interpolate(distance, normalized=True)
                coord = Coordinate(point.y, point.x)
                coordinates.append(coord)
                
                # Sample elevation at this point
                elevation = self._sample_elevation_at_point(coord, dem_data)
                elevations.append(elevation)
            
            # Convert distances to meters (approximate)
            total_distance_m = self._calculate_distance_meters(start, end)
            distances_m = [d * total_distance_m for d in distances]
            
            # Calculate profile statistics
            profile = self._calculate_profile_statistics(
                distances_m, elevations, coordinates
            )
            
            logger.info(f"Extracted elevation profile: {len(elevations)} points, "
                       f"{total_distance_m:.0f}m total distance, "
                       f"{profile.elevation_gain:.0f}m gain")
            
            return profile
            
        except Exception as e:
            logger.error(f"Elevation profile extraction failed: {e}")
            raise RuntimeError(f"Profile extraction failed: {e}") from e
    
    async def generate_cost_surface(self,
                                  dem_data: DEMData,
                                  slope_weights: Optional[Dict[str, float]] = None) -> CostSurface:
        """
        Generate cost surface with configurable slope weights.
        
        This method creates a weighted cost surface for route optimization,
        combining slope difficulty, elevation zones, and other terrain factors
        specific to Uttarakhand conditions.
        
        Args:
            dem_data: Input elevation data
            slope_weights: Optional custom weights for different factors
            
        Returns:
            CostSurface: Weighted cost surface for pathfinding
            
        Raises:
            RuntimeError: If cost surface generation fails
        """
        try:
            # Use default Uttarakhand weights if not provided
            if slope_weights is None:
                slope_weights = {
                    'slope_factor': 0.4,        # Primary factor for Himalayan terrain
                    'elevation_factor': 0.2,    # Altitude effects
                    'aspect_factor': 0.1,       # North-facing slopes (shadow/ice)
                    'roughness_factor': 0.2,    # Terrain roughness
                    'base_cost': 0.1           # Minimum traversal cost
                }
            
            # Calculate slope if not already done
            if dem_data.slope_array is None:
                slope_data = await self.calculate_slope(dem_data)
                dem_data.slope_array = slope_data.slope_degrees
                dem_data.aspect_array = slope_data.aspect_degrees
            
            # Initialize cost array
            cost_array = np.ones_like(dem_data.elevation_array, dtype=np.float32)
            cost_array *= slope_weights.get('base_cost', 0.1)
            
            # Apply slope-based costs (primary factor in mountains)
            slope_costs = self._calculate_slope_costs(
                dem_data.slope_array, slope_weights.get('slope_factor', 0.4)
            )
            cost_array += slope_costs
            
            # Apply elevation-based costs (altitude effects)
            elevation_costs = self._calculate_elevation_costs(
                dem_data.elevation_array, slope_weights.get('elevation_factor', 0.2)
            )
            cost_array += elevation_costs
            
            # Apply aspect-based costs (north-facing slopes in Himalayas)
            if dem_data.aspect_array is not None:
                aspect_costs = self._calculate_aspect_costs(
                    dem_data.aspect_array, slope_weights.get('aspect_factor', 0.1)
                )
                cost_array += aspect_costs
            
            # Apply roughness-based costs
            roughness_costs = self._calculate_roughness_costs(
                dem_data.elevation_array, slope_weights.get('roughness_factor', 0.2)
            )
            cost_array += roughness_costs
            
            # Normalize costs to reasonable range (1.0 to 10.0)
            cost_array = np.clip(cost_array, 1.0, 10.0)
            
            cost_surface = CostSurface(
                cost_array=cost_array,
                weights=slope_weights,
                bounds=dem_data.bounds,
                resolution=dem_data.resolution,
                transform=dem_data.transform,
                coordinate_system=dem_data.coordinate_system
            )
            
            logger.info(f"Generated cost surface: {cost_array.shape} "
                       f"(cost range: {np.min(cost_array):.2f}-{np.max(cost_array):.2f})")
            
            return cost_surface
            
        except Exception as e:
            logger.error(f"Cost surface generation failed: {e}")
            raise RuntimeError(f"Cost surface generation failed: {e}") from e
    
    def _generate_cache_key(self, source: Union[BoundingBox, str, ElevationData]) -> str:
        """Generate cache key for DEM data."""
        if isinstance(source, BoundingBox):
            return f"bounds_{source.north}_{source.south}_{source.east}_{source.west}"
        elif isinstance(source, str):
            return f"file_{Path(source).name}"
        elif isinstance(source, ElevationData):
            return f"api_{source.source}_{len(source.elevations)}"
        else:
            return f"unknown_{hash(str(source))}"
    
    async def _load_from_bounds(self, bounds: BoundingBox, force_local: bool) -> DEMData:
        """Load DEM data from bounding box using API or local file."""
        if not force_local and self.api_client:
            try:
                # Try to fetch from API first
                elevation_data = await self.api_client.fetch_elevation_data(bounds)
                if elevation_data and elevation_data.source != "local_dem":
                    return await self._convert_api_response(elevation_data)
            except Exception as e:
                logger.warning(f"API fetch failed, falling back to local: {e}")
        
        # Fallback to local DEM file
        return await self._load_from_local_dem(bounds)
    
    async def _load_from_file(self, file_path: str) -> DEMData:
        """Load DEM data from local TIFF file."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"DEM file not found: {file_path}")
        
        try:
            with rasterio.open(file_path) as dataset:
                # Read elevation data
                elevation_array = dataset.read(1)
                
                # Get metadata
                bounds = BoundingBox(
                    north=dataset.bounds.top,
                    south=dataset.bounds.bottom,
                    east=dataset.bounds.right,
                    west=dataset.bounds.left
                )
                
                # Calculate resolution
                resolution = abs(dataset.transform[0])  # Pixel width in degrees
                if dataset.crs and dataset.crs.to_epsg() == 4326:
                    # Convert degrees to meters (approximate at equator)
                    resolution *= 111000  # meters per degree
                
                return DEMData(
                    elevation_array=elevation_array,
                    bounds=bounds,
                    resolution=resolution,
                    coordinate_system=str(dataset.crs) if dataset.crs else "EPSG:4326",
                    transform=dataset.transform,
                    nodata_value=dataset.nodata,
                    source=f"local_file_{file_path.name}",
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            raise RuntimeError(f"Failed to load DEM file {file_path}: {e}") from e
    
    async def _load_from_local_dem(self, bounds: BoundingBox) -> DEMData:
        """Load DEM data from local Uttarkashi DEM file."""
        # Use the Uttarkashi DEM file from the project
        dem_file = Path("Uttarkashi_Terrain/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif")
        
        if not dem_file.exists():
            logger.warning(f"Uttarkashi DEM file not found: {dem_file}")
            return self._create_mock_dem_data(bounds)
        
        try:
            with rasterio.open(dem_file) as dataset:
                # Check if bounds intersect with dataset
                if not self._bounds_intersect(bounds, dataset.bounds):
                    logger.warning(f"Bounds {bounds} do not intersect with DEM coverage")
                    return self._create_mock_dem_data(bounds)
                
                # Get window for the bounding box
                window = from_bounds(
                    bounds.west, bounds.south, bounds.east, bounds.north,
                    dataset.transform
                )
                
                # Ensure window is within dataset bounds
                window = window.intersection(
                    Window(0, 0, dataset.width, dataset.height)
                )
                
                if window.width <= 0 or window.height <= 0:
                    logger.warning("No valid data in requested bounds")
                    return self._create_mock_dem_data(bounds)
                
                # Read elevation data
                elevation_array = dataset.read(1, window=window)
                
                # Handle nodata values
                if dataset.nodata is not None:
                    elevation_array = elevation_array.astype(np.float32)
                    elevation_array[elevation_array == dataset.nodata] = np.nan
                
                return DEMData(
                    elevation_array=elevation_array,
                    bounds=bounds,
                    resolution=30.0,  # SRTM 30m resolution
                    coordinate_system="EPSG:4326",
                    transform=dataset.transform,
                    nodata_value=dataset.nodata,
                    source="local_uttarkashi_dem",
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Failed to load Uttarkashi DEM: {e}")
            return self._create_mock_dem_data(bounds)
    
    async def _convert_api_response(self, elevation_data: ElevationData) -> DEMData:
        """Convert API elevation response to DEMData."""
        try:
            # Convert coordinate list to 2D elevation array
            if not elevation_data.coordinates:
                raise ValueError("No coordinate data in API response")
            
            # Determine grid dimensions
            lats = [coord.latitude for coord in elevation_data.coordinates]
            lons = [coord.longitude for coord in elevation_data.coordinates]
            elevs = elevation_data.elevations
            
            # Create regular grid
            unique_lats = sorted(set(lats), reverse=True)  # North to south
            unique_lons = sorted(set(lons))  # West to east
            
            if len(unique_lats) == 1 or len(unique_lons) == 1:
                # Single row or column - create minimal 2D array
                elevation_array = np.array(elevs).reshape(len(unique_lats), len(unique_lons))
            else:
                # Create 2D grid
                elevation_array = np.full((len(unique_lats), len(unique_lons)), np.nan)
                
                for coord, elev in zip(elevation_data.coordinates, elevs):
                    try:
                        lat_idx = unique_lats.index(coord.latitude)
                        lon_idx = unique_lons.index(coord.longitude)
                        elevation_array[lat_idx, lon_idx] = elev
                    except ValueError:
                        continue  # Skip points that don't fit the grid
            
            # Create transform
            if len(unique_lats) > 1 and len(unique_lons) > 1:
                pixel_height = (unique_lats[0] - unique_lats[-1]) / (len(unique_lats) - 1)
                pixel_width = (unique_lons[-1] - unique_lons[0]) / (len(unique_lons) - 1)
            else:
                pixel_height = pixel_width = elevation_data.resolution / 111000  # Convert m to degrees
            
            transform = rasterio.transform.from_bounds(
                min(lons), min(lats), max(lons), max(lats),
                len(unique_lons), len(unique_lats)
            )
            
            return DEMData(
                elevation_array=elevation_array,
                bounds=elevation_data.bounds,
                resolution=elevation_data.resolution,
                coordinate_system="EPSG:4326",
                transform=transform,
                source=elevation_data.source,
                timestamp=elevation_data.timestamp,
                freshness_info=elevation_data.freshness_info
            )
            
        except Exception as e:
            logger.error(f"Failed to convert API response: {e}")
            # Fallback to mock data
            return self._create_mock_dem_data(elevation_data.bounds or BoundingBox(30.8, 30.6, 78.6, 78.4))
    
    def _create_mock_dem_data(self, bounds: BoundingBox) -> DEMData:
        """Create mock DEM data for testing when real data is unavailable."""
        # Create a realistic elevation grid for Uttarkashi region
        rows, cols = 50, 50
        
        # Generate elevation values with realistic Himalayan characteristics
        lat_range = bounds.north - bounds.south
        lon_range = bounds.east - bounds.west
        
        # Create coordinate grids
        lats = np.linspace(bounds.south, bounds.north, rows)
        lons = np.linspace(bounds.west, bounds.east, cols)
        
        # Generate realistic elevation pattern
        elevation_array = np.zeros((rows, cols))
        
        for i, lat in enumerate(lats):
            for j, lon in enumerate(lons):
                # Base elevation increases with latitude (northward in Himalayas)
                base_elevation = 1000 + (lat - bounds.south) / lat_range * 2000
                
                # Add some east-west variation
                ew_variation = np.sin((lon - bounds.west) / lon_range * np.pi) * 300
                
                # Add random variation
                np.random.seed(int((lat * 1000 + lon * 1000) % 1000))  # Deterministic randomness
                random_variation = np.random.normal(0, 100)
                
                elevation_array[i, j] = base_elevation + ew_variation + random_variation
        
        # Ensure realistic elevation range
        elevation_array = np.clip(elevation_array, 500, 4000)
        
        # Create transform
        transform = rasterio.transform.from_bounds(
            bounds.west, bounds.south, bounds.east, bounds.north,
            cols, rows
        )
        
        return DEMData(
            elevation_array=elevation_array,
            bounds=bounds,
            resolution=30.0,
            coordinate_system="EPSG:4326",
            transform=transform,
            source="mock_uttarkashi_dem",
            timestamp=datetime.now()
        )
    
    async def _calculate_slope_gdal(self, dem_data: DEMData) -> SlopeData:
        """Calculate slope using GDAL DEMProcessing."""
        if not GDAL_AVAILABLE:
            logger.warning("GDAL not available, falling back to numpy")
            return self._calculate_slope_numpy(dem_data)
        
        try:
            # Create temporary files for GDAL processing
            with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as temp_dem:
                with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as temp_slope:
                    with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as temp_aspect:
                        try:
                            # Write DEM data to temporary file
                            self._write_dem_to_file(dem_data, temp_dem.name)
                            
                            # Calculate slope using GDAL
                            gdal.DEMProcessing(
                                temp_slope.name,
                                temp_dem.name,
                                'slope',
                                format='GTiff',
                                computeEdges=True,
                                slopeFormat='degree'
                            )
                            
                            # Calculate aspect using GDAL
                            gdal.DEMProcessing(
                                temp_aspect.name,
                                temp_dem.name,
                                'aspect',
                                format='GTiff',
                                computeEdges=True
                            )
                            
                            # Read results
                            with rasterio.open(temp_slope.name) as slope_ds:
                                slope_degrees = slope_ds.read(1)
                            
                            with rasterio.open(temp_aspect.name) as aspect_ds:
                                aspect_degrees = aspect_ds.read(1)
                            
                            # Convert slope to percent
                            slope_percent = np.tan(np.radians(slope_degrees)) * 100
                            
                            return SlopeData(
                                slope_degrees=slope_degrees,
                                slope_percent=slope_percent,
                                aspect_degrees=aspect_degrees,
                                bounds=dem_data.bounds,
                                resolution=dem_data.resolution
                            )
                            
                        finally:
                            # Clean up temporary files
                            for temp_file in [temp_dem.name, temp_slope.name, temp_aspect.name]:
                                try:
                                    os.unlink(temp_file)
                                except OSError:
                                    pass
                                    
        except Exception as e:
            logger.warning(f"GDAL slope calculation failed: {e}, falling back to numpy")
            return self._calculate_slope_numpy(dem_data)
    
    def _calculate_slope_numpy(self, dem_data: DEMData) -> SlopeData:
        """Calculate slope using numpy gradients."""
        try:
            elevation = dem_data.elevation_array.astype(np.float64)
            
            # Calculate gradients
            dy, dx = np.gradient(elevation)
            
            # Convert pixel gradients to real-world gradients
            pixel_size = dem_data.resolution  # meters
            
            # Calculate slope in radians then convert to degrees
            slope_radians = np.arctan(np.sqrt(dx**2 + dy**2) / pixel_size)
            slope_degrees = np.degrees(slope_radians)
            
            # Calculate slope percent
            slope_percent = np.tan(slope_radians) * 100
            
            # Calculate aspect
            aspect_radians = np.arctan2(-dx, dy)
            aspect_degrees = np.degrees(aspect_radians)
            aspect_degrees = (aspect_degrees + 360) % 360  # Normalize to 0-360
            
            return SlopeData(
                slope_degrees=slope_degrees,
                slope_percent=slope_percent,
                aspect_degrees=aspect_degrees,
                bounds=dem_data.bounds,
                resolution=dem_data.resolution
            )
            
        except Exception as e:
            logger.error(f"Numpy slope calculation failed: {e}")
            raise RuntimeError(f"Slope calculation failed: {e}") from e
    
    def _calculate_slope_scipy(self, dem_data: DEMData) -> SlopeData:
        """Calculate slope using scipy filters."""
        try:
            elevation = dem_data.elevation_array.astype(np.float64)
            
            # Use Sobel filters for gradient calculation
            dx = ndimage.sobel(elevation, axis=1) / 8.0
            dy = ndimage.sobel(elevation, axis=0) / 8.0
            
            # Convert to slope
            pixel_size = dem_data.resolution
            slope_radians = np.arctan(np.sqrt(dx**2 + dy**2) / pixel_size)
            slope_degrees = np.degrees(slope_radians)
            slope_percent = np.tan(slope_radians) * 100
            
            # Calculate aspect
            aspect_radians = np.arctan2(-dx, dy)
            aspect_degrees = np.degrees(aspect_radians)
            aspect_degrees = (aspect_degrees + 360) % 360
            
            return SlopeData(
                slope_degrees=slope_degrees,
                slope_percent=slope_percent,
                aspect_degrees=aspect_degrees,
                bounds=dem_data.bounds,
                resolution=dem_data.resolution
            )
            
        except Exception as e:
            logger.error(f"Scipy slope calculation failed: {e}")
            raise RuntimeError(f"Slope calculation failed: {e}") from e
    
    def _write_dem_to_file(self, dem_data: DEMData, filename: str) -> None:
        """Write DEM data to a GeoTIFF file for GDAL processing."""
        if not GDAL_AVAILABLE:
            raise RuntimeError("GDAL not available for file writing")
            
        with rasterio.open(
            filename,
            'w',
            driver='GTiff',
            height=dem_data.elevation_array.shape[0],
            width=dem_data.elevation_array.shape[1],
            count=1,
            dtype=dem_data.elevation_array.dtype,
            crs=dem_data.coordinate_system,
            transform=dem_data.transform,
            nodata=dem_data.nodata_value
        ) as dst:
            dst.write(dem_data.elevation_array, 1)
    
    def _classify_slopes_uttarakhand(self, slope_degrees: np.ndarray) -> np.ndarray:
        """Classify slopes using Uttarakhand-specific thresholds."""
        classification = np.zeros_like(slope_degrees, dtype=np.int8)
        
        thresholds = self.uttarakhand_params['slope_thresholds']
        
        classification[slope_degrees <= thresholds['flat']] = 0      # Flat
        classification[(slope_degrees > thresholds['flat']) & 
                      (slope_degrees <= thresholds['gentle'])] = 1   # Gentle
        classification[(slope_degrees > thresholds['gentle']) & 
                      (slope_degrees <= thresholds['moderate'])] = 2 # Moderate
        classification[(slope_degrees > thresholds['moderate']) & 
                      (slope_degrees <= thresholds['steep'])] = 3    # Steep
        classification[(slope_degrees > thresholds['steep']) & 
                      (slope_degrees <= thresholds['very_steep'])] = 4 # Very steep
        classification[slope_degrees > thresholds['very_steep']] = 5  # Extreme
        
        return classification
    
    def _sample_elevation_at_point(self, coord: Coordinate, dem_data: DEMData) -> float:
        """Sample elevation at a specific coordinate."""
        try:
            if dem_data.transform is None:
                # Fallback to simple indexing
                lat_idx = int((coord.latitude - dem_data.bounds.south) / 
                            (dem_data.bounds.north - dem_data.bounds.south) * 
                            dem_data.elevation_array.shape[0])
                lon_idx = int((coord.longitude - dem_data.bounds.west) / 
                            (dem_data.bounds.east - dem_data.bounds.west) * 
                            dem_data.elevation_array.shape[1])
                
                lat_idx = np.clip(lat_idx, 0, dem_data.elevation_array.shape[0] - 1)
                lon_idx = np.clip(lon_idx, 0, dem_data.elevation_array.shape[1] - 1)
                
                return float(dem_data.elevation_array[lat_idx, lon_idx])
            else:
                # Use rasterio transform
                row, col = rowcol(dem_data.transform, coord.longitude, coord.latitude)
                
                # Ensure indices are within bounds
                row = np.clip(row, 0, dem_data.elevation_array.shape[0] - 1)
                col = np.clip(col, 0, dem_data.elevation_array.shape[1] - 1)
                
                elevation = dem_data.elevation_array[row, col]
                
                # Handle nodata values
                if np.isnan(elevation) or (dem_data.nodata_value is not None and 
                                         elevation == dem_data.nodata_value):
                    # Interpolate from nearby values
                    return self._interpolate_elevation(coord, dem_data)
                
                return float(elevation)
                
        except Exception as e:
            logger.warning(f"Failed to sample elevation at {coord}: {e}")
            return 1500.0  # Default elevation for Uttarkashi region
    
    def _interpolate_elevation(self, coord: Coordinate, dem_data: DEMData) -> float:
        """Interpolate elevation from nearby valid values."""
        try:
            # Get a small window around the point
            if dem_data.transform:
                row, col = rowcol(dem_data.transform, coord.longitude, coord.latitude)
            else:
                row = int((coord.latitude - dem_data.bounds.south) / 
                         (dem_data.bounds.north - dem_data.bounds.south) * 
                         dem_data.elevation_array.shape[0])
                col = int((coord.longitude - dem_data.bounds.west) / 
                         (dem_data.bounds.east - dem_data.bounds.west) * 
                         dem_data.elevation_array.shape[1])
            
            # Extract 3x3 window
            window_size = 1
            row_start = max(0, row - window_size)
            row_end = min(dem_data.elevation_array.shape[0], row + window_size + 1)
            col_start = max(0, col - window_size)
            col_end = min(dem_data.elevation_array.shape[1], col + window_size + 1)
            
            window = dem_data.elevation_array[row_start:row_end, col_start:col_end]
            
            # Find valid values
            if dem_data.nodata_value is not None:
                valid_mask = (window != dem_data.nodata_value) & ~np.isnan(window)
            else:
                valid_mask = ~np.isnan(window)
            
            if np.any(valid_mask):
                return float(np.mean(window[valid_mask]))
            else:
                return 1500.0  # Default for Uttarkashi
                
        except Exception:
            return 1500.0  # Default for Uttarkashi
    
    def _calculate_distance_meters(self, start: Coordinate, end: Coordinate) -> float:
        """Calculate distance between coordinates in meters."""
        # Haversine formula for great circle distance
        R = 6371000  # Earth radius in meters
        
        lat1, lon1 = np.radians(start.latitude), np.radians(start.longitude)
        lat2, lon2 = np.radians(end.latitude), np.radians(end.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = (np.sin(dlat/2)**2 + 
             np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2)
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    def _calculate_profile_statistics(self, 
                                    distances: List[float], 
                                    elevations: List[float],
                                    coordinates: List[Coordinate]) -> ElevationProfile:
        """Calculate elevation profile statistics."""
        elevations_array = np.array(elevations)
        distances_array = np.array(distances)
        
        # Calculate elevation changes
        elevation_diffs = np.diff(elevations_array)
        elevation_gain = np.sum(elevation_diffs[elevation_diffs > 0])
        elevation_loss = -np.sum(elevation_diffs[elevation_diffs < 0])
        
        # Calculate slopes between points
        distance_diffs = np.diff(distances_array)
        slopes = []
        for i in range(len(elevation_diffs)):
            if distance_diffs[i] > 0:
                slope_rad = np.arctan(elevation_diffs[i] / distance_diffs[i])
                slopes.append(np.degrees(slope_rad))
        
        slopes_array = np.array(slopes) if slopes else np.array([0])
        
        return ElevationProfile(
            distances=distances,
            elevations=elevations,
            coordinates=coordinates,
            total_distance=distances[-1] if distances else 0.0,
            elevation_gain=elevation_gain,
            elevation_loss=elevation_loss,
            max_elevation=np.max(elevations_array),
            min_elevation=np.min(elevations_array),
            average_slope=np.mean(np.abs(slopes_array)),
            max_slope=np.max(np.abs(slopes_array)) if len(slopes_array) > 0 else 0.0
        )
    
    def _calculate_slope_costs(self, slope_array: np.ndarray, weight: float) -> np.ndarray:
        """Calculate costs based on slope difficulty."""
        costs = np.zeros_like(slope_array, dtype=np.float32)
        
        difficulty = self.uttarakhand_params['construction_difficulty']
        thresholds = self.uttarakhand_params['slope_thresholds']
        
        # Apply costs based on slope categories
        costs[slope_array <= thresholds['flat']] = difficulty['flat']
        costs[(slope_array > thresholds['flat']) & 
              (slope_array <= thresholds['gentle'])] = difficulty['gentle']
        costs[(slope_array > thresholds['gentle']) & 
              (slope_array <= thresholds['moderate'])] = difficulty['moderate']
        costs[(slope_array > thresholds['moderate']) & 
              (slope_array <= thresholds['steep'])] = difficulty['steep']
        costs[(slope_array > thresholds['steep']) & 
              (slope_array <= thresholds['very_steep'])] = difficulty['very_steep']
        costs[slope_array > thresholds['very_steep']] = difficulty['extreme']
        
        return costs * weight
    
    def _calculate_elevation_costs(self, elevation_array: np.ndarray, weight: float) -> np.ndarray:
        """Calculate costs based on elevation zones."""
        costs = np.ones_like(elevation_array, dtype=np.float32)
        
        zones = self.uttarakhand_params['elevation_zones']
        
        # Higher elevations are more difficult for construction
        costs[elevation_array < zones['valley'][1]] = 1.0      # Valley
        costs[(elevation_array >= zones['low_hills'][0]) & 
              (elevation_array < zones['low_hills'][1])] = 1.2  # Low hills
        costs[(elevation_array >= zones['mid_hills'][0]) & 
              (elevation_array < zones['mid_hills'][1])] = 1.5  # Mid hills
        costs[(elevation_array >= zones['high_hills'][0]) & 
              (elevation_array < zones['high_hills'][1])] = 2.0 # High hills
        costs[elevation_array >= zones['alpine'][0]] = 3.0     # Alpine
        
        return costs * weight
    
    def _calculate_aspect_costs(self, aspect_array: np.ndarray, weight: float) -> np.ndarray:
        """Calculate costs based on aspect (north-facing slopes are more difficult)."""
        costs = np.ones_like(aspect_array, dtype=np.float32)
        
        # North-facing slopes (315-45 degrees) are more difficult in Himalayas
        # due to ice, snow, and reduced sunlight
        north_facing = ((aspect_array >= 315) | (aspect_array <= 45))
        costs[north_facing] = 1.5
        
        # South-facing slopes are easier
        south_facing = ((aspect_array >= 135) & (aspect_array <= 225))
        costs[south_facing] = 0.8
        
        return costs * weight
    
    def _calculate_roughness_costs(self, elevation_array: np.ndarray, weight: float) -> np.ndarray:
        """Calculate costs based on terrain roughness."""
        # Calculate terrain roughness using standard deviation in a moving window
        from scipy.ndimage import uniform_filter
        
        # Calculate local standard deviation (roughness)
        mean_elev = uniform_filter(elevation_array.astype(np.float64), size=3)
        sqr_elev = uniform_filter(elevation_array.astype(np.float64)**2, size=3)
        roughness = np.sqrt(sqr_elev - mean_elev**2)
        
        # Normalize roughness to cost multiplier (1.0 to 2.0)
        max_roughness = np.nanpercentile(roughness, 95)  # Use 95th percentile to avoid outliers
        if max_roughness > 0:
            normalized_roughness = roughness / max_roughness
            costs = 1.0 + normalized_roughness
        else:
            costs = np.ones_like(roughness)
        
        return costs * weight
    
    def _bounds_intersect(self, bounds: BoundingBox, dataset_bounds) -> bool:
        """Check if bounding boxes intersect."""
        return not (bounds.east < dataset_bounds.left or 
                   bounds.west > dataset_bounds.right or
                   bounds.north < dataset_bounds.bottom or 
                   bounds.south > dataset_bounds.top)
    
    async def calculate_terrain_difficulty(self,
                                      dem_data: DEMData,
                                      include_real_time_factors: bool = True) -> TerrainDifficulty:
        """
        Calculate comprehensive terrain difficulty classification with real-time data.
        
        This method implements slope-based terrain difficulty scoring on a 0-100 scale,
        applies Uttarkashi-specific slope thresholds and difficulty factors, creates
        terrain type classification, and integrates real-time elevation data when available.
        
        Args:
            dem_data: Input elevation data (from API or local source)
            include_real_time_factors: Whether to include real-time data adjustments
            
        Returns:
            TerrainDifficulty: Comprehensive terrain difficulty analysis
            
        Raises:
            RuntimeError: If terrain difficulty calculation fails
        """
        try:
            # Calculate slope if not already done
            if dem_data.slope_array is None:
                slope_data = await self.calculate_slope(dem_data)
                dem_data.slope_array = slope_data.slope_degrees
                dem_data.aspect_array = slope_data.aspect_degrees
            
            # Classify terrain types using Uttarkashi-specific thresholds
            terrain_types = self._classify_terrain_types_uttarkashi(dem_data.slope_array)
            
            # Calculate difficulty scores (0-100 scale)
            difficulty_scores = self._calculate_difficulty_scores(
                dem_data.slope_array, dem_data.elevation_array, terrain_types
            )
            
            # Calculate construction difficulty factors
            construction_factors = self._calculate_construction_factors(
                terrain_types, dem_data.elevation_array, dem_data.aspect_array
            )
            
            # Calculate accessibility scores
            accessibility_scores = self._calculate_accessibility_scores(
                difficulty_scores, construction_factors, dem_data.elevation_array
            )
            
            # Apply real-time data adjustments if available and requested
            seasonal_factors = None
            if include_real_time_factors and dem_data.freshness_info:
                seasonal_factors = self._apply_real_time_adjustments(
                    difficulty_scores, dem_data.freshness_info
                )
                # Adjust scores based on real-time factors
                difficulty_scores = self._adjust_scores_for_real_time(
                    difficulty_scores, seasonal_factors
                )
            
            terrain_difficulty = TerrainDifficulty(
                difficulty_scores=difficulty_scores,
                terrain_types=terrain_types,
                construction_factors=construction_factors,
                accessibility_scores=accessibility_scores,
                seasonal_factors=seasonal_factors,
                bounds=dem_data.bounds,
                resolution=dem_data.resolution,
                source_freshness=dem_data.freshness_info
            )
            
            stats = terrain_difficulty.get_difficulty_statistics()
            logger.info(f"Calculated terrain difficulty: mean score {stats['difficulty_mean']:.1f}, "
                       f"terrain distribution: {stats['terrain_distribution']}")
            
            return terrain_difficulty
            
        except Exception as e:
            logger.error(f"Terrain difficulty calculation failed: {e}")
            raise RuntimeError(f"Terrain difficulty calculation failed: {e}") from e
    
    def _classify_terrain_types_uttarkashi(self, slope_degrees: np.ndarray) -> np.ndarray:
        """
        Classify terrain types using Uttarkashi-specific slope thresholds.
        
        Uses region-specific thresholds optimized for Himalayan terrain conditions
        in Uttarkashi district, considering local construction practices and
        geological characteristics.
        
        Args:
            slope_degrees: Slope angles in degrees
            
        Returns:
            np.ndarray: Terrain type classification (0-5)
        """
        terrain_types = np.zeros_like(slope_degrees, dtype=np.int8)
        thresholds = self.uttarakhand_params['slope_thresholds']
        
        # Apply Uttarkashi-specific terrain classification
        terrain_types[slope_degrees <= thresholds['flat']] = TerrainDifficulty.TERRAIN_FLAT
        terrain_types[(slope_degrees > thresholds['flat']) & 
                     (slope_degrees <= thresholds['gentle'])] = TerrainDifficulty.TERRAIN_GENTLE
        terrain_types[(slope_degrees > thresholds['gentle']) & 
                     (slope_degrees <= thresholds['moderate'])] = TerrainDifficulty.TERRAIN_MODERATE
        terrain_types[(slope_degrees > thresholds['moderate']) & 
                     (slope_degrees <= thresholds['steep'])] = TerrainDifficulty.TERRAIN_STEEP
        terrain_types[(slope_degrees > thresholds['steep']) & 
                     (slope_degrees <= thresholds['very_steep'])] = TerrainDifficulty.TERRAIN_VERY_STEEP
        terrain_types[slope_degrees > thresholds['very_steep']] = TerrainDifficulty.TERRAIN_EXTREME
        
        return terrain_types
    
    def _calculate_difficulty_scores(self, 
                                   slope_degrees: np.ndarray,
                                   elevation_array: np.ndarray,
                                   terrain_types: np.ndarray) -> np.ndarray:
        """
        Calculate terrain difficulty scores on 0-100 scale.
        
        Combines slope difficulty, elevation effects, and terrain type factors
        to produce a comprehensive difficulty score suitable for route planning
        and construction cost estimation.
        
        Args:
            slope_degrees: Slope angles in degrees
            elevation_array: Elevation values in meters
            terrain_types: Classified terrain types
            
        Returns:
            np.ndarray: Difficulty scores (0-100 scale)
        """
        # Base difficulty from slope (0-60 points)
        slope_difficulty = np.clip(slope_degrees * 1.2, 0, 60)
        
        # Elevation difficulty (0-20 points)
        elevation_difficulty = self._calculate_elevation_difficulty(elevation_array)
        
        # Terrain type bonus/penalty (0-20 points)
        terrain_difficulty = self._calculate_terrain_type_difficulty(terrain_types)
        
        # Combine factors
        total_difficulty = slope_difficulty + elevation_difficulty + terrain_difficulty
        
        # Ensure 0-100 scale
        difficulty_scores = np.clip(total_difficulty, 0, 100)
        
        return difficulty_scores.astype(np.float32)
    
    def _calculate_elevation_difficulty(self, elevation_array: np.ndarray) -> np.ndarray:
        """Calculate difficulty component based on elevation zones."""
        difficulty = np.zeros_like(elevation_array, dtype=np.float32)
        zones = self.uttarakhand_params['elevation_zones']
        
        # Valley (500-1000m): Low difficulty
        valley_mask = ((elevation_array >= zones['valley'][0]) & 
                      (elevation_array < zones['valley'][1]))
        difficulty[valley_mask] = 2.0
        
        # Low hills (1000-2000m): Moderate difficulty
        low_hills_mask = ((elevation_array >= zones['low_hills'][0]) & 
                         (elevation_array < zones['low_hills'][1]))
        difficulty[low_hills_mask] = 5.0
        
        # Mid hills (2000-3000m): Higher difficulty
        mid_hills_mask = ((elevation_array >= zones['mid_hills'][0]) & 
                         (elevation_array < zones['mid_hills'][1]))
        difficulty[mid_hills_mask] = 10.0
        
        # High hills (3000-4000m): High difficulty
        high_hills_mask = ((elevation_array >= zones['high_hills'][0]) & 
                          (elevation_array < zones['high_hills'][1]))
        difficulty[high_hills_mask] = 15.0
        
        # Alpine (4000m+): Maximum difficulty
        alpine_mask = elevation_array >= zones['alpine'][0]
        difficulty[alpine_mask] = 20.0
        
        # Below valley: Very low difficulty
        below_valley_mask = elevation_array < zones['valley'][0]
        difficulty[below_valley_mask] = 1.0
        
        return difficulty
    
    def _calculate_terrain_type_difficulty(self, terrain_types: np.ndarray) -> np.ndarray:
        """Calculate difficulty component based on terrain type classification."""
        difficulty = np.zeros_like(terrain_types, dtype=np.float32)
        
        # Terrain type difficulty bonuses
        difficulty[terrain_types == TerrainDifficulty.TERRAIN_FLAT] = 0.0
        difficulty[terrain_types == TerrainDifficulty.TERRAIN_GENTLE] = 2.0
        difficulty[terrain_types == TerrainDifficulty.TERRAIN_MODERATE] = 5.0
        difficulty[terrain_types == TerrainDifficulty.TERRAIN_STEEP] = 10.0
        difficulty[terrain_types == TerrainDifficulty.TERRAIN_VERY_STEEP] = 15.0
        difficulty[terrain_types == TerrainDifficulty.TERRAIN_EXTREME] = 20.0
        
        return difficulty
    
    def _calculate_construction_factors(self,
                                      terrain_types: np.ndarray,
                                      elevation_array: np.ndarray,
                                      aspect_array: Optional[np.ndarray]) -> np.ndarray:
        """
        Calculate construction difficulty factors using Uttarkashi-specific parameters.
        
        Applies region-specific construction difficulty multipliers that account for
        local conditions, equipment accessibility, and construction practices in
        the Himalayan environment.
        
        Args:
            terrain_types: Classified terrain types
            elevation_array: Elevation values
            aspect_array: Optional aspect (slope direction) values
            
        Returns:
            np.ndarray: Construction difficulty multipliers
        """
        factors = np.ones_like(terrain_types, dtype=np.float32)
        difficulty_params = self.uttarakhand_params['construction_difficulty']
        
        # Base factors from terrain type
        factors[terrain_types == TerrainDifficulty.TERRAIN_FLAT] = difficulty_params['flat']
        factors[terrain_types == TerrainDifficulty.TERRAIN_GENTLE] = difficulty_params['gentle']
        factors[terrain_types == TerrainDifficulty.TERRAIN_MODERATE] = difficulty_params['moderate']
        factors[terrain_types == TerrainDifficulty.TERRAIN_STEEP] = difficulty_params['steep']
        factors[terrain_types == TerrainDifficulty.TERRAIN_VERY_STEEP] = difficulty_params['very_steep']
        factors[terrain_types == TerrainDifficulty.TERRAIN_EXTREME] = difficulty_params['extreme']
        
        # Elevation adjustments (higher altitude = more difficult)
        elevation_multiplier = 1.0 + (np.clip(elevation_array - 1000, 0, 4000) / 4000) * 0.5
        factors *= elevation_multiplier
        
        # Aspect adjustments (north-facing slopes more difficult in Himalayas)
        if aspect_array is not None:
            aspect_multiplier = np.ones_like(aspect_array)
            # North-facing slopes (315-45 degrees) are more difficult
            north_facing = ((aspect_array >= 315) | (aspect_array <= 45))
            aspect_multiplier[north_facing] = 1.3
            # South-facing slopes are easier
            south_facing = ((aspect_array >= 135) & (aspect_array <= 225))
            aspect_multiplier[south_facing] = 0.9
            factors *= aspect_multiplier
        
        return factors
    
    def _calculate_accessibility_scores(self,
                                      difficulty_scores: np.ndarray,
                                      construction_factors: np.ndarray,
                                      elevation_array: np.ndarray) -> np.ndarray:
        """
        Calculate accessibility scores (0-100) for terrain areas.
        
        Higher scores indicate better accessibility for construction equipment,
        material transport, and maintenance operations. Considers terrain difficulty,
        construction factors, and elevation constraints.
        
        Args:
            difficulty_scores: Terrain difficulty scores (0-100)
            construction_factors: Construction difficulty multipliers
            elevation_array: Elevation values
            
        Returns:
            np.ndarray: Accessibility scores (0-100, higher is better)
        """
        # Start with inverse of difficulty (100 - difficulty)
        base_accessibility = 100.0 - difficulty_scores
        
        # Adjust for construction factors (higher factors = lower accessibility)
        construction_penalty = (construction_factors - 1.0) * 10.0
        accessibility = base_accessibility - construction_penalty
        
        # Elevation penalty (very high elevations reduce accessibility)
        elevation_penalty = np.clip((elevation_array - 3000) / 1000 * 10, 0, 20)
        accessibility -= elevation_penalty
        
        # Ensure 0-100 range
        accessibility_scores = np.clip(accessibility, 0, 100)
        
        return accessibility_scores.astype(np.float32)
    
    def _apply_real_time_adjustments(self,
                                   difficulty_scores: np.ndarray,
                                   freshness_info: DataFreshnessInfo) -> np.ndarray:
        """
        Apply real-time data adjustments to terrain difficulty.
        
        Adjusts terrain difficulty based on data freshness, source quality,
        and real-time conditions when API data is available.
        
        Args:
            difficulty_scores: Base terrain difficulty scores
            freshness_info: Information about data freshness and source
            
        Returns:
            np.ndarray: Seasonal/real-time adjustment factors
        """
        seasonal_factors = np.ones_like(difficulty_scores)
        
        # Quality adjustment based on data source
        if freshness_info.source_type == "api":
            # Real-time API data gets confidence boost
            if freshness_info.is_real_time:
                seasonal_factors *= 0.95  # Slight reduction in difficulty due to current data
            elif freshness_info.data_age_hours < 24:
                seasonal_factors *= 0.98  # Fresh data gets small adjustment
        else:
            # Local data gets slight penalty for staleness
            seasonal_factors *= 1.02
        
        # Data quality adjustment
        quality_adjustment = 1.0 + (1.0 - freshness_info.quality_score) * 0.05
        seasonal_factors *= quality_adjustment
        
        # Seasonal adjustments based on current time (if real-time)
        if freshness_info.is_real_time:
            current_month = datetime.now().month
            # Monsoon season (June-September) increases difficulty
            if 6 <= current_month <= 9:
                seasonal_factors *= 1.15  # 15% increase during monsoon
            # Winter season (December-February) increases difficulty at high elevation
            elif 12 <= current_month or current_month <= 2:
                seasonal_factors *= 1.08  # 8% increase during winter
        
        return seasonal_factors
    
    def _adjust_scores_for_real_time(self,
                                   difficulty_scores: np.ndarray,
                                   seasonal_factors: np.ndarray) -> np.ndarray:
        """Apply real-time seasonal factors to difficulty scores."""
        adjusted_scores = difficulty_scores * seasonal_factors
        return np.clip(adjusted_scores, 0, 100).astype(np.float32)
    
    def get_terrain_difficulty_at_point(self,
                                      coord: Coordinate,
                                      terrain_difficulty: TerrainDifficulty) -> Dict[str, Any]:
        """
        Get terrain difficulty information at a specific coordinate.
        
        Args:
            coord: Geographic coordinate
            terrain_difficulty: Terrain difficulty analysis results
            
        Returns:
            Dict containing difficulty metrics at the point
        """
        try:
            # Sample values at the coordinate
            if terrain_difficulty.bounds is None:
                raise ValueError("Terrain difficulty data has no bounds information")
            
            # Convert coordinate to array indices
            lat_idx = int((coord.latitude - terrain_difficulty.bounds.south) / 
                         (terrain_difficulty.bounds.north - terrain_difficulty.bounds.south) * 
                         terrain_difficulty.difficulty_scores.shape[0])
            lon_idx = int((coord.longitude - terrain_difficulty.bounds.west) / 
                         (terrain_difficulty.bounds.east - terrain_difficulty.bounds.west) * 
                         terrain_difficulty.difficulty_scores.shape[1])
            
            # Ensure indices are within bounds
            lat_idx = np.clip(lat_idx, 0, terrain_difficulty.difficulty_scores.shape[0] - 1)
            lon_idx = np.clip(lon_idx, 0, terrain_difficulty.difficulty_scores.shape[1] - 1)
            
            # Extract values
            difficulty_score = float(terrain_difficulty.difficulty_scores[lat_idx, lon_idx])
            terrain_type = int(terrain_difficulty.terrain_types[lat_idx, lon_idx])
            construction_factor = float(terrain_difficulty.construction_factors[lat_idx, lon_idx])
            accessibility_score = float(terrain_difficulty.accessibility_scores[lat_idx, lon_idx])
            
            seasonal_factor = None
            if terrain_difficulty.seasonal_factors is not None:
                seasonal_factor = float(terrain_difficulty.seasonal_factors[lat_idx, lon_idx])
            
            return {
                'coordinate': coord.to_dict(),
                'difficulty_score': difficulty_score,
                'terrain_type': terrain_type,
                'terrain_type_name': terrain_difficulty.get_terrain_type_name(terrain_type),
                'construction_factor': construction_factor,
                'accessibility_score': accessibility_score,
                'seasonal_factor': seasonal_factor,
                'data_freshness': terrain_difficulty.source_freshness.get_freshness_indicator() 
                                if terrain_difficulty.source_freshness else "Unknown"
            }
            
        except Exception as e:
            logger.warning(f"Failed to get terrain difficulty at {coord}: {e}")
            return {
                'coordinate': coord.to_dict(),
                'difficulty_score': 50.0,  # Default moderate difficulty
                'terrain_type': TerrainDifficulty.TERRAIN_MODERATE,
                'terrain_type_name': 'moderate',
                'construction_factor': 2.5,
                'accessibility_score': 50.0,
                'seasonal_factor': 1.0,
                'data_freshness': "Unknown"
            }
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get statistics about DEM processing operations."""
        return {
            'cache_size': len(self.cache),
            'uttarakhand_params': self.uttarakhand_params,
            'supported_algorithms': ['gdal', 'numpy', 'scipy'],
            'default_resolution': 30.0,
            'coordinate_system': 'EPSG:4326',
            'terrain_difficulty_features': {
                'slope_based_scoring': True,
                'uttarkashi_specific_thresholds': True,
                'terrain_type_classification': True,
                'real_time_data_integration': True,
                'construction_factor_calculation': True,
                'accessibility_scoring': True,
                'seasonal_adjustments': True
            },
            'terrain_types': {
                'flat': '0-5 degrees',
                'gentle': '5-15 degrees',
                'moderate': '15-25 degrees', 
                'steep': '25-35 degrees',
                'very_steep': '35-45 degrees',
                'extreme': '>45 degrees'
            }
        }
    
    def clear_cache(self) -> None:
        """Clear the DEM processing cache."""
        self.cache.clear()
        logger.info("DEM processing cache cleared")