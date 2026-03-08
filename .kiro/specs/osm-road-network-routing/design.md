# Design Document: OSM Road Network Routing

## Overview

This design document specifies the implementation of realistic road routing in MAARGDARSHAN using OpenStreetMap (OSM) road network data. The system will parse OSM PBF files to extract road networks, implement graph-based pathfinding algorithms, and integrate road-aware routing into the existing Lambda-based infrastructure while maintaining AWS resource constraints.

### Goals

- Parse OSM road network data from PBF files into a graph structure
- Implement graph-based pathfinding with multiple optimization criteria
- Classify route segments as "new construction" vs "upgrade existing"
- Display road networks and routes on the map interface
- Maintain compatibility with existing MAARGDARSHAN functionality
- Operate within AWS Lambda constraints (512MB memory, 30s timeout, 6MB response)

### Non-Goals

- Real-time traffic data integration
- Turn-by-turn navigation instructions
- Multi-modal transportation routing
- Road network editing capabilities
- Historical route analysis

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Leaflet)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Map Display  │  │ Route Cards  │  │ Layer Toggle │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS/JSON
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    AWS Lambda Function                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Route Calculator (Main)                  │  │
│  │  • Request validation                                 │  │
│  │  • Coordinate processing                              │  │
│  │  • Response assembly                                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                              │                               │
│         ┌────────────────────┼────────────────────┐         │
│         ▼                    ▼                    ▼         │
│  ┌─────────────┐      ┌─────────────┐     ┌─────────────┐ │
│  │ OSM_Parser  │      │   Pathfinder│     │Road_Renderer│ │
│  │             │      │             │     │             │ │
│  │ • Parse PBF │      │ • Dijkstra/ │     │ • GeoJSON   │ │
│  │ • Build     │      │   A* search │     │   conversion│ │
│  │   graph     │      │ • Cost      │     │ • Layer     │ │
│  │ • Cache     │      │   functions │     │   formatting│ │
│  └─────────────┘      └─────────────┘     └─────────────┘ │
│         │                    │                    │         │
└─────────┼────────────────────┼────────────────────┼─────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                         AWS S3 Bucket                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ OSM PBF File │  │ Cached Graph │  │ DEM/Rainfall │     │
│  │ (~500MB)     │  │ (JSON)       │  │ Data         │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Initialization (Cold Start)**:
   - Lambda loads cached Road_Network from S3
   - If cache missing/invalid, parse PBF file
   - Build spatial index for fast lookups

2. **Route Request**:
   - Frontend sends start/end coordinates
   - Lambda finds snap points on road network
   - Pathfinder calculates 4 routes with different cost functions
   - Classify segments as new/upgrade
   - Return routes with metadata

3. **Rendering**:
   - Frontend receives GeoJSON data
   - Display existing roads (gray layer)
   - Display calculated routes (colored layers)
   - Show bridges, settlements, waypoints

## Components and Interfaces

### OSM_Parser Component

**Responsibility**: Parse OSM PBF files and construct Road_Network graph

**Interface**:
```python
class OSMParser:
    def parse_pbf(self, pbf_path: str) -> RoadNetwork:
        """Parse PBF file and return road network graph"""
        
    def load_from_cache(self, cache_path: str) -> Optional[RoadNetwork]:
        """Load cached road network from S3"""
        
    def save_to_cache(self, network: RoadNetwork, cache_path: str) -> None:
        """Serialize and save road network to S3"""
        
    def validate_cache(self, network: RoadNetwork, pbf_hash: str) -> bool:
        """Verify cache integrity"""

```

**Implementation Details**:
- Use `pyosmium` library for PBF parsing
- Filter highway types: primary, secondary, tertiary, unclassified, track
- Extract metadata: name, surface, condition, highway_type
- Handle missing data with defaults: "Unnamed_Road_{id}", "unpaved"
- Stream processing for files >512MB
- Log data quality issues to CloudWatch

**Dependencies**:
- pyosmium (OSM PBF parsing)
- boto3 (S3 access)

### Route_Calculator Component

**Responsibility**: Calculate optimal routes using graph algorithms

**Interface**:
```python
class RouteCalculator:
    def __init__(self, network: RoadNetwork):
        """Initialize with road network"""
        
    def find_snap_point(self, lat: float, lon: float, max_distance_m: float = 500) -> Optional[RoadNode]:
        """Find nearest road node within max_distance"""
        
    def calculate_routes(self, start: Tuple[float, float], end: Tuple[float, float]) -> List[Route]:
        """Calculate 4 routes with different optimization criteria"""
        
    def classify_segments(self, route: Route, network: RoadNetwork) -> Route:
        """Classify route segments as new construction or upgrade"""
        
    def calculate_cost(self, route: Route) -> float:
        """Calculate construction cost considering existing roads"""
```

**Implementation Details**:
- Use `networkx` library for graph operations
- Implement A* pathfinding with custom heuristics
- Four cost functions:
  1. **Shortest**: Minimize euclidean distance
  2. **Safest**: Prefer primary/secondary roads, avoid tracks
  3. **Budget**: Prefer paved surfaces, maximize existing road usage
  4. **Social**: Prefer routes near settlements (<1km)
- Spatial index (R-tree) for fast snap point searches
- Segment classification: 10m tolerance for overlap detection

**Dependencies**:
- networkx (graph algorithms)
- scipy.spatial (KDTree for spatial indexing)
- numpy (distance calculations)

### Road_Renderer Component

**Responsibility**: Convert road data to frontend-compatible formats

**Interface**:
```python
class RoadRenderer:
    def to_geojson(self, network: RoadNetwork) -> dict:
        """Convert road network to GeoJSON"""
        
    def format_route(self, route: Route) -> dict:
        """Format route for frontend display"""
        
    def create_layer_config(self, routes: List[Route]) -> dict:
        """Create Leaflet layer configuration"""
```

**Implementation Details**:
- GeoJSON LineString for roads
- GeoJSON Point for bridges, settlements
- Color mapping: blue (shortest), green (safest), yellow (budget), red (social)
- Layer structure: base roads (gray, 2px) + routes (colored, 4px)
- Include metadata: distance, cost, risk scores

## Data Models

### RoadNetwork

```python
@dataclass
class RoadNode:
    """Intersection or endpoint in road network"""
    id: str
    lat: float
    lon: float
    elevation: int  # from DEM
    
@dataclass
class RoadEdge:
    """Road segment connecting two nodes"""
    id: str
    source_node_id: str
    target_node_id: str
    coordinates: List[Tuple[float, float]]  # intermediate points
    distance_m: float
    name: str
    highway_type: str  # primary, secondary, tertiary, unclassified, track
    surface: str  # paved, unpaved, gravel, etc.
    condition: Optional[str]  # good, fair, poor
    
@dataclass
class RoadNetwork:
    """Complete road network graph"""
    nodes: Dict[str, RoadNode]
    edges: Dict[str, RoadEdge]
    spatial_index: Any  # KDTree for fast lookups
    metadata: dict  # source file, parse date, coverage area
```

### Route

```python
@dataclass
class RouteSegment:
    """Portion of a route"""
    edge_id: str
    construction_type: str  # "new_construction" or "upgrade_existing"
    distance_m: float
    cost_factor: float  # 1.0 for new, 0.4 for upgrade
    
@dataclass
class Route:
    """Calculated route with metadata"""
    id: str
    name: str  # "Shortest Route", "Safest Route", etc.
    segments: List[RouteSegment]
    waypoints: List[dict]  # {lat, lon, elevation}
    total_distance_km: float
    elevation_gain_m: int
    construction_stats: dict  # new_km, upgrade_km, percentage
    estimated_cost: float
    risk_scores: dict  # terrain, flood, seasonal
    bridges: List[dict]  # river crossings
    settlements: List[dict]  # nearby villages
```

## Algorithms

### Pathfinding Algorithm

**Choice**: A* algorithm with custom heuristics

**Rationale**:
- More efficient than Dijkstra for point-to-point routing
- Heuristic guides search toward destination
- Supports custom cost functions for different route types

**Implementation**:
```python
def a_star_search(graph, start_node, end_node, cost_function):
    """
    A* pathfinding with custom cost function
    
    Args:
        graph: RoadNetwork
        start_node: RoadNode
        end_node: RoadNode
        cost_function: Callable[[RoadEdge], float]
    
    Returns:
        List[RoadEdge]: Ordered sequence of edges
    """
    # Priority queue: (f_score, node_id)
    open_set = [(0, start_node.id)]
    came_from = {}
    g_score = {start_node.id: 0}
    
    while open_set:
        current_f, current_id = heappop(open_set)
        
        if current_id == end_node.id:
            return reconstruct_path(came_from, current_id)
        
        for edge in graph.get_outgoing_edges(current_id):
            neighbor_id = edge.target_node_id
            tentative_g = g_score[current_id] + cost_function(edge)
            
            if neighbor_id not in g_score or tentative_g < g_score[neighbor_id]:
                came_from[neighbor_id] = (current_id, edge)
                g_score[neighbor_id] = tentative_g
                f_score = tentative_g + heuristic(neighbor_id, end_node)
                heappush(open_set, (f_score, neighbor_id))
    
    return None  # No path found
```

**Heuristic Function**:
```python
def heuristic(node_id, goal_node):
    """Euclidean distance to goal (admissible heuristic)"""
    node = graph.nodes[node_id]
    lat_diff = goal_node.lat - node.lat
    lon_diff = goal_node.lon - node.lon
    return math.sqrt(lat_diff**2 + lon_diff**2) * 111000  # meters
```

### Cost Functions

**1. Shortest Distance**:
```python
def cost_shortest(edge: RoadEdge) -> float:
    return edge.distance_m
```

**2. Safest Route**:
```python
def cost_safest(edge: RoadEdge) -> float:
    base_cost = edge.distance_m
    if edge.highway_type in ['primary', 'secondary']:
        return base_cost * 0.8  # Prefer major roads
    elif edge.highway_type == 'track':
        return base_cost * 1.5  # Avoid tracks
    return base_cost
```

**3. Budget Route**:
```python
def cost_budget(edge: RoadEdge) -> float:
    base_cost = edge.distance_m
    if 'paved' in edge.surface.lower():
        return base_cost * 0.7  # Prefer paved roads
    return base_cost
```

**4. Social Impact Route**:
```python
def cost_social(edge: RoadEdge, settlements: List[dict]) -> float:
    base_cost = edge.distance_m
    # Check if edge passes near settlements
    min_distance = min_distance_to_settlements(edge, settlements)
    if min_distance < 1000:  # Within 1km
        return base_cost * 0.6  # Strong preference
    return base_cost
```

### Snap-to-Road Algorithm

**Purpose**: Find nearest road node to arbitrary coordinates

**Implementation**:
```python
def find_snap_point(lat: float, lon: float, max_distance_m: float = 500) -> Optional[RoadNode]:
    """
    Find nearest road node using spatial index
    
    Uses KDTree for O(log n) nearest neighbor search
    """
    # Query spatial index
    distances, indices = spatial_index.query([[lat, lon]], k=1)
    
    if distances[0][0] * 111000 <= max_distance_m:  # Convert degrees to meters
        return nodes[indices[0][0]]
    
    return None  # No road within max_distance
```

### Segment Classification Algorithm

**Purpose**: Determine if route segment uses existing road or requires new construction

**Implementation**:
```python
def classify_segment(route_segment: RouteSegment, road_network: RoadNetwork) -> str:
    """
    Classify segment as 'new_construction' or 'upgrade_existing'
    
    Uses 10m tolerance for overlap detection
    """
    segment_line = route_segment.get_line_geometry()
    
    for edge in road_network.edges.values():
        edge_line = edge.get_line_geometry()
        
        # Check if lines are within 10m of each other
        if hausdorff_distance(segment_line, edge_line) < 10:
            return 'upgrade_existing'
    
    return 'new_construction'
```

## API Changes

### Request Format (Unchanged)

```json
{
  "start": {"lat": 30.7268, "lon": 78.4354},
  "end": {"lat": 30.9993, "lon": 78.9394},
  "context": "Route planning for rural connectivity"
}
```

### Response Format (Enhanced)

```json
{
  "success": true,
  "routes": [
    {
      "id": "route-1",
      "name": "Shortest Route",
      "distance_km": 45.2,
      "waypoints": [...],
      "construction_stats": {
        "total_distance_km": 45.2,
        "new_construction_km": 30.5,
        "upgrade_existing_km": 14.7,
        "utilization_percent": 32.5,
        "cost_savings_percent": 26.0
      },
      "road_segments": [
        {
          "edge_id": "way_12345",
          "construction_type": "upgrade_existing",
          "distance_m": 1200,
          "road_name": "NH-108",
          "highway_type": "primary"
        }
      ]
    }
  ],
  "road_network_metadata": {
    "total_roads": 1523,
    "total_nodes": 3847,
    "coverage_area_km2": 450,
    "source_file": "northern-zone-260121.osm.pbf"
  }
}
```

## Performance Optimizations

### 1. Caching Strategy

**Problem**: Parsing 500MB PBF file on every request exceeds Lambda timeout

**Solution**:
- Parse PBF once, cache Road_Network to S3 as compressed JSON
- Lambda loads from cache on cold start (~2 seconds)
- Cache invalidation: check PBF file hash

**Implementation**:
```python
def get_road_network(pbf_path: str, cache_path: str) -> RoadNetwork:
    # Check cache
    if cache_exists(cache_path):
        pbf_hash = compute_file_hash(pbf_path)
        cached_network = load_from_cache(cache_path)
        
        if cached_network.metadata['pbf_hash'] == pbf_hash:
            return cached_network
    
    # Parse and cache
    network = parse_pbf(pbf_path)
    save_to_cache(network, cache_path)
    return network
```

### 2. Spatial Indexing

**Problem**: Finding snap points requires checking all nodes (O(n))

**Solution**:
- Build KDTree spatial index during parsing
- Snap point search becomes O(log n)

**Implementation**:
```python
from scipy.spatial import KDTree

# Build index
coords = [(node.lat, node.lon) for node in network.nodes.values()]
spatial_index = KDTree(coords)

# Query (fast)
distances, indices = spatial_index.query([[lat, lon]], k=1)
```

### 3. Graph Simplification

**Problem**: Full road network has too many nodes/edges for Lambda memory

**Solution**:
- Remove nodes with degree 2 (merge edges)
- Exclude track-type roads if memory pressure
- Keep only roads in bounding box of interest

**Implementation**:
```python
def simplify_network(network: RoadNetwork, bbox: BoundingBox) -> RoadNetwork:
    # Filter by bounding box
    filtered_nodes = {nid: n for nid, n in network.nodes.items() 
                      if bbox.contains(n.lat, n.lon)}
    
    # Merge degree-2 nodes
    simplified = merge_linear_segments(filtered_nodes, network.edges)
    
    return simplified
```

### 4. Response Size Management

**Problem**: 4 routes with full waypoints can exceed 6MB API Gateway limit

**Solution**:
- Limit waypoints per route to 100 points
- Downsample using Ramer-Douglas-Peucker algorithm
- Remove downloadable formats from response (generate client-side)

**Implementation**:
```python
def downsample_waypoints(waypoints: List[dict], max_points: int = 100) -> List[dict]:
    if len(waypoints) <= max_points:
        return waypoints
    
    # Use RDP algorithm to preserve shape while reducing points
    simplified = rdp_algorithm(waypoints, epsilon=0.0001)
    
    if len(simplified) > max_points:
        # Uniform sampling as fallback
        step = len(waypoints) // max_points
        return waypoints[::step]
    
    return simplified
```

### 5. Parallel Route Calculation

**Problem**: Calculating 4 routes sequentially takes too long

**Solution**:
- Use multiprocessing to calculate routes in parallel
- Lambda has multiple vCPUs available

**Implementation**:
```python
from multiprocessing import Pool

def calculate_all_routes(start, end, network):
    cost_functions = [cost_shortest, cost_safest, cost_budget, cost_social]
    
    with Pool(processes=4) as pool:
        routes = pool.starmap(
            calculate_single_route,
            [(start, end, network, cf) for cf in cost_functions]
        )
    
    return routes
```

## Error Handling

### Error Categories

1. **Input Validation Errors**
   - Invalid coordinates (out of bounds)
   - Missing required fields
   - Malformed request

2. **Data Quality Errors**
   - Malformed PBF data
   - Missing road metadata
   - Disconnected road segments

3. **Routing Errors**
   - No snap point found (location not accessible)
   - No path exists between start and end
   - Route calculation timeout

4. **Resource Errors**
   - Memory limit exceeded
   - S3 access failure
   - Cache corruption

### Error Handling Strategy

```python
class RoutingError(Exception):
    """Base class for routing errors"""
    pass

class SnapPointNotFoundError(RoutingError):
    """No road within snap distance"""
    pass

class NoPathExistsError(RoutingError):
    """Start and end are in disconnected components"""
    pass

class CacheCorruptionError(RoutingError):
    """Cached data failed validation"""
    pass

def lambda_handler(event, context):
    try:
        # Parse request
        start, end = parse_request(event)
        
        # Load network
        try:
            network = get_road_network(PBF_PATH, CACHE_PATH)
        except CacheCorruptionError:
            logger.warning("Cache corrupted, reparsing PBF")
            network = parse_pbf(PBF_PATH)
            save_to_cache(network, CACHE_PATH)
        
        # Find snap points
        start_node = find_snap_point(start.lat, start.lon)
        if not start_node:
            return error_response(
                400,
                "Start location not accessible by road",
                "NO_SNAP_POINT_START"
            )
        
        end_node = find_snap_point(end.lat, end.lon)
        if not end_node:
            return error_response(
                400,
                "End location not accessible by road",
                "NO_SNAP_POINT_END"
            )
        
        # Calculate routes
        routes = calculate_routes(start_node, end_node, network)
        
        if not routes:
            return error_response(
                400,
                "No route exists between locations",
                "NO_PATH_EXISTS"
            )
        
        return success_response(routes)
        
    except MemoryError:
        logger.error("Memory limit exceeded")
        return error_response(500, "Server resource limit exceeded", "MEMORY_ERROR")
        
    except Exception as e:
        logger.exception("Unexpected error")
        return error_response(500, "Internal server error", "INTERNAL_ERROR")
```

### Data Quality Handling

```python
def parse_road_with_defaults(osm_way):
    """Parse OSM way with default values for missing data"""
    road = RoadEdge(
        id=osm_way.id,
        name=osm_way.tags.get('name', f'Unnamed_Road_{osm_way.id}'),
        highway_type=osm_way.tags.get('highway', 'unclassified'),
        surface=osm_way.tags.get('surface', 'unpaved'),
        condition=osm_way.tags.get('condition', None)
    )
    
    # Log data quality issues
    if 'name' not in osm_way.tags:
        logger.info(f"Road {osm_way.id} missing name, using default")
    
    if 'surface' not in osm_way.tags:
        logger.info(f"Road {osm_way.id} missing surface, defaulting to unpaved")
    
    return road
```

## Testing Strategy

### Unit Testing

**Scope**: Individual components and functions

**Tools**: pytest, unittest.mock

**Key Test Cases**:
- OSM_Parser: Parse sample PBF, handle malformed data
- Route_Calculator: Pathfinding correctness, cost functions
- Road_Renderer: GeoJSON format validation
- Snap point algorithm: Distance calculations
- Segment classification: Overlap detection

**Example**:
```python
def test_snap_point_within_range():
    """Test snap point finds nearest node within range"""
    network = create_test_network()
    calculator = RouteCalculator(network)
    
    # Node at (30.0, 78.0)
    snap = calculator.find_snap_point(30.001, 78.001, max_distance_m=500)
    
    assert snap is not None
    assert abs(snap.lat - 30.0) < 0.01
    assert abs(snap.lon - 78.0) < 0.01

def test_snap_point_out_of_range():
    """Test snap point returns None when too far"""
    network = create_test_network()
    calculator = RouteCalculator(network)
    
    snap = calculator.find_snap_point(35.0, 85.0, max_distance_m=500)
    
    assert snap is None
```

### Property-Based Testing

**Scope**: Universal properties that should hold for all inputs

**Tools**: Hypothesis (Python property-based testing library)

**Configuration**: Minimum 100 iterations per test


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified the following redundancies:
- Properties 4.4 and 4.5 (calculating distances by type) are subsumed by Property 4.6 (percentage calculation)
- Property 8.4 (validating node/edge counts) is redundant with Property 8.3 (round-trip equivalence)
- Properties 4.2 and 4.3 can be combined into a single comprehensive classification property

The following properties represent the minimal set needed for comprehensive correctness validation:

### Property 1: Highway Tag Extraction

*For any* valid PBF file containing OSM ways with highway tags, parsing should extract all and only those ways that have highway tags.

**Validates: Requirements 1.1**

### Property 2: Highway Type Filtering

*For any* set of parsed roads, the filtered result should contain only roads with highway types in {primary, secondary, tertiary, unclassified, track}.

**Validates: Requirements 1.2**

### Property 3: Road Metadata Completeness

*For any* extracted road, the road object should contain all required fields: node coordinates, road name, highway type, surface type, and condition metadata (with defaults applied for missing values).

**Validates: Requirements 1.3**

### Property 4: Graph Structure Validity

*For any* constructed Road_Network, all edges should reference valid nodes that exist in the node collection, and all node IDs should be unique.

**Validates: Requirements 1.4**

### Property 5: Cache Persistence

*For any* successfully parsed Road_Network, after saving to cache, the cache file should exist and be readable.

**Validates: Requirements 1.5**

### Property 6: Malformed Data Resilience

*For any* PBF file containing malformed road data, the parser should log errors and continue processing, returning a Road_Network with all valid roads.

**Validates: Requirements 1.8**

### Property 7: Snap Point Distance Constraint

*For any* coordinate and Road_Network, if a snap point is found, the distance between the coordinate and snap point should be at most 500 meters.

**Validates: Requirements 2.2**

### Property 8: Route Count and Distinctness

*For any* valid start and end points with a path between them, the Route_Calculator should return exactly 4 routes, and all routes should have different waypoint sequences.

**Validates: Requirements 2.4**

### Property 9: Shortest Route Optimality

*For any* set of calculated routes, the route named "Shortest Route" should have a distance less than or equal to all other routes.

**Validates: Requirements 2.5**

### Property 10: Safest Route Road Type Preference

*For any* calculated "Safest Route", the proportion of primary and secondary highway segments should be greater than or equal to the proportion in the "Shortest Route".

**Validates: Requirements 2.6**

### Property 11: Budget Route Surface Preference

*For any* calculated "Budget Route", the proportion of paved road segments should be greater than or equal to the proportion in the "Shortest Route".

**Validates: Requirements 2.7**

### Property 12: Social Impact Route Settlement Proximity

*For any* calculated "Social Impact Route", the average distance from route waypoints to nearest settlements should be less than or equal to the average for the "Shortest Route".

**Validates: Requirements 2.8**

### Property 13: Route Output Structure

*For any* calculated route, the route object should contain an ordered sequence of Road_Edges with geographic coordinates for each waypoint.

**Validates: Requirements 2.9**

### Property 14: GeoJSON Round-Trip

*For any* valid Road_Network, converting to GeoJSON and parsing back should produce an equivalent Road_Network with the same nodes and edges.

**Validates: Requirements 3.1**

### Property 15: Layer Toggle Visibility

*For any* map state where the existing roads layer toggle is set to hidden, querying the visible layers should return only the proposed route layers and not the existing roads layer.

**Validates: Requirements 3.6, 3.7**

### Property 16: Segment Classification Completeness

*For any* calculated route, every Route_Segment should be classified as either "new_construction" or "upgrade_existing", with no segments unclassified.

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 17: Distance Aggregation Correctness

*For any* calculated route, the sum of distances of all "new_construction" segments plus the sum of distances of all "upgrade_existing" segments should equal the total route distance.

**Validates: Requirements 4.4, 4.5, 4.6**

### Property 18: Cost Reduction Factor Application

*For any* route with both new construction and upgrade segments, the cost per kilometer for upgrade segments should be 0.4 times the cost per kilometer for new construction segments.

**Validates: Requirements 4.7**

### Property 19: Construction Type in Response

*For any* route in the API response, the route object should include a construction_stats field containing new_construction_km and upgrade_existing_km values.

**Validates: Requirements 4.8**

### Property 20: API Request Compatibility

*For any* valid request in the existing API format (with start and end coordinates), the enhanced Route_Calculator should successfully process the request and return a response.

**Validates: Requirements 5.1**

### Property 21: API Response Compatibility

*For any* API response from the enhanced Route_Calculator, the response should contain all fields present in the original API response structure (routes, waypoints, distance_km, estimated_cost_usd, risk_factors).

**Validates: Requirements 5.2**

### Property 22: Waypoint Interval Consistency

*For any* calculated route, the distance between consecutive construction waypoints should be approximately 100 meters (±10m tolerance).

**Validates: Requirements 5.3**

### Property 23: Existing Functionality Preservation

*For any* calculated route, the route object should include cut_fill volumes, risk_factors (terrain, flood, seasonal), and cost estimates with materials and labor breakdown.

**Validates: Requirements 5.4, 5.5, 5.6**

### Property 24: Response Size Constraint

*For any* API response, the total JSON payload size should be less than 6MB.

**Validates: Requirements 5.7**

### Property 25: Default Name Assignment

*For any* road with missing name metadata, the assigned name should match the format "Unnamed_Road_{id}" where {id} is the road's unique identifier.

**Validates: Requirements 6.1**

### Property 26: Default Surface Assignment

*For any* road with missing surface metadata, the assigned surface type should be "unpaved".

**Validates: Requirements 6.2**

### Property 27: Disconnected Component Handling

*For any* Road_Network with disconnected road segments, the graph should contain multiple connected components, each internally connected.

**Validates: Requirements 6.3**

### Property 28: Isolated Node Exclusion

*For any* Road_Network, all nodes in the final graph should have at least one connecting edge (degree ≥ 1).

**Validates: Requirements 6.5**

### Property 29: Data Quality Logging

*For any* parsing operation that encounters missing metadata or malformed data, the diagnostic log should contain entries describing each data quality issue.

**Validates: Requirements 6.6**

### Property 30: Cache Compression Effectiveness

*For any* Road_Network saved to cache, the compressed cache file size should be at most 50% of the uncompressed JSON representation size.

**Validates: Requirements 7.6**

### Property 31: Cache Reuse

*For any* sequence of multiple route requests within the same Lambda execution, the Road_Network should be loaded from memory cache only once, not reloaded for each request.

**Validates: Requirements 7.7**

### Property 32: Serialization Round-Trip

*For any* valid Road_Network, serializing to JSON then deserializing should produce an equivalent Road_Network with identical node coordinates, edge connections, and metadata.

**Validates: Requirements 8.1, 8.2, 8.3**

## Error Handling

### Error Response Format

All errors return consistent JSON structure:

```json
{
  "success": false,
  "error_code": "NO_SNAP_POINT_START",
  "message": "Start location not accessible by road",
  "details": {
    "requested_location": {"lat": 30.5, "lon": 78.5},
    "nearest_road_distance_m": 1200,
    "max_snap_distance_m": 500
  }
}
```

### Error Codes

| Code | HTTP Status | Description | Recovery Action |
|------|-------------|-------------|-----------------|
| INVALID_COORDINATES | 400 | Coordinates out of bounds | Provide coordinates within Uttarakhand |
| NO_SNAP_POINT_START | 400 | Start location too far from roads | Choose location closer to existing roads |
| NO_SNAP_POINT_END | 400 | End location too far from roads | Choose location closer to existing roads |
| NO_PATH_EXISTS | 400 | No route between locations | Locations in disconnected road networks |
| CACHE_CORRUPTED | 500 | Cache validation failed | System will reparse PBF automatically |
| MEMORY_ERROR | 500 | Lambda memory limit exceeded | Retry with smaller region |
| TIMEOUT_ERROR | 500 | Processing exceeded 30s | Retry or reduce route complexity |
| S3_ACCESS_ERROR | 500 | Cannot access PBF or cache | Check S3 permissions |

### Graceful Degradation

When encountering non-critical errors:

1. **Missing Road Metadata**: Apply defaults and log warning
2. **Disconnected Roads**: Return routes within reachable component
3. **Memory Pressure**: Simplify network by excluding track roads
4. **Response Size Limit**: Reduce waypoint density progressively

## Testing Strategy

### Dual Testing Approach

The testing strategy employs both unit tests and property-based tests as complementary approaches:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs through randomization
- Together they provide comprehensive coverage: unit tests catch concrete bugs, property tests verify general correctness

### Property-Based Testing Configuration

**Library**: Hypothesis (Python)

**Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with comment referencing design property
- Tag format: `# Feature: osm-road-network-routing, Property {number}: {property_text}`

**Example Property Test**:
```python
from hypothesis import given, strategies as st
import pytest

# Feature: osm-road-network-routing, Property 7: Snap Point Distance Constraint
@given(
    lat=st.floats(min_value=28.6, max_value=31.5),
    lon=st.floats(min_value=77.5, max_value=81.0)
)
@pytest.mark.property_test
def test_snap_point_distance_constraint(lat, lon, road_network):
    """For any coordinate, if snap point found, distance <= 500m"""
    calculator = RouteCalculator(road_network)
    snap_point = calculator.find_snap_point(lat, lon, max_distance_m=500)
    
    if snap_point is not None:
        distance_m = haversine_distance(lat, lon, snap_point.lat, snap_point.lon)
        assert distance_m <= 500, f"Snap point {distance_m}m away, exceeds 500m limit"

# Feature: osm-road-network-routing, Property 32: Serialization Round-Trip
@given(network=st.builds(generate_random_road_network))
@pytest.mark.property_test
def test_serialization_round_trip(network):
    """For any Road_Network, serialize then deserialize produces equivalent network"""
    parser = OSMParser()
    
    # Serialize
    json_data = parser.serialize(network)
    
    # Deserialize
    restored_network = parser.deserialize(json_data)
    
    # Verify equivalence
    assert len(restored_network.nodes) == len(network.nodes)
    assert len(restored_network.edges) == len(network.edges)
    
    for node_id, node in network.nodes.items():
        restored_node = restored_network.nodes[node_id]
        assert abs(restored_node.lat - node.lat) < 1e-6
        assert abs(restored_node.lon - node.lon) < 1e-6
```

### Unit Testing Focus

Unit tests should focus on:

1. **Specific Examples**:
   - Parse known PBF file with expected road count
   - Calculate route between Uttarkashi and Gangotri
   - Classify segment overlapping NH-108 as "upgrade_existing"

2. **Edge Cases**:
   - Empty PBF file
   - Single-node network
   - Start and end at same location
   - Coordinates exactly on road vs 499m away

3. **Error Conditions**:
   - Malformed PBF data
   - Corrupted cache file
   - Disconnected road networks
   - Memory limit exceeded

4. **Integration Points**:
   - S3 read/write operations
   - DEM elevation lookup
   - Bedrock AI explanation generation

**Example Unit Tests**:
```python
def test_parse_uttarkashi_pbf():
    """Test parsing actual Uttarkashi PBF file"""
    parser = OSMParser()
    network = parser.parse_pbf('Maps/northern-zone-260121.osm.pbf')
    
    assert len(network.nodes) > 1000
    assert len(network.edges) > 500
    assert 'NH-108' in [e.name for e in network.edges.values()]

def test_no_path_between_disconnected_components():
    """Test error when start and end in different components"""
    network = create_disconnected_network()
    calculator = RouteCalculator(network)
    
    with pytest.raises(NoPathExistsError):
        calculator.calculate_routes(
            start=(30.0, 78.0),  # Component A
            end=(31.0, 79.0)     # Component B
        )

def test_snap_point_exactly_on_road():
    """Edge case: coordinate exactly on road node"""
    network = create_test_network()
    calculator = RouteCalculator(network)
    
    # Node exists at exactly (30.0, 78.0)
    snap = calculator.find_snap_point(30.0, 78.0, max_distance_m=500)
    
    assert snap is not None
    assert snap.lat == 30.0
    assert snap.lon == 78.0
```

### Integration Testing

**Scope**: End-to-end Lambda function execution

**Test Cases**:
- Cold start with cache miss (full PBF parse)
- Warm start with cache hit
- Multiple requests in same execution
- Response size validation
- Timeout handling

**Example**:
```python
def test_lambda_cold_start():
    """Test Lambda cold start with PBF parsing"""
    event = {
        'body': json.dumps({
            'start': {'lat': 30.7268, 'lon': 78.4354},
            'end': {'lat': 30.9993, 'lon': 78.9394}
        })
    }
    
    response = lambda_handler(event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] == True
    assert len(body['routes']) == 4
    assert all('construction_stats' in r for r in body['routes'])
```

### Performance Testing

**Metrics to Track**:
- PBF parse time (target: <60s for 500MB file)
- Cache load time (target: <2s)
- Snap point search time (target: <100ms)
- Route calculation time (target: <25s for 4 routes)
- Total Lambda execution time (target: <30s)
- Memory usage (target: <512MB)
- Response size (target: <6MB)

**Tools**:
- AWS CloudWatch for Lambda metrics
- Python `memory_profiler` for memory analysis
- `cProfile` for CPU profiling

## Deployment Considerations

### Lambda Configuration

```yaml
Runtime: python3.11
Memory: 512 MB
Timeout: 30 seconds
Environment Variables:
  S3_BUCKET: maargdarshan-data
  PBF_PATH: osm/northern-zone-260121.osm.pbf
  CACHE_PATH: osm/cache/road_network.json.gz
  BEDROCK_MODEL: anthropic.claude-3-haiku-20240307-v1:0
```

### Dependencies

```
# requirements-lambda.txt
pyosmium==3.6.4
networkx==3.2.1
scipy==1.11.4
numpy==1.26.2
boto3==1.34.10
```

### S3 Structure

```
s3://maargdarshan-data/
├── osm/
│   ├── northern-zone-260121.osm.pbf (500MB)
│   └── cache/
│       ├── road_network.json.gz (compressed graph)
│       └── metadata.json (parse date, PBF hash)
├── dem/
│   └── P5_PAN_CD_N30_000_E078_000_DEM_30m.tif
└── geospatial-data/
    └── uttarkashi/
        ├── rivers/
        └── villages/
```

### Monitoring

**CloudWatch Metrics**:
- Lambda invocations
- Duration (p50, p95, p99)
- Memory usage (max)
- Error rate
- Cache hit rate (custom metric)

**CloudWatch Logs**:
- Data quality issues
- Cache invalidations
- Routing errors
- Performance warnings

### Rollback Plan

If OSM routing causes issues:

1. Feature flag to disable OSM routing
2. Fallback to existing curve-based routing
3. Gradual rollout: 10% → 50% → 100% traffic
4. Monitor error rates and latency

## Future Enhancements

### Phase 2 Features

1. **Turn-by-Turn Navigation**
   - Generate driving instructions
   - Voice guidance integration

2. **Real-Time Traffic**
   - Integrate traffic data APIs
   - Dynamic route recalculation

3. **Multi-Modal Routing**
   - Walking + driving combinations
   - Public transport integration

4. **Route Optimization**
   - Multi-stop route planning
   - Vehicle routing problem (VRP)

5. **Historical Analysis**
   - Route usage statistics
   - Seasonal pattern analysis

### Technical Debt

1. Replace simplified road utilization heuristic with actual OSM road matching
2. Implement proper Hausdorff distance for segment classification
3. Add support for one-way roads and turn restrictions
4. Optimize memory usage for larger regions
5. Add support for incremental PBF updates

## References

- [OpenStreetMap Wiki - Highway Tag](https://wiki.openstreetmap.org/wiki/Key:highway)
- [pyosmium Documentation](https://osmcode.org/pyosmium/)
- [NetworkX Documentation](https://networkx.org/documentation/stable/)
- [A* Pathfinding Algorithm](https://en.wikipedia.org/wiki/A*_search_algorithm)
- [AWS Lambda Limits](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
- [GeoJSON Specification](https://geojson.org/)
- [Hypothesis Property-Based Testing](https://hypothesis.readthedocs.io/)
