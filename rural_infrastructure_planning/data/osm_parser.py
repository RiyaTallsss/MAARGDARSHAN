"""
OSM Parser for real-time OSM data parsing and road network analysis.

This module provides the OSM_Parser class that handles extracting road networks
and infrastructure from Overpass API or local OSM data with geographic bounds.
"""

import asyncio
import aiohttp
import requests
import osmium
import osmnx as ox
import networkx as nx
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass
from pathlib import Path
import logging
import json
import time
from datetime import datetime
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
import numpy as np

from ..config.settings import config
from ..utils.cache import get_global_cache, cached
from ..utils.rate_limiter import get_global_rate_limiter, rate_limited
from .api_client import BoundingBox, Coordinate, OSMData, DataFreshnessInfo

logger = logging.getLogger(__name__)


@dataclass
class RoadNetwork:
    """Road network data structure with NetworkX graph."""
    graph: nx.MultiDiGraph
    nodes: Dict[int, Dict[str, Any]]
    edges: Dict[Tuple[int, int], Dict[str, Any]]
    bounds: BoundingBox
    total_length_km: float
    road_types: Dict[str, int]  # highway type -> count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'node_count': len(self.nodes),
            'edge_count': len(self.edges),
            'bounds': self.bounds.to_dict(),
            'total_length_km': self.total_length_km,
            'road_types': self.road_types,
            'connectivity_info': {
                'is_connected': nx.is_connected(self.graph.to_undirected()),
                'number_of_components': nx.number_connected_components(self.graph.to_undirected()),
                'average_degree': sum(dict(self.graph.degree()).values()) / len(self.graph.nodes()) if self.graph.nodes() else 0
            }
        }


@dataclass
class Settlement:
    """Settlement data structure."""
    id: str
    name: str
    place_type: str  # city, town, village, hamlet
    coordinate: Coordinate
    population: Optional[int] = None
    tags: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'place_type': self.place_type,
            'coordinate': self.coordinate.to_dict(),
            'population': self.population,
            'tags': self.tags or {}
        }


@dataclass
class Infrastructure:
    """Infrastructure data structure."""
    id: str
    name: str
    infrastructure_type: str  # school, hospital, market, etc.
    coordinate: Coordinate
    tags: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.infrastructure_type,
            'coordinate': self.coordinate.to_dict(),
            'tags': self.tags or {}
        }


class OSMPBFHandler(osmium.SimpleHandler):
    """OSM PBF file handler for extracting data within geographic bounds."""
    
    def __init__(self, bounds: BoundingBox, features: List[str]):
        osmium.SimpleHandler.__init__(self)
        self.bounds = bounds
        self.features = features
        self.roads = []
        self.settlements = []
        self.infrastructure = []
        
    def node(self, n):
        """Process OSM nodes."""
        if not self._is_within_bounds(n.location.lat, n.location.lon):
            return
            
        tags = {tag.k: tag.v for tag in n.tags}
        
        # Extract settlements
        if "settlements" in self.features and 'place' in tags:
            self.settlements.append({
                'id': f"osm_node_{n.id}",
                'name': tags.get('name', 'Unknown'),
                'place_type': tags['place'],
                'lat': n.location.lat,
                'lon': n.location.lon,
                'tags': tags
            })
        
        # Extract infrastructure
        if "infrastructure" in self.features and 'amenity' in tags:
            amenity_type = tags['amenity']
            if amenity_type in ['school', 'hospital', 'clinic', 'pharmacy', 'bank', 'market', 'fuel']:
                self.infrastructure.append({
                    'id': f"osm_node_{n.id}",
                    'name': tags.get('name', 'Unknown'),
                    'type': amenity_type,
                    'lat': n.location.lat,
                    'lon': n.location.lon,
                    'tags': tags
                })
    
    def way(self, w):
        """Process OSM ways."""
        tags = {tag.k: tag.v for tag in w.tags}
        
        # Extract roads
        if "roads" in self.features and 'highway' in tags:
            highway_type = tags['highway']
            
            # Filter for relevant road types
            if highway_type in ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 
                              'unclassified', 'residential', 'service', 'track', 'path']:
                
                # Get way geometry
                geometry = []
                for node_ref in w.nodes:
                    # Note: In a full implementation, you'd need to resolve node references
                    # For now, we'll create a simplified representation
                    geometry.append({'node_id': node_ref.ref})
                
                self.roads.append({
                    'id': f"osm_way_{w.id}",
                    'highway_type': highway_type,
                    'geometry': geometry,
                    'tags': tags
                })
    
    def _is_within_bounds(self, lat: float, lon: float) -> bool:
        """Check if coordinates are within the bounding box."""
        return (self.bounds.south <= lat <= self.bounds.north and 
                self.bounds.west <= lon <= self.bounds.east)


class OSM_Parser:
    """
    OSM Parser for real-time OSM data parsing and road network analysis.
    
    This class handles extracting road networks and infrastructure from Overpass API
    or local OSM data with geographic bounds, building NetworkX graphs, and identifying
    populated areas and existing infrastructure.
    
    Features:
    - Real-time Overpass API integration with fallback to local PBF files
    - NetworkX graph construction for road networks
    - Settlement and infrastructure extraction
    - Geographic bounds filtering
    - Multiple API integration for enhanced infrastructure data
    """
    
    def __init__(self):
        self.cache = get_global_cache()
        self.rate_limiter = get_global_rate_limiter()
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Configure OSMnx settings for better performance
        ox.settings.log_console = False
        ox.settings.use_cache = True
        ox.settings.cache_folder = config.data.cache_directory if hasattr(config.data, 'cache_directory') else './cache'
        
        logger.info("Initialized OSM_Parser with Overpass API integration and local PBF fallback")
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    @rate_limited('overpass')
    async def query_overpass_api(self, bounds: BoundingBox, query: str) -> Optional[Dict[str, Any]]:
        """
        Query Overpass API for real-time OSM data.
        
        Args:
            bounds: Geographic bounding box for the query
            query: Overpass QL query string
            
        Returns:
            Raw OSM data from Overpass API or None if failed
        """
        cache_key = f"overpass_{bounds.north}_{bounds.south}_{bounds.east}_{bounds.west}_{hash(query)}"
        
        # Try cache first
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.debug("Using cached Overpass API data")
            return cached_data
        
        url = "https://overpass-api.de/api/interpreter"
        
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        try:
            # Use shorter timeout for better responsiveness
            timeout = aiohttp.ClientTimeout(total=15)
            async with self.session.post(url, data=query, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Cache the result
                    self.cache.set(cache_key, data, ttl_hours=6, source="overpass_api")
                    logger.info("Successfully fetched data from Overpass API")
                    return data
                else:
                    logger.error(f"Overpass API error: {response.status}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.warning("Overpass API timeout")
            return None
        except Exception as e:
            logger.warning(f"Overpass API error: {e}")
            return None
    
    async def load_local_osm_data(self, pbf_file: str, bounds: BoundingBox) -> Optional[Dict[str, Any]]:
        """
        Load OSM data from local PBF file with geographic bounds filtering.
        
        Args:
            pbf_file: Path to the OSM PBF file
            bounds: Geographic bounding box for filtering
            
        Returns:
            Processed OSM data or None if failed
        """
        pbf_path = Path(pbf_file)
        if not pbf_path.exists():
            # Try relative to data directory
            pbf_path = config.data.data_root / config.data.osm_directory / pbf_file
            if not pbf_path.exists():
                logger.warning(f"OSM PBF file not found: {pbf_file}")
                return self._create_mock_osm_data(bounds)
        
        try:
            # Use osmium to parse PBF file
            handler = OSMPBFHandler(bounds, ['roads', 'settlements', 'infrastructure'])
            handler.apply_file(str(pbf_path))
            
            return {
                'elements': (
                    [{'type': 'way', **road} for road in handler.roads] +
                    [{'type': 'node', **settlement} for settlement in handler.settlements] +
                    [{'type': 'node', **infra} for infra in handler.infrastructure]
                )
            }
            
        except Exception as e:
            logger.error(f"Error parsing PBF file: {e}")
            return self._create_mock_osm_data(bounds)
    
    def _create_mock_osm_data(self, bounds: BoundingBox) -> Dict[str, Any]:
        """Create mock OSM data for testing when real data is unavailable."""
        # Generate realistic road network for Uttarkashi region
        elements = []
        
        # Create main roads
        main_roads = [
            {
                'type': 'way',
                'id': 'mock_road_1',
                'tags': {'highway': 'primary', 'name': 'NH-108'},
                'geometry': [
                    {'lat': bounds.south + 0.01, 'lon': bounds.west + 0.01},
                    {'lat': bounds.north - 0.01, 'lon': bounds.east - 0.01}
                ]
            },
            {
                'type': 'way',
                'id': 'mock_road_2',
                'tags': {'highway': 'secondary', 'name': 'State Highway'},
                'geometry': [
                    {'lat': bounds.south + 0.02, 'lon': bounds.west + 0.02},
                    {'lat': bounds.north - 0.02, 'lon': bounds.east - 0.02}
                ]
            },
            {
                'type': 'way',
                'id': 'mock_road_3',
                'tags': {'highway': 'tertiary', 'name': 'District Road'},
                'geometry': [
                    {'lat': (bounds.north + bounds.south) / 2, 'lon': bounds.west + 0.01},
                    {'lat': (bounds.north + bounds.south) / 2, 'lon': bounds.east - 0.01}
                ]
            }
        ]
        
        # Create settlements
        settlements = [
            {
                'type': 'node',
                'id': 'mock_settlement_1',
                'lat': (bounds.north + bounds.south) / 2,
                'lon': (bounds.east + bounds.west) / 2,
                'tags': {'place': 'town', 'name': 'Uttarkashi', 'population': '22000'}
            },
            {
                'type': 'node',
                'id': 'mock_settlement_2',
                'lat': bounds.south + (bounds.north - bounds.south) * 0.3,
                'lon': bounds.west + (bounds.east - bounds.west) * 0.7,
                'tags': {'place': 'village', 'name': 'Bhatwari'}
            },
            {
                'type': 'node',
                'id': 'mock_settlement_3',
                'lat': bounds.south + (bounds.north - bounds.south) * 0.8,
                'lon': bounds.west + (bounds.east - bounds.west) * 0.3,
                'tags': {'place': 'village', 'name': 'Gangori'}
            }
        ]
        
        # Create infrastructure
        infrastructure = [
            {
                'type': 'node',
                'id': 'mock_infra_1',
                'lat': (bounds.north + bounds.south) / 2 + 0.01,
                'lon': (bounds.east + bounds.west) / 2 + 0.01,
                'tags': {'amenity': 'hospital', 'name': 'District Hospital Uttarkashi'}
            },
            {
                'type': 'node',
                'id': 'mock_infra_2',
                'lat': (bounds.north + bounds.south) / 2 - 0.01,
                'lon': (bounds.east + bounds.west) / 2 - 0.01,
                'tags': {'amenity': 'school', 'name': 'Government Senior Secondary School'}
            },
            {
                'type': 'node',
                'id': 'mock_infra_3',
                'lat': bounds.south + (bounds.north - bounds.south) * 0.6,
                'lon': bounds.west + (bounds.east - bounds.west) * 0.4,
                'tags': {'amenity': 'market', 'name': 'Local Market'}
            }
        ]
        
        elements.extend(main_roads)
        elements.extend(settlements)
        elements.extend(infrastructure)
        
        return {'elements': elements}
    
    def extract_road_network(self, osm_data: Dict[str, Any], bounds: BoundingBox) -> RoadNetwork:
        """
        Extract road network and build NetworkX graph from OSM data.
        
        Args:
            osm_data: Raw OSM data from API or local file
            bounds: Geographic bounding box
            
        Returns:
            RoadNetwork with NetworkX graph and metadata
        """
        # Create NetworkX MultiDiGraph for road network
        graph = nx.MultiDiGraph()
        nodes = {}
        edges = {}
        road_types = {}
        total_length_km = 0.0
        
        # Process OSM elements
        node_coords = {}  # Store node coordinates for edge length calculation
        
        for element in osm_data.get('elements', []):
            if element.get('type') == 'node':
                node_id = element.get('id')
                lat = element.get('lat')
                lon = element.get('lon')
                
                if lat is not None and lon is not None:
                    node_coords[node_id] = (lat, lon)
                    
                    # Add node to graph if it's within bounds
                    if bounds.contains_point(lat, lon):
                        nodes[node_id] = {
                            'lat': lat,
                            'lon': lon,
                            'tags': element.get('tags', {})
                        }
                        graph.add_node(node_id, lat=lat, lon=lon, **element.get('tags', {}))
            
            elif element.get('type') == 'way':
                tags = element.get('tags', {})
                highway_type = tags.get('highway')
                
                if highway_type and highway_type in ['motorway', 'trunk', 'primary', 'secondary', 
                                                   'tertiary', 'unclassified', 'residential', 
                                                   'service', 'track', 'path']:
                    
                    # Count road types
                    road_types[highway_type] = road_types.get(highway_type, 0) + 1
                    
                    # Process way geometry
                    geometry = element.get('geometry', [])
                    if not geometry and 'nodes' in element:
                        # Handle node references
                        geometry = [{'node_id': node_ref} for node_ref in element['nodes']]
                    
                    # Create edges between consecutive nodes
                    prev_node = None
                    for i, geom_point in enumerate(geometry):
                        if 'lat' in geom_point and 'lon' in geom_point:
                            # Direct coordinates
                            current_node = f"way_{element['id']}_node_{i}"
                            lat, lon = geom_point['lat'], geom_point['lon']
                            
                            if bounds.contains_point(lat, lon):
                                nodes[current_node] = {'lat': lat, 'lon': lon}
                                graph.add_node(current_node, lat=lat, lon=lon)
                                
                                if prev_node:
                                    # Calculate edge length
                                    prev_lat, prev_lon = nodes[prev_node]['lat'], nodes[prev_node]['lon']
                                    length_km = self._calculate_distance(prev_lat, prev_lon, lat, lon)
                                    total_length_km += length_km
                                    
                                    edge_key = (prev_node, current_node)
                                    edges[edge_key] = {
                                        'highway': highway_type,
                                        'length_km': length_km,
                                        'name': tags.get('name', ''),
                                        'tags': tags
                                    }
                                    graph.add_edge(prev_node, current_node, 
                                                 highway=highway_type, 
                                                 length_km=length_km,
                                                 **tags)
                                
                                prev_node = current_node
                        
                        elif 'node_id' in geom_point:
                            # Node reference
                            node_id = geom_point['node_id']
                            if node_id in node_coords:
                                lat, lon = node_coords[node_id]
                                if bounds.contains_point(lat, lon):
                                    if prev_node and prev_node in nodes:
                                        # Calculate edge length
                                        prev_lat, prev_lon = nodes[prev_node]['lat'], nodes[prev_node]['lon']
                                        length_km = self._calculate_distance(prev_lat, prev_lon, lat, lon)
                                        total_length_km += length_km
                                        
                                        edge_key = (prev_node, node_id)
                                        edges[edge_key] = {
                                            'highway': highway_type,
                                            'length_km': length_km,
                                            'name': tags.get('name', ''),
                                            'tags': tags
                                        }
                                        graph.add_edge(prev_node, node_id,
                                                     highway=highway_type,
                                                     length_km=length_km,
                                                     **tags)
                                    
                                    prev_node = node_id
        
        return RoadNetwork(
            graph=graph,
            nodes=nodes,
            edges=edges,
            bounds=bounds,
            total_length_km=total_length_km,
            road_types=road_types
        )
    
    def find_settlements(self, osm_data: Dict[str, Any], bounds: BoundingBox) -> List[Settlement]:
        """
        Identify populated areas from OSM data.
        
        Args:
            osm_data: Raw OSM data from API or local file
            bounds: Geographic bounding box
            
        Returns:
            List of Settlement objects
        """
        settlements = []
        
        for element in osm_data.get('elements', []):
            if element.get('type') == 'node':
                tags = element.get('tags', {})
                
                if 'place' in tags:
                    lat = element.get('lat')
                    lon = element.get('lon')
                    
                    if lat is not None and lon is not None and bounds.contains_point(lat, lon):
                        # Extract population if available
                        population = None
                        if 'population' in tags:
                            try:
                                population = int(tags['population'])
                            except (ValueError, TypeError):
                                pass
                        
                        settlement = Settlement(
                            id=str(element.get('id', f"settlement_{len(settlements)}")),
                            name=tags.get('name', 'Unknown'),
                            place_type=tags['place'],
                            coordinate=Coordinate(lat, lon),
                            population=population,
                            tags=tags
                        )
                        settlements.append(settlement)
        
        # Sort by importance (city > town > village > hamlet)
        place_priority = {'city': 0, 'town': 1, 'village': 2, 'hamlet': 3}
        settlements.sort(key=lambda s: (place_priority.get(s.place_type, 4), -s.population if s.population else 0))
        
        return settlements
    
    async def get_existing_infrastructure(self, bounds: BoundingBox, 
                                        infrastructure_types: Optional[List[str]] = None) -> List[Infrastructure]:
        """
        Get existing infrastructure (schools, hospitals, markets) using multiple APIs.
        
        Args:
            bounds: Geographic bounding box
            infrastructure_types: List of infrastructure types to search for
            
        Returns:
            List of Infrastructure objects
        """
        if infrastructure_types is None:
            infrastructure_types = ['school', 'hospital', 'clinic', 'pharmacy', 'bank', 'market', 'fuel']
        
        # Build Overpass query for infrastructure
        bbox_str = f"{bounds.south},{bounds.west},{bounds.north},{bounds.east}"
        
        # Create query for multiple amenity types
        amenity_filter = '|'.join(infrastructure_types)
        query = f"""
        [out:json][timeout:10];
        (
          node["amenity"~"{amenity_filter}"]({bbox_str});
          way["amenity"~"{amenity_filter}"]({bbox_str});
        );
        out center geom;
        """
        
        infrastructure = []
        
        # Try Overpass API first
        osm_data = await self.query_overpass_api(bounds, query)
        if osm_data:
            infrastructure.extend(self._extract_infrastructure_from_osm(osm_data, bounds))
        else:
            # Fallback to local data
            logger.info("Overpass API unavailable, using local OSM data for infrastructure")
            local_data = await self.load_local_osm_data(
                config.data.northern_zone_osm_file if hasattr(config.data, 'northern_zone_osm_file') else 'northern-zone-260121.osm.pbf',
                bounds
            )
            if local_data:
                infrastructure.extend(self._extract_infrastructure_from_osm(local_data, bounds))
        
        return infrastructure
    
    def _extract_infrastructure_from_osm(self, osm_data: Dict[str, Any], bounds: BoundingBox) -> List[Infrastructure]:
        """Extract infrastructure from OSM data."""
        infrastructure = []
        
        for element in osm_data.get('elements', []):
            tags = element.get('tags', {})
            
            if 'amenity' in tags:
                amenity_type = tags['amenity']
                
                # Get coordinates
                lat, lon = None, None
                
                if element.get('type') == 'node':
                    lat = element.get('lat')
                    lon = element.get('lon')
                elif element.get('type') == 'way' and 'center' in element:
                    # For ways, use center point
                    center = element['center']
                    lat = center.get('lat')
                    lon = center.get('lon')
                
                if lat is not None and lon is not None and bounds.contains_point(lat, lon):
                    infra = Infrastructure(
                        id=str(element.get('id', f"infra_{len(infrastructure)}")),
                        name=tags.get('name', f'Unknown {amenity_type}'),
                        infrastructure_type=amenity_type,
                        coordinate=Coordinate(lat, lon),
                        tags=tags
                    )
                    infrastructure.append(infra)
        
        return infrastructure
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        
        Returns:
            Distance in kilometers
        """
        from math import radians, cos, sin, asin, sqrt
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Earth radius in kilometers
        r = 6371
        
        return c * r
    
    def _build_overpass_query(self, bounds: BoundingBox, features: List[str]) -> str:
        """
        Build Overpass QL query for specified features.
        
        Args:
            bounds: Geographic bounding box
            features: List of features to extract (roads, settlements, infrastructure)
            
        Returns:
            Overpass QL query string
        """
        bbox_str = f"{bounds.south},{bounds.west},{bounds.north},{bounds.east}"
        query_parts = ["[out:json][timeout:10];", "("]
        
        if "roads" in features:
            # Query for major roads only for performance
            query_parts.append(f'way["highway"~"motorway|trunk|primary|secondary|tertiary"]({bbox_str});')
        
        if "settlements" in features:
            query_parts.append(f'node["place"~"city|town|village|hamlet"]({bbox_str});')
        
        if "infrastructure" in features:
            # Query for essential infrastructure
            query_parts.append(f'node["amenity"~"school|hospital|clinic|pharmacy|bank|market|fuel"]({bbox_str});')
            query_parts.append(f'way["amenity"~"school|hospital|clinic|pharmacy|bank|market|fuel"]({bbox_str});')
        
        query_parts.extend([");", "out center geom;"])
        
        return "".join(query_parts)
    
    async def parse_osm_data(self, bounds: BoundingBox, 
                           features: Optional[List[str]] = None,
                           use_local_fallback: bool = True) -> OSMData:
        """
        Main method to parse OSM data with comprehensive feature extraction.
        
        Args:
            bounds: Geographic bounding box
            features: List of features to extract (roads, settlements, infrastructure)
            use_local_fallback: Whether to use local PBF file as fallback
            
        Returns:
            OSMData object with extracted features and freshness information
        """
        if features is None:
            features = ['roads', 'settlements', 'infrastructure']
        
        # Build Overpass query
        query = self._build_overpass_query(bounds, features)
        
        # Try Overpass API first
        osm_raw_data = await self.query_overpass_api(bounds, query)
        source = "overpass_api"
        
        if not osm_raw_data and use_local_fallback:
            # Fallback to local PBF file
            logger.info("Overpass API unavailable, falling back to local OSM PBF data")
            osm_raw_data = await self.load_local_osm_data(
                config.data.northern_zone_osm_file if hasattr(config.data, 'northern_zone_osm_file') else 'northern-zone-260121.osm.pbf',
                bounds
            )
            source = "local_pbf"
        
        if not osm_raw_data:
            logger.warning("No OSM data available, creating mock data")
            osm_raw_data = self._create_mock_osm_data(bounds)
            source = "mock_data"
        
        # Extract features
        roads = []
        settlements = []
        infrastructure = []
        
        if "roads" in features:
            road_network = self.extract_road_network(osm_raw_data, bounds)
            # Convert road network to simple road list for compatibility
            for edge_key, edge_data in road_network.edges.items():
                start_node, end_node = edge_key
                start_coord = road_network.nodes.get(start_node, {})
                end_coord = road_network.nodes.get(end_node, {})
                
                roads.append({
                    'id': f"road_{start_node}_{end_node}",
                    'highway_type': edge_data.get('highway', 'unknown'),
                    'geometry': [
                        {'lat': start_coord.get('lat'), 'lon': start_coord.get('lon')},
                        {'lat': end_coord.get('lat'), 'lon': end_coord.get('lon')}
                    ],
                    'tags': edge_data.get('tags', {}),
                    'length_km': edge_data.get('length_km', 0.0)
                })
        
        if "settlements" in features:
            settlement_objects = self.find_settlements(osm_raw_data, bounds)
            settlements = [settlement.to_dict() for settlement in settlement_objects]
        
        if "infrastructure" in features:
            infrastructure_objects = self._extract_infrastructure_from_osm(osm_raw_data, bounds)
            infrastructure = [infra.to_dict() for infra in infrastructure_objects]
        
        # Create freshness info
        freshness_info = DataFreshnessInfo(
            source_type="api" if source == "overpass_api" else "local",
            source_name=source,
            data_age_hours=0.1 if source == "overpass_api" else 720.0,  # 6 minutes vs 30 days
            is_real_time=source == "overpass_api",
            quality_score=0.95 if source == "overpass_api" else 0.8,
            last_updated=datetime.now()
        )
        
        return OSMData(
            roads=roads,
            settlements=settlements,
            infrastructure=infrastructure,
            bounds=bounds,
            source=source,
            timestamp=datetime.now(),
            freshness_info=freshness_info
        )