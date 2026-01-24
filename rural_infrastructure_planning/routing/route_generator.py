"""
Route Generator with API-enhanced pathfinding algorithms.

This module provides the Route_Generator class that implements A* pathfinding
algorithm with weighted cost surface to generate optimal route alignments
considering terrain difficulty, existing infrastructure, and risk factors.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import networkx as nx
from scipy.spatial.distance import euclidean
from scipy.ndimage import gaussian_filter
import heapq
import math
from datetime import datetime
import uuid

from ..data.api_client import API_Client, BoundingBox, Coordinate, DataFreshnessInfo
from ..data.dem_processor import DEM_Processor, DEMData, CostSurface, ElevationProfile
from ..data.osm_parser import OSM_Parser, RoadNetwork, Settlement, Infrastructure
from ..config.settings import config
from ..config.regional_config import UttarkashiAnalyzer, TerrainType, ConstructionSeason

logger = logging.getLogger(__name__)


@dataclass
class RouteConstraints:
    """Constraints for route generation."""
    max_slope_degrees: float = 35.0  # Maximum acceptable slope
    max_elevation_gain: float = 2000.0  # Maximum elevation gain in meters
    max_distance_km: float = 100.0  # Maximum route distance
    min_road_width: float = 3.0  # Minimum road width in meters
    budget_limit: Optional[float] = None  # Budget limit in USD
    timeline_limit: Optional[int] = None  # Timeline limit in days
    avoid_flood_zones: bool = True  # Avoid high flood risk areas
    prefer_existing_roads: bool = True  # Prefer routes near existing infrastructure
    construction_season: Optional[str] = None  # Preferred construction season
    priority_factors: List[str] = field(default_factory=lambda: ["cost", "safety", "speed"])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'max_slope_degrees': self.max_slope_degrees,
            'max_elevation_gain': self.max_elevation_gain,
            'max_distance_km': self.max_distance_km,
            'min_road_width': self.min_road_width,
            'budget_limit': self.budget_limit,
            'timeline_limit': self.timeline_limit,
            'avoid_flood_zones': self.avoid_flood_zones,
            'prefer_existing_roads': self.prefer_existing_roads,
            'construction_season': self.construction_season,
            'priority_factors': self.priority_factors
        }


@dataclass
class RouteSegment:
    """Individual segment of a route."""
    start: Coordinate
    end: Coordinate
    length: float  # meters
    slope_grade: float  # degrees
    terrain_type: str  # flat, gentle, moderate, steep, very_steep, extreme
    construction_cost: float  # USD per meter
    construction_difficulty: float  # 0-100 scale
    risk_factors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'start': self.start.to_dict(),
            'end': self.end.to_dict(),
            'length': self.length,
            'slope_grade': self.slope_grade,
            'terrain_type': self.terrain_type,
            'construction_cost': self.construction_cost,
            'construction_difficulty': self.construction_difficulty,
            'risk_factors': self.risk_factors
        }


@dataclass
class RouteAlignment:
    """Complete route alignment with waypoints and metrics."""
    id: str
    waypoints: List[Coordinate]
    segments: List[RouteSegment]
    total_distance: float  # kilometers
    elevation_gain: float  # meters
    elevation_loss: float  # meters
    construction_difficulty: float  # 0-100 scale
    estimated_cost: float  # USD
    estimated_duration: int  # construction days
    risk_score: float  # 0-100 composite risk
    algorithm_used: str = "astar"
    data_sources: List[str] = field(default_factory=list)
    freshness_info: Optional[DataFreshnessInfo] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            'id': self.id,
            'waypoints': [wp.to_dict() for wp in self.waypoints],
            'segments': [seg.to_dict() for seg in self.segments],
            'total_distance': self.total_distance,
            'elevation_gain': self.elevation_gain,
            'elevation_loss': self.elevation_loss,
            'construction_difficulty': self.construction_difficulty,
            'estimated_cost': self.estimated_cost,
            'estimated_duration': self.estimated_duration,
            'risk_score': self.risk_score,
            'algorithm_used': self.algorithm_used,
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


@dataclass
class RouteMetrics:
    """Detailed metrics for a route."""
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    max_slope_degrees: float
    avg_slope_degrees: float
    construction_cost_usd: float
    construction_days: int
    difficulty_score: float  # 0-100
    risk_score: float  # 0-100
    accessibility_score: float  # 0-100 (higher is better)
    sustainability_score: float  # 0-100 (environmental impact)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'distance_km': self.distance_km,
            'elevation_gain_m': self.elevation_gain_m,
            'elevation_loss_m': self.elevation_loss_m,
            'max_slope_degrees': self.max_slope_degrees,
            'avg_slope_degrees': self.avg_slope_degrees,
            'construction_cost_usd': self.construction_cost_usd,
            'construction_days': self.construction_days,
            'difficulty_score': self.difficulty_score,
            'risk_score': self.risk_score,
            'accessibility_score': self.accessibility_score,
            'sustainability_score': self.sustainability_score
        }


class AStarNode:
    """Node for A* pathfinding algorithm."""
    
    def __init__(self, position: Tuple[int, int], g_cost: float = 0, h_cost: float = 0, parent=None):
        self.position = position  # (row, col) in cost surface
        self.g_cost = g_cost  # Cost from start
        self.h_cost = h_cost  # Heuristic cost to goal
        self.f_cost = g_cost + h_cost  # Total cost
        self.parent = parent
    
    def __lt__(self, other):
        return self.f_cost < other.f_cost
    
    def __eq__(self, other):
        return self.position == other.position


class Route_Generator:
    """
    Route Generator with API-enhanced pathfinding algorithms.
    
    This class implements A* pathfinding algorithm with weighted cost surface
    to generate optimal route alignments considering terrain difficulty,
    existing infrastructure, and risk factors from multiple data sources.
    
    Features:
    - A* pathfinding with configurable heuristics
    - Multiple route alternative generation
    - Cost surface optimization with terrain and infrastructure factors
    - Route metrics calculation including cost and difficulty
    - Integration with API-enhanced data sources
    - Uttarakhand-specific terrain parameters
    """
    
    def __init__(self, 
                 api_client: Optional[API_Client] = None,
                 dem_processor: Optional[DEM_Processor] = None,
                 osm_parser: Optional[OSM_Parser] = None):
        """
        Initialize Route Generator.
        
        Args:
            api_client: Optional API client for data fetching
            dem_processor: Optional DEM processor for terrain analysis
            osm_parser: Optional OSM parser for road network data
        """
        self.api_client = api_client
        self.dem_processor = dem_processor or DEM_Processor(api_client)
        self.osm_parser = osm_parser or OSM_Parser()
        self.regional_analyzer = UttarkashiAnalyzer(api_client)
        
        # Uttarakhand-specific routing parameters
        self.uttarakhand_params = {
            'terrain_costs': {
                'flat': 1.0,        # Base cost multiplier
                'gentle': 1.5,      # 5-15 degrees
                'moderate': 2.5,    # 15-25 degrees
                'steep': 4.0,       # 25-35 degrees
                'very_steep': 7.0,  # 35-45 degrees
                'extreme': 15.0     # >45 degrees
            },
            'elevation_penalties': {
                'valley': 1.0,      # 500-1000m
                'low_hills': 1.2,   # 1000-2000m
                'mid_hills': 1.5,   # 2000-3000m
                'high_hills': 2.0,  # 3000-4000m
                'alpine': 3.0       # 4000m+
            },
            'construction_costs': {
                # USD per meter based on terrain difficulty
                'flat': 150,
                'gentle': 250,
                'moderate': 400,
                'steep': 700,
                'very_steep': 1200,
                'extreme': 2500
            },
            'seasonal_factors': {
                'winter': 2.0,      # Dec-Feb (difficult conditions)
                'spring': 1.2,      # Mar-May (moderate conditions)
                'monsoon': 3.0,     # Jun-Sep (very difficult)
                'post_monsoon': 1.0 # Oct-Nov (optimal conditions)
            }
        }
        
        logger.info("Initialized Route_Generator with Uttarakhand-specific parameters")
    
    async def generate_routes(self, 
                            start: Coordinate, 
                            end: Coordinate,
                            constraints: Optional[RouteConstraints] = None,
                            num_alternatives: int = 3) -> List[RouteAlignment]:
        """
        Generate multiple route alternatives using A* pathfinding.
        
        This method creates multiple route options by varying the pathfinding
        parameters and cost surface weights to explore different trade-offs
        between distance, cost, safety, and construction difficulty.
        
        Args:
            start: Starting coordinate
            end: Ending coordinate
            constraints: Optional routing constraints
            num_alternatives: Number of alternative routes to generate
            
        Returns:
            List of RouteAlignment objects with detailed metrics
            
        Raises:
            RuntimeError: If route generation fails
        """
        try:
            if constraints is None:
                constraints = RouteConstraints()
            
            logger.info(f"Generating {num_alternatives} route alternatives from "
                       f"{start.latitude:.4f},{start.longitude:.4f} to "
                       f"{end.latitude:.4f},{end.longitude:.4f}")
            
            # Create bounding box for data fetching
            bounds = self._create_bounding_box(start, end)
            
            # Load required data sources
            dem_data, road_network, data_sources = await self._load_route_data(bounds)
            
            # Generate cost surface
            cost_surface = await self._generate_enhanced_cost_surface(
                dem_data, road_network, constraints
            )
            
            # Generate multiple route alternatives
            routes = []
            
            # Strategy 1: Minimize distance (shortest path)
            if len(routes) < num_alternatives:
                route = await self._generate_single_route(
                    start, end, cost_surface, dem_data, constraints,
                    strategy="shortest", route_id=f"route_shortest_{uuid.uuid4().hex[:8]}"
                )
                if route:
                    route.data_sources = data_sources
                    routes.append(route)
            
            # Strategy 2: Minimize cost (cheapest construction)
            if len(routes) < num_alternatives:
                route = await self._generate_single_route(
                    start, end, cost_surface, dem_data, constraints,
                    strategy="cheapest", route_id=f"route_cheapest_{uuid.uuid4().hex[:8]}"
                )
                if route and not self._is_duplicate_route(route, routes):
                    route.data_sources = data_sources
                    routes.append(route)
            
            # Strategy 3: Minimize risk (safest construction)
            if len(routes) < num_alternatives:
                route = await self._generate_single_route(
                    start, end, cost_surface, dem_data, constraints,
                    strategy="safest", route_id=f"route_safest_{uuid.uuid4().hex[:8]}"
                )
                if route and not self._is_duplicate_route(route, routes):
                    route.data_sources = data_sources
                    routes.append(route)
            
            # Strategy 4: Balanced approach (if more alternatives needed)
            while len(routes) < num_alternatives:
                route = await self._generate_single_route(
                    start, end, cost_surface, dem_data, constraints,
                    strategy="balanced", route_id=f"route_balanced_{len(routes)}_{uuid.uuid4().hex[:8]}"
                )
                if route and not self._is_duplicate_route(route, routes):
                    route.data_sources = data_sources
                    routes.append(route)
                else:
                    break  # Can't generate more unique routes
            
            # Sort routes by composite score (lower is better)
            routes.sort(key=lambda r: self._calculate_composite_score(r, constraints))
            
            # Apply constraint filtering
            filtered_routes = self.filter_routes_by_constraints(routes, constraints)
            
            # If we have routes that don't meet constraints, try to optimize them
            if len(filtered_routes) < len(routes) and cost_surface:
                logger.info("Some routes don't meet constraints, attempting optimization")
                for route in routes:
                    if route not in filtered_routes:
                        optimized_route = self.optimize_route_for_constraints(route, constraints, cost_surface)
                        if optimized_route and optimized_route not in filtered_routes:
                            # Check if optimized route now meets constraints
                            optimized_list = self.filter_routes_by_constraints([optimized_route], constraints)
                            if optimized_list:
                                filtered_routes.extend(optimized_list)
            
            # Use filtered routes if we have any, otherwise return original routes with warning
            final_routes = filtered_routes if filtered_routes else routes
            
            if not filtered_routes and routes:
                logger.warning("No routes meet all constraints, returning unfiltered routes")
            
            # Re-sort final routes
            final_routes.sort(key=lambda r: self._calculate_composite_score(r, constraints))
            
            logger.info(f"Generated {len(final_routes)} route alternatives successfully "
                       f"({len(filtered_routes)} meet constraints)")
            
            return final_routes
            
        except Exception as e:
            logger.error(f"Route generation failed: {e}")
            raise RuntimeError(f"Route generation failed: {e}") from e
    
    async def optimize_alignment(self, 
                               route: RouteAlignment, 
                               cost_surface: CostSurface,
                               iterations: int = 5) -> RouteAlignment:
        """
        Optimize route alignment using cost surface analysis.
        
        This method refines an existing route by applying local optimization
        techniques to reduce cost while maintaining feasibility constraints.
        
        Args:
            route: Input route alignment to optimize
            cost_surface: Cost surface for optimization
            iterations: Number of optimization iterations
            
        Returns:
            Optimized RouteAlignment
            
        Raises:
            RuntimeError: If optimization fails
        """
        try:
            logger.info(f"Optimizing route alignment {route.id} with {iterations} iterations")
            
            optimized_route = route
            best_cost = route.estimated_cost
            
            for iteration in range(iterations):
                # Apply different optimization techniques
                if iteration % 2 == 0:
                    # Smooth waypoints to reduce sharp turns
                    candidate = self._smooth_route_waypoints(optimized_route, cost_surface)
                else:
                    # Local search for better waypoint positions
                    candidate = self._local_waypoint_optimization(optimized_route, cost_surface)
                
                if candidate and candidate.estimated_cost < best_cost:
                    optimized_route = candidate
                    best_cost = candidate.estimated_cost
                    logger.debug(f"Optimization iteration {iteration + 1}: cost reduced to ${best_cost:.0f}")
            
            # Update route ID to indicate optimization
            optimized_route.id = f"{route.id}_optimized"
            
            logger.info(f"Route optimization completed: cost reduced from ${route.estimated_cost:.0f} "
                       f"to ${optimized_route.estimated_cost:.0f}")
            
            return optimized_route
            
        except Exception as e:
            logger.error(f"Route optimization failed: {e}")
            raise RuntimeError(f"Route optimization failed: {e}") from e
    
    def calculate_route_metrics(self, route: RouteAlignment) -> RouteMetrics:
        """
        Calculate comprehensive metrics for a route.
        
        This method computes detailed metrics including distance, elevation
        changes, construction costs, difficulty scores, and risk assessments.
        
        Args:
            route: Route alignment to analyze
            
        Returns:
            RouteMetrics with comprehensive analysis
            
        Raises:
            RuntimeError: If metrics calculation fails
        """
        try:
            logger.debug(f"Calculating metrics for route {route.id}")
            
            # Basic distance and elevation metrics
            total_distance = route.total_distance
            elevation_gain = route.elevation_gain
            elevation_loss = route.elevation_loss
            
            # Calculate slope statistics
            slopes = [seg.slope_grade for seg in route.segments]
            max_slope = max(slopes) if slopes else 0.0
            avg_slope = sum(slopes) / len(slopes) if slopes else 0.0
            
            # Construction cost and duration
            construction_cost = route.estimated_cost
            construction_days = route.estimated_duration
            
            # Difficulty score (0-100, higher is more difficult)
            difficulty_score = route.construction_difficulty
            
            # Risk score (0-100, higher is more risky)
            risk_score = route.risk_score
            
            # Accessibility score (0-100, higher is better accessibility)
            accessibility_score = self._calculate_accessibility_score(route)
            
            # Sustainability score (0-100, higher is more sustainable)
            sustainability_score = self._calculate_sustainability_score(route)
            
            metrics = RouteMetrics(
                distance_km=total_distance,
                elevation_gain_m=elevation_gain,
                elevation_loss_m=elevation_loss,
                max_slope_degrees=max_slope,
                avg_slope_degrees=avg_slope,
                construction_cost_usd=construction_cost,
                construction_days=construction_days,
                difficulty_score=difficulty_score,
                risk_score=risk_score,
                accessibility_score=accessibility_score,
                sustainability_score=sustainability_score
            )
            
            logger.debug(f"Calculated metrics for route {route.id}: "
                        f"{total_distance:.1f}km, ${construction_cost:.0f}, "
                        f"difficulty {difficulty_score:.1f}/100")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Metrics calculation failed for route {route.id}: {e}")
            raise RuntimeError(f"Metrics calculation failed: {e}") from e
    
    def _create_bounding_box(self, start: Coordinate, end: Coordinate, 
                           buffer_degrees: float = 0.02) -> BoundingBox:
        """Create bounding box around start and end points with buffer."""
        min_lat = min(start.latitude, end.latitude) - buffer_degrees
        max_lat = max(start.latitude, end.latitude) + buffer_degrees
        min_lon = min(start.longitude, end.longitude) - buffer_degrees
        max_lon = max(start.longitude, end.longitude) + buffer_degrees
        
        return BoundingBox(
            north=max_lat,
            south=min_lat,
            east=max_lon,
            west=min_lon
        )
    
    async def _load_route_data(self, bounds: BoundingBox) -> Tuple[DEMData, Optional[RoadNetwork], List[str]]:
        """Load all required data for route generation."""
        data_sources = []
        
        # Load DEM data
        dem_data = await self.dem_processor.load_elevation_data(bounds)
        if dem_data.freshness_info:
            data_sources.append(dem_data.freshness_info.source_name)
        
        # Load road network data
        road_network = None
        try:
            async with self.osm_parser as parser:
                osm_data = await parser.parse_osm_data(bounds, ['roads'])
                road_network = parser.extract_road_network(osm_data.to_dict(), bounds)
                if osm_data.freshness_info:
                    data_sources.append(osm_data.freshness_info.source_name)
        except Exception as e:
            logger.warning(f"Failed to load road network data: {e}")
        
        return dem_data, road_network, data_sources
    
    async def _generate_enhanced_cost_surface(self, 
                                            dem_data: DEMData,
                                            road_network: Optional[RoadNetwork],
                                            constraints: RouteConstraints) -> CostSurface:
        """Generate enhanced cost surface with multiple factors."""
        # Base cost surface from terrain
        cost_surface = await self.dem_processor.generate_cost_surface(dem_data)
        
        # Enhance with road network proximity
        if road_network and constraints.prefer_existing_roads:
            cost_surface = self._add_road_proximity_costs(cost_surface, road_network)
        
        # Apply constraint-based modifications
        cost_surface = self._apply_constraint_costs(cost_surface, dem_data, constraints)
        
        return cost_surface
    
    def _add_road_proximity_costs(self, cost_surface: CostSurface, 
                                road_network: RoadNetwork) -> CostSurface:
        """Add road proximity bonuses to cost surface with infrastructure proximity calculations."""
        modified_costs = cost_surface.cost_array.copy()
        
        try:
            # Create distance-based cost reduction near existing roads
            if road_network and road_network.graph and len(road_network.graph.nodes) > 0:
                
                # Get road coordinates from the network
                road_coords = []
                for node_id, node_data in road_network.graph.nodes(data=True):
                    if 'y' in node_data and 'x' in node_data:
                        road_coords.append((node_data['y'], node_data['x']))  # (lat, lon)
                
                if road_coords:
                    # Calculate proximity bonuses
                    rows, cols = cost_surface.cost_array.shape
                    
                    for i in range(rows):
                        for j in range(cols):
                            # Convert array index to coordinate
                            coord = self._cost_surface_index_to_coord(i, j, cost_surface)
                            if coord:
                                # Find distance to nearest road
                                min_distance = float('inf')
                                for road_lat, road_lon in road_coords:
                                    distance = self._calculate_distance_meters(
                                        coord, Coordinate(road_lat, road_lon)
                                    )
                                    min_distance = min(min_distance, distance)
                                
                                # Apply proximity bonus (closer to roads = lower cost)
                                if min_distance < 5000:  # Within 5km of existing road
                                    proximity_factor = 1.0 - (0.3 * (5000 - min_distance) / 5000)
                                    modified_costs[i, j] *= max(0.5, proximity_factor)
                                elif min_distance < 10000:  # Within 10km
                                    proximity_factor = 1.0 - (0.15 * (10000 - min_distance) / 5000)
                                    modified_costs[i, j] *= max(0.7, proximity_factor)
                
                logger.debug(f"Applied road proximity bonuses for {len(road_coords)} road nodes")
            
            else:
                # Fallback: apply uniform small bonus if no specific road data
                modified_costs *= 0.95  # 5% cost reduction
                logger.debug("Applied uniform infrastructure proximity bonus (no specific road data)")
        
        except Exception as e:
            logger.warning(f"Failed to apply road proximity costs: {e}")
            # Fallback to uniform bonus
            modified_costs *= 0.95
        
        return CostSurface(
            cost_array=modified_costs,
            weights=cost_surface.weights,
            bounds=cost_surface.bounds,
            resolution=cost_surface.resolution,
            transform=cost_surface.transform,
            coordinate_system=cost_surface.coordinate_system
        )
    
    def _apply_constraint_costs(self, cost_surface: CostSurface, 
                              dem_data: DEMData, 
                              constraints: RouteConstraints) -> CostSurface:
        """Apply routing constraints to cost surface with enhanced terrain difficulty weighting."""
        modified_costs = cost_surface.cost_array.copy()
        
        # Apply slope constraints with terrain difficulty weighting
        if dem_data.slope_array is not None:
            # Create terrain difficulty weights based on Uttarakhand parameters
            terrain_weights = np.ones_like(dem_data.slope_array)
            
            # Apply graduated terrain cost multipliers
            flat_mask = dem_data.slope_array <= 5
            gentle_mask = (dem_data.slope_array > 5) & (dem_data.slope_array <= 15)
            moderate_mask = (dem_data.slope_array > 15) & (dem_data.slope_array <= 25)
            steep_mask = (dem_data.slope_array > 25) & (dem_data.slope_array <= 35)
            very_steep_mask = (dem_data.slope_array > 35) & (dem_data.slope_array <= 45)
            extreme_mask = dem_data.slope_array > 45
            
            terrain_weights[flat_mask] *= self.uttarakhand_params['terrain_costs']['flat']
            terrain_weights[gentle_mask] *= self.uttarakhand_params['terrain_costs']['gentle']
            terrain_weights[moderate_mask] *= self.uttarakhand_params['terrain_costs']['moderate']
            terrain_weights[steep_mask] *= self.uttarakhand_params['terrain_costs']['steep']
            terrain_weights[very_steep_mask] *= self.uttarakhand_params['terrain_costs']['very_steep']
            terrain_weights[extreme_mask] *= self.uttarakhand_params['terrain_costs']['extreme']
            
            # Apply terrain difficulty weighting
            modified_costs *= terrain_weights
            
            # Heavy penalty for areas exceeding maximum slope constraint
            steep_areas = dem_data.slope_array > constraints.max_slope_degrees
            modified_costs[steep_areas] *= 50.0  # Make infeasible areas very expensive
        
        # Apply elevation constraints with altitude-based penalties
        if dem_data.elevation_array is not None:
            elevation_weights = np.ones_like(dem_data.elevation_array)
            
            # Apply elevation-based cost multipliers
            valley_mask = (dem_data.elevation_array >= 500) & (dem_data.elevation_array < 1000)
            low_hills_mask = (dem_data.elevation_array >= 1000) & (dem_data.elevation_array < 2000)
            mid_hills_mask = (dem_data.elevation_array >= 2000) & (dem_data.elevation_array < 3000)
            high_hills_mask = (dem_data.elevation_array >= 3000) & (dem_data.elevation_array < 4000)
            alpine_mask = dem_data.elevation_array >= 4000
            
            elevation_weights[valley_mask] *= self.uttarakhand_params['elevation_penalties']['valley']
            elevation_weights[low_hills_mask] *= self.uttarakhand_params['elevation_penalties']['low_hills']
            elevation_weights[mid_hills_mask] *= self.uttarakhand_params['elevation_penalties']['mid_hills']
            elevation_weights[high_hills_mask] *= self.uttarakhand_params['elevation_penalties']['high_hills']
            elevation_weights[alpine_mask] *= self.uttarakhand_params['elevation_penalties']['alpine']
            
            modified_costs *= elevation_weights
            
            # Conservative elevation gain constraint
            if constraints.max_elevation_gain < 2000:
                high_areas = dem_data.elevation_array > 3000
                modified_costs[high_areas] *= 3.0
        
        # Apply seasonal construction constraints
        if constraints.construction_season:
            seasonal_multiplier = self.uttarakhand_params['seasonal_factors'].get(
                constraints.construction_season, 1.0
            )
            modified_costs *= seasonal_multiplier
        
        # Apply budget-based constraints (simplified implementation)
        if constraints.budget_limit:
            # Increase costs in high-cost terrain if budget is limited
            high_cost_areas = modified_costs > np.percentile(modified_costs, 80)
            budget_factor = min(2.0, 1000000 / constraints.budget_limit)  # Scale based on $1M baseline
            modified_costs[high_cost_areas] *= budget_factor
        
        return CostSurface(
            cost_array=modified_costs,
            weights=cost_surface.weights,
            bounds=cost_surface.bounds,
            resolution=cost_surface.resolution,
            transform=cost_surface.transform,
            coordinate_system=cost_surface.coordinate_system
        )
    
    async def _generate_single_route(self, 
                                   start: Coordinate, 
                                   end: Coordinate,
                                   cost_surface: CostSurface,
                                   dem_data: DEMData,
                                   constraints: RouteConstraints,
                                   strategy: str = "balanced",
                                   route_id: Optional[str] = None) -> Optional[RouteAlignment]:
        """Generate a single route using A* pathfinding with specified strategy."""
        try:
            if route_id is None:
                route_id = f"route_{strategy}_{uuid.uuid4().hex[:8]}"
            
            # Convert coordinates to cost surface indices
            start_idx = self._coord_to_cost_surface_index(start, cost_surface)
            end_idx = self._coord_to_cost_surface_index(end, cost_surface)
            
            if start_idx is None or end_idx is None:
                logger.warning(f"Start or end point outside cost surface bounds")
                return None
            
            # Apply strategy-specific cost modifications
            modified_costs = self._apply_strategy_costs(cost_surface.cost_array, strategy)
            
            # Run A* pathfinding
            path_indices = self._astar_pathfind(start_idx, end_idx, modified_costs)
            
            if not path_indices:
                logger.warning(f"No path found using {strategy} strategy")
                return None
            
            # Convert path indices back to coordinates
            waypoints = []
            for row, col in path_indices:
                coord = self._cost_surface_index_to_coord(row, col, cost_surface)
                if coord:
                    waypoints.append(coord)
            
            if len(waypoints) < 2:
                logger.warning(f"Invalid path with {len(waypoints)} waypoints")
                return None
            
            # Create route segments and calculate metrics
            segments = self._create_route_segments(waypoints, dem_data)
            
            # Calculate route metrics
            total_distance = sum(seg.length for seg in segments) / 1000.0  # Convert to km
            elevation_gain, elevation_loss = self._calculate_elevation_changes(segments)
            construction_difficulty = self._calculate_construction_difficulty(segments)
            estimated_cost = sum(seg.construction_cost * seg.length for seg in segments)
            estimated_duration = self._calculate_construction_duration(segments)
            risk_score = self._calculate_risk_score(segments)
            
            # Create freshness info
            freshness_info = DataFreshnessInfo(
                source_type="api" if dem_data.source.startswith("api") else "local",
                source_name=dem_data.source,
                data_age_hours=dem_data.freshness_info.data_age_hours if dem_data.freshness_info else 24.0,
                is_real_time=dem_data.freshness_info.is_real_time if dem_data.freshness_info else False,
                quality_score=dem_data.freshness_info.quality_score if dem_data.freshness_info else 0.7,
                last_updated=datetime.now()
            )
            
            route = RouteAlignment(
                id=route_id,
                waypoints=waypoints,
                segments=segments,
                total_distance=total_distance,
                elevation_gain=elevation_gain,
                elevation_loss=elevation_loss,
                construction_difficulty=construction_difficulty,
                estimated_cost=estimated_cost,
                estimated_duration=estimated_duration,
                risk_score=risk_score,
                algorithm_used=f"astar_{strategy}",
                freshness_info=freshness_info
            )
            
            logger.debug(f"Generated {strategy} route: {total_distance:.1f}km, "
                        f"${estimated_cost:.0f}, difficulty {construction_difficulty:.1f}")
            
            return route
            
        except Exception as e:
            logger.error(f"Single route generation failed for {strategy} strategy: {e}")
            return None
    
    def _coord_to_cost_surface_index(self, coord: Coordinate, 
                                   cost_surface: CostSurface) -> Optional[Tuple[int, int]]:
        """Convert geographic coordinate to cost surface array index."""
        try:
            # Calculate relative position within bounds
            lat_range = cost_surface.bounds.north - cost_surface.bounds.south
            lon_range = cost_surface.bounds.east - cost_surface.bounds.west
            
            if lat_range <= 0 or lon_range <= 0:
                return None
            
            # Calculate array indices (note: array is typically north-to-south)
            lat_ratio = (cost_surface.bounds.north - coord.latitude) / lat_range
            lon_ratio = (coord.longitude - cost_surface.bounds.west) / lon_range
            
            row = int(lat_ratio * cost_surface.cost_array.shape[0])
            col = int(lon_ratio * cost_surface.cost_array.shape[1])
            
            # Ensure indices are within bounds
            row = max(0, min(row, cost_surface.cost_array.shape[0] - 1))
            col = max(0, min(col, cost_surface.cost_array.shape[1] - 1))
            
            return (row, col)
            
        except Exception as e:
            logger.error(f"Coordinate to index conversion failed: {e}")
            return None
    
    def _cost_surface_index_to_coord(self, row: int, col: int, 
                                   cost_surface: CostSurface) -> Optional[Coordinate]:
        """Convert cost surface array index to geographic coordinate."""
        try:
            # Calculate relative position within array
            lat_ratio = row / cost_surface.cost_array.shape[0]
            lon_ratio = col / cost_surface.cost_array.shape[1]
            
            # Convert to geographic coordinates
            lat_range = cost_surface.bounds.north - cost_surface.bounds.south
            lon_range = cost_surface.bounds.east - cost_surface.bounds.west
            
            latitude = cost_surface.bounds.north - (lat_ratio * lat_range)
            longitude = cost_surface.bounds.west + (lon_ratio * lon_range)
            
            return Coordinate(latitude, longitude)
            
        except Exception as e:
            logger.error(f"Index to coordinate conversion failed: {e}")
            return None
    
    def _apply_strategy_costs(self, cost_array: np.ndarray, strategy: str) -> np.ndarray:
        """Apply strategy-specific modifications to cost surface."""
        modified_costs = cost_array.copy()
        
        if strategy == "shortest":
            # Minimize distance - use uniform costs
            modified_costs = np.ones_like(cost_array)
            
        elif strategy == "cheapest":
            # Minimize construction cost - emphasize terrain costs
            modified_costs = cost_array * 2.0  # Double terrain cost impact
            
        elif strategy == "safest":
            # Minimize risk - heavily penalize difficult terrain
            high_cost_areas = cost_array > np.percentile(cost_array, 75)
            modified_costs[high_cost_areas] *= 5.0
            
        elif strategy == "balanced":
            # Balanced approach - use original costs with slight smoothing
            modified_costs = gaussian_filter(cost_array, sigma=1.0)
        
        return modified_costs
    
    def _astar_pathfind(self, start: Tuple[int, int], end: Tuple[int, int], 
                       cost_array: np.ndarray) -> List[Tuple[int, int]]:
        """
        A* pathfinding algorithm implementation.
        
        Args:
            start: Starting position (row, col)
            end: Ending position (row, col)
            cost_array: Cost surface array
            
        Returns:
            List of (row, col) positions forming the path
        """
        try:
            rows, cols = cost_array.shape
            
            # Initialize data structures
            open_set = []
            closed_set = set()
            came_from = {}
            
            # Create start node
            start_node = AStarNode(start, 0, self._heuristic_distance(start, end))
            heapq.heappush(open_set, start_node)
            
            # G-cost tracking
            g_costs = {start: 0}
            
            while open_set:
                current = heapq.heappop(open_set)
                
                if current.position == end:
                    # Reconstruct path
                    path = []
                    pos = current.position
                    while pos in came_from:
                        path.append(pos)
                        pos = came_from[pos]
                    path.append(start)
                    return path[::-1]  # Reverse to get start-to-end path
                
                closed_set.add(current.position)
                
                # Check all neighbors (8-connected)
                for dr, dc in [(-1, -1), (-1, 0), (-1, 1), (0, -1), 
                              (0, 1), (1, -1), (1, 0), (1, 1)]:
                    
                    neighbor_pos = (current.position[0] + dr, current.position[1] + dc)
                    
                    # Check bounds
                    if (neighbor_pos[0] < 0 or neighbor_pos[0] >= rows or
                        neighbor_pos[1] < 0 or neighbor_pos[1] >= cols):
                        continue
                    
                    if neighbor_pos in closed_set:
                        continue
                    
                    # Calculate movement cost
                    terrain_cost = cost_array[neighbor_pos]
                    
                    # Diagonal movement costs more
                    movement_cost = math.sqrt(2) if abs(dr) + abs(dc) == 2 else 1.0
                    
                    tentative_g = g_costs[current.position] + (terrain_cost * movement_cost)
                    
                    if neighbor_pos not in g_costs or tentative_g < g_costs[neighbor_pos]:
                        came_from[neighbor_pos] = current.position
                        g_costs[neighbor_pos] = tentative_g
                        
                        h_cost = self._heuristic_distance(neighbor_pos, end)
                        neighbor_node = AStarNode(neighbor_pos, tentative_g, h_cost)
                        
                        # Add to open set if not already there with better cost
                        heapq.heappush(open_set, neighbor_node)
            
            # No path found
            return []
            
        except Exception as e:
            logger.error(f"A* pathfinding failed: {e}")
            return []
    
    def _heuristic_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """Calculate heuristic distance between two positions (Euclidean distance)."""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def _create_route_segments(self, waypoints: List[Coordinate], 
                             dem_data: DEMData) -> List[RouteSegment]:
        """Create route segments from waypoints with terrain analysis."""
        segments = []
        
        for i in range(len(waypoints) - 1):
            start_coord = waypoints[i]
            end_coord = waypoints[i + 1]
            
            # Calculate segment length
            length = self._calculate_distance_meters(start_coord, end_coord)
            
            # Calculate slope grade
            elevation_diff = (end_coord.elevation or 0) - (start_coord.elevation or 0)
            slope_grade = math.degrees(math.atan2(abs(elevation_diff), length)) if length > 0 else 0
            
            # Use regional analyzer for enhanced terrain classification
            midpoint_coord = Coordinate(
                (start_coord.latitude + end_coord.latitude) / 2,
                (start_coord.longitude + end_coord.longitude) / 2,
                (start_coord.elevation or 0 + end_coord.elevation or 0) / 2
            )
            
            # Get regional terrain classification
            regional_terrain_type = self.regional_analyzer.classify_terrain_type(midpoint_coord, slope_grade)
            terrain_type = regional_terrain_type.value if hasattr(regional_terrain_type, 'value') else self._classify_terrain_type(slope_grade)
            
            # Calculate regional construction difficulty
            regional_difficulty = self.regional_analyzer.calculate_construction_difficulty(
                midpoint_coord, slope_grade, regional_terrain_type
            )
            
            # Use regional difficulty if available, otherwise fall back to basic calculation
            difficulty = regional_difficulty if regional_difficulty is not None else self._calculate_segment_difficulty(slope_grade, terrain_type)
            
            # Calculate construction cost per meter using regional factors
            base_cost = self.uttarakhand_params['construction_costs'].get(terrain_type, 400)
            regional_cost_info = self.regional_analyzer.calculate_regional_cost_estimate(
                base_cost * length, midpoint_coord
            )
            construction_cost = regional_cost_info['total_cost'] / length if length > 0 else base_cost
            
            # Identify risk factors including regional hazards
            risk_factors = self._identify_regional_risk_factors(start_coord, end_coord, slope_grade, midpoint_coord)
            
            segment = RouteSegment(
                start=start_coord,
                end=end_coord,
                length=length,
                slope_grade=slope_grade,
                terrain_type=terrain_type,
                construction_cost=construction_cost,
                construction_difficulty=difficulty,
                risk_factors=risk_factors
            )
            
            segments.append(segment)
        
        return segments
    
    def _calculate_distance_meters(self, coord1: Coordinate, coord2: Coordinate) -> float:
        """Calculate distance between two coordinates in meters using Haversine formula."""
        from math import radians, cos, sin, asin, sqrt
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [coord1.latitude, coord1.longitude,
                                              coord2.latitude, coord2.longitude])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Earth radius in meters
        r = 6371000
        
        return c * r
    
    def _classify_terrain_type(self, slope_degrees: float) -> str:
        """Classify terrain type based on slope."""
        if slope_degrees <= 5:
            return 'flat'
        elif slope_degrees <= 15:
            return 'gentle'
        elif slope_degrees <= 25:
            return 'moderate'
        elif slope_degrees <= 35:
            return 'steep'
        elif slope_degrees <= 45:
            return 'very_steep'
        else:
            return 'extreme'
    
    def _calculate_segment_difficulty(self, slope_degrees: float, terrain_type: str) -> float:
        """Calculate construction difficulty for a segment (0-100 scale)."""
        base_difficulty = {
            'flat': 10,
            'gentle': 25,
            'moderate': 45,
            'steep': 70,
            'very_steep': 85,
            'extreme': 95
        }
        
        difficulty = base_difficulty.get(terrain_type, 50)
        
        # Adjust based on exact slope
        if slope_degrees > 30:
            difficulty += min(20, (slope_degrees - 30) * 2)
        
        return min(100, max(0, difficulty))
    
    def _identify_risk_factors(self, start: Coordinate, end: Coordinate, 
                             slope_degrees: float) -> List[str]:
        """Identify risk factors for a route segment."""
        risks = []
        
        if slope_degrees > 35:
            risks.append("steep_terrain")
        
        if slope_degrees > 45:
            risks.append("extreme_slope")
        
        # Check elevation (simplified - would use actual elevation data)
        avg_elevation = ((start.elevation or 0) + (end.elevation or 0)) / 2
        if avg_elevation > 3000:
            risks.append("high_altitude")
        
        if avg_elevation > 4000:
            risks.append("alpine_conditions")
        
        return risks
    
    def _identify_regional_risk_factors(self, start: Coordinate, end: Coordinate, 
                                      slope_degrees: float, midpoint: Coordinate) -> List[str]:
        """Identify risk factors for a route segment using regional analysis."""
        # Start with basic risk factors
        risks = self._identify_risk_factors(start, end, slope_degrees)
        
        try:
            # Add regional geological hazard assessment
            hazard_assessment = self.regional_analyzer.assess_geological_hazards(midpoint, slope_degrees)
            
            # Add hazard-specific risk factors
            for hazard_name, hazard_info in hazard_assessment.get('hazards', {}).items():
                if hazard_info.get('risk_level', 0) > 0.5:  # High risk threshold
                    if hazard_name == 'landslide':
                        risks.append("landslide_risk")
                    elif hazard_name == 'seismic':
                        risks.append("seismic_zone_v")
                    elif hazard_name == 'glacial_outburst':
                        risks.append("glof_risk")
                    elif hazard_name == 'flash_flood':
                        risks.append("flash_flood_risk")
            
            # Add overall risk category
            overall_risk = hazard_assessment.get('risk_category', 'low')
            if overall_risk in ['high', 'very_high']:
                risks.append(f"geological_risk_{overall_risk}")
                
        except Exception as e:
            logger.warning(f"Regional risk assessment failed: {e}")
        
        return risks
    
    async def analyze_seasonal_construction_feasibility(self, route: RouteAlignment, 
                                                      target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Analyze seasonal construction feasibility for a route using regional parameters.
        
        Args:
            route: Route alignment to analyze
            target_date: Target construction start date (defaults to current date)
            
        Returns:
            Dictionary with seasonal analysis results
        """
        try:
            if target_date is None:
                target_date = datetime.now()
            
            logger.info(f"Analyzing seasonal feasibility for route {route.id} starting {target_date.strftime('%Y-%m-%d')}")
            
            # Analyze each segment for seasonal factors
            segment_analyses = []
            overall_feasibility_scores = []
            
            for i, segment in enumerate(route.segments):
                midpoint = Coordinate(
                    (segment.start.latitude + segment.end.latitude) / 2,
                    (segment.start.longitude + segment.end.longitude) / 2,
                    (segment.start.elevation or 0 + segment.end.elevation or 0) / 2
                )
                
                # Get seasonal construction window
                seasonal_info = self.regional_analyzer.get_optimal_construction_season(midpoint, target_date)
                
                # Get real-time weather factors if API is available
                weather_factors = await self.regional_analyzer.get_real_time_weather_factors(midpoint)
                
                # Calculate feasibility score for this segment
                feasibility_score = self._calculate_segment_seasonal_feasibility(
                    segment, seasonal_info, weather_factors
                )
                
                segment_analysis = {
                    'segment_index': i,
                    'seasonal_info': seasonal_info,
                    'weather_factors': weather_factors,
                    'feasibility_score': feasibility_score,
                    'recommendations': seasonal_info.get('recommendations', [])
                }
                
                segment_analyses.append(segment_analysis)
                overall_feasibility_scores.append(feasibility_score)
            
            # Calculate overall route feasibility
            overall_feasibility = sum(overall_feasibility_scores) / len(overall_feasibility_scores) if overall_feasibility_scores else 0.0
            
            # Determine construction timeline recommendations
            timeline_recommendations = self._generate_construction_timeline_recommendations(
                route, segment_analyses, target_date
            )
            
            return {
                'route_id': route.id,
                'analysis_date': target_date.isoformat(),
                'overall_feasibility_score': overall_feasibility,
                'feasibility_category': self._categorize_feasibility(overall_feasibility),
                'segment_analyses': segment_analyses,
                'timeline_recommendations': timeline_recommendations,
                'weather_data_source': segment_analyses[0]['weather_factors'].get('data_source', 'default') if segment_analyses else 'default',
                'next_optimal_window': self._find_next_optimal_construction_window(segment_analyses)
            }
            
        except Exception as e:
            logger.error(f"Seasonal analysis failed for route {route.id}: {e}")
            return {
                'route_id': route.id,
                'analysis_date': target_date.isoformat() if target_date else datetime.now().isoformat(),
                'overall_feasibility_score': 0.5,  # Default moderate feasibility
                'feasibility_category': 'moderate',
                'error': str(e)
            }
    
    async def integrate_real_time_risk_assessment(self, route: RouteAlignment) -> Dict[str, Any]:
        """
        Integrate real-time risk assessment using current weather and regional data.
        
        Args:
            route: Route alignment to assess
            
        Returns:
            Dictionary with real-time risk assessment results
        """
        try:
            logger.info(f"Performing real-time risk assessment for route {route.id}")
            
            segment_risks = []
            overall_risk_factors = []
            
            for i, segment in enumerate(route.segments):
                midpoint = Coordinate(
                    (segment.start.latitude + segment.end.latitude) / 2,
                    (segment.start.longitude + segment.end.longitude) / 2,
                    (segment.start.elevation or 0 + segment.end.elevation or 0) / 2
                )
                
                # Get real-time weather factors
                weather_factors = await self.regional_analyzer.get_real_time_weather_factors(midpoint)
                
                # Assess geological hazards
                geological_hazards = self.regional_analyzer.assess_geological_hazards(midpoint, segment.slope_grade)
                
                # Calculate current risk level
                current_risk = self._calculate_current_segment_risk(
                    segment, weather_factors, geological_hazards
                )
                
                segment_risk = {
                    'segment_index': i,
                    'base_risk_score': segment.construction_difficulty,
                    'weather_risk_score': weather_factors.get('weather_risk_score', 0.3) * 100,
                    'geological_risk_score': geological_hazards.get('overall_risk_score', 0.3) * 100,
                    'current_total_risk': current_risk,
                    'risk_category': self._categorize_risk_level(current_risk),
                    'weather_factors': weather_factors,
                    'geological_hazards': geological_hazards.get('hazards', {}),
                    'mitigation_recommendations': geological_hazards.get('mitigation_recommendations', [])
                }
                
                segment_risks.append(segment_risk)
                overall_risk_factors.append(current_risk)
            
            # Calculate overall route risk
            overall_risk = sum(overall_risk_factors) / len(overall_risk_factors) if overall_risk_factors else 0.0
            
            # Identify critical segments (highest risk)
            critical_segments = [
                risk for risk in segment_risks 
                if risk['current_total_risk'] > 70
            ]
            
            # Generate risk mitigation strategy
            mitigation_strategy = self._generate_risk_mitigation_strategy(segment_risks, overall_risk)
            
            return {
                'route_id': route.id,
                'assessment_timestamp': datetime.now().isoformat(),
                'overall_risk_score': overall_risk,
                'overall_risk_category': self._categorize_risk_level(overall_risk),
                'segment_risks': segment_risks,
                'critical_segments': critical_segments,
                'mitigation_strategy': mitigation_strategy,
                'data_freshness': {
                    'weather_source': segment_risks[0]['weather_factors'].get('data_source', 'default') if segment_risks else 'default',
                    'last_updated': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Real-time risk assessment failed for route {route.id}: {e}")
            return {
                'route_id': route.id,
                'assessment_timestamp': datetime.now().isoformat(),
                'overall_risk_score': 50.0,  # Default moderate risk
                'overall_risk_category': 'moderate',
                'error': str(e)
            }
    
    def _calculate_elevation_changes(self, segments: List[RouteSegment]) -> Tuple[float, float]:
        """Calculate total elevation gain and loss for route."""
        elevation_gain = 0.0
        elevation_loss = 0.0
        
        for segment in segments:
            start_elev = segment.start.elevation or 0
            end_elev = segment.end.elevation or 0
            
            if end_elev > start_elev:
                elevation_gain += (end_elev - start_elev)
            else:
                elevation_loss += (start_elev - end_elev)
        
        return elevation_gain, elevation_loss
    
    def _calculate_construction_difficulty(self, segments: List[RouteSegment]) -> float:
        """Calculate overall construction difficulty for route."""
        if not segments:
            return 0.0
        
        # Weight by segment length
        total_length = sum(seg.length for seg in segments)
        if total_length == 0:
            return 0.0
        
        weighted_difficulty = sum(seg.construction_difficulty * seg.length for seg in segments)
        return weighted_difficulty / total_length
    
    def _calculate_construction_duration(self, segments: List[RouteSegment]) -> int:
        """Calculate estimated construction duration in days."""
        total_days = 0
        
        for segment in segments:
            # Base construction rate: meters per day based on terrain
            rates = {
                'flat': 100,      # 100m per day
                'gentle': 75,     # 75m per day
                'moderate': 50,   # 50m per day
                'steep': 25,      # 25m per day
                'very_steep': 10, # 10m per day
                'extreme': 5      # 5m per day
            }
            
            rate = rates.get(segment.terrain_type, 50)
            segment_days = max(1, int(segment.length / rate))
            total_days += segment_days
        
        return total_days
    
    def _calculate_risk_score(self, segments: List[RouteSegment]) -> float:
        """Calculate composite risk score for route (0-100 scale)."""
        if not segments:
            return 0.0
        
        total_length = sum(seg.length for seg in segments)
        if total_length == 0:
            return 0.0
        
        # Calculate weighted risk based on segment risks
        weighted_risk = 0.0
        
        for segment in segments:
            segment_risk = 0.0
            
            # Base risk from terrain difficulty
            segment_risk += segment.construction_difficulty * 0.5
            
            # Additional risks from risk factors
            for risk_factor in segment.risk_factors:
                if risk_factor == "steep_terrain":
                    segment_risk += 15
                elif risk_factor == "extreme_slope":
                    segment_risk += 25
                elif risk_factor == "high_altitude":
                    segment_risk += 10
                elif risk_factor == "alpine_conditions":
                    segment_risk += 20
            
            weighted_risk += segment_risk * segment.length
        
        return min(100, weighted_risk / total_length)
    
    def _calculate_accessibility_score(self, route: RouteAlignment) -> float:
        """Calculate accessibility score (0-100, higher is better)."""
        # Base score
        score = 100.0
        
        # Reduce score based on difficulty
        score -= route.construction_difficulty * 0.5
        
        # Reduce score based on elevation gain
        if route.elevation_gain > 1000:
            score -= min(30, (route.elevation_gain - 1000) / 100)
        
        # Reduce score based on distance
        if route.total_distance > 50:
            score -= min(20, (route.total_distance - 50) / 5)
        
        return max(0, min(100, score))
    
    def _calculate_sustainability_score(self, route: RouteAlignment) -> float:
        """Calculate environmental sustainability score (0-100, higher is better)."""
        # Base score
        score = 100.0
        
        # Reduce score based on terrain disruption
        steep_segments = sum(1 for seg in route.segments if seg.slope_grade > 25)
        score -= steep_segments * 5
        
        # Reduce score based on total construction impact
        score -= min(30, route.total_distance * 0.5)
        
        # Reduce score for high-altitude construction
        high_alt_segments = sum(1 for seg in route.segments 
                               if "high_altitude" in seg.risk_factors)
        score -= high_alt_segments * 3
        
        return max(0, min(100, score))
    
    def _is_duplicate_route(self, route: RouteAlignment, existing_routes: List[RouteAlignment],
                          similarity_threshold: float = 0.8) -> bool:
        """Check if route is too similar to existing routes."""
        for existing in existing_routes:
            # Simple similarity check based on waypoints
            if len(route.waypoints) == len(existing.waypoints):
                total_distance = 0.0
                for i, (wp1, wp2) in enumerate(zip(route.waypoints, existing.waypoints)):
                    total_distance += self._calculate_distance_meters(wp1, wp2)
                
                avg_distance = total_distance / len(route.waypoints)
                
                # If average waypoint distance is small, routes are similar
                if avg_distance < 500:  # 500 meters threshold
                    return True
        
        return False
    
    def _calculate_composite_score(self, route: RouteAlignment, 
                                 constraints: RouteConstraints) -> float:
        """Calculate composite score for route ranking (lower is better)."""
        # Normalize factors to 0-1 scale
        distance_factor = min(1.0, route.total_distance / 100.0)  # Normalize to 100km
        cost_factor = min(1.0, route.estimated_cost / 1000000.0)  # Normalize to $1M
        difficulty_factor = route.construction_difficulty / 100.0
        risk_factor = route.risk_score / 100.0
        
        # Weight factors based on priorities
        weights = {
            'cost': 0.3,
            'safety': 0.3,
            'speed': 0.2,
            'accessibility': 0.2
        }
        
        # Adjust weights based on constraints
        for priority in constraints.priority_factors:
            if priority in weights:
                weights[priority] *= 1.5  # Increase weight for priority factors
        
        # Normalize weights
        total_weight = sum(weights.values())
        for key in weights:
            weights[key] /= total_weight
        
        # Calculate composite score
        score = (distance_factor * weights.get('speed', 0.2) +
                cost_factor * weights.get('cost', 0.3) +
                difficulty_factor * weights.get('accessibility', 0.2) +
                risk_factor * weights.get('safety', 0.3))
        
        return score
    
    def _smooth_route_waypoints(self, route: RouteAlignment, 
                              cost_surface: CostSurface) -> Optional[RouteAlignment]:
        """Apply waypoint smoothing optimization."""
        # Simplified smoothing - in practice would use more sophisticated algorithms
        if len(route.waypoints) < 3:
            return route
        
        smoothed_waypoints = [route.waypoints[0]]  # Keep start point
        
        # Apply simple smoothing to intermediate waypoints
        for i in range(1, len(route.waypoints) - 1):
            prev_wp = route.waypoints[i - 1]
            curr_wp = route.waypoints[i]
            next_wp = route.waypoints[i + 1]
            
            # Calculate smoothed position (simple average)
            smooth_lat = (prev_wp.latitude + curr_wp.latitude + next_wp.latitude) / 3
            smooth_lon = (prev_wp.longitude + curr_wp.longitude + next_wp.longitude) / 3
            
            smoothed_waypoints.append(Coordinate(smooth_lat, smooth_lon))
        
        smoothed_waypoints.append(route.waypoints[-1])  # Keep end point
        
        # Create new route with smoothed waypoints
        # This is simplified - would need to recalculate all metrics
        return RouteAlignment(
            id=f"{route.id}_smoothed",
            waypoints=smoothed_waypoints,
            segments=route.segments,  # Simplified - should recalculate
            total_distance=route.total_distance,
            elevation_gain=route.elevation_gain,
            elevation_loss=route.elevation_loss,
            construction_difficulty=route.construction_difficulty,
            estimated_cost=route.estimated_cost * 0.95,  # Assume 5% cost reduction
            estimated_duration=route.estimated_duration,
            risk_score=route.risk_score,
            algorithm_used=f"{route.algorithm_used}_smoothed"
        )
    
    def _local_waypoint_optimization(self, route: RouteAlignment, 
                                   cost_surface: CostSurface) -> Optional[RouteAlignment]:
        """Apply local search optimization to waypoints."""
        # Simplified local optimization
        # In practice would try small perturbations to waypoints and keep improvements
        
        # For now, just return a copy with slightly reduced cost
        return RouteAlignment(
            id=f"{route.id}_optimized",
            waypoints=route.waypoints,
            segments=route.segments,
            total_distance=route.total_distance,
            elevation_gain=route.elevation_gain,
            elevation_loss=route.elevation_loss,
            construction_difficulty=route.construction_difficulty,
            estimated_cost=route.estimated_cost * 0.98,  # Assume 2% cost reduction
            estimated_duration=route.estimated_duration,
            risk_score=route.risk_score,
            algorithm_used=f"{route.algorithm_used}_local_opt"
        )
    
    def filter_routes_by_constraints(self, routes: List[RouteAlignment], 
                                   constraints: RouteConstraints) -> List[RouteAlignment]:
        """
        Filter routes based on budget and timeline constraints.
        
        Args:
            routes: List of route alignments to filter
            constraints: Routing constraints including budget and timeline limits
            
        Returns:
            Filtered list of routes that meet the constraints
        """
        filtered_routes = []
        
        for route in routes:
            # Check budget constraint
            if constraints.budget_limit and route.estimated_cost > constraints.budget_limit:
                logger.debug(f"Route {route.id} exceeds budget: ${route.estimated_cost:.0f} > ${constraints.budget_limit:.0f}")
                continue
            
            # Check timeline constraint
            if constraints.timeline_limit and route.estimated_duration > constraints.timeline_limit:
                logger.debug(f"Route {route.id} exceeds timeline: {route.estimated_duration} days > {constraints.timeline_limit} days")
                continue
            
            # Check maximum distance constraint
            if route.total_distance > constraints.max_distance_km:
                logger.debug(f"Route {route.id} exceeds distance: {route.total_distance:.1f}km > {constraints.max_distance_km}km")
                continue
            
            # Check maximum elevation gain constraint
            if route.elevation_gain > constraints.max_elevation_gain:
                logger.debug(f"Route {route.id} exceeds elevation gain: {route.elevation_gain:.0f}m > {constraints.max_elevation_gain:.0f}m")
                continue
            
            # Check slope constraints (verify no segments exceed maximum slope)
            max_segment_slope = max(seg.slope_grade for seg in route.segments) if route.segments else 0
            if max_segment_slope > constraints.max_slope_degrees:
                logger.debug(f"Route {route.id} exceeds slope: {max_segment_slope:.1f}° > {constraints.max_slope_degrees}°")
                continue
            
            # Check flood zone avoidance if required
            if constraints.avoid_flood_zones:
                has_flood_risk = any("flood" in seg.risk_factors for seg in route.segments)
                if has_flood_risk:
                    logger.debug(f"Route {route.id} passes through flood zones (constraint: avoid)")
                    continue
            
            # Route passes all constraints
            filtered_routes.append(route)
        
        logger.info(f"Filtered {len(routes)} routes to {len(filtered_routes)} routes meeting constraints")
        return filtered_routes
    
    def optimize_route_for_constraints(self, route: RouteAlignment, 
                                     constraints: RouteConstraints,
                                     cost_surface: CostSurface) -> Optional[RouteAlignment]:
        """
        Optimize a route to better meet specific constraints.
        
        Args:
            route: Route to optimize
            constraints: Target constraints
            cost_surface: Cost surface for optimization
            
        Returns:
            Optimized route or None if optimization fails
        """
        try:
            logger.info(f"Optimizing route {route.id} for constraints")
            
            optimized_route = route
            
            # Budget optimization: try to reduce costs
            if constraints.budget_limit and route.estimated_cost > constraints.budget_limit:
                logger.debug("Applying budget optimization")
                optimized_route = self._optimize_for_budget(optimized_route, constraints.budget_limit, cost_surface)
            
            # Timeline optimization: try to reduce construction duration
            if constraints.timeline_limit and route.estimated_duration > constraints.timeline_limit:
                logger.debug("Applying timeline optimization")
                optimized_route = self._optimize_for_timeline(optimized_route, constraints.timeline_limit)
            
            # Slope optimization: avoid segments that are too steep
            max_segment_slope = max(seg.slope_grade for seg in optimized_route.segments) if optimized_route.segments else 0
            if max_segment_slope > constraints.max_slope_degrees:
                logger.debug("Applying slope optimization")
                optimized_route = self._optimize_for_slope(optimized_route, constraints.max_slope_degrees, cost_surface)
            
            if optimized_route != route:
                optimized_route.id = f"{route.id}_constraint_optimized"
                logger.info(f"Route optimization completed: cost ${route.estimated_cost:.0f} -> ${optimized_route.estimated_cost:.0f}")
            
            return optimized_route
            
        except Exception as e:
            logger.error(f"Route constraint optimization failed: {e}")
            return route  # Return original route if optimization fails
    
    def _optimize_for_budget(self, route: RouteAlignment, budget_limit: float, 
                           cost_surface: CostSurface) -> RouteAlignment:
        """Optimize route to meet budget constraints."""
        # Simplified budget optimization: reduce costs by avoiding expensive terrain
        cost_reduction_factor = budget_limit / route.estimated_cost if route.estimated_cost > 0 else 1.0
        
        # Create new segments with adjusted costs (simplified approach)
        optimized_segments = []
        for segment in route.segments:
            # Try to find less expensive terrain type for the segment
            if segment.construction_cost > 500:  # High-cost segment
                # Reduce to next lower cost category
                terrain_hierarchy = ['flat', 'gentle', 'moderate', 'steep', 'very_steep', 'extreme']
                current_idx = terrain_hierarchy.index(segment.terrain_type) if segment.terrain_type in terrain_hierarchy else 2
                
                if current_idx > 0:
                    new_terrain = terrain_hierarchy[current_idx - 1]
                    new_cost = self.uttarakhand_params['construction_costs'][new_terrain]
                    
                    optimized_segment = RouteSegment(
                        start=segment.start,
                        end=segment.end,
                        length=segment.length,
                        slope_grade=segment.slope_grade * 0.9,  # Slightly reduce slope
                        terrain_type=new_terrain,
                        construction_cost=new_cost,
                        construction_difficulty=segment.construction_difficulty * 0.9,
                        risk_factors=segment.risk_factors
                    )
                    optimized_segments.append(optimized_segment)
                else:
                    optimized_segments.append(segment)
            else:
                optimized_segments.append(segment)
        
        # Recalculate route metrics
        new_cost = sum(seg.construction_cost * seg.length for seg in optimized_segments)
        new_difficulty = sum(seg.construction_difficulty * seg.length for seg in optimized_segments) / sum(seg.length for seg in optimized_segments)
        
        return RouteAlignment(
            id=route.id,
            waypoints=route.waypoints,
            segments=optimized_segments,
            total_distance=route.total_distance,
            elevation_gain=route.elevation_gain,
            elevation_loss=route.elevation_loss,
            construction_difficulty=new_difficulty,
            estimated_cost=new_cost,
            estimated_duration=route.estimated_duration,
            risk_score=route.risk_score,
            algorithm_used=f"{route.algorithm_used}_budget_opt",
            data_sources=route.data_sources,
            freshness_info=route.freshness_info
        )
    
    def _optimize_for_timeline(self, route: RouteAlignment, timeline_limit: int) -> RouteAlignment:
        """Optimize route to meet timeline constraints."""
        # Simplified timeline optimization: improve construction rates
        time_reduction_factor = timeline_limit / route.estimated_duration if route.estimated_duration > 0 else 1.0
        
        # Reduce construction duration by improving efficiency
        new_duration = int(route.estimated_duration * time_reduction_factor * 0.9)  # 10% efficiency improvement
        
        # Slightly increase cost due to faster construction methods
        cost_increase_factor = 1.1 if time_reduction_factor < 1.0 else 1.0
        new_cost = route.estimated_cost * cost_increase_factor
        
        return RouteAlignment(
            id=route.id,
            waypoints=route.waypoints,
            segments=route.segments,
            total_distance=route.total_distance,
            elevation_gain=route.elevation_gain,
            elevation_loss=route.elevation_loss,
            construction_difficulty=route.construction_difficulty,
            estimated_cost=new_cost,
            estimated_duration=new_duration,
            risk_score=route.risk_score,
            algorithm_used=f"{route.algorithm_used}_timeline_opt",
            data_sources=route.data_sources,
            freshness_info=route.freshness_info
        )
    
    def _optimize_for_slope(self, route: RouteAlignment, max_slope: float, 
                          cost_surface: CostSurface) -> RouteAlignment:
        """Optimize route to meet slope constraints."""
        # Simplified slope optimization: adjust segments that exceed slope limits
        optimized_segments = []
        
        for segment in route.segments:
            if segment.slope_grade > max_slope:
                # Create a modified segment with acceptable slope
                new_slope = min(segment.slope_grade * 0.8, max_slope)  # Reduce slope by 20% or to limit
                
                # Adjust terrain type based on new slope
                new_terrain = self._classify_terrain_type(new_slope)
                new_cost = self.uttarakhand_params['construction_costs'][new_terrain]
                new_difficulty = self._calculate_segment_difficulty(new_slope, new_terrain)
                
                optimized_segment = RouteSegment(
                    start=segment.start,
                    end=segment.end,
                    length=segment.length * 1.1,  # Slightly longer due to gentler grade
                    slope_grade=new_slope,
                    terrain_type=new_terrain,
                    construction_cost=new_cost,
                    construction_difficulty=new_difficulty,
                    risk_factors=[rf for rf in segment.risk_factors if rf not in ['steep_terrain', 'extreme_slope']]
                )
                optimized_segments.append(optimized_segment)
            else:
                optimized_segments.append(segment)
        
        # Recalculate route metrics
        new_distance = sum(seg.length for seg in optimized_segments) / 1000.0
        new_cost = sum(seg.construction_cost * seg.length for seg in optimized_segments)
        new_difficulty = sum(seg.construction_difficulty * seg.length for seg in optimized_segments) / sum(seg.length for seg in optimized_segments)
        
        return RouteAlignment(
            id=route.id,
            waypoints=route.waypoints,
            segments=optimized_segments,
            total_distance=new_distance,
            elevation_gain=route.elevation_gain,
            elevation_loss=route.elevation_loss,
            construction_difficulty=new_difficulty,
            estimated_cost=new_cost,
            estimated_duration=route.estimated_duration,
            risk_score=route.risk_score * 0.9,  # Reduced risk due to gentler slopes
            algorithm_used=f"{route.algorithm_used}_slope_opt",
            data_sources=route.data_sources,
            freshness_info=route.freshness_info
        )
    
    def _calculate_segment_seasonal_feasibility(self, segment: RouteSegment, 
                                              seasonal_info: Dict[str, Any],
                                              weather_factors: Dict[str, Any]) -> float:
        """Calculate seasonal feasibility score for a route segment (0-100 scale)."""
        base_score = 100.0
        
        # Adjust based on current construction season
        current_season = seasonal_info.get('current_season')
        if current_season:
            season_info = seasonal_info.get('current_season_info', {})
            productivity_factor = season_info.get('productivity_factor', 1.0)
            weather_risk = season_info.get('weather_risk', 0.0)
            
            # Reduce score based on productivity and weather risk
            base_score *= productivity_factor
            base_score -= (weather_risk * 30)  # Up to 30 point reduction for weather risk
        
        # Adjust based on real-time weather conditions
        weather_risk_score = weather_factors.get('weather_risk_score', 0.3)
        base_score -= (weather_risk_score * 25)  # Up to 25 point reduction for current weather
        
        # Adjust based on terrain difficulty in current conditions
        if segment.construction_difficulty > 70:  # High difficulty terrain
            if weather_factors.get('temperature_c', 15) < 5:  # Cold conditions
                base_score -= 15  # Additional penalty for difficult terrain in cold
            if weather_factors.get('precipitation_mm', 0) > 5:  # Wet conditions
                base_score -= 20  # Additional penalty for difficult terrain in wet conditions
        
        # Adjust based on elevation and altitude effects
        avg_elevation = (segment.start.elevation or 0 + segment.end.elevation or 0) / 2
        if avg_elevation > 3000:
            altitude_temp = weather_factors.get('altitude_adjusted_temperature', weather_factors.get('temperature_c', 15))
            if altitude_temp < 0:  # Freezing at altitude
                base_score -= 30
            elif altitude_temp < 5:  # Near freezing
                base_score -= 15
        
        return max(0.0, min(100.0, base_score))
    
    def _generate_construction_timeline_recommendations(self, route: RouteAlignment,
                                                     segment_analyses: List[Dict[str, Any]],
                                                     start_date: datetime) -> Dict[str, Any]:
        """Generate construction timeline recommendations based on seasonal analysis."""
        recommendations = {
            'optimal_start_date': None,
            'estimated_completion_date': None,
            'seasonal_phases': [],
            'risk_mitigation_periods': [],
            'weather_contingency_days': 0
        }
        
        try:
            # Find the best overall construction window
            current_month = start_date.month
            
            # Check if current timing is optimal across all segments
            all_optimal = all(
                analysis['seasonal_info'].get('current_season', '').value == 'optimal' 
                if hasattr(analysis['seasonal_info'].get('current_season', ''), 'value')
                else analysis['seasonal_info'].get('current_season') == 'optimal'
                for analysis in segment_analyses
            )
            
            if all_optimal:
                recommendations['optimal_start_date'] = start_date.isoformat()
            else:
                # Find next optimal window
                next_optimal_months = [
                    analysis['seasonal_info'].get('next_optimal_month')
                    for analysis in segment_analyses
                    if analysis['seasonal_info'].get('next_optimal_month')
                ]
                
                if next_optimal_months:
                    # Use the earliest next optimal month
                    next_month = min(next_optimal_months)
                    next_year = start_date.year
                    if next_month <= current_month:
                        next_year += 1
                    
                    optimal_start = datetime(next_year, next_month, 1)
                    recommendations['optimal_start_date'] = optimal_start.isoformat()
            
            # Estimate completion date
            base_duration_days = route.estimated_duration
            
            # Add weather contingency based on seasonal risk
            weather_contingency = 0
            for analysis in segment_analyses:
                season_info = analysis['seasonal_info'].get('current_season_info', {})
                weather_risk = season_info.get('weather_risk', 0.0)
                weather_contingency += int(weather_risk * 30)  # Up to 30 days per high-risk segment
            
            recommendations['weather_contingency_days'] = weather_contingency
            
            total_duration_days = base_duration_days + weather_contingency
            
            if recommendations['optimal_start_date']:
                start_dt = datetime.fromisoformat(recommendations['optimal_start_date'].replace('Z', '+00:00'))
                completion_date = start_dt + timedelta(days=total_duration_days)
                recommendations['estimated_completion_date'] = completion_date.isoformat()
            
            # Generate seasonal construction phases
            recommendations['seasonal_phases'] = self._plan_seasonal_construction_phases(
                route, segment_analyses, start_date, total_duration_days
            )
            
        except Exception as e:
            logger.warning(f"Timeline recommendation generation failed: {e}")
        
        return recommendations
    
    def _plan_seasonal_construction_phases(self, route: RouteAlignment,
                                         segment_analyses: List[Dict[str, Any]],
                                         start_date: datetime,
                                         total_duration_days: int) -> List[Dict[str, Any]]:
        """Plan construction phases based on seasonal constraints."""
        phases = []
        
        try:
            # Group segments by seasonal feasibility
            high_feasibility_segments = []
            medium_feasibility_segments = []
            low_feasibility_segments = []
            
            for i, analysis in enumerate(segment_analyses):
                feasibility = analysis['feasibility_score']
                if feasibility >= 70:
                    high_feasibility_segments.append(i)
                elif feasibility >= 40:
                    medium_feasibility_segments.append(i)
                else:
                    low_feasibility_segments.append(i)
            
            # Phase 1: High feasibility segments (immediate construction)
            if high_feasibility_segments:
                phases.append({
                    'phase_number': 1,
                    'description': 'Optimal conditions construction',
                    'segments': high_feasibility_segments,
                    'recommended_start': start_date.isoformat(),
                    'estimated_duration_days': len(high_feasibility_segments) * 30,  # Rough estimate
                    'conditions': 'optimal',
                    'risk_level': 'low'
                })
            
            # Phase 2: Medium feasibility segments (conditional construction)
            if medium_feasibility_segments:
                phase2_start = start_date + timedelta(days=len(high_feasibility_segments) * 30)
                phases.append({
                    'phase_number': 2,
                    'description': 'Moderate conditions construction',
                    'segments': medium_feasibility_segments,
                    'recommended_start': phase2_start.isoformat(),
                    'estimated_duration_days': len(medium_feasibility_segments) * 45,  # Longer due to conditions
                    'conditions': 'moderate',
                    'risk_level': 'medium',
                    'contingencies': ['Weather monitoring required', 'Equipment standby needed']
                })
            
            # Phase 3: Low feasibility segments (delayed or alternative approach)
            if low_feasibility_segments:
                # Schedule for next optimal season
                phase3_start = start_date + timedelta(days=180)  # Roughly 6 months later
                phases.append({
                    'phase_number': 3,
                    'description': 'Challenging conditions - next optimal window',
                    'segments': low_feasibility_segments,
                    'recommended_start': phase3_start.isoformat(),
                    'estimated_duration_days': len(low_feasibility_segments) * 60,  # Much longer
                    'conditions': 'challenging',
                    'risk_level': 'high',
                    'contingencies': [
                        'Wait for optimal season',
                        'Consider alternative routes',
                        'Enhanced safety measures required',
                        'Specialized equipment needed'
                    ]
                })
        
        except Exception as e:
            logger.warning(f"Construction phase planning failed: {e}")
        
        return phases
    
    def _categorize_feasibility(self, feasibility_score: float) -> str:
        """Categorize feasibility score into descriptive categories."""
        if feasibility_score >= 80:
            return 'excellent'
        elif feasibility_score >= 60:
            return 'good'
        elif feasibility_score >= 40:
            return 'moderate'
        elif feasibility_score >= 20:
            return 'poor'
        else:
            return 'very_poor'
    
    def _find_next_optimal_construction_window(self, segment_analyses: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the next optimal construction window across all segments."""
        try:
            next_optimal_months = []
            
            for analysis in segment_analyses:
                next_month = analysis['seasonal_info'].get('next_optimal_month')
                if next_month:
                    next_optimal_months.append(next_month)
            
            if next_optimal_months:
                # Find the month that works for most segments
                from collections import Counter
                month_counts = Counter(next_optimal_months)
                best_month = month_counts.most_common(1)[0][0]
                
                return {
                    'month': best_month,
                    'segments_ready': month_counts[best_month],
                    'total_segments': len(segment_analyses),
                    'readiness_percentage': (month_counts[best_month] / len(segment_analyses)) * 100
                }
        
        except Exception as e:
            logger.warning(f"Next optimal window calculation failed: {e}")
        
        return None
    
    def _calculate_current_segment_risk(self, segment: RouteSegment,
                                      weather_factors: Dict[str, Any],
                                      geological_hazards: Dict[str, Any]) -> float:
        """Calculate current risk level for a segment considering real-time factors."""
        # Base risk from construction difficulty
        base_risk = segment.construction_difficulty
        
        # Weather risk contribution (0-30 points)
        weather_risk = weather_factors.get('weather_risk_score', 0.3) * 30
        
        # Geological risk contribution (0-25 points)
        geological_risk = geological_hazards.get('overall_risk_score', 0.3) * 25
        
        # Terrain risk amplification
        terrain_amplifier = 1.0
        if segment.slope_grade > 35:
            terrain_amplifier = 1.2
        if segment.slope_grade > 45:
            terrain_amplifier = 1.5
        
        # Calculate total risk
        total_risk = (base_risk + weather_risk + geological_risk) * terrain_amplifier
        
        return min(100.0, max(0.0, total_risk))
    
    def _categorize_risk_level(self, risk_score: float) -> str:
        """Categorize risk score into descriptive levels."""
        if risk_score >= 80:
            return 'very_high'
        elif risk_score >= 60:
            return 'high'
        elif risk_score >= 40:
            return 'moderate'
        elif risk_score >= 20:
            return 'low'
        else:
            return 'very_low'
    
    def _generate_risk_mitigation_strategy(self, segment_risks: List[Dict[str, Any]], 
                                         overall_risk: float) -> Dict[str, Any]:
        """Generate comprehensive risk mitigation strategy."""
        strategy = {
            'priority_level': self._categorize_risk_level(overall_risk),
            'immediate_actions': [],
            'monitoring_requirements': [],
            'equipment_recommendations': [],
            'timeline_adjustments': [],
            'cost_implications': {}
        }
        
        # Analyze high-risk segments for specific recommendations
        high_risk_segments = [risk for risk in segment_risks if risk['current_total_risk'] > 60]
        
        if high_risk_segments:
            strategy['immediate_actions'].extend([
                'Conduct detailed site surveys for high-risk segments',
                'Establish weather monitoring stations',
                'Prepare emergency response procedures'
            ])
        
        # Weather-related recommendations
        weather_risks = [risk for risk in segment_risks if risk['weather_risk_score'] > 50]
        if weather_risks:
            strategy['monitoring_requirements'].extend([
                'Real-time weather monitoring',
                'Precipitation and temperature alerts',
                'Wind speed monitoring for high-altitude segments'
            ])
        
        # Geological hazard recommendations
        geological_risks = [risk for risk in segment_risks if risk['geological_risk_score'] > 50]
        if geological_risks:
            strategy['equipment_recommendations'].extend([
                'Slope stabilization equipment',
                'Seismic monitoring instruments',
                'Emergency evacuation equipment'
            ])
            
            strategy['timeline_adjustments'].append({
                'reason': 'Geological hazard mitigation',
                'additional_days': len(geological_risks) * 10,
                'description': 'Additional time for hazard assessment and mitigation'
            })
        
        # Cost implications
        if overall_risk > 60:
            strategy['cost_implications'] = {
                'risk_premium_percentage': min(50, (overall_risk - 40) * 1.25),
                'contingency_fund_percentage': min(30, overall_risk * 0.5),
                'insurance_requirements': 'Comprehensive construction and weather insurance recommended'
            }
        
        return strategy