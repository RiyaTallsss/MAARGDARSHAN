"""
OSM PBF Parser

Parses OpenStreetMap PBF files and constructs road network graphs.
"""

import json
import gzip
import hashlib
import math
import logging
from typing import Optional, Set
import osmium

from .models import RoadNetwork, RoadNode, RoadEdge

# Set up logging
logger = logging.getLogger(__name__)

# Highway types to include (OPTIMIZED: Major roads only for Lambda performance)
# This reduces cache size from 110MB to ~15MB and loads 10x faster
HIGHWAY_TYPES = {
    'motorway', 'trunk', 'primary', 'secondary',
    'motorway_link', 'trunk_link', 'primary_link', 'secondary_link'
}


class RoadHandler(osmium.SimpleHandler):
    """Handler for processing OSM ways (roads)"""
    
    def __init__(self, bbox: Optional[tuple] = None):
            """
            Initialize handler

            Args:
                bbox: Optional bounding box (min_lat, min_lon, max_lat, max_lon)
            """
            osmium.SimpleHandler.__init__(self)
            self.roads = []
            self.nodes_used = set()
            self.data_quality_issues = []
            self.ways_processed = 0
            self.last_progress_report = 0
            self.bbox = bbox
    
    def way(self, w):
            """Process each way in the OSM file"""
            self.ways_processed += 1

            # Progress reporting every 10,000 ways
            if self.ways_processed - self.last_progress_report >= 10000:
                logger.info(f"Processed {self.ways_processed:,} ways, found {len(self.roads):,} roads so far...")
                self.last_progress_report = self.ways_processed

            # Check if it's a road
            if 'highway' not in w.tags:
                return

            highway_type = w.tags['highway']

            # Filter by highway type
            if highway_type not in HIGHWAY_TYPES:
                return

            # Extract node coordinates
            try:
                coordinates = [(n.lon, n.lat) for n in w.nodes]
                node_ids = [n.ref for n in w.nodes]

                if len(coordinates) < 2:
                    return  # Skip roads with less than 2 nodes

                # Filter by bounding box if specified
                if self.bbox:
                    min_lat, min_lon, max_lat, max_lon = self.bbox
                    # Check if any coordinate is within bbox
                    in_bbox = any(
                        min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
                        for lon, lat in coordinates
                    )
                    if not in_bbox:
                        return  # Skip roads outside bbox

                # Extract metadata with defaults for missing data
                name = w.tags.get('name', f'Unnamed_Road_{w.id}')
                surface = w.tags.get('surface', 'unpaved')
                condition = w.tags.get('condition', None)

                # Log data quality issues
                if 'name' not in w.tags:
                    self.data_quality_issues.append(f"Road {w.id} missing name, using default")

                if 'surface' not in w.tags:
                    self.data_quality_issues.append(f"Road {w.id} missing surface, defaulting to unpaved")

                # Calculate distance
                distance_m = self._calculate_distance(coordinates)

                # Store road data
                self.roads.append({
                    'id': str(w.id),
                    'name': name,
                    'highway_type': highway_type,
                    'surface': surface,
                    'condition': condition,
                    'coordinates': coordinates,
                    'node_ids': node_ids,
                    'distance_m': distance_m
                })

                # Track which nodes are used
                self.nodes_used.update(node_ids)

            except Exception as e:
                logger.error(f"Error processing way {w.id}: {e}")
                self.data_quality_issues.append(f"Error processing way {w.id}: {e}")
    
    def _calculate_distance(self, coordinates):
        """Calculate total distance of a road segment"""
        total = 0.0
        for i in range(len(coordinates) - 1):
            lon1, lat1 = coordinates[i]
            lon2, lat2 = coordinates[i + 1]
            total += self._haversine_distance(lat1, lon1, lat2, lon2)
        return total
    
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in meters"""
        R = 6371000  # Earth radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c


class OSMParser:
    """Parser for OSM PBF files"""
    
    def __init__(self):
        self.data_quality_issues = []
    
    def parse_pbf(self, pbf_path: str, bbox: Optional[tuple] = None) -> RoadNetwork:
            """
            Parse PBF file and return road network graph

            Args:
                pbf_path: Path to OSM PBF file
                bbox: Optional bounding box (min_lat, min_lon, max_lat, max_lon)

            Returns:
                RoadNetwork with nodes and edges
            """
            logger.info(f"Parsing PBF file: {pbf_path}")
            if bbox:
                logger.info(f"Filtering to bounding box: {bbox}")

            # Create handler and parse file
            handler = RoadHandler(bbox=bbox)

            try:
                handler.apply_file(pbf_path, locations=True)
            except Exception as e:
                logger.error(f"Error parsing PBF file: {e}")
                raise

            logger.info(f"Parsed {len(handler.roads)} roads")
            logger.info(f"Data quality issues: {len(handler.data_quality_issues)}")

            # Store data quality issues
            self.data_quality_issues = handler.data_quality_issues

            # Log first few issues
            for issue in handler.data_quality_issues[:10]:
                logger.info(f"  {issue}")

            if len(handler.data_quality_issues) > 10:
                logger.info(f"  ... and {len(handler.data_quality_issues) - 10} more issues")

            # Build network (will be implemented in Task 3)
            # For now, return empty network with metadata
            network = self._build_graph(handler.roads, handler.nodes_used)

            # Add metadata
            network.metadata.update({
                'source_file': pbf_path,
                'total_roads_parsed': len(handler.roads),
                'data_quality_issues': len(handler.data_quality_issues),
                'highway_types': list(HIGHWAY_TYPES),
                'total_nodes': len(network.nodes),
                'total_edges': len(network.edges),
                'bbox': bbox
            })

            logger.info(f"Built graph with {len(network.nodes)} nodes and {len(network.edges)} edges")

            return network
    
    def _build_graph(self, roads_data: list, nodes_used: Set[int]) -> RoadNetwork:
        """
        Build graph structure from parsed road data
        
        Args:
            roads_data: List of road dictionaries
            nodes_used: Set of node IDs that are used
            
        Returns:
            RoadNetwork with nodes and edges
        """
        logger.info(f"Building graph from {len(roads_data)} roads...")
        network = RoadNetwork()
        node_coords = {}  # node_id -> (lat, lon)
        
        # First pass: collect all node coordinates
        logger.info("Pass 1/3: Collecting node coordinates...")
        for i, road in enumerate(roads_data):
            if i > 0 and i % 10000 == 0:
                logger.info(f"  Processed {i:,}/{len(roads_data):,} roads for node collection")
            
            node_ids = road['node_ids']
            coordinates = road['coordinates']
            
            for node_id, (lon, lat) in zip(node_ids, coordinates):
                if node_id not in node_coords:
                    node_coords[node_id] = (lat, lon)
        
        logger.info(f"  Collected {len(node_coords):,} unique nodes")
        
        # Second pass: create RoadNode objects
        logger.info("Pass 2/3: Creating RoadNode objects...")
        for i, (node_id, (lat, lon)) in enumerate(node_coords.items()):
            if i > 0 and i % 50000 == 0:
                logger.info(f"  Created {i:,}/{len(node_coords):,} nodes")
            
            network.nodes[str(node_id)] = RoadNode(
                id=str(node_id),
                lat=lat,
                lon=lon,
                elevation=0  # Will be populated later from DEM
            )
        
        logger.info(f"  Created {len(network.nodes):,} RoadNode objects")
        
        # Third pass: create RoadEdge objects
        logger.info("Pass 3/3: Creating RoadEdge objects...")
        edge_count = 0
        for i, road in enumerate(roads_data):
            if i > 0 and i % 10000 == 0:
                logger.info(f"  Processed {i:,}/{len(roads_data):,} roads, created {edge_count:,} edges")
            
            node_ids = road['node_ids']
            coordinates = road['coordinates']
            
            # Create edges between consecutive nodes
            for j in range(len(node_ids) - 1):
                source_id = str(node_ids[j])
                target_id = str(node_ids[j + 1])
                
                # Calculate segment distance
                lon1, lat1 = coordinates[j]
                lon2, lat2 = coordinates[j + 1]
                segment_distance = self._haversine_distance(lat1, lon1, lat2, lon2)
                
                # Create edge
                edge_id = f"{road['id']}_{j}"
                edge = RoadEdge(
                    id=edge_id,
                    source_node_id=source_id,
                    target_node_id=target_id,
                    coordinates=[coordinates[j], coordinates[j + 1]],
                    distance_m=segment_distance,
                    name=road['name'],
                    highway_type=road['highway_type'],
                    surface=road['surface'],
                    condition=road['condition']
                )
                
                network.edges[edge_id] = edge
                edge_count += 1
        
        logger.info(f"  Created {len(network.edges):,} RoadEdge objects")
        
        # Skip isolated node removal - it's too slow and not necessary for routing
        logger.info("Skipping isolated node removal (not needed for routing)")
        
        logger.info(f"Graph building complete!")
        return network
    
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in meters"""
        R = 6371000  # Earth radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def load_from_cache(self, cache_path: str) -> Optional[RoadNetwork]:
        """
        Load cached road network from file
        
        Args:
            cache_path: Path to cached network (local or S3)
            
        Returns:
            RoadNetwork if cache valid, None otherwise
        """
        try:
            logger.info(f"Loading network from cache: {cache_path}")
            
            # Read compressed JSON
            with gzip.open(cache_path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
            
            # Deserialize network (this will call build_adjacency_lists via from_dict)
            network = RoadNetwork.from_dict(data)
            
            logger.info(f"Loaded network with {len(network.nodes)} nodes and {len(network.edges)} edges")
            return network
            
        except FileNotFoundError:
            logger.info(f"Cache file not found: {cache_path}")
            return None
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return None
    
    def save_to_cache(self, network: RoadNetwork, cache_path: str) -> None:
        """
        Serialize and save road network to file
        
        Args:
            network: RoadNetwork to cache
            cache_path: Path for cache file
        """
        try:
            logger.info(f"Saving network to cache: {cache_path}")
            
            # Serialize network
            data = network.to_dict()
            
            # Write compressed JSON
            with gzip.open(cache_path, 'wt', encoding='utf-8') as f:
                json.dump(data, f)
            
            # Calculate compression ratio
            import os
            if os.path.exists(cache_path):
                compressed_size = os.path.getsize(cache_path)
                logger.info(f"Cache saved: {compressed_size / 1024 / 1024:.2f} MB")
            
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
            raise
    
    def validate_cache(self, network: RoadNetwork, pbf_hash: str) -> bool:
        """
        Verify cache integrity
        
        Args:
            network: Cached network
            pbf_hash: Hash of source PBF file
            
        Returns:
            True if cache is valid
        """
        return network.metadata.get('pbf_hash') == pbf_hash
    
    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
