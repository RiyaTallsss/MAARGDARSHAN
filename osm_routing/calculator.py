"""
Route Calculator

Implements graph-based pathfinding with multiple optimization criteria.
"""

import math
import logging
from typing import Optional, List, Tuple, Callable
from .models import RoadNetwork, RoadNode, RoadEdge, Route, RouteSegment

logger = logging.getLogger(__name__)


class RouteCalculator:
    """Calculator for optimal routes using graph algorithms"""
    
    def __init__(self, network: RoadNetwork):
        """
        Initialize with road network
        
        Args:
            network: RoadNetwork graph
        """
        self.network = network
        
        # Build spatial index if not already built
        if self.network.spatial_index is None:
            logger.info("Building spatial index...")
            self.network.build_spatial_index()
            logger.info(f"Spatial index built with {len(self.network.nodes)} nodes")
    
    def find_snap_point(self, lat: float, lon: float, max_distance_m: float = 2000) -> Optional[RoadNode]:
            """
            Find nearest road node within max_distance

            Args:
                lat: Latitude
                lon: Longitude
                max_distance_m: Maximum snap distance in meters (default 2000m for sparse networks)

            Returns:
                Nearest RoadNode or None if too far
            """
            if self.network.spatial_index is None:
                logger.error("Spatial index not built")
                return None

            if not self.network.nodes:
                logger.error("No nodes in network")
                return None

            # Query KDTree for nearest neighbor
            query_point = [[lat, lon]]  # sklearn expects 2D array
            distance, index = self.network.spatial_index.query(query_point, k=1)
            distance = distance[0][0]  # Extract scalar from nested array
            index = index[0][0]

            # Convert angular distance to meters (approximate)
            distance_m = distance * 111000  # 1 degree ≈ 111km

            logger.debug(f"Nearest node at {distance_m:.1f}m")

            # Check if within threshold
            if distance_m > max_distance_m:
                logger.warning(f"Nearest road is {distance_m:.1f}m away (threshold: {max_distance_m}m)")
                return None

            # Get node ID and return node
            node_id = self.network.node_id_list[index]
            return self.network.nodes[node_id]
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters using Haversine formula"""
        R = 6371000  # Earth radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _heuristic(self, node_id: str, target_node_id: str) -> float:
        """Euclidean distance heuristic for A*"""
        node = self.network.nodes[node_id]
        target = self.network.nodes[target_node_id]
        return self._haversine_distance(node.lat, node.lon, target.lat, target.lon)
    
    def find_path(self, start_node_id: str, end_node_id: str, cost_function: Callable[[RoadEdge], float], timeout_seconds: float = 30.0) -> Optional[List[RoadEdge]]:
        """
        Find optimal path using Bidirectional A* algorithm with timeout
        
        Bidirectional search explores from both start and end simultaneously,
        meeting in the middle. This is much faster for long-distance routing.
        
        Args:
            start_node_id: Starting node ID
            end_node_id: Target node ID
            cost_function: Function that returns cost for an edge
            timeout_seconds: Maximum time to search (default 30s)
            
        Returns:
            List of RoadEdges forming the path, or None if no path exists or timeout
        """
        import heapq
        import time
        
        start_time = time.time()
        
        # Check if nodes exist
        if start_node_id not in self.network.nodes or end_node_id not in self.network.nodes:
            logger.error(f"Start or end node not in network")
            return None
        
        # Handle start == end case
        if start_node_id == end_node_id:
            return []
        
        # Forward search (from start)
        forward_open = [(0, start_node_id)]
        forward_came_from = {}
        forward_g_score = {start_node_id: 0}
        forward_visited = set()
        
        # Backward search (from end)
        backward_open = [(0, end_node_id)]
        backward_came_from = {}
        backward_g_score = {end_node_id: 0}
        backward_visited = set()
        
        # Best path found so far
        best_path_cost = float('inf')
        meeting_node = None
        
        iterations = 0
        last_log_time = start_time
        
        while forward_open and backward_open:
            # Check timeout
            current_time = time.time()
            elapsed = current_time - start_time
            
            if elapsed > timeout_seconds:
                logger.warning(f"Bidirectional A* timed out after {elapsed:.1f}s (forward: {len(forward_visited):,}, backward: {len(backward_visited):,})")
                return None
            
            # Progress logging every 5 seconds
            if current_time - last_log_time > 5.0:
                logger.info(f"Bidirectional A* progress: {elapsed:.1f}s, forward: {len(forward_visited):,}, backward: {len(backward_visited):,}")
                last_log_time = current_time
            
            iterations += 1
            
            # Alternate between forward and backward search
            if iterations % 2 == 0:
                # Forward step
                if not forward_open:
                    continue
                
                current_f, current_node = heapq.heappop(forward_open)
                
                if current_node in forward_visited:
                    continue
                
                forward_visited.add(current_node)
                
                # Check if we've met the backward search
                if current_node in backward_visited:
                    # Found a path! Check if it's better than current best
                    path_cost = forward_g_score[current_node] + backward_g_score[current_node]
                    if path_cost < best_path_cost:
                        best_path_cost = path_cost
                        meeting_node = current_node
                        logger.info(f"Found meeting point at node {meeting_node} with cost {best_path_cost:.1f}")
                
                # Explore neighbors
                for edge in self.network.get_outgoing_edges(current_node):
                    neighbor = edge.target_node_id
                    
                    if neighbor in forward_visited:
                        continue
                    
                    edge_cost = cost_function(edge)
                    tentative_g = forward_g_score[current_node] + edge_cost
                    
                    if neighbor not in forward_g_score or tentative_g < forward_g_score[neighbor]:
                        forward_came_from[neighbor] = (current_node, edge)
                        forward_g_score[neighbor] = tentative_g
                        f = tentative_g + self._heuristic(neighbor, end_node_id)
                        heapq.heappush(forward_open, (f, neighbor))
            
            else:
                # Backward step
                if not backward_open:
                    continue
                
                current_f, current_node = heapq.heappop(backward_open)
                
                if current_node in backward_visited:
                    continue
                
                backward_visited.add(current_node)
                
                # Check if we've met the forward search
                if current_node in forward_visited:
                    path_cost = forward_g_score[current_node] + backward_g_score[current_node]
                    if path_cost < best_path_cost:
                        best_path_cost = path_cost
                        meeting_node = current_node
                        logger.info(f"Found meeting point at node {meeting_node} with cost {best_path_cost:.1f}")
                
                # Explore neighbors (in reverse - incoming edges)
                for edge in self.network.get_incoming_edges(current_node):
                    neighbor = edge.source_node_id
                    
                    if neighbor in backward_visited:
                        continue
                    
                    edge_cost = cost_function(edge)
                    tentative_g = backward_g_score[current_node] + edge_cost
                    
                    if neighbor not in backward_g_score or tentative_g < backward_g_score[neighbor]:
                        backward_came_from[neighbor] = (current_node, edge)
                        backward_g_score[neighbor] = tentative_g
                        f = tentative_g + self._heuristic(neighbor, start_node_id)
                        heapq.heappush(backward_open, (f, neighbor))
            
            # Early termination: if both searches have explored beyond the meeting point
            if meeting_node is not None:
                # Check if we can terminate
                min_forward_f = forward_open[0][0] if forward_open else float('inf')
                min_backward_f = backward_open[0][0] if backward_open else float('inf')
                
                if min_forward_f + min_backward_f >= best_path_cost:
                    # Reconstruct path
                    path = []
                    
                    # Forward path (start to meeting)
                    node = meeting_node
                    forward_path = []
                    while node in forward_came_from:
                        prev_node, edge = forward_came_from[node]
                        forward_path.append(edge)
                        node = prev_node
                    forward_path.reverse()
                    path.extend(forward_path)
                    
                    # Backward path (meeting to end)
                    node = meeting_node
                    while node in backward_came_from:
                        next_node, edge = backward_came_from[node]
                        path.append(edge)
                        node = next_node
                    
                    elapsed = time.time() - start_time
                    logger.info(f"Found path with {len(path)} edges in {elapsed:.1f}s (forward: {len(forward_visited):,}, backward: {len(backward_visited):,})")
                    return path
        
        # No path found
        elapsed = time.time() - start_time
        logger.warning(f"No path found after {elapsed:.1f}s (forward: {len(forward_visited):,}, backward: {len(backward_visited):,})")
        return None
    
    def calculate_routes(self, start: Tuple[float, float], end: Tuple[float, float]) -> List[Route]:
        """
        Calculate 4 routes with different optimization criteria
        
        Args:
            start: (lat, lon) tuple
            end: (lat, lon) tuple
            
        Returns:
            List of 4 Route objects
        """
        # TODO: Implement in Task 8
        raise NotImplementedError("calculate_routes will be implemented in Task 8")
    
    def classify_segments(self, route: Route, network: RoadNetwork) -> Route:
        """
        Classify route segments as new construction or upgrade
        
        Args:
            route: Route to classify
            network: Road network for comparison
            
        Returns:
            Route with classified segments
        """
        # TODO: Implement in Task 10
        raise NotImplementedError("classify_segments will be implemented in Task 10")
    
    def calculate_cost(self, route: Route) -> float:
        """
        Calculate construction cost considering existing roads
        
        Args:
            route: Route with classified segments
            
        Returns:
            Estimated cost in USD
        """
        # TODO: Implement in Task 10
        raise NotImplementedError("calculate_cost will be implemented in Task 10")

    # Cost Functions for Route Optimization
    
    def cost_shortest(self, edge: RoadEdge) -> float:
        """
        Cost function for shortest route - just distance
        
        Args:
            edge: Road edge
            
        Returns:
            Edge distance in meters
        """
        return edge.distance_m
    
    def cost_safest(self, edge: RoadEdge) -> float:
        """
        Cost function for safest route - prefers major roads
        
        Args:
            edge: Road edge
            
        Returns:
            Weighted cost favoring primary/secondary roads
        """
        base_cost = edge.distance_m
        
        # Prefer primary/secondary roads (0.8x cost)
        if edge.highway_type in ['primary', 'secondary']:
            return base_cost * 0.8
        
        # Avoid tracks (1.5x cost)
        elif edge.highway_type == 'track':
            return base_cost * 1.5
        
        # Neutral for tertiary/unclassified
        else:
            return base_cost
    
    def cost_budget(self, edge: RoadEdge) -> float:
        """
        Cost function for budget route - prefers paved surfaces
        
        Args:
            edge: Road edge
            
        Returns:
            Weighted cost favoring paved roads
        """
        base_cost = edge.distance_m
        
        # Prefer paved surfaces (0.7x cost)
        if edge.surface in ['paved', 'asphalt', 'concrete']:
            return base_cost * 0.7
        
        # Neutral for unpaved
        else:
            return base_cost
    
    def cost_social(self, edge: RoadEdge, settlements: List[dict]) -> float:
        """
        Cost function for social impact route - prefers routes near settlements
        
        Args:
            edge: Road edge
            settlements: List of settlement dictionaries with lat/lon
            
        Returns:
            Weighted cost favoring routes near settlements
        """
        base_cost = edge.distance_m
        
        # Check if edge is near any settlement (<1km)
        edge_midpoint_lat = (edge.coordinates[0][1] + edge.coordinates[-1][1]) / 2
        edge_midpoint_lon = (edge.coordinates[0][0] + edge.coordinates[-1][0]) / 2
        
        for settlement in settlements:
            dist = self._haversine_distance(
                edge_midpoint_lat, edge_midpoint_lon,
                settlement['lat'], settlement['lon']
            )
            
            if dist < 1000:  # Within 1km
                return base_cost * 0.6
        
        return base_cost
    
    def calculate_routes(self, start: Tuple[float, float], end: Tuple[float, float], 
                        settlements: Optional[List[dict]] = None) -> List[Route]:
        """
        Calculate 2 routes with different optimization criteria
        
        Args:
            start: (lat, lon) tuple
            end: (lat, lon) tuple
            settlements: Optional list of settlements for social impact route
            
        Returns:
            List of 2 Route objects (Shortest and Safest)
        """
        import time
        start_time = time.time()
        
        # Find snap points
        start_lat, start_lon = start
        end_lat, end_lon = end
        
        start_node = self.find_snap_point(start_lat, start_lon)
        end_node = self.find_snap_point(end_lat, end_lon)
        
        if start_node is None:
            raise ValueError(f"NO_SNAP_POINT_START: No road within 500m of start point")
        
        if end_node is None:
            raise ValueError(f"NO_SNAP_POINT_END: No road within 500m of end point")
        
        logger.info(f"Snapped to nodes: {start_node.id} -> {end_node.id}")
        
        # Calculate 2 most important routes (Shortest and Safest)
        routes = []
        timeout_per_route = 10.0  # 10 seconds per route (total 20s for 2 routes)
        
        # 1. Shortest route
        logger.info("Calculating shortest route...")
        path_edges = self.find_path(start_node.id, end_node.id, self.cost_shortest, timeout_seconds=timeout_per_route)
        if path_edges:
            routes.append(self._create_route("shortest", "Shortest Route", path_edges))
        
        # 2. Safest route
        logger.info("Calculating safest route...")
        path_edges = self.find_path(start_node.id, end_node.id, self.cost_safest, timeout_seconds=timeout_per_route)
        if path_edges:
            routes.append(self._create_route("safest", "Safest Route", path_edges))
        
        elapsed = time.time() - start_time
        logger.info(f"Calculated {len(routes)} routes in {elapsed:.2f}s")
        
        if elapsed > 25:
            logger.warning(f"Route calculation took {elapsed:.2f}s (threshold: 25s)")
        
        if not routes:
            raise ValueError("NO_PATH_EXISTS: No path found between start and end points")
        
        return routes
    
    def _create_route(self, route_id: str, name: str, path_edges: List[RoadEdge]) -> Route:
        """
        Create Route object from path edges
        
        Args:
            route_id: Route identifier
            name: Route name
            path_edges: List of edges forming the path
            
        Returns:
            Route object
        """
        # Create route segments
        segments = []
        total_distance = 0
        
        for edge in path_edges:
            segment = RouteSegment(
                edge_id=edge.id,
                construction_type="new_construction",  # Will be classified later
                distance_m=edge.distance_m,
                cost_factor=1.0,
                road_name=edge.name,
                highway_type=edge.highway_type
            )
            segments.append(segment)
            total_distance += edge.distance_m
        
        # Create waypoints from edges
        waypoints = []
        for edge in path_edges:
            for lon, lat in edge.coordinates:
                waypoints.append({
                    'lat': lat,
                    'lon': lon,
                    'elevation': 0  # Will be populated from DEM later
                })
        
        # Remove duplicate waypoints
        unique_waypoints = []
        for wp in waypoints:
            if not unique_waypoints or (wp['lat'] != unique_waypoints[-1]['lat'] or 
                                       wp['lon'] != unique_waypoints[-1]['lon']):
                unique_waypoints.append(wp)
        
        route = Route(
            id=route_id,
            name=name,
            segments=segments,
            waypoints=unique_waypoints,
            total_distance_km=total_distance / 1000,
            elevation_gain_m=0,  # Will be calculated from DEM
            construction_stats={},
            estimated_cost=0,
            risk_scores={},
            bridges=[],
            settlements=[]
        )
        
        return route

    
    def classify_segments(self, route: Route) -> Route:
        """
        Classify route segments as new construction or upgrade existing
        
        Args:
            route: Route to classify
            
        Returns:
            Route with classified segments and construction stats
        """
        new_construction_km = 0
        upgrade_existing_km = 0
        
        for segment in route.segments:
            # Get the edge from network
            edge = self.network.edges.get(segment.edge_id)
            
            if edge is None:
                # If edge not in network, it's new construction
                segment.construction_type = "new_construction"
                segment.cost_factor = 1.0
                new_construction_km += segment.distance_m / 1000
                continue
            
            # Check if this edge overlaps with existing roads
            # Since we're using OSM data, all edges ARE existing roads
            # We only include major roads (motorway, trunk, primary, secondary) in our cache
            # So ALL of them should be classified as "upgrade_existing"
            
            # Major highways (motorway, trunk, primary, secondary) = upgrade existing
            if edge.highway_type in ['motorway', 'trunk', 'primary', 'secondary', 
                                     'motorway_link', 'trunk_link', 'primary_link', 'secondary_link']:
                segment.construction_type = "upgrade_existing"
                segment.cost_factor = 0.3  # Major roads need minimal work
                upgrade_existing_km += segment.distance_m / 1000
            elif edge.highway_type in ['tertiary', 'tertiary_link']:
                segment.construction_type = "upgrade_existing"
                segment.cost_factor = 0.5  # Tertiary roads need more work
                upgrade_existing_km += segment.distance_m / 1000
            elif edge.surface in ['paved', 'asphalt', 'concrete']:
                segment.construction_type = "upgrade_existing"
                segment.cost_factor = 0.4
                upgrade_existing_km += segment.distance_m / 1000
            else:
                # Unpaved track - needs significant work
                segment.construction_type = "upgrade_existing"  # Still existing, just poor quality
                segment.cost_factor = 0.7  # More work needed
                upgrade_existing_km += segment.distance_m / 1000
        
        # Calculate utilization and cost savings
        total_km = route.total_distance_km
        utilization_percent = (upgrade_existing_km / total_km * 100) if total_km > 0 else 0
        cost_savings_percent = (upgrade_existing_km * 0.6 / total_km * 100) if total_km > 0 else 0
        
        # Update route construction stats
        route.construction_stats = {
            'new_construction_km': round(new_construction_km, 2),
            'upgrade_existing_km': round(upgrade_existing_km, 2),
            'utilization_percent': round(utilization_percent, 1),
            'cost_savings_percent': round(cost_savings_percent, 1)
        }
        
        # Calculate estimated cost
        route.estimated_cost = self.calculate_cost(route)
        
        return route
    
    def calculate_cost(self, route: Route) -> float:
        """
        Calculate construction cost considering existing roads
        
        Args:
            route: Route with classified segments
            
        Returns:
            Estimated cost in USD
        """
        # Cost per km: $1M for new construction, $400k for upgrade
        cost_per_km_new = 1_000_000
        cost_per_km_upgrade = 400_000
        
        total_cost = 0
        
        for segment in route.segments:
            distance_km = segment.distance_m / 1000
            
            if segment.construction_type == "new_construction":
                total_cost += distance_km * cost_per_km_new
            else:
                total_cost += distance_km * cost_per_km_upgrade
        
        return total_cost
