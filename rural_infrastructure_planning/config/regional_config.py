"""
Regional configuration for Uttarkashi-specific analysis parameters.

This module provides region-specific parameters, thresholds, and analysis logic
tailored for the Uttarkashi district in Uttarakhand, India.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from datetime import datetime, timedelta

from ..data.api_client import Coordinate


class TerrainType(Enum):
    """Terrain classification for Uttarkashi region."""
    VALLEY_FLOOR = "valley_floor"
    GENTLE_SLOPE = "gentle_slope"
    MODERATE_SLOPE = "moderate_slope"
    STEEP_SLOPE = "steep_slope"
    CLIFF_FACE = "cliff_face"
    GLACIAL_MORAINE = "glacial_moraine"
    RIVER_TERRACE = "river_terrace"


class ConstructionSeason(Enum):
    """Construction seasons for high-altitude regions."""
    OPTIMAL = "optimal"      # Oct-Mar: Dry, stable weather
    FEASIBLE = "feasible"    # Apr-May, Sep: Moderate conditions
    CHALLENGING = "challenging"  # Jun-Aug: Monsoon season
    IMPOSSIBLE = "impossible"    # Dec-Feb: Extreme cold at high altitude


@dataclass
class UttarkashiParameters:
    """Uttarkashi-specific analysis parameters."""
    
    # Elevation-based parameters
    elevation_zones: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "valley": (500, 1500),      # River valleys
        "mid_hills": (1500, 2500),  # Mid-altitude hills
        "high_hills": (2500, 3500), # High hills
        "alpine": (3500, 5000),     # Alpine zone
        "glacial": (5000, 7000)     # Glacial zone
    })
    
    # Slope thresholds (degrees) - more restrictive for high altitude
    slope_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "flat": 5.0,           # 0-5°: Flat terrain
        "gentle": 15.0,        # 5-15°: Gentle slopes
        "moderate": 25.0,      # 15-25°: Moderate slopes
        "steep": 35.0,         # 25-35°: Steep slopes
        "very_steep": 45.0,    # 35-45°: Very steep
        "cliff": 90.0          # 45-90°: Cliff faces
    })
    
    # Construction difficulty multipliers by elevation
    elevation_difficulty_multipliers: Dict[str, float] = field(default_factory=lambda: {
        "valley": 1.0,         # Base difficulty
        "mid_hills": 1.3,      # 30% more difficult
        "high_hills": 1.7,     # 70% more difficult
        "alpine": 2.5,         # 150% more difficult
        "glacial": 4.0         # 300% more difficult
    })
    
    # Seasonal construction windows
    seasonal_windows: Dict[ConstructionSeason, Dict[str, Any]] = field(default_factory=lambda: {
        ConstructionSeason.OPTIMAL: {
            "months": [10, 11, 12, 1, 2, 3],
            "productivity_factor": 1.0,
            "weather_risk": 0.1,
            "description": "Dry season, optimal conditions"
        },
        ConstructionSeason.FEASIBLE: {
            "months": [4, 5, 9],
            "productivity_factor": 0.8,
            "weather_risk": 0.3,
            "description": "Moderate conditions, some weather delays"
        },
        ConstructionSeason.CHALLENGING: {
            "months": [6, 7, 8],
            "productivity_factor": 0.5,
            "weather_risk": 0.7,
            "description": "Monsoon season, high weather risk"
        }
    })
    
    # High-altitude specific factors
    altitude_factors: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "oxygen_reduction": {
            1500: 0.95,   # 5% reduction at 1500m
            2500: 0.85,   # 15% reduction at 2500m
            3500: 0.75,   # 25% reduction at 3500m
            4500: 0.65,   # 35% reduction at 4500m
        },
        "temperature_lapse": {
            "rate_per_100m": -0.65,  # °C per 100m elevation gain
            "base_temp": 25.0        # Base temperature at sea level
        },
        "equipment_efficiency": {
            1500: 0.98,   # 2% efficiency loss
            2500: 0.92,   # 8% efficiency loss
            3500: 0.85,   # 15% efficiency loss
            4500: 0.75,   # 25% efficiency loss
        }
    })
    
    # Regional cost factors (relative to base costs)
    cost_factors: Dict[str, float] = field(default_factory=lambda: {
        "material_transport": 1.5,    # 50% higher due to remote location
        "labor_availability": 1.3,    # 30% higher due to skilled labor scarcity
        "equipment_mobilization": 2.0, # 100% higher due to difficult access
        "weather_delays": 1.2,        # 20% buffer for weather-related delays
        "high_altitude_premium": 1.4,  # 40% premium for high-altitude work
        "environmental_compliance": 1.1 # 10% for environmental protection measures
    })
    
    # Geological hazard zones
    hazard_zones: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "landslide_prone": {
            "slope_threshold": 20.0,
            "elevation_range": (1000, 3000),
            "risk_multiplier": 1.8,
            "mitigation_cost_factor": 1.5
        },
        "seismic_zone": {
            "zone_level": 5,  # Uttarkashi is in Zone V (highest seismic risk)
            "design_factor": 1.3,
            "foundation_cost_multiplier": 1.4
        },
        "glacial_lake_outburst": {
            "elevation_threshold": 3500,
            "proximity_risk_km": 10.0,
            "risk_multiplier": 2.0
        },
        "flash_flood": {
            "river_proximity_m": 500,
            "elevation_threshold": 2000,
            "risk_multiplier": 1.6
        }
    })
    
    # Local infrastructure constraints
    infrastructure_constraints: Dict[str, Any] = field(default_factory=lambda: {
        "road_access": {
            "main_highways": ["NH34", "NH108"],
            "seasonal_closures": {
                "high_passes": [12, 1, 2, 3],  # Winter months
                "monsoon_routes": [7, 8, 9]    # Monsoon months
            }
        },
        "power_grid": {
            "reliability_factor": 0.7,  # 70% reliability
            "backup_required": True,
            "solar_potential": 0.85     # Good solar potential
        },
        "communication": {
            "mobile_coverage": 0.6,     # 60% area coverage
            "satellite_required": True,
            "internet_reliability": 0.5
        }
    })


class UttarkashiAnalyzer:
    """Regional analyzer for Uttarkashi-specific parameters."""
    
    def __init__(self, api_client=None):
        self.params = UttarkashiParameters()
        self.api_client = api_client
        
    def classify_terrain_type(self, coordinate: Coordinate, slope_degrees: float) -> TerrainType:
        """Classify terrain type based on elevation and slope."""
        elevation = coordinate.elevation or 1000  # Default if not provided
        
        # Determine elevation zone
        elevation_zone = self._get_elevation_zone(elevation)
        
        # Classify based on slope and elevation
        if slope_degrees <= self.params.slope_thresholds["flat"]:
            if elevation_zone in ["valley", "mid_hills"]:
                return TerrainType.VALLEY_FLOOR
            else:
                return TerrainType.RIVER_TERRACE
        
        elif slope_degrees <= self.params.slope_thresholds["gentle"]:
            return TerrainType.GENTLE_SLOPE
        
        elif slope_degrees <= self.params.slope_thresholds["moderate"]:
            return TerrainType.MODERATE_SLOPE
        
        elif slope_degrees <= self.params.slope_thresholds["steep"]:
            return TerrainType.STEEP_SLOPE
        
        elif slope_degrees <= self.params.slope_thresholds["very_steep"]:
            if elevation_zone == "glacial":
                return TerrainType.GLACIAL_MORAINE
            else:
                return TerrainType.CLIFF_FACE
        
        else:
            return TerrainType.CLIFF_FACE
    
    def calculate_construction_difficulty(self, coordinate: Coordinate, 
                                        slope_degrees: float,
                                        terrain_type: Optional[TerrainType] = None) -> float:
        """Calculate construction difficulty score (0-100) for Uttarkashi conditions."""
        elevation = coordinate.elevation or 1000
        
        if terrain_type is None:
            terrain_type = self.classify_terrain_type(coordinate, slope_degrees)
        
        # Base difficulty from slope
        if slope_degrees <= 5:
            base_difficulty = 10
        elif slope_degrees <= 15:
            base_difficulty = 25
        elif slope_degrees <= 25:
            base_difficulty = 45
        elif slope_degrees <= 35:
            base_difficulty = 65
        elif slope_degrees <= 45:
            base_difficulty = 85
        else:
            base_difficulty = 95
        
        # Elevation multiplier
        elevation_zone = self._get_elevation_zone(elevation)
        elevation_multiplier = self.params.elevation_difficulty_multipliers.get(elevation_zone, 1.0)
        
        # Altitude effects
        altitude_factor = self._get_altitude_factor(elevation, "equipment_efficiency")
        
        # Terrain-specific adjustments
        terrain_adjustments = {
            TerrainType.VALLEY_FLOOR: 0.8,
            TerrainType.GENTLE_SLOPE: 1.0,
            TerrainType.MODERATE_SLOPE: 1.2,
            TerrainType.STEEP_SLOPE: 1.5,
            TerrainType.CLIFF_FACE: 2.0,
            TerrainType.GLACIAL_MORAINE: 1.8,
            TerrainType.RIVER_TERRACE: 0.9
        }
        
        terrain_factor = terrain_adjustments.get(terrain_type, 1.0)
        
        # Calculate final difficulty
        difficulty = base_difficulty * elevation_multiplier * terrain_factor / altitude_factor
        
        return min(100.0, max(0.0, difficulty))
    
    def get_optimal_construction_season(self, coordinate: Coordinate,
                                      current_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Determine optimal construction season for the location."""
        if current_date is None:
            current_date = datetime.now()
        
        elevation = coordinate.elevation or 1000
        current_month = current_date.month
        
        # Adjust seasonal windows based on elevation
        if elevation > 3500:  # High altitude - shorter optimal window
            optimal_months = [10, 11, 3, 4]  # Avoid extreme winter
            feasible_months = [5, 9]
            challenging_months = [6, 7, 8]
            impossible_months = [12, 1, 2]
        elif elevation > 2500:  # Mid-high altitude
            optimal_months = [10, 11, 12, 1, 2, 3]
            feasible_months = [4, 5, 9]
            challenging_months = [6, 7, 8]
            impossible_months = []
        else:  # Lower altitude - more flexible
            optimal_months = [10, 11, 12, 1, 2, 3, 4]
            feasible_months = [5, 9]
            challenging_months = [6, 7, 8]
            impossible_months = []
        
        # Determine current season
        if current_month in optimal_months:
            current_season = ConstructionSeason.OPTIMAL
        elif current_month in feasible_months:
            current_season = ConstructionSeason.FEASIBLE
        elif current_month in challenging_months:
            current_season = ConstructionSeason.CHALLENGING
        else:
            current_season = ConstructionSeason.IMPOSSIBLE
        
        # Calculate next optimal window
        next_optimal_month = None
        for month in range(current_month + 1, current_month + 13):
            check_month = ((month - 1) % 12) + 1
            if check_month in optimal_months:
                next_optimal_month = check_month
                break
        
        return {
            "current_season": current_season,
            "current_season_info": self.params.seasonal_windows.get(current_season, {}),
            "next_optimal_month": next_optimal_month,
            "optimal_months": optimal_months,
            "elevation_adjusted": elevation > 2500,
            "recommendations": self._get_seasonal_recommendations(current_season, elevation)
        }
    
    async def get_real_time_weather_factors(self, coordinate: Coordinate) -> Dict[str, Any]:
        """Get real-time weather factors affecting construction."""
        weather_factors = {
            "temperature_c": 15.0,  # Default
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 10.0,
            "humidity_percent": 60.0,
            "visibility_km": 10.0,
            "weather_risk_score": 0.3,
            "data_source": "default"
        }
        
        if self.api_client:
            try:
                # Get real-time weather data
                weather_data = await self.api_client.get_weather_data(coordinate)
                
                if weather_data and not weather_data.get("cached", True):
                    # Update with real API data
                    weather_factors.update({
                        "temperature_c": weather_data.get("temperature", 15.0),
                        "precipitation_mm": weather_data.get("precipitation", 0.0),
                        "wind_speed_kmh": weather_data.get("wind_speed", 10.0),
                        "humidity_percent": weather_data.get("humidity", 60.0),
                        "visibility_km": weather_data.get("visibility", 10.0),
                        "data_source": "api"
                    })
                    
                    # Calculate weather risk score
                    weather_factors["weather_risk_score"] = self._calculate_weather_risk(weather_factors)
                
            except Exception as e:
                # Fall back to default values
                weather_factors["data_source"] = f"fallback_due_to_{type(e).__name__}"
        
        # Adjust for altitude
        elevation = coordinate.elevation or 1000
        altitude_temp_adjustment = self._get_temperature_at_altitude(elevation, weather_factors["temperature_c"])
        weather_factors["altitude_adjusted_temperature"] = altitude_temp_adjustment
        
        return weather_factors
    
    def calculate_regional_cost_estimate(self, base_cost: float, 
                                       coordinate: Coordinate,
                                       construction_type: str = "road") -> Dict[str, Any]:
        """Calculate region-specific cost estimate with Uttarkashi factors."""
        elevation = coordinate.elevation or 1000
        elevation_zone = self._get_elevation_zone(elevation)
        
        # Apply regional cost factors
        adjusted_cost = base_cost
        cost_breakdown = {"base_cost": base_cost}
        
        for factor_name, multiplier in self.params.cost_factors.items():
            if factor_name == "high_altitude_premium" and elevation < 2500:
                # No high altitude premium for lower elevations
                continue
            
            factor_cost = base_cost * (multiplier - 1.0)
            adjusted_cost += factor_cost
            cost_breakdown[factor_name] = factor_cost
        
        # Elevation-specific adjustments
        elevation_multiplier = self.params.elevation_difficulty_multipliers.get(elevation_zone, 1.0)
        elevation_adjustment = base_cost * (elevation_multiplier - 1.0)
        adjusted_cost += elevation_adjustment
        cost_breakdown["elevation_adjustment"] = elevation_adjustment
        
        # Seasonal adjustment (if construction in challenging season)
        current_season = self.get_optimal_construction_season(coordinate)
        if current_season["current_season"] == ConstructionSeason.CHALLENGING:
            seasonal_cost = base_cost * 0.3  # 30% increase for challenging season
            adjusted_cost += seasonal_cost
            cost_breakdown["seasonal_adjustment"] = seasonal_cost
        
        return {
            "total_cost": adjusted_cost,
            "cost_breakdown": cost_breakdown,
            "regional_factors_applied": list(self.params.cost_factors.keys()),
            "elevation_zone": elevation_zone,
            "cost_increase_factor": adjusted_cost / base_cost,
            "currency": "USD",
            "confidence_level": 0.8
        }
    
    def assess_geological_hazards(self, coordinate: Coordinate, 
                                slope_degrees: float) -> Dict[str, Any]:
        """Assess geological hazards specific to Uttarkashi region."""
        elevation = coordinate.elevation or 1000
        hazards = {}
        overall_risk_score = 0.0
        
        # Landslide risk
        landslide_config = self.params.hazard_zones["landslide_prone"]
        if (slope_degrees > landslide_config["slope_threshold"] and
            landslide_config["elevation_range"][0] <= elevation <= landslide_config["elevation_range"][1]):
            
            landslide_risk = min(1.0, slope_degrees / 45.0)  # Normalize to 0-1
            hazards["landslide"] = {
                "risk_level": landslide_risk,
                "mitigation_required": landslide_risk > 0.5,
                "cost_multiplier": landslide_config["risk_multiplier"] if landslide_risk > 0.5 else 1.0
            }
            overall_risk_score += landslide_risk * 0.4
        
        # Seismic risk (always present in Uttarkashi - Zone V)
        seismic_config = self.params.hazard_zones["seismic_zone"]
        hazards["seismic"] = {
            "zone_level": seismic_config["zone_level"],
            "risk_level": 0.8,  # High risk for Zone V
            "design_requirements": "IS 1893 Zone V compliance required",
            "cost_multiplier": seismic_config["design_factor"]
        }
        overall_risk_score += 0.8 * 0.3
        
        # Glacial Lake Outburst Flood (GLOF) risk
        glof_config = self.params.hazard_zones["glacial_lake_outburst"]
        if elevation > glof_config["elevation_threshold"]:
            glof_risk = min(1.0, (elevation - glof_config["elevation_threshold"]) / 2000.0)
            hazards["glacial_outburst"] = {
                "risk_level": glof_risk,
                "monitoring_required": glof_risk > 0.3,
                "cost_multiplier": glof_config["risk_multiplier"] if glof_risk > 0.5 else 1.0
            }
            overall_risk_score += glof_risk * 0.2
        
        # Flash flood risk
        flash_flood_config = self.params.hazard_zones["flash_flood"]
        if elevation < flash_flood_config["elevation_threshold"]:
            # Assume higher risk near rivers (simplified - would use actual river proximity)
            flash_flood_risk = 0.4  # Moderate risk
            hazards["flash_flood"] = {
                "risk_level": flash_flood_risk,
                "drainage_required": True,
                "cost_multiplier": flash_flood_config["risk_multiplier"]
            }
            overall_risk_score += flash_flood_risk * 0.1
        
        return {
            "hazards": hazards,
            "overall_risk_score": min(1.0, overall_risk_score),
            "risk_category": self._categorize_risk(overall_risk_score),
            "mitigation_recommendations": self._get_hazard_mitigation_recommendations(hazards)
        }
    
    def _get_elevation_zone(self, elevation: float) -> str:
        """Determine elevation zone for the given elevation."""
        for zone, (min_elev, max_elev) in self.params.elevation_zones.items():
            if min_elev <= elevation < max_elev:
                return zone
        return "glacial"  # Default for very high elevations
    
    def _get_altitude_factor(self, elevation: float, factor_type: str) -> float:
        """Get altitude factor for given elevation and factor type."""
        factors = self.params.altitude_factors.get(factor_type, {})
        
        # Find the appropriate factor by elevation
        for elev_threshold in sorted(factors.keys()):
            if elevation <= elev_threshold:
                return factors[elev_threshold]
        
        # If elevation is higher than all thresholds, use the highest threshold value
        if factors:
            return factors[max(factors.keys())]
        
        return 1.0  # Default
    
    def _get_temperature_at_altitude(self, elevation: float, base_temperature: float) -> float:
        """Calculate temperature at altitude using lapse rate."""
        lapse_config = self.params.altitude_factors["temperature_lapse"]
        lapse_rate = lapse_config["rate_per_100m"]
        
        # Calculate temperature drop
        elevation_hundreds = elevation / 100.0
        temperature_drop = elevation_hundreds * lapse_rate
        
        return base_temperature + temperature_drop
    
    def _calculate_weather_risk(self, weather_factors: Dict[str, Any]) -> float:
        """Calculate weather risk score based on current conditions."""
        risk_score = 0.0
        
        # Temperature risk
        temp = weather_factors["temperature_c"]
        if temp < 0:
            risk_score += 0.4  # High risk for freezing
        elif temp < 5:
            risk_score += 0.2  # Moderate risk for near-freezing
        elif temp > 35:
            risk_score += 0.2  # High temperature risk
        
        # Precipitation risk
        precip = weather_factors["precipitation_mm"]
        if precip > 10:
            risk_score += 0.3  # High precipitation
        elif precip > 2:
            risk_score += 0.1  # Light precipitation
        
        # Wind risk
        wind = weather_factors["wind_speed_kmh"]
        if wind > 50:
            risk_score += 0.3  # High wind
        elif wind > 30:
            risk_score += 0.1  # Moderate wind
        
        # Visibility risk
        visibility = weather_factors["visibility_km"]
        if visibility < 1:
            risk_score += 0.2  # Poor visibility
        elif visibility < 5:
            risk_score += 0.1  # Reduced visibility
        
        return min(1.0, risk_score)
    
    def _get_seasonal_recommendations(self, season: ConstructionSeason, elevation: float) -> List[str]:
        """Get construction recommendations based on season and elevation."""
        recommendations = []
        
        if season == ConstructionSeason.OPTIMAL:
            recommendations.extend([
                "Ideal conditions for construction",
                "Maximize work progress during this period",
                "Plan material deliveries and equipment mobilization"
            ])
        
        elif season == ConstructionSeason.FEASIBLE:
            recommendations.extend([
                "Monitor weather conditions closely",
                "Have contingency plans for weather delays",
                "Consider accelerated work schedule"
            ])
        
        elif season == ConstructionSeason.CHALLENGING:
            recommendations.extend([
                "Limit construction to essential activities only",
                "Implement enhanced safety measures",
                "Ensure proper drainage and erosion control",
                "Consider temporary work suspension during heavy rains"
            ])
        
        elif season == ConstructionSeason.IMPOSSIBLE:
            recommendations.extend([
                "Suspend construction activities",
                "Focus on planning and material procurement",
                "Maintain equipment and prepare for next season"
            ])
        
        # Elevation-specific recommendations
        if elevation > 3500:
            recommendations.extend([
                "Account for reduced equipment efficiency at high altitude",
                "Ensure adequate oxygen supply for workers",
                "Monitor for altitude-related health issues"
            ])
        
        if elevation > 2500:
            recommendations.extend([
                "Plan for temperature variations",
                "Use cold-weather construction techniques",
                "Ensure proper material storage"
            ])
        
        return recommendations
    
    def _categorize_risk(self, risk_score: float) -> str:
        """Categorize overall risk score."""
        if risk_score < 0.3:
            return "low"
        elif risk_score < 0.6:
            return "moderate"
        elif risk_score < 0.8:
            return "high"
        else:
            return "very_high"
    
    def _get_hazard_mitigation_recommendations(self, hazards: Dict[str, Any]) -> List[str]:
        """Get mitigation recommendations for identified hazards."""
        recommendations = []
        
        if "landslide" in hazards and hazards["landslide"]["mitigation_required"]:
            recommendations.extend([
                "Implement slope stabilization measures",
                "Install proper drainage systems",
                "Consider retaining walls or terracing",
                "Regular slope monitoring during construction"
            ])
        
        if "seismic" in hazards:
            recommendations.extend([
                "Follow IS 1893 seismic design standards",
                "Use earthquake-resistant construction techniques",
                "Ensure proper foundation design for seismic loads",
                "Consider base isolation for critical structures"
            ])
        
        if "glacial_outburst" in hazards and hazards["glacial_outburst"]["monitoring_required"]:
            recommendations.extend([
                "Install early warning systems",
                "Monitor upstream glacial lakes",
                "Design for potential flood scenarios",
                "Establish evacuation procedures"
            ])
        
        if "flash_flood" in hazards:
            recommendations.extend([
                "Implement comprehensive drainage design",
                "Elevate critical infrastructure",
                "Use flood-resistant materials",
                "Install flood monitoring systems"
            ])
        
        return recommendations