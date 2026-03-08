"""
Data models for OSM road network routing
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any


@dataclass
class RoadNode:
    """Intersection or endpoint in road network"""
    id: str
    lat: float
    lon: float
    elevation: int = 0  # from DEM, populated later
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'lat': self.lat,
            'lon': self.lon,
            'elevation': self.elevation
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RoadNode':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            lat=data['lat'],
            lon=data['lon'],
            elevation=data.get('elevation', 0)
        )


@dataclass
class RoadEdge:
    """Road segment connecting two nodes"""
    id: str
    source_node_id: str
    target_node_id: str
    coordinates: List[Tuple[float, float]] = field(default_factory=list)
    distance_m: float = 0.0
    name: str = ""
    highway_type: str = "unclassified"
    surface: str = "unpaved"
    condition: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'source_node_id': self.source_node_id,
            'target_node_id': self.target_node_id,
            'coordinates': self.coordinates,
            'distance_m': self.distance_m,
            'name': self.name,
            'highway_type': self.highway_type,
            'surface': self.surface,
            'condition': self.condition
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RoadEdge':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            source_node_id=data['source_node_id'],
            target_node_id=data['target_node_id'],
            coordinates=[tuple(c) for c in data.get('coordinates', [])],
            distance_m=data.get('distance_m', 0.0),
            name=data.get('name', ''),
            highway_type=data.get('highway_type', 'unclassified'),
            surface=data.get('surface', 'unpaved'),
            condition=data.get('condition')
        )


@dataclass
class RoadNetwork:
    """Complete road network graph"""
    nodes: Dict[str, RoadNode] = field(default_factory=dict)
    edges: Dict[str, RoadEdge] = field(default_factory=dict)
    spatial_index: Any = None  # KDTree, not serialized
    node_id_list: List[str] = field(default_factory=list)  # Maps KDTree indices to node IDs
    metadata: dict = field(default_factory=dict)
    
    # Adjacency lists for fast edge lookup (not serialized)
    _outgoing_edges: Dict[str, List[RoadEdge]] = field(default_factory=dict, repr=False)
    _incoming_edges: Dict[str, List[RoadEdge]] = field(default_factory=dict, repr=False)
    _adjacency_built: bool = field(default=False, repr=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization (excludes spatial_index and adjacency lists)"""
        return {
            'nodes': {nid: node.to_dict() for nid, node in self.nodes.items()},
            'edges': {eid: edge.to_dict() for eid, edge in self.edges.items()},
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RoadNetwork':
        """Create from dictionary"""
        network = cls(
            nodes={nid: RoadNode.from_dict(ndata) for nid, ndata in data.get('nodes', {}).items()},
            edges={eid: RoadEdge.from_dict(edata) for eid, edata in data.get('edges', {}).items()},
            metadata=data.get('metadata', {})
        )
        # Build adjacency lists after loading
        network.build_adjacency_lists()
        return network
    
    def build_spatial_index(self):
        """Build KDTree spatial index for fast nearest-neighbor queries"""
        from sklearn.neighbors import KDTree
        
        if not self.nodes:
            return
        
        # Create coordinate array and node ID mapping
        coords = []
        node_ids = []
        
        for node_id, node in self.nodes.items():
            coords.append([node.lat, node.lon])
            node_ids.append(node_id)
        
        # Build KDTree
        self.spatial_index = KDTree(coords, metric='euclidean')
        self.node_id_list = node_ids
    
    def build_adjacency_lists(self):
        """Build adjacency lists for O(1) edge lookup"""
        if self._adjacency_built:
            return
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Building adjacency lists for fast edge lookup...")
        
        self._outgoing_edges = {}
        self._incoming_edges = {}
        
        for edge in self.edges.values():
            # Outgoing edges
            if edge.source_node_id not in self._outgoing_edges:
                self._outgoing_edges[edge.source_node_id] = []
            self._outgoing_edges[edge.source_node_id].append(edge)
            
            # Incoming edges
            if edge.target_node_id not in self._incoming_edges:
                self._incoming_edges[edge.target_node_id] = []
            self._incoming_edges[edge.target_node_id].append(edge)
        
        self._adjacency_built = True
        logger.info(f"Adjacency lists built: {len(self._outgoing_edges):,} nodes with outgoing edges")
    
    def get_outgoing_edges(self, node_id: str) -> List[RoadEdge]:
        """Get all edges starting from a node (O(1) lookup)"""
        if not self._adjacency_built:
            self.build_adjacency_lists()
        return self._outgoing_edges.get(node_id, [])
    
    def get_incoming_edges(self, node_id: str) -> List[RoadEdge]:
        """Get all edges ending at a node (O(1) lookup)"""
        if not self._adjacency_built:
            self.build_adjacency_lists()
        return self._incoming_edges.get(node_id, [])


@dataclass
class RouteSegment:
    """Portion of a route"""
    edge_id: str
    construction_type: str  # "new_construction" or "upgrade_existing"
    distance_m: float
    cost_factor: float  # 1.0 for new, 0.4 for upgrade
    road_name: str = ""
    highway_type: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'edge_id': self.edge_id,
            'construction_type': self.construction_type,
            'distance_m': self.distance_m,
            'cost_factor': self.cost_factor,
            'road_name': self.road_name,
            'highway_type': self.highway_type
        }


@dataclass
class Route:
    """Calculated route with metadata"""
    id: str
    name: str
    segments: List[RouteSegment] = field(default_factory=list)
    waypoints: List[dict] = field(default_factory=list)
    total_distance_km: float = 0.0
    elevation_gain_m: int = 0
    construction_stats: dict = field(default_factory=dict)
    estimated_cost: float = 0.0
    risk_scores: dict = field(default_factory=dict)
    bridges: List[dict] = field(default_factory=list)
    settlements: List[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'segments': [seg.to_dict() for seg in self.segments],
            'waypoints': self.waypoints,
            'total_distance_km': self.total_distance_km,
            'elevation_gain_m': self.elevation_gain_m,
            'construction_stats': self.construction_stats,
            'estimated_cost': self.estimated_cost,
            'risk_scores': self.risk_scores,
            'bridges': self.bridges,
            'settlements': self.settlements
        }
