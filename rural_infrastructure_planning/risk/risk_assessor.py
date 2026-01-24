"""
Risk Assessment System with API-enhanced risk analysis.

This module provides the Risk_Assessor class that implements comprehensive
risk analysis for rural infrastructure planning, integrating real-time data
from multiple API sources with local fallback data.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np
import math

from ..data.api_client import API_Client, BoundingBox, Coordinate, DataFreshnessInfo
from ..data.dem_processor import DEM_Processor, DEMData
from ..routing.route_generator import RouteAlignment, RouteSegment
from ..config.settings import config

logger = logging.getLogger(__name__)


@dataclass
class TerrainRisk:
    """Terrain-based risk assessment."""
    slope_risk: float  # 0-100 scale
    elevation_risk: float  # 0-100 scale
    stability_risk: float  # 0-100 scale (landslide, erosion)
    accessibility_risk: float  # 0-100 scale
    composite_score: float  # 0-100 scale
    risk_factors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'slope_risk': self.slope_risk,
            'elevation_risk': self.elevation_risk,
            'stability_risk': self.stability_risk,
            'accessibility_risk': self.accessibility_risk,
            'composite_score': self.composite_score,
            'risk_factors': self.risk_factors
        }


@dataclass
class FloodRisk:
    """Flood-based risk assessment."""
    historical_flood_risk: float  # 0-100 scale
    current_flood_risk: float  # 0-100 scale
    seasonal_flood_risk: float  # 0-100 scale
    drainage_risk: float  # 0-100 scale
    composite_score: float  # 0-100 scale
    flood_zones: List[str] = field(default_factory=list)
    mitigation_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'historical_flood_risk': self.historical_flood_risk,
            'current_flood_risk': self.current_flood_risk,
            'seasonal_flood_risk': self.seasonal_flood_risk,
            'drainage_risk': self.drainage_risk,
            'composite_score': self.composite_score,
            'flood_zones': self.flood_zones,
            'mitigation_required': self.mitigation_required
        }


@dataclass
class SeasonalRisk:
    """Seasonal risk assessment."""
    monsoon_risk: float  # 0-100 scale
    winter_risk: float  # 0-100 scale
    temperature_risk: float  # 0-100 scale
    weather_variability: float  # 0-100 scale
    optimal_construction_window: List[str] = field(default_factory=list)
    current_season_risk: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'monsoon_risk': self.monsoon_risk,
            'winter_risk': self.winter_risk,
            'temperature_risk': self.temperature_risk,
            'weather_variability': self.weather_variability,
            'optimal_construction_window': self.optimal_construction_window,
            'current_season_risk': self.current_season_risk
        }


@dataclass
class CompositeRisk:
    """Comprehensive risk assessment combining all factors."""
    terrain_risk: TerrainRisk
    flood_risk: FloodRisk
    seasonal_risk: SeasonalRisk
    overall_score: float  # 0-100 scale
    risk_category: str  # low, moderate, high, extreme
    critical_factors: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    freshness_info: Optional[DataFreshnessInfo] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            'terrain_risk': self.terrain_risk.to_dict(),
            'flood_risk': self.flood_risk.to_dict(),
            'seasonal_risk': self.seasonal_risk.to_dict(),
            'overall_score': self.overall_score,
            'risk_category': self.risk_category,
            'critical_factors': self.critical_factors,
            'mitigation_strategies': self.mitigation_strategies,
            'data_sources': self.data_sources
        }
        
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


class Risk_Assessor:
    """
    Risk Assessment System with API-enhanced risk analysis.
    
    This class provides comprehensive risk analysis for rural infrastructure
    planning, integrating real-time data from multiple API sources including
    elevation data, weather information, and flood zone data.
    
    Features:
    - Terrain risk assessment using real-time elevation data
    - Flood risk analysis with API flood zone data and local atlas fallback
    - Seasonal risk assessment using current weather APIs and historical data
    - Composite risk scoring with data source weighting
    - Real-time risk updates based on current conditions
    - Uttarakhand-specific risk parameters and thresholds
    """
    
    def __init__(self, 
                 api_client: Optional[API_Client] = None,
                 dem_processor: Optional[DEM_Processor] = None):
        """
        Initialize Risk Assessor.
        
        Args:
            api_client: Optional API client for data fetching
            dem_processor: Optional DEM processor for terrain analysis
        """
        self.api_client = api_client
        self.dem_processor = dem_processor or DEM_Processor(api_client)
        
        # Initialize regional analyzer for enhanced risk assessment
        from ..config.regional_config import UttarkashiAnalyzer
        self.regional_analyzer = UttarkashiAnalyzer(api_client)
        
        # Uttarakhand-specific risk parameters
        self.uttarakhand_risk_params = {
            'terrain_thresholds': {
                'slope_low': 15.0,      # degrees
                'slope_moderate': 25.0,
                'slope_high': 35.0,
                'slope_extreme': 45.0,
                'elevation_low': 1000.0,  # meters
                'elevation_moderate': 2500.0,
                'elevation_high': 3500.0,
                'elevation_extreme': 4500.0
            },
            'flood_zones': {
                'very_high': ['Haridwar', 'Dehradun', 'Udham Singh Nagar'],
                'high': ['Pauri Garhwal', 'Tehri Garhwal', 'Nainital'],
                'moderate': ['Almora', 'Bageshwar', 'Chamoli'],
                'low': ['Pithoragarh', 'Rudraprayag', 'Uttarkashi']
            },
            'seasonal_windows': {
                'optimal': ['October', 'November', 'March', 'April'],
                'acceptable': ['December', 'February', 'May'],
                'difficult': ['January', 'June', 'September'],
                'avoid': ['July', 'August']  # Peak monsoon
            },
            'risk_weights': {
                'terrain': 0.4,
                'flood': 0.3,
                'seasonal': 0.3
            }
        }
        
        logger.info("Initialized Risk_Assessor with Uttarakhand-specific parameters")
    
    async def assess_terrain_risk(self, 
                                coordinate: Coordinate,
                                radius_meters: float = 1000.0) -> TerrainRisk:
        """
        Assess terrain-based risks using real-time elevation data from APIs.
        
        Args:
            coordinate: Location to assess
            radius_meters: Assessment radius around the coordinate
            
        Returns:
            TerrainRisk assessment with detailed risk factors
            
        Raises:
            RuntimeError: If terrain risk assessment fails
        """
        try:
            logger.debug(f"Assessing terrain risk at {coordinate.latitude:.4f},{coordinate.longitude:.4f}")
            
            # Create bounding box around coordinate
            bounds = self._create_assessment_bounds(coordinate, radius_meters)
            
            # Load elevation data from APIs with local fallback
            dem_data = await self.dem_processor.load_elevation_data(bounds)
            
            # Calculate slope risk
            slope_risk = self._calculate_slope_risk(dem_data, coordinate)
            
            # Calculate elevation risk
            elevation_risk = self._calculate_elevation_risk(dem_data, coordinate)
            
            # Calculate stability risk (landslide, erosion potential)
            stability_risk = self._calculate_stability_risk(dem_data, coordinate)
            
            # Calculate accessibility risk
            accessibility_risk = self._calculate_accessibility_risk(dem_data, coordinate)
            
            # Identify specific risk factors
            risk_factors = self._identify_terrain_risk_factors(
                slope_risk, elevation_risk, stability_risk, accessibility_risk
            )
            
            # Calculate composite terrain risk score
            composite_score = self._calculate_terrain_composite_score(
                slope_risk, elevation_risk, stability_risk, accessibility_risk
            )
            
            terrain_risk = TerrainRisk(
                slope_risk=slope_risk,
                elevation_risk=elevation_risk,
                stability_risk=stability_risk,
                accessibility_risk=accessibility_risk,
                composite_score=composite_score,
                risk_factors=risk_factors
            )
            
            logger.debug(f"Terrain risk assessment completed: composite score {composite_score:.1f}/100")
            
            return terrain_risk
            
        except Exception as e:
            logger.error(f"Terrain risk assessment failed: {e}")
            raise RuntimeError(f"Terrain risk assessment failed: {e}") from e
    
    async def assess_flood_risk(self, 
                              coordinate: Coordinate,
                              route_segments: Optional[List[RouteSegment]] = None) -> FloodRisk:
        """
        Assess flood risks with API flood zone data and local atlas fallback.
        
        Args:
            coordinate: Location to assess
            route_segments: Optional route segments for detailed analysis
            
        Returns:
            FloodRisk assessment with mitigation recommendations
            
        Raises:
            RuntimeError: If flood risk assessment fails
        """
        try:
            logger.debug(f"Assessing flood risk at {coordinate.latitude:.4f},{coordinate.longitude:.4f}")
            
            # Get historical flood risk from local data and APIs
            historical_risk = await self._get_historical_flood_risk(coordinate)
            
            # Get current flood conditions from APIs
            current_risk = await self._get_current_flood_risk(coordinate)
            
            # Calculate seasonal flood risk
            seasonal_risk = self._calculate_seasonal_flood_risk(coordinate)
            
            # Assess drainage and topographic flood risk
            drainage_risk = await self._assess_drainage_risk(coordinate)
            
            # Identify flood zones
            flood_zones = self._identify_flood_zones(coordinate)
            
            # Determine if mitigation is required
            mitigation_required = max(historical_risk, current_risk, seasonal_risk) > 60.0
            
            # Calculate composite flood risk score
            composite_score = self._calculate_flood_composite_score(
                historical_risk, current_risk, seasonal_risk, drainage_risk
            )
            
            flood_risk = FloodRisk(
                historical_flood_risk=historical_risk,
                current_flood_risk=current_risk,
                seasonal_flood_risk=seasonal_risk,
                drainage_risk=drainage_risk,
                composite_score=composite_score,
                flood_zones=flood_zones,
                mitigation_required=mitigation_required
            )
            
            logger.debug(f"Flood risk assessment completed: composite score {composite_score:.1f}/100")
            
            return flood_risk
            
        except Exception as e:
            logger.error(f"Flood risk assessment failed: {e}")
            raise RuntimeError(f"Flood risk assessment failed: {e}") from e
    
    async def assess_seasonal_risk(self, 
                                 coordinate: Coordinate,
                                 construction_timeline: Optional[int] = None) -> SeasonalRisk:
        """
        Assess seasonal risks using current weather APIs and historical data.
        
        Args:
            coordinate: Location to assess
            construction_timeline: Optional construction duration in days
            
        Returns:
            SeasonalRisk assessment with optimal construction windows
            
        Raises:
            RuntimeError: If seasonal risk assessment fails
        """
        try:
            logger.debug(f"Assessing seasonal risk at {coordinate.latitude:.4f},{coordinate.longitude:.4f}")
            
            # Get current weather conditions from APIs
            current_weather = await self._get_current_weather_risk(coordinate)
            
            # Calculate monsoon risk
            monsoon_risk = await self._calculate_monsoon_risk(coordinate)
            
            # Calculate winter construction risk
            winter_risk = self._calculate_winter_risk(coordinate)
            
            # Calculate temperature-related risks
            temperature_risk = await self._calculate_temperature_risk(coordinate)
            
            # Assess weather variability
            weather_variability = await self._assess_weather_variability(coordinate)
            
            # Determine optimal construction windows
            optimal_windows = self._determine_construction_windows(
                coordinate, construction_timeline
            )
            
            # Get current season risk based on current date
            current_season_risk = self._get_current_season_risk()
            
            seasonal_risk = SeasonalRisk(
                monsoon_risk=monsoon_risk,
                winter_risk=winter_risk,
                temperature_risk=temperature_risk,
                weather_variability=weather_variability,
                optimal_construction_window=optimal_windows,
                current_season_risk=current_season_risk
            )
            
            logger.debug(f"Seasonal risk assessment completed: current season risk {current_season_risk:.1f}/100")
            
            return seasonal_risk
            
        except Exception as e:
            logger.error(f"Seasonal risk assessment failed: {e}")
            raise RuntimeError(f"Seasonal risk assessment failed: {e}") from e
    
    async def calculate_composite_risk(self, 
                                     coordinate: Coordinate,
                                     route_segments: Optional[List[RouteSegment]] = None,
                                     construction_timeline: Optional[int] = None) -> CompositeRisk:
        """
        Calculate comprehensive composite risk with data source weighting.
        
        Args:
            coordinate: Location to assess
            route_segments: Optional route segments for detailed analysis
            construction_timeline: Optional construction duration in days
            
        Returns:
            CompositeRisk assessment with mitigation strategies
            
        Raises:
            RuntimeError: If composite risk calculation fails
        """
        try:
            logger.info(f"Calculating composite risk at {coordinate.latitude:.4f},{coordinate.longitude:.4f}")
            
            # Perform individual risk assessments
            terrain_risk = await self.assess_terrain_risk(coordinate)
            flood_risk = await self.assess_flood_risk(coordinate, route_segments)
            seasonal_risk = await self.assess_seasonal_risk(coordinate, construction_timeline)
            
            # Calculate weighted composite score
            weights = self.uttarakhand_risk_params['risk_weights']
            overall_score = (
                terrain_risk.composite_score * weights['terrain'] +
                flood_risk.composite_score * weights['flood'] +
                seasonal_risk.current_season_risk * weights['seasonal']
            )
            
            # Determine risk category
            risk_category = self._categorize_risk_level(overall_score)
            
            # Identify critical factors
            critical_factors = self._identify_critical_factors(
                terrain_risk, flood_risk, seasonal_risk
            )
            
            # Generate mitigation strategies
            mitigation_strategies = self._generate_mitigation_strategies(
                terrain_risk, flood_risk, seasonal_risk, overall_score
            )
            
            # Collect data sources
            data_sources = ['terrain_analysis', 'flood_assessment', 'weather_apis']
            
            # Create freshness info (simplified - would aggregate from individual assessments)
            freshness_info = DataFreshnessInfo(
                source_type="api",
                source_name="composite_risk_assessment",
                data_age_hours=1.0,  # Assume recent data
                is_real_time=True,
                quality_score=0.85,
                last_updated=datetime.now()
            )
            
            composite_risk = CompositeRisk(
                terrain_risk=terrain_risk,
                flood_risk=flood_risk,
                seasonal_risk=seasonal_risk,
                overall_score=overall_score,
                risk_category=risk_category,
                critical_factors=critical_factors,
                mitigation_strategies=mitigation_strategies,
                data_sources=data_sources,
                freshness_info=freshness_info
            )
            
            logger.info(f"Composite risk assessment completed: {risk_category} risk "
                       f"(score {overall_score:.1f}/100)")
            
            return composite_risk
            
        except Exception as e:
            logger.error(f"Composite risk calculation failed: {e}")
            raise RuntimeError(f"Composite risk calculation failed: {e}") from e
    
    def _create_assessment_bounds(self, coordinate: Coordinate, 
                                radius_meters: float) -> BoundingBox:
        """Create bounding box for risk assessment around coordinate."""
        # Convert radius to approximate degrees (rough approximation)
        lat_offset = radius_meters / 111000.0  # ~111km per degree latitude
        lon_offset = radius_meters / (111000.0 * math.cos(math.radians(coordinate.latitude)))
        
        return BoundingBox(
            north=coordinate.latitude + lat_offset,
            south=coordinate.latitude - lat_offset,
            east=coordinate.longitude + lon_offset,
            west=coordinate.longitude - lon_offset
        )
    
    def _calculate_slope_risk(self, dem_data: DEMData, coordinate: Coordinate) -> float:
        """Calculate slope-based risk score."""
        try:
            if dem_data.slope_array is None:
                logger.warning("No slope data available, using moderate risk estimate")
                return 50.0
            
            # Get slope at coordinate (simplified - would use proper interpolation)
            center_row = dem_data.slope_array.shape[0] // 2
            center_col = dem_data.slope_array.shape[1] // 2
            slope_degrees = dem_data.slope_array[center_row, center_col]
            
            # Calculate risk based on Uttarakhand thresholds
            thresholds = self.uttarakhand_risk_params['terrain_thresholds']
            
            if slope_degrees <= thresholds['slope_low']:
                return 10.0  # Low risk
            elif slope_degrees <= thresholds['slope_moderate']:
                return 30.0  # Moderate risk
            elif slope_degrees <= thresholds['slope_high']:
                return 60.0  # High risk
            elif slope_degrees <= thresholds['slope_extreme']:
                return 85.0  # Very high risk
            else:
                return 95.0  # Extreme risk
                
        except Exception as e:
            logger.warning(f"Slope risk calculation failed: {e}")
            return 50.0  # Default moderate risk
    
    def _calculate_elevation_risk(self, dem_data: DEMData, coordinate: Coordinate) -> float:
        """Calculate elevation-based risk score."""
        try:
            elevation = coordinate.elevation or 0
            
            # If no elevation in coordinate, try to get from DEM data
            if elevation == 0 and dem_data.elevation_array is not None:
                center_row = dem_data.elevation_array.shape[0] // 2
                center_col = dem_data.elevation_array.shape[1] // 2
                elevation = dem_data.elevation_array[center_row, center_col]
            
            # Calculate risk based on elevation thresholds
            thresholds = self.uttarakhand_risk_params['terrain_thresholds']
            
            if elevation <= thresholds['elevation_low']:
                return 15.0  # Low risk
            elif elevation <= thresholds['elevation_moderate']:
                return 35.0  # Moderate risk
            elif elevation <= thresholds['elevation_high']:
                return 65.0  # High risk
            elif elevation <= thresholds['elevation_extreme']:
                return 85.0  # Very high risk
            else:
                return 95.0  # Extreme risk (above 4500m)
                
        except Exception as e:
            logger.warning(f"Elevation risk calculation failed: {e}")
            return 40.0  # Default moderate risk
    
    def _calculate_stability_risk(self, dem_data: DEMData, coordinate: Coordinate) -> float:
        """Calculate terrain stability risk (landslide, erosion potential)."""
        try:
            # Simplified stability assessment based on slope and elevation
            slope_risk = self._calculate_slope_risk(dem_data, coordinate)
            elevation_risk = self._calculate_elevation_risk(dem_data, coordinate)
            
            # Higher slopes and elevations increase instability
            base_stability_risk = (slope_risk * 0.7 + elevation_risk * 0.3)
            
            # Additional factors for Uttarakhand (geological instability)
            if coordinate.latitude >= 30.0 and coordinate.latitude <= 31.5:
                # Higher Himalayas - more unstable
                base_stability_risk *= 1.3
            elif coordinate.latitude >= 29.5 and coordinate.latitude <= 30.0:
                # Middle Himalayas - moderately unstable
                base_stability_risk *= 1.1
            
            return min(100.0, base_stability_risk)
            
        except Exception as e:
            logger.warning(f"Stability risk calculation failed: {e}")
            return 45.0  # Default moderate risk
    
    def _calculate_accessibility_risk(self, dem_data: DEMData, coordinate: Coordinate) -> float:
        """Calculate accessibility risk for construction and maintenance."""
        try:
            # Base accessibility risk on elevation and slope
            elevation_risk = self._calculate_elevation_risk(dem_data, coordinate)
            slope_risk = self._calculate_slope_risk(dem_data, coordinate)
            
            # Accessibility decreases with elevation and slope
            accessibility_risk = (elevation_risk * 0.6 + slope_risk * 0.4)
            
            # Remote areas in Uttarakhand have additional accessibility challenges
            if coordinate.longitude <= 78.5:  # Western Uttarakhand
                accessibility_risk *= 1.2
            
            return min(100.0, accessibility_risk)
            
        except Exception as e:
            logger.warning(f"Accessibility risk calculation failed: {e}")
            return 50.0  # Default moderate risk
    
    def _identify_terrain_risk_factors(self, slope_risk: float, elevation_risk: float,
                                     stability_risk: float, accessibility_risk: float) -> List[str]:
        """Identify specific terrain risk factors."""
        factors = []
        
        if slope_risk > 60:
            factors.append("steep_terrain")
        if slope_risk > 85:
            factors.append("extreme_slopes")
        if elevation_risk > 65:
            factors.append("high_altitude")
        if elevation_risk > 85:
            factors.append("alpine_conditions")
        if stability_risk > 70:
            factors.append("landslide_risk")
        if stability_risk > 85:
            factors.append("geological_instability")
        if accessibility_risk > 70:
            factors.append("remote_location")
        if accessibility_risk > 85:
            factors.append("extreme_isolation")
        
        return factors
    
    def _calculate_terrain_composite_score(self, slope_risk: float, elevation_risk: float,
                                         stability_risk: float, accessibility_risk: float) -> float:
        """Calculate composite terrain risk score."""
        # Weight different terrain factors
        weights = {
            'slope': 0.35,
            'elevation': 0.25,
            'stability': 0.25,
            'accessibility': 0.15
        }
        
        composite = (
            slope_risk * weights['slope'] +
            elevation_risk * weights['elevation'] +
            stability_risk * weights['stability'] +
            accessibility_risk * weights['accessibility']
        )
        
        return min(100.0, composite)
    
    async def _get_historical_flood_risk(self, coordinate: Coordinate) -> float:
        """Get historical flood risk from APIs and local data."""
        try:
            # Try to get flood data from API client
            if self.api_client:
                flood_data = await self.api_client.check_flood_risk(coordinate)
                if flood_data and 'historical_risk' in flood_data:
                    return min(100.0, flood_data['historical_risk'] * 100)
            
            # Fallback to district-based flood risk assessment
            district_risk = self._get_district_flood_risk(coordinate)
            return district_risk
            
        except Exception as e:
            logger.warning(f"Historical flood risk assessment failed: {e}")
            return 30.0  # Default moderate risk
    
    async def _get_current_flood_risk(self, coordinate: Coordinate) -> float:
        """Get current flood conditions from APIs."""
        try:
            # Try to get current weather and flood conditions
            if self.api_client:
                weather_data = await self.api_client.get_weather_data(coordinate)
                if weather_data and 'precipitation' in weather_data:
                    # High precipitation increases current flood risk
                    precip_mm = weather_data.get('precipitation', 0)
                    if precip_mm > 50:  # Heavy rain
                        return 80.0
                    elif precip_mm > 20:  # Moderate rain
                        return 50.0
                    elif precip_mm > 5:  # Light rain
                        return 25.0
                    else:
                        return 10.0  # No significant precipitation
            
            # Fallback to seasonal assessment
            return self._calculate_seasonal_flood_risk(coordinate)
            
        except Exception as e:
            logger.warning(f"Current flood risk assessment failed: {e}")
            return 25.0  # Default low-moderate risk
    
    def _calculate_seasonal_flood_risk(self, coordinate: Coordinate) -> float:
        """Calculate seasonal flood risk based on current date."""
        current_month = datetime.now().month
        
        # Monsoon season (June-September) has highest flood risk
        if current_month in [6, 7, 8, 9]:  # Monsoon
            return 85.0
        elif current_month in [5, 10]:  # Pre/post monsoon
            return 45.0
        elif current_month in [11, 12, 1, 2]:  # Winter
            return 15.0
        else:  # Spring
            return 25.0
    
    async def _assess_drainage_risk(self, coordinate: Coordinate) -> float:
        """Assess drainage and topographic flood risk."""
        try:
            # Create small bounds around coordinate for topographic analysis
            bounds = self._create_assessment_bounds(coordinate, 500.0)
            dem_data = await self.dem_processor.load_elevation_data(bounds)
            
            if dem_data.elevation_array is not None:
                # Calculate local slope to assess drainage
                if dem_data.slope_array is not None:
                    center_row = dem_data.slope_array.shape[0] // 2
                    center_col = dem_data.slope_array.shape[1] // 2
                    local_slope = dem_data.slope_array[center_row, center_col]
                    
                    # Flatter areas have higher drainage risk
                    if local_slope < 2.0:
                        return 70.0  # Poor drainage
                    elif local_slope < 5.0:
                        return 45.0  # Moderate drainage
                    elif local_slope < 10.0:
                        return 25.0  # Good drainage
                    else:
                        return 15.0  # Excellent drainage
            
            return 40.0  # Default moderate drainage risk
            
        except Exception as e:
            logger.warning(f"Drainage risk assessment failed: {e}")
            return 40.0
    
    def _get_district_flood_risk(self, coordinate: Coordinate) -> float:
        """Get flood risk based on district classification."""
        # Simplified district identification based on coordinate
        # In practice, would use proper geographic lookup
        
        flood_zones = self.uttarakhand_risk_params['flood_zones']
        
        # Rough coordinate-based district classification for Uttarakhand
        if coordinate.latitude < 29.5:  # Southern districts
            if coordinate.longitude < 78.5:
                return 75.0  # Haridwar/Dehradun area - very high risk
            else:
                return 60.0  # Udham Singh Nagar - high risk
        elif coordinate.latitude < 30.5:  # Central districts
            return 45.0  # Pauri/Tehri/Nainital - moderate to high risk
        else:  # Northern districts
            return 25.0  # Chamoli/Uttarkashi - lower risk
    
    def _identify_flood_zones(self, coordinate: Coordinate) -> List[str]:
        """Identify flood zones for the coordinate."""
        zones = []
        
        # Add zone based on district flood risk
        district_risk = self._get_district_flood_risk(coordinate)
        
        if district_risk > 70:
            zones.append("very_high_risk")
        elif district_risk > 50:
            zones.append("high_risk")
        elif district_risk > 30:
            zones.append("moderate_risk")
        else:
            zones.append("low_risk")
        
        # Add seasonal zone
        current_month = datetime.now().month
        if current_month in [6, 7, 8, 9]:
            zones.append("monsoon_zone")
        
        return zones
    
    def _calculate_flood_composite_score(self, historical_risk: float, current_risk: float,
                                       seasonal_risk: float, drainage_risk: float) -> float:
        """Calculate composite flood risk score."""
        # Weight different flood factors
        weights = {
            'historical': 0.3,
            'current': 0.4,
            'seasonal': 0.2,
            'drainage': 0.1
        }
        
        composite = (
            historical_risk * weights['historical'] +
            current_risk * weights['current'] +
            seasonal_risk * weights['seasonal'] +
            drainage_risk * weights['drainage']
        )
        
        return min(100.0, composite)
    
    async def _get_current_weather_risk(self, coordinate: Coordinate) -> float:
        """Get current weather-related risks."""
        try:
            if self.api_client:
                weather_data = await self.api_client.get_weather_data(coordinate)
                if weather_data:
                    risk_score = 0.0
                    
                    # Temperature risk
                    temp = weather_data.get('temperature', 15)
                    if temp < -5 or temp > 35:
                        risk_score += 30.0
                    elif temp < 0 or temp > 30:
                        risk_score += 15.0
                    
                    # Wind risk
                    wind_speed = weather_data.get('wind_speed', 0)
                    if wind_speed > 15:  # m/s
                        risk_score += 25.0
                    elif wind_speed > 10:
                        risk_score += 10.0
                    
                    # Precipitation risk
                    precip = weather_data.get('precipitation', 0)
                    if precip > 20:
                        risk_score += 40.0
                    elif precip > 5:
                        risk_score += 20.0
                    
                    return min(100.0, risk_score)
            
            return 20.0  # Default low risk
            
        except Exception as e:
            logger.warning(f"Current weather risk assessment failed: {e}")
            return 30.0
    
    async def _calculate_monsoon_risk(self, coordinate: Coordinate) -> float:
        """Calculate monsoon-related construction risks."""
        current_month = datetime.now().month
        
        # Base monsoon risk by month
        monsoon_risk_by_month = {
            1: 10, 2: 15, 3: 20, 4: 25, 5: 45,  # Pre-monsoon buildup
            6: 85, 7: 95, 8: 95, 9: 80,         # Peak monsoon
            10: 50, 11: 25, 12: 15              # Post-monsoon
        }
        
        base_risk = monsoon_risk_by_month.get(current_month, 30)
        
        # Adjust for elevation (higher elevations have different monsoon patterns)
        elevation = coordinate.elevation or 1000
        if elevation > 3000:
            base_risk *= 0.8  # Less intense but longer duration
        elif elevation > 2000:
            base_risk *= 0.9
        
        return min(100.0, base_risk)
    
    def _calculate_winter_risk(self, coordinate: Coordinate) -> float:
        """Calculate winter construction risks."""
        current_month = datetime.now().month
        
        # Base winter risk by month
        winter_risk_by_month = {
            1: 85, 2: 75, 3: 45, 4: 25, 5: 15, 6: 10,
            7: 10, 8: 10, 9: 15, 10: 25, 11: 45, 12: 70
        }
        
        base_risk = winter_risk_by_month.get(current_month, 30)
        
        # Adjust for elevation (higher elevations have more severe winters)
        elevation = coordinate.elevation or 1000
        if elevation > 3500:
            base_risk *= 1.5  # Severe winter conditions
        elif elevation > 2500:
            base_risk *= 1.3  # Harsh winter conditions
        elif elevation > 1500:
            base_risk *= 1.1  # Moderate winter conditions
        
        return min(100.0, base_risk)
    
    async def _calculate_temperature_risk(self, coordinate: Coordinate) -> float:
        """Calculate temperature-related construction risks."""
        try:
            if self.api_client:
                weather_data = await self.api_client.get_weather_data(coordinate)
                if weather_data and 'temperature' in weather_data:
                    temp = weather_data['temperature']
                    
                    # Optimal construction temperature range: 5-25°C
                    if temp < -10 or temp > 40:
                        return 90.0  # Extreme temperature risk
                    elif temp < 0 or temp > 35:
                        return 70.0  # High temperature risk
                    elif temp < 5 or temp > 30:
                        return 45.0  # Moderate temperature risk
                    elif temp < 10 or temp > 25:
                        return 25.0  # Low temperature risk
                    else:
                        return 10.0  # Optimal temperature range
            
            # Fallback to seasonal estimate
            current_month = datetime.now().month
            if current_month in [12, 1, 2]:  # Winter
                return 60.0
            elif current_month in [6, 7, 8]:  # Summer
                return 40.0
            else:
                return 25.0  # Spring/Autumn
                
        except Exception as e:
            logger.warning(f"Temperature risk assessment failed: {e}")
            return 35.0
    
    async def _assess_weather_variability(self, coordinate: Coordinate) -> float:
        """Assess weather variability and unpredictability."""
        try:
            # Uttarakhand has high weather variability, especially in mountains
            elevation = coordinate.elevation or 1000
            
            base_variability = 40.0  # Base variability for the region
            
            # Higher elevations have more variable weather
            if elevation > 3000:
                base_variability += 30.0
            elif elevation > 2000:
                base_variability += 20.0
            elif elevation > 1000:
                base_variability += 10.0
            
            # Monsoon season increases variability
            current_month = datetime.now().month
            if current_month in [6, 7, 8, 9]:
                base_variability += 25.0
            elif current_month in [5, 10]:
                base_variability += 15.0
            
            return min(100.0, base_variability)
            
        except Exception as e:
            logger.warning(f"Weather variability assessment failed: {e}")
            return 50.0
    
    def _determine_construction_windows(self, coordinate: Coordinate, 
                                     construction_timeline: Optional[int]) -> List[str]:
        """Determine optimal construction windows."""
        seasonal_windows = self.uttarakhand_risk_params['seasonal_windows']
        
        # Base optimal windows for Uttarakhand
        optimal_months = seasonal_windows['optimal'].copy()
        
        # Adjust for elevation
        elevation = coordinate.elevation or 1000
        if elevation > 3500:
            # High altitude - shorter construction season
            optimal_months = ['October', 'November', 'April']
        elif elevation > 2500:
            # Medium altitude - avoid extreme winter
            optimal_months = ['October', 'November', 'March', 'April']
        
        # If construction timeline is long, may need to include acceptable months
        if construction_timeline and construction_timeline > 120:  # > 4 months
            optimal_months.extend(seasonal_windows['acceptable'])
        
        return optimal_months
    
    def _get_current_season_risk(self) -> float:
        """Get risk score for current season."""
        current_month = datetime.now().month
        
        seasonal_windows = self.uttarakhand_risk_params['seasonal_windows']
        
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        
        current_month_name = month_names[current_month]
        
        if current_month_name in seasonal_windows['optimal']:
            return 15.0  # Low risk - optimal season
        elif current_month_name in seasonal_windows['acceptable']:
            return 35.0  # Moderate risk - acceptable season
        elif current_month_name in seasonal_windows['difficult']:
            return 65.0  # High risk - difficult season
        else:  # avoid season
            return 90.0  # Very high risk - should avoid
    
    def _categorize_risk_level(self, overall_score: float) -> str:
        """Categorize overall risk level."""
        if overall_score <= 25:
            return "low"
        elif overall_score <= 50:
            return "moderate"
        elif overall_score <= 75:
            return "high"
        else:
            return "extreme"
    
    def _identify_critical_factors(self, terrain_risk: TerrainRisk, 
                                 flood_risk: FloodRisk, 
                                 seasonal_risk: SeasonalRisk) -> List[str]:
        """Identify critical risk factors requiring attention."""
        critical_factors = []
        
        # Terrain critical factors
        if terrain_risk.composite_score > 70:
            critical_factors.append("high_terrain_risk")
        if terrain_risk.slope_risk > 80:
            critical_factors.append("extreme_slopes")
        if terrain_risk.stability_risk > 75:
            critical_factors.append("geological_instability")
        
        # Flood critical factors
        if flood_risk.composite_score > 60:
            critical_factors.append("flood_risk")
        if flood_risk.mitigation_required:
            critical_factors.append("flood_mitigation_required")
        
        # Seasonal critical factors
        if seasonal_risk.current_season_risk > 70:
            critical_factors.append("unfavorable_season")
        if seasonal_risk.monsoon_risk > 80:
            critical_factors.append("monsoon_risk")
        if seasonal_risk.winter_risk > 80:
            critical_factors.append("winter_conditions")
        
        return critical_factors
    
    def _generate_mitigation_strategies(self, terrain_risk: TerrainRisk,
                                      flood_risk: FloodRisk,
                                      seasonal_risk: SeasonalRisk,
                                      overall_score: float) -> List[str]:
        """Generate risk mitigation strategies."""
        strategies = []
        
        # Terrain mitigation strategies
        if terrain_risk.slope_risk > 60:
            strategies.append("implement_slope_stabilization")
            strategies.append("use_retaining_walls")
        
        if terrain_risk.stability_risk > 70:
            strategies.append("conduct_geological_survey")
            strategies.append("implement_landslide_protection")
        
        if terrain_risk.accessibility_risk > 70:
            strategies.append("plan_helicopter_access")
            strategies.append("establish_material_staging_areas")
        
        # Flood mitigation strategies
        if flood_risk.composite_score > 50:
            strategies.append("implement_drainage_systems")
            strategies.append("elevate_road_alignment")
        
        if flood_risk.mitigation_required:
            strategies.append("install_flood_barriers")
            strategies.append("create_emergency_evacuation_routes")
        
        # Seasonal mitigation strategies
        if seasonal_risk.current_season_risk > 60:
            strategies.append("delay_construction_to_optimal_season")
        
        if seasonal_risk.monsoon_risk > 70:
            strategies.append("implement_monsoon_protection")
            strategies.append("plan_seasonal_work_suspension")
        
        if seasonal_risk.winter_risk > 70:
            strategies.append("use_cold_weather_construction_methods")
            strategies.append("plan_winter_access_routes")
        
        # Overall high-risk strategies
        if overall_score > 75:
            strategies.append("conduct_detailed_risk_assessment")
            strategies.append("implement_comprehensive_monitoring")
            strategies.append("establish_emergency_response_plan")
        
        return strategies
    
    async def detect_flood_zone_intersections(self, 
                                            route_segments: List[RouteSegment],
                                            detailed_analysis: bool = True) -> Dict[str, Any]:
        """
        Detect geometric intersections between route segments and real-time flood zones.
        
        Args:
            route_segments: List of route segments to analyze
            detailed_analysis: Whether to perform detailed intersection analysis
            
        Returns:
            Dictionary containing intersection analysis results
            
        Raises:
            RuntimeError: If flood zone intersection detection fails
        """
        try:
            logger.info(f"Detecting flood zone intersections for {len(route_segments)} route segments")
            
            intersection_results = {
                'total_segments': len(route_segments),
                'intersecting_segments': [],
                'flood_zones_encountered': [],
                'risk_summary': {},
                'mitigation_recommendations': [],
                'data_sources': []
            }
            
            # Analyze each route segment
            for i, segment in enumerate(route_segments):
                segment_analysis = await self._analyze_segment_flood_intersection(
                    segment, i, detailed_analysis
                )
                
                if segment_analysis['intersects_flood_zone']:
                    intersection_results['intersecting_segments'].append(segment_analysis)
                    
                    # Collect unique flood zones
                    for zone in segment_analysis['flood_zones']:
                        if zone not in intersection_results['flood_zones_encountered']:
                            intersection_results['flood_zones_encountered'].append(zone)
            
            # Generate risk summary
            intersection_results['risk_summary'] = self._generate_intersection_risk_summary(
                intersection_results['intersecting_segments']
            )
            
            # Generate mitigation recommendations
            intersection_results['mitigation_recommendations'] = self._generate_flood_mitigation_recommendations(
                intersection_results['intersecting_segments'],
                intersection_results['flood_zones_encountered']
            )
            
            # Add data sources
            intersection_results['data_sources'] = ['api_flood_data', 'local_atlas_fallback', 'real_time_weather']
            
            logger.info(f"Flood zone intersection analysis completed: "
                       f"{len(intersection_results['intersecting_segments'])} segments intersect flood zones")
            
            return intersection_results
            
        except Exception as e:
            logger.error(f"Flood zone intersection detection failed: {e}")
            raise RuntimeError(f"Flood zone intersection detection failed: {e}") from e
    
    async def _analyze_segment_flood_intersection(self, 
                                                segment: RouteSegment, 
                                                segment_index: int,
                                                detailed_analysis: bool) -> Dict[str, Any]:
        """Analyze flood zone intersection for a single route segment."""
        try:
            segment_result = {
                'segment_index': segment_index,
                'segment_id': f"segment_{segment_index}",
                'intersects_flood_zone': False,
                'flood_zones': [],
                'intersection_length': 0.0,
                'risk_level': 'low',
                'mitigation_required': False,
                'seasonal_accessibility': {}
            }
            
            # Check flood risk at segment start and end points
            start_flood_risk = await self.assess_flood_risk(segment.start)
            end_flood_risk = await self.assess_flood_risk(segment.end)
            
            # Determine if segment intersects flood zones
            max_flood_risk = max(start_flood_risk.composite_score, end_flood_risk.composite_score)
            
            if max_flood_risk > 40.0:  # Moderate flood risk threshold
                segment_result['intersects_flood_zone'] = True
                
                # Collect flood zones from both endpoints
                segment_result['flood_zones'].extend(start_flood_risk.flood_zones)
                segment_result['flood_zones'].extend(end_flood_risk.flood_zones)
                segment_result['flood_zones'] = list(set(segment_result['flood_zones']))  # Remove duplicates
                
                # Estimate intersection length (simplified)
                if max_flood_risk > 70.0:
                    segment_result['intersection_length'] = segment.length  # Full segment in flood zone
                elif max_flood_risk > 55.0:
                    segment_result['intersection_length'] = segment.length * 0.7  # Most of segment
                else:
                    segment_result['intersection_length'] = segment.length * 0.3  # Partial intersection
                
                # Determine risk level
                if max_flood_risk > 75.0:
                    segment_result['risk_level'] = 'extreme'
                elif max_flood_risk > 60.0:
                    segment_result['risk_level'] = 'high'
                elif max_flood_risk > 40.0:
                    segment_result['risk_level'] = 'moderate'
                
                # Check if mitigation is required
                segment_result['mitigation_required'] = (
                    start_flood_risk.mitigation_required or 
                    end_flood_risk.mitigation_required or 
                    max_flood_risk > 60.0
                )
                
                # Calculate seasonal accessibility
                if detailed_analysis:
                    segment_result['seasonal_accessibility'] = await self._calculate_seasonal_accessibility(
                        segment, max_flood_risk
                    )
            
            return segment_result
            
        except Exception as e:
            logger.warning(f"Segment flood intersection analysis failed: {e}")
            return {
                'segment_index': segment_index,
                'segment_id': f"segment_{segment_index}",
                'intersects_flood_zone': False,
                'flood_zones': [],
                'intersection_length': 0.0,
                'risk_level': 'unknown',
                'mitigation_required': False,
                'seasonal_accessibility': {}
            }
    
    async def _calculate_seasonal_accessibility(self, 
                                              segment: RouteSegment, 
                                              flood_risk_score: float) -> Dict[str, str]:
        """Calculate seasonal accessibility windows for flood-prone segments."""
        accessibility = {}
        
        # Define accessibility levels based on flood risk and season
        months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        
        for month in months:
            month_num = months.index(month) + 1
            
            # Base seasonal flood risk
            if month_num in [6, 7, 8, 9]:  # Monsoon season
                seasonal_flood_multiplier = 2.0
            elif month_num in [5, 10]:  # Pre/post monsoon
                seasonal_flood_multiplier = 1.3
            else:  # Dry season
                seasonal_flood_multiplier = 0.5
            
            adjusted_risk = flood_risk_score * seasonal_flood_multiplier
            
            # Determine accessibility level
            if adjusted_risk > 80:
                accessibility[month] = 'inaccessible'
            elif adjusted_risk > 60:
                accessibility[month] = 'high_risk'
            elif adjusted_risk > 40:
                accessibility[month] = 'moderate_risk'
            elif adjusted_risk > 20:
                accessibility[month] = 'low_risk'
            else:
                accessibility[month] = 'accessible'
        
        return accessibility
    
    def _generate_intersection_risk_summary(self, intersecting_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate risk summary for flood zone intersections."""
        if not intersecting_segments:
            return {
                'total_intersecting_segments': 0,
                'total_intersection_length': 0.0,
                'risk_distribution': {'low': 0, 'moderate': 0, 'high': 0, 'extreme': 0},
                'mitigation_required_segments': 0,
                'overall_flood_risk': 'low'
            }
        
        total_length = sum(seg['intersection_length'] for seg in intersecting_segments)
        risk_counts = {'low': 0, 'moderate': 0, 'high': 0, 'extreme': 0}
        mitigation_count = 0
        
        for segment in intersecting_segments:
            risk_level = segment.get('risk_level', 'low')
            if risk_level in risk_counts:
                risk_counts[risk_level] += 1
            
            if segment.get('mitigation_required', False):
                mitigation_count += 1
        
        # Determine overall flood risk
        if risk_counts['extreme'] > 0:
            overall_risk = 'extreme'
        elif risk_counts['high'] > 0:
            overall_risk = 'high'
        elif risk_counts['moderate'] > 0:
            overall_risk = 'moderate'
        else:
            overall_risk = 'low'
        
        return {
            'total_intersecting_segments': len(intersecting_segments),
            'total_intersection_length': total_length,
            'risk_distribution': risk_counts,
            'mitigation_required_segments': mitigation_count,
            'overall_flood_risk': overall_risk
        }
    
    def _generate_flood_mitigation_recommendations(self, 
                                                 intersecting_segments: List[Dict[str, Any]],
                                                 flood_zones: List[str]) -> List[str]:
        """Generate flood mitigation recommendations based on intersection analysis."""
        recommendations = []
        
        if not intersecting_segments:
            return recommendations
        
        # General recommendations based on flood zone types
        if 'very_high_risk' in flood_zones:
            recommendations.extend([
                "implement_comprehensive_flood_protection_system",
                "elevate_road_alignment_significantly",
                "install_advanced_drainage_infrastructure",
                "establish_flood_monitoring_stations"
            ])
        
        if 'high_risk' in flood_zones or 'monsoon_zone' in flood_zones:
            recommendations.extend([
                "install_culverts_and_bridges",
                "implement_roadside_drainage_channels",
                "use_flood_resistant_construction_materials",
                "plan_seasonal_access_restrictions"
            ])
        
        # Recommendations based on risk levels
        extreme_risk_segments = [seg for seg in intersecting_segments if seg['risk_level'] == 'extreme']
        high_risk_segments = [seg for seg in intersecting_segments if seg['risk_level'] == 'high']
        
        if extreme_risk_segments:
            recommendations.extend([
                "consider_alternative_route_alignment",
                "implement_emergency_evacuation_procedures",
                "establish_real_time_flood_warning_system",
                "conduct_detailed_hydrological_study"
            ])
        
        if high_risk_segments:
            recommendations.extend([
                "install_flood_barriers_and_retaining_walls",
                "implement_permeable_pavement_systems",
                "create_emergency_vehicle_turnarounds",
                "establish_maintenance_access_during_floods"
            ])
        
        # Recommendations based on mitigation requirements
        mitigation_required_count = sum(1 for seg in intersecting_segments if seg['mitigation_required'])
        if mitigation_required_count > len(intersecting_segments) * 0.5:  # More than 50% require mitigation
            recommendations.extend([
                "develop_comprehensive_flood_management_plan",
                "coordinate_with_local_disaster_management_authorities",
                "implement_community_based_flood_preparedness",
                "establish_flood_insurance_requirements"
            ])
        
        # Remove duplicates while preserving order
        unique_recommendations = []
        for rec in recommendations:
            if rec not in unique_recommendations:
                unique_recommendations.append(rec)
        
        return unique_recommendations
    
    async def suggest_flood_mitigation_strategies(self, 
                                                route_alignment: RouteAlignment,
                                                intersection_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest specific flood mitigation strategies based on current conditions.
        
        Args:
            route_alignment: Complete route alignment
            intersection_results: Results from flood zone intersection detection
            
        Returns:
            Dictionary containing detailed mitigation strategies
        """
        try:
            logger.info(f"Generating flood mitigation strategies for route {route_alignment.id}")
            
            mitigation_plan = {
                'route_id': route_alignment.id,
                'engineering_solutions': [],
                'operational_strategies': [],
                'monitoring_requirements': [],
                'cost_estimates': {},
                'implementation_timeline': {},
                'priority_segments': []
            }
            
            # Identify priority segments requiring immediate attention
            priority_segments = [
                seg for seg in intersection_results.get('intersecting_segments', [])
                if seg['risk_level'] in ['extreme', 'high'] or seg['mitigation_required']
            ]
            mitigation_plan['priority_segments'] = priority_segments
            
            # Engineering solutions based on risk levels
            if intersection_results.get('risk_summary', {}).get('overall_flood_risk') == 'extreme':
                mitigation_plan['engineering_solutions'].extend([
                    {
                        'solution': 'elevated_roadway_design',
                        'description': 'Elevate road alignment 2-3 meters above flood level',
                        'cost_estimate_usd': 500000,
                        'implementation_time_months': 8
                    },
                    {
                        'solution': 'comprehensive_drainage_system',
                        'description': 'Install large-capacity culverts and storm drains',
                        'cost_estimate_usd': 300000,
                        'implementation_time_months': 6
                    }
                ])
            
            elif intersection_results.get('risk_summary', {}).get('overall_flood_risk') == 'high':
                mitigation_plan['engineering_solutions'].extend([
                    {
                        'solution': 'improved_drainage_infrastructure',
                        'description': 'Install roadside drainage channels and culverts',
                        'cost_estimate_usd': 150000,
                        'implementation_time_months': 4
                    },
                    {
                        'solution': 'flood_resistant_materials',
                        'description': 'Use concrete and stone construction in flood-prone areas',
                        'cost_estimate_usd': 100000,
                        'implementation_time_months': 2
                    }
                ])
            
            # Operational strategies
            mitigation_plan['operational_strategies'] = [
                {
                    'strategy': 'seasonal_access_management',
                    'description': 'Restrict heavy vehicle access during monsoon season',
                    'cost_estimate_usd': 5000,
                    'implementation_time_months': 1
                },
                {
                    'strategy': 'emergency_response_protocol',
                    'description': 'Establish flood emergency response and evacuation procedures',
                    'cost_estimate_usd': 10000,
                    'implementation_time_months': 2
                }
            ]
            
            # Monitoring requirements
            mitigation_plan['monitoring_requirements'] = [
                {
                    'requirement': 'real_time_weather_monitoring',
                    'description': 'Install weather stations and flood level sensors',
                    'cost_estimate_usd': 25000,
                    'implementation_time_months': 3
                },
                {
                    'requirement': 'regular_drainage_maintenance',
                    'description': 'Monthly inspection and cleaning of drainage systems',
                    'cost_estimate_usd': 2000,  # Annual cost
                    'implementation_time_months': 1
                }
            ]
            
            # Calculate total cost estimates
            total_engineering_cost = sum(
                sol['cost_estimate_usd'] for sol in mitigation_plan['engineering_solutions']
            )
            total_operational_cost = sum(
                strat['cost_estimate_usd'] for strat in mitigation_plan['operational_strategies']
            )
            total_monitoring_cost = sum(
                req['cost_estimate_usd'] for req in mitigation_plan['monitoring_requirements']
            )
            
            mitigation_plan['cost_estimates'] = {
                'engineering_solutions': total_engineering_cost,
                'operational_strategies': total_operational_cost,
                'monitoring_requirements': total_monitoring_cost,
                'total_estimated_cost': total_engineering_cost + total_operational_cost + total_monitoring_cost
            }
            
            # Implementation timeline
            max_engineering_time = max(
                (sol['implementation_time_months'] for sol in mitigation_plan['engineering_solutions']),
                default=0
            )
            mitigation_plan['implementation_timeline'] = {
                'phase_1_preparation': '1-2 months',
                'phase_2_engineering': f'{max_engineering_time} months',
                'phase_3_operational': '1-3 months',
                'total_timeline': f'{max_engineering_time + 4} months'
            }
            
            logger.info(f"Flood mitigation plan generated: total cost ${mitigation_plan['cost_estimates']['total_estimated_cost']:,.0f}")
            
            return mitigation_plan
            
        except Exception as e:
            logger.error(f"Flood mitigation strategy generation failed: {e}")
            raise RuntimeError(f"Flood mitigation strategy generation failed: {e}") from e
    
    async def calculate_seasonal_accessibility_windows(self, 
                                                     route_alignment: RouteAlignment) -> Dict[str, Any]:
        """
        Calculate seasonal accessibility windows using weather forecasts.
        
        Args:
            route_alignment: Route alignment to analyze
            
        Returns:
            Dictionary containing seasonal accessibility analysis
        """
        try:
            logger.info(f"Calculating seasonal accessibility for route {route_alignment.id}")
            
            accessibility_analysis = {
                'route_id': route_alignment.id,
                'monthly_accessibility': {},
                'optimal_construction_periods': [],
                'restricted_periods': [],
                'weather_dependencies': {},
                'recommendations': []
            }
            
            # Analyze each month
            months = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            
            for month in months:
                month_analysis = await self._analyze_monthly_accessibility(route_alignment, month)
                accessibility_analysis['monthly_accessibility'][month] = month_analysis
                
                # Categorize periods
                if month_analysis['accessibility_score'] >= 80:
                    accessibility_analysis['optimal_construction_periods'].append(month)
                elif month_analysis['accessibility_score'] <= 30:
                    accessibility_analysis['restricted_periods'].append(month)
            
            # Generate weather dependencies
            accessibility_analysis['weather_dependencies'] = {
                'monsoon_impact': 'High - construction severely limited June-September',
                'winter_impact': 'Moderate - cold weather affects high-altitude segments December-February',
                'temperature_range': 'Optimal construction temperature: 5-25°C',
                'precipitation_threshold': 'Construction stops when daily rainfall > 25mm'
            }
            
            # Generate recommendations
            accessibility_analysis['recommendations'] = [
                f"Plan major construction during: {', '.join(accessibility_analysis['optimal_construction_periods'])}",
                f"Avoid construction during: {', '.join(accessibility_analysis['restricted_periods'])}",
                "Implement weather monitoring system for real-time construction decisions",
                "Prepare seasonal material stockpiling strategy",
                "Establish emergency access protocols for restricted periods"
            ]
            
            logger.info(f"Seasonal accessibility analysis completed: "
                       f"{len(accessibility_analysis['optimal_construction_periods'])} optimal months identified")
            
            return accessibility_analysis
            
        except Exception as e:
            logger.error(f"Seasonal accessibility calculation failed: {e}")
            raise RuntimeError(f"Seasonal accessibility calculation failed: {e}") from e
    
    async def _analyze_monthly_accessibility(self, 
                                           route_alignment: RouteAlignment, 
                                           month: str) -> Dict[str, Any]:
        """Analyze accessibility for a specific month."""
        try:
            # Get month number
            months = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            month_num = months.index(month) + 1
            
            # Calculate base accessibility factors
            weather_score = self._get_monthly_weather_score(month_num)
            terrain_score = self._get_terrain_accessibility_score(route_alignment)
            flood_score = self._get_monthly_flood_score(month_num)
            
            # Calculate composite accessibility score
            accessibility_score = (weather_score * 0.4 + terrain_score * 0.3 + flood_score * 0.3)
            
            # Determine accessibility level
            if accessibility_score >= 80:
                level = 'excellent'
            elif accessibility_score >= 60:
                level = 'good'
            elif accessibility_score >= 40:
                level = 'moderate'
            elif accessibility_score >= 20:
                level = 'poor'
            else:
                level = 'very_poor'
            
            return {
                'month': month,
                'accessibility_score': accessibility_score,
                'accessibility_level': level,
                'weather_score': weather_score,
                'terrain_score': terrain_score,
                'flood_score': flood_score,
                'limiting_factors': self._identify_monthly_limiting_factors(month_num, weather_score, flood_score)
            }
            
        except Exception as e:
            logger.warning(f"Monthly accessibility analysis failed for {month}: {e}")
            return {
                'month': month,
                'accessibility_score': 50.0,
                'accessibility_level': 'moderate',
                'weather_score': 50.0,
                'terrain_score': 50.0,
                'flood_score': 50.0,
                'limiting_factors': ['data_unavailable']
            }
    
    def _get_monthly_weather_score(self, month_num: int) -> float:
        """Get weather accessibility score for a specific month."""
        # Uttarakhand weather patterns
        weather_scores = {
            1: 40,   # January - cold, possible snow
            2: 50,   # February - cold but improving
            3: 75,   # March - good weather
            4: 85,   # April - excellent weather
            5: 70,   # May - getting hot, pre-monsoon
            6: 30,   # June - monsoon starts
            7: 15,   # July - peak monsoon
            8: 15,   # August - peak monsoon
            9: 25,   # September - monsoon continues
            10: 80,  # October - post-monsoon, excellent
            11: 85,  # November - excellent weather
            12: 60   # December - getting cold
        }
        
        return weather_scores.get(month_num, 50.0)
    
    def _get_terrain_accessibility_score(self, route_alignment: RouteAlignment) -> float:
        """Get terrain-based accessibility score."""
        # Base score on route difficulty
        difficulty = route_alignment.construction_difficulty
        
        # Convert difficulty (0-100, higher is more difficult) to accessibility (0-100, higher is better)
        accessibility_score = 100 - difficulty
        
        return max(0.0, min(100.0, accessibility_score))
    
    def _get_monthly_flood_score(self, month_num: int) -> float:
        """Get flood risk accessibility score for a specific month."""
        # Inverse of flood risk (higher flood risk = lower accessibility)
        flood_risk_scores = {
            1: 85,   # January - low flood risk
            2: 85,   # February - low flood risk
            3: 80,   # March - low flood risk
            4: 75,   # April - low flood risk
            5: 55,   # May - pre-monsoon, moderate risk
            6: 15,   # June - high flood risk
            7: 5,    # July - very high flood risk
            8: 5,    # August - very high flood risk
            9: 20,   # September - high flood risk
            10: 50,  # October - moderate risk
            11: 75,  # November - low risk
            12: 80   # December - low risk
        }
        
        return flood_risk_scores.get(month_num, 50.0)
    
    def _identify_monthly_limiting_factors(self, month_num: int, 
                                         weather_score: float, 
                                         flood_score: float) -> List[str]:
        """Identify limiting factors for monthly accessibility."""
        factors = []
        
        if month_num in [6, 7, 8, 9] and flood_score < 30:
            factors.append('monsoon_flooding')
        
        if month_num in [12, 1, 2] and weather_score < 50:
            factors.append('winter_conditions')
        
        if month_num in [5, 6] and weather_score < 70:
            factors.append('pre_monsoon_heat')
        
        if weather_score < 40:
            factors.append('adverse_weather')
        
        if flood_score < 40:
            factors.append('flood_risk')
        
        return factors if factors else ['no_major_limitations']
    
    async def integrate_regional_risk_assessment(self, coordinate: Coordinate, 
                                               route_segments: Optional[List[RouteSegment]] = None) -> Dict[str, Any]:
        """
        Integrate regional risk assessment using UttarkashiAnalyzer for enhanced risk analysis.
        
        Args:
            coordinate: Location to assess
            route_segments: Optional route segments for detailed analysis
            
        Returns:
            Dictionary with integrated regional risk assessment
        """
        try:
            logger.info(f"Performing integrated regional risk assessment at {coordinate.latitude:.4f},{coordinate.longitude:.4f}")
            
            # Get standard risk assessments
            terrain_risk = await self.assess_terrain_risk(coordinate)
            flood_risk = await self.assess_flood_risk(coordinate, route_segments)
            seasonal_risk = await self.assess_seasonal_risk(coordinate)
            
            # Get regional geological hazard assessment
            regional_hazards = self.regional_analyzer.assess_geological_hazards(coordinate, 0.0)  # Will calculate slope internally
            
            # Get regional seasonal analysis
            regional_seasonal = self.regional_analyzer.get_optimal_construction_season(coordinate)
            
            # Get real-time weather factors
            weather_factors = await self.regional_analyzer.get_real_time_weather_factors(coordinate)
            
            # Calculate regional cost implications
            base_cost = 500000  # Base construction cost estimate
            regional_cost_analysis = self.regional_analyzer.calculate_regional_cost_estimate(
                base_cost, coordinate
            )
            
            # Integrate regional factors with standard risk assessment
            integrated_terrain_risk = self._integrate_regional_terrain_risk(terrain_risk, regional_hazards)
            integrated_seasonal_risk = self._integrate_regional_seasonal_risk(seasonal_risk, regional_seasonal, weather_factors)
            
            # Calculate enhanced composite risk
            enhanced_composite_risk = self._calculate_enhanced_composite_risk(
                integrated_terrain_risk, flood_risk, integrated_seasonal_risk, regional_hazards
            )
            
            # Generate comprehensive mitigation strategy
            comprehensive_mitigation = self._generate_comprehensive_mitigation_strategy(
                integrated_terrain_risk, flood_risk, integrated_seasonal_risk, 
                regional_hazards, weather_factors
            )
            
            return {
                'coordinate': coordinate.to_dict(),
                'assessment_timestamp': datetime.now().isoformat(),
                'standard_risk_assessment': {
                    'terrain_risk': terrain_risk.to_dict(),
                    'flood_risk': flood_risk.to_dict(),
                    'seasonal_risk': seasonal_risk.to_dict()
                },
                'regional_analysis': {
                    'geological_hazards': regional_hazards,
                    'seasonal_analysis': regional_seasonal,
                    'weather_factors': weather_factors,
                    'cost_analysis': regional_cost_analysis
                },
                'integrated_risk_assessment': {
                    'enhanced_terrain_risk': integrated_terrain_risk,
                    'enhanced_seasonal_risk': integrated_seasonal_risk,
                    'composite_risk_score': enhanced_composite_risk,
                    'risk_category': self._categorize_risk_level(enhanced_composite_risk)
                },
                'comprehensive_mitigation_strategy': comprehensive_mitigation,
                'data_sources': {
                    'weather_data_source': weather_factors.get('data_source', 'default'),
                    'regional_analysis_source': 'uttarkashi_analyzer',
                    'standard_assessment_source': 'risk_assessor'
                }
            }
            
        except Exception as e:
            logger.error(f"Integrated regional risk assessment failed: {e}")
            return {
                'coordinate': coordinate.to_dict(),
                'assessment_timestamp': datetime.now().isoformat(),
                'error': str(e),
                'fallback_risk_score': 50.0,
                'fallback_risk_category': 'moderate'
            }
    
    def _integrate_regional_terrain_risk(self, terrain_risk: TerrainRisk, 
                                       regional_hazards: Dict[str, Any]) -> Dict[str, Any]:
        """Integrate regional geological hazards with standard terrain risk."""
        enhanced_risk = terrain_risk.to_dict()
        
        # Add regional hazard factors
        regional_risk_score = regional_hazards.get('overall_risk_score', 0.3) * 100
        
        # Enhance composite score with regional factors
        original_score = enhanced_risk['composite_score']
        regional_weight = 0.3  # 30% weight for regional factors
        
        enhanced_score = (original_score * (1 - regional_weight)) + (regional_risk_score * regional_weight)
        enhanced_risk['composite_score'] = min(100.0, enhanced_score)
        
        # Add regional risk factors
        regional_risk_factors = []
        for hazard_name, hazard_info in regional_hazards.get('hazards', {}).items():
            if hazard_info.get('risk_level', 0) > 0.4:
                regional_risk_factors.append(f"regional_{hazard_name}_risk")
        
        enhanced_risk['risk_factors'].extend(regional_risk_factors)
        enhanced_risk['regional_hazards'] = regional_hazards.get('hazards', {})
        enhanced_risk['regional_risk_category'] = regional_hazards.get('risk_category', 'low')
        
        return enhanced_risk
    
    def _integrate_regional_seasonal_risk(self, seasonal_risk: SeasonalRisk,
                                        regional_seasonal: Dict[str, Any],
                                        weather_factors: Dict[str, Any]) -> Dict[str, Any]:
        """Integrate regional seasonal analysis with standard seasonal risk."""
        enhanced_risk = seasonal_risk.to_dict()
        
        # Add real-time weather risk
        weather_risk_score = weather_factors.get('weather_risk_score', 0.3) * 100
        
        # Enhance current season risk with real-time data
        current_season_info = regional_seasonal.get('current_season_info', {})
        productivity_factor = current_season_info.get('productivity_factor', 1.0)
        weather_risk = current_season_info.get('weather_risk', 0.0)
        
        # Calculate enhanced current season risk
        base_current_risk = enhanced_risk['current_season_risk']
        weather_adjustment = weather_risk_score * 0.4  # 40% weight for real-time weather
        productivity_adjustment = (1.0 - productivity_factor) * 50  # Productivity impact
        
        enhanced_current_risk = base_current_risk + weather_adjustment + productivity_adjustment
        enhanced_risk['current_season_risk'] = min(100.0, enhanced_current_risk)
        
        # Add regional seasonal information
        enhanced_risk['regional_seasonal_analysis'] = {
            'current_season': regional_seasonal.get('current_season', {}).value if hasattr(regional_seasonal.get('current_season', {}), 'value') else str(regional_seasonal.get('current_season', 'unknown')),
            'elevation_adjusted': regional_seasonal.get('elevation_adjusted', False),
            'optimal_months': regional_seasonal.get('optimal_months', []),
            'next_optimal_month': regional_seasonal.get('next_optimal_month'),
            'recommendations': regional_seasonal.get('recommendations', [])
        }
        
        enhanced_risk['real_time_weather'] = {
            'temperature_c': weather_factors.get('temperature_c', 15),
            'precipitation_mm': weather_factors.get('precipitation_mm', 0),
            'weather_risk_score': weather_risk_score,
            'data_source': weather_factors.get('data_source', 'default')
        }
        
        return enhanced_risk
    
    def _calculate_enhanced_composite_risk(self, enhanced_terrain_risk: Dict[str, Any],
                                         flood_risk: FloodRisk,
                                         enhanced_seasonal_risk: Dict[str, Any],
                                         regional_hazards: Dict[str, Any]) -> float:
        """Calculate enhanced composite risk score incorporating regional factors."""
        # Base composite calculation
        terrain_score = enhanced_terrain_risk['composite_score']
        flood_score = flood_risk.composite_score
        seasonal_score = enhanced_seasonal_risk['current_season_risk']
        
        # Regional hazard contribution
        regional_score = regional_hazards.get('overall_risk_score', 0.3) * 100
        
        # Weighted combination with regional factors
        weights = {
            'terrain': 0.35,
            'flood': 0.25,
            'seasonal': 0.25,
            'regional': 0.15
        }
        
        composite_score = (
            terrain_score * weights['terrain'] +
            flood_score * weights['flood'] +
            seasonal_score * weights['seasonal'] +
            regional_score * weights['regional']
        )
        
        return min(100.0, max(0.0, composite_score))
    
    def _generate_comprehensive_mitigation_strategy(self, enhanced_terrain_risk: Dict[str, Any],
                                                  flood_risk: FloodRisk,
                                                  enhanced_seasonal_risk: Dict[str, Any],
                                                  regional_hazards: Dict[str, Any],
                                                  weather_factors: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive mitigation strategy incorporating regional factors."""
        strategy = {
            'priority_level': 'moderate',
            'immediate_actions': [],
            'regional_specific_actions': [],
            'seasonal_recommendations': [],
            'monitoring_requirements': [],
            'equipment_recommendations': [],
            'timeline_adjustments': [],
            'cost_implications': {}
        }
        
        # Determine priority level
        composite_risk = self._calculate_enhanced_composite_risk(
            enhanced_terrain_risk, flood_risk, enhanced_seasonal_risk, regional_hazards
        )
        strategy['priority_level'] = self._categorize_risk_level(composite_risk)
        
        # Regional hazard-specific actions
        hazards = regional_hazards.get('hazards', {})
        regional_recommendations = regional_hazards.get('mitigation_recommendations', [])
        
        if 'landslide' in hazards and hazards['landslide'].get('risk_level', 0) > 0.5:
            strategy['regional_specific_actions'].extend([
                'Implement comprehensive slope stabilization',
                'Install landslide monitoring systems',
                'Design proper drainage to prevent slope saturation'
            ])
        
        if 'seismic' in hazards:
            strategy['regional_specific_actions'].extend([
                'Follow IS 1893 Zone V seismic design standards',
                'Use earthquake-resistant construction techniques',
                'Implement base isolation for critical structures'
            ])
        
        if 'glacial_outburst' in hazards and hazards['glacial_outburst'].get('risk_level', 0) > 0.3:
            strategy['regional_specific_actions'].extend([
                'Install GLOF early warning systems',
                'Monitor upstream glacial lakes',
                'Design for potential flood scenarios'
            ])
        
        # Add all regional recommendations
        strategy['regional_specific_actions'].extend(regional_recommendations)
        
        # Seasonal recommendations from regional analysis
        seasonal_recommendations = enhanced_seasonal_risk.get('regional_seasonal_analysis', {}).get('recommendations', [])
        strategy['seasonal_recommendations'].extend(seasonal_recommendations)
        
        # Weather-based monitoring
        weather_risk = weather_factors.get('weather_risk_score', 0.3)
        if weather_risk > 0.5:
            strategy['monitoring_requirements'].extend([
                'Continuous weather monitoring',
                'Real-time precipitation alerts',
                'Temperature and wind speed tracking'
            ])
        
        # Cost implications
        if composite_risk > 60:
            strategy['cost_implications'] = {
                'risk_premium_percentage': min(40, (composite_risk - 40) * 1.0),
                'regional_cost_multiplier': regional_hazards.get('overall_risk_score', 0.3) + 1.0,
                'contingency_fund_percentage': min(25, composite_risk * 0.4),
                'specialized_equipment_cost': 'High - regional hazard mitigation equipment required'
            }
        
        return strategy