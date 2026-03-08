# Implementation Plan: OSM Road Network Routing

## Overview

This implementation plan breaks down the OSM road network routing feature into discrete, actionable coding tasks. The implementation will add realistic road-based routing to MAARGDARSHAN by parsing OpenStreetMap data, implementing graph-based pathfinding with multiple optimization criteria, and integrating seamlessly with the existing Lambda infrastructure.

The approach follows these phases:
1. Set up dependencies and core data structures
2. Implement OSM parsing with caching
3. Build spatial indexing for fast lookups
4. Implement pathfinding with 4 cost functions
5. Integrate with existing Lambda function
6. Add frontend visualization
7. Testing and validation

## Tasks

- [x] 1. Set up project dependencies and core data structures
  - Add pyosmium, networkx, scipy to requirements-lambda.txt
  - Create osm_routing/ module directory structure
  - Define RoadNode, RoadEdge, RoadNetwork dataclasses
  - Define Route, RouteSegment dataclasses
  - _Requirements: 1.3, 1.4_

- [ ]* 1.1 Write property test for data model round-trip
  - **Property 32: Serialization Round-Trip**
  - **Validates: Requirements 8.1, 8.2, 8.3**

- [x] 2. Implement OSM parser with PBF file handling
  - [x] 2.1 Create OSMParser class with parse_pbf method
    - Use pyosmium to read PBF files
    - Filter highway types: primary, secondary, tertiary, unclassified, track
    - Extract node coordinates and road metadata
    - Handle missing metadata with defaults (Unnamed_Road_{id}, unpaved)
    - Log data quality issues to CloudWatch
    - _Requirements: 1.1, 1.2, 1.3, 6.1, 6.2, 6.6_

  - [ ]* 2.2 Write property tests for OSM parser
    - **Property 1: Highway Tag Extraction**
    - **Property 2: Highway Type Filtering**
    - **Property 3: Road Metadata Completeness**
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [ ]* 2.3 Write unit tests for OSM parser edge cases
    - Test empty PBF file handling
    - Test malformed data resilience
    - Test missing metadata defaults
    - _Requirements: 1.8, 6.1, 6.2_

- [x] 3. Build road network graph structure
  - [x] 3.1 Implement graph construction from parsed roads
    - Create nodes for intersections and endpoints
    - Create edges for road segments with metadata
    - Handle disconnected road segments as separate components
    - Exclude isolated nodes (degree 0)
    - _Requirements: 1.4, 6.3, 6.5_

  - [ ]* 3.2 Write property tests for graph structure
    - **Property 4: Graph Structure Validity**
    - **Property 27: Disconnected Component Handling**
    - **Property 28: Isolated Node Exclusion**
    - **Validates: Requirements 1.4, 6.3, 6.5**

  - [ ]* 3.3 Write unit tests for graph construction
    - Test single-node network
    - Test disconnected components
    - Test isolated node exclusion
    - _Requirements: 1.4, 6.3, 6.5_

- [x] 4. Implement caching system for parsed networks
  - [x] 4.1 Create cache serialization and deserialization
    - Serialize RoadNetwork to compressed JSON (gzip)
    - Store in S3 at osm/cache/road_network.json.gz
    - Include metadata: parse date, PBF hash, node/edge counts
    - Implement cache validation with PBF hash comparison
    - _Requirements: 1.5, 1.6, 7.6, 8.1, 8.2_

  - [x] 4.2 Implement cache loading with validation
    - Load cached network from S3
    - Validate cache integrity (hash match, node/edge counts)
    - Fall back to PBF parsing if cache invalid
    - _Requirements: 1.6, 8.3, 8.4, 8.5_

  - [ ]* 4.3 Write property tests for caching
    - **Property 5: Cache Persistence**
    - **Property 30: Cache Compression Effectiveness**
    - **Property 32: Serialization Round-Trip**
    - **Validates: Requirements 1.5, 7.6, 8.1, 8.2, 8.3**

  - [ ]* 4.4 Write unit tests for cache handling
    - Test cache hit scenario
    - Test cache miss scenario
    - Test corrupted cache recovery
    - _Requirements: 1.6, 8.5_

- [x] 5. Checkpoint - Ensure parsing and caching work end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement spatial indexing for fast lookups
  - [x] 6.1 Build KDTree spatial index from road nodes
    - Use scipy.spatial.KDTree
    - Index all node coordinates (lat, lon)
    - Store index in RoadNetwork object
    - _Requirements: 7.4_

  - [x] 6.2 Implement find_snap_point method
    - Query KDTree for nearest neighbor
    - Validate distance is within 500m threshold
    - Return None if no road within range
    - _Requirements: 2.2, 2.3, 7.5_

  - [ ]* 6.3 Write property test for snap point distance
    - **Property 7: Snap Point Distance Constraint**
    - **Validates: Requirements 2.2**

  - [ ]* 6.4 Write unit tests for snap point edge cases
    - Test coordinate exactly on road node
    - Test coordinate 499m from road (should snap)
    - Test coordinate 501m from road (should fail)
    - Test empty network
    - _Requirements: 2.2, 2.3_

- [x] 7. Implement A* pathfinding algorithm
  - [x] 7.1 Create RouteCalculator class with A* implementation
    - Implement priority queue-based A* search
    - Use euclidean distance heuristic
    - Support custom cost functions
    - Return ordered sequence of RoadEdges
    - Handle no-path-exists case
    - _Requirements: 2.1, 2.9, 6.4_

  - [ ]* 7.2 Write property test for pathfinding
    - **Property 13: Route Output Structure**
    - **Validates: Requirements 2.9**

  - [ ]* 7.3 Write unit tests for pathfinding
    - Test simple path between two nodes
    - Test no path exists (disconnected components)
    - Test start equals end
    - _Requirements: 2.1, 6.4_

- [x] 8. Implement four cost functions for route optimization
  - [x] 8.1 Implement cost_shortest function
    - Return edge distance in meters
    - _Requirements: 2.5_

  - [x] 8.2 Implement cost_safest function
    - Prefer primary/secondary roads (0.8x cost)
    - Avoid tracks (1.5x cost)
    - _Requirements: 2.6_

  - [x] 8.3 Implement cost_budget function
    - Prefer paved surfaces (0.7x cost)
    - _Requirements: 2.7_

  - [x] 8.4 Implement cost_social function
    - Prefer routes near settlements <1km (0.6x cost)
    - Integrate with existing load_settlements_data
    - _Requirements: 2.8_

  - [x] 8.5 Implement calculate_routes method
    - Calculate 4 routes with different cost functions
    - Ensure all routes are distinct
    - Complete within 25 seconds
    - _Requirements: 2.4, 2.10_

  - [ ]* 8.6 Write property tests for cost functions
    - **Property 8: Route Count and Distinctness**
    - **Property 9: Shortest Route Optimality**
    - **Property 10: Safest Route Road Type Preference**
    - **Property 11: Budget Route Surface Preference**
    - **Property 12: Social Impact Route Settlement Proximity**
    - **Validates: Requirements 2.4, 2.5, 2.6, 2.7, 2.8**

  - [ ]* 8.7 Write unit tests for cost functions
    - Test shortest route is actually shortest
    - Test safest route prefers major roads
    - Test budget route prefers paved roads
    - Test social route proximity to settlements
    - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [x] 9. Checkpoint - Ensure pathfinding works with all cost functions
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement route segment classification
  - [x] 10.1 Create classify_segments method
    - For each route segment, check overlap with existing roads
    - Use 10m tolerance for overlap detection
    - Classify as "new_construction" or "upgrade_existing"
    - Calculate total distances for each type
    - Calculate utilization percentage
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 10.2 Implement cost calculation with reduction factor
    - Apply 0.4x cost factor to upgrade_existing segments
    - Apply 1.0x cost factor to new_construction segments
    - _Requirements: 4.7_

  - [ ]* 10.3 Write property tests for segment classification
    - **Property 16: Segment Classification Completeness**
    - **Property 17: Distance Aggregation Correctness**
    - **Property 18: Cost Reduction Factor Application**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7**

  - [ ]* 10.4 Write unit tests for segment classification
    - Test segment exactly on existing road
    - Test segment 5m from existing road (should be upgrade)
    - Test segment 15m from existing road (should be new)
    - Test cost calculation with mixed segments
    - _Requirements: 4.1, 4.2, 4.3, 4.7_

- [x] 11. Integrate OSM routing into Lambda function
  - [x] 11.1 Add OSM network initialization to Lambda cold start
    - Load cached network from S3 on cold start
    - Fall back to PBF parsing if cache missing
    - Store network in global variable for reuse
    - _Requirements: 1.6, 7.7_

  - [x] 11.2 Modify generate_routes_with_real_data function
    - Find snap points for start and end coordinates
    - Return error if snap points not found
    - Calculate 4 routes using OSM pathfinding
    - Generate waypoints at 100m intervals along routes
    - Maintain existing DEM, risk, and cost calculations
    - _Requirements: 2.2, 2.3, 2.4, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 11.3 Add construction_stats to route response
    - Include new_construction_km, upgrade_existing_km
    - Include utilization_percent, cost_savings_percent
    - _Requirements: 4.8, 5.2_

  - [x] 11.4 Implement response size management
    - Monitor total response size
    - Downsample waypoints if approaching 6MB limit
    - Use Ramer-Douglas-Peucker algorithm for simplification
    - _Requirements: 5.7, 5.8_

  - [ ]* 11.5 Write property tests for Lambda integration
    - **Property 20: API Request Compatibility**
    - **Property 21: API Response Compatibility**
    - **Property 22: Waypoint Interval Consistency**
    - **Property 23: Existing Functionality Preservation**
    - **Property 24: Response Size Constraint**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**

  - [ ]* 11.6 Write integration tests for Lambda handler
    - Test cold start with cache miss
    - Test warm start with cache hit
    - Test multiple requests in same execution
    - Test response size validation
    - Test timeout handling
    - _Requirements: 5.9, 7.7_

- [x] 12. Implement error handling for routing failures
  - [x] 12.1 Add error responses for snap point failures
    - Return NO_SNAP_POINT_START error with details
    - Return NO_SNAP_POINT_END error with details
    - Include nearest road distance in error details
    - _Requirements: 2.3_

  - [x] 12.2 Add error response for no path exists
    - Return NO_PATH_EXISTS error
    - Explain disconnected road networks
    - _Requirements: 6.4_

  - [x] 12.3 Add error handling for resource limits
    - Catch MemoryError and return MEMORY_ERROR
    - Catch timeout and return TIMEOUT_ERROR
    - Implement graceful degradation (exclude tracks if memory pressure)
    - _Requirements: 7.1, 7.2, 7.3, 5.9_

  - [ ]* 12.4 Write unit tests for error handling
    - Test snap point not found error
    - Test no path exists error
    - Test memory limit handling
    - Test timeout handling
    - _Requirements: 2.3, 6.4, 7.1, 7.2_

- [x] 13. Checkpoint - Ensure Lambda integration works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Implement road network rendering for frontend
  - [x] 14.1 Create RoadRenderer class with to_geojson method
    - Convert RoadNetwork to GeoJSON LineString format
    - Include road metadata (name, highway_type, surface)
    - _Requirements: 3.1_

  - [x] 14.2 Add road network layer to Lambda response
    - Include road_network_geojson in response
    - Add road_network_metadata (total_roads, total_nodes, coverage_area)
    - _Requirements: 3.1_

  - [ ]* 14.3 Write property test for GeoJSON conversion
    - **Property 14: GeoJSON Round-Trip**
    - **Validates: Requirements 3.1**

  - [ ]* 14.4 Write unit tests for road rendering
    - Test GeoJSON format validation
    - Test metadata completeness
    - _Requirements: 3.1_

- [x] 15. Add frontend visualization for roads and routes
  - [-] 15.1 Add existing roads layer to map
    - Display roads as gray lines (2px width)
    - Add to base layer below routes
    - _Requirements: 3.2_

  - [-] 15.2 Update route display with distinct colors
    - Blue for shortest route
    - Green for safest route
    - Yellow for budget route
    - Red for social impact route
    - Use 4px width for routes
    - _Requirements: 3.3, 3.4_

  - [-] 15.3 Add layer toggle control for existing roads
    - Add checkbox to show/hide existing roads layer
    - Update legend to distinguish roads from routes
    - _Requirements: 3.5, 3.6, 3.7_

  - [-] 15.4 Add construction stats to route cards
    - Display new_construction_km and upgrade_existing_km
    - Display utilization_percent
    - Display cost_savings_percent
    - _Requirements: 4.8_

  - [ ]* 15.5 Write property test for layer visibility
    - **Property 15: Layer Toggle Visibility**
    - **Validates: Requirements 3.6, 3.7**

  - [ ]* 15.6 Write unit tests for frontend rendering
    - Test road layer rendering
    - Test route color mapping
    - Test layer toggle functionality
    - Test construction stats display
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

- [x] 16. Optimize memory usage and performance
  - [x] 16.1 Implement graph simplification
    - Remove degree-2 nodes (merge linear segments)
    - Filter roads by bounding box
    - Exclude tracks if memory exceeds 400MB
    - _Requirements: 7.1, 7.3_

  - [x] 16.2 Add performance monitoring
    - Log parse time, cache load time, route calculation time
    - Log memory usage at key points
    - Add custom CloudWatch metrics for cache hit rate
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

  - [ ]* 16.3 Write performance tests
    - Test cache load time <2s
    - Test snap point search <100ms
    - Test route calculation <25s
    - Test total execution <30s
    - Test memory usage <512MB
    - _Requirements: 1.6, 7.1, 7.2, 7.4, 7.5, 5.9_

- [x] 17. Add comprehensive logging and monitoring
  - [x] 17.1 Add data quality logging
    - Log missing road names
    - Log missing surface metadata
    - Log disconnected components
    - Log isolated nodes excluded
    - _Requirements: 6.6_

  - [x] 17.2 Add operational logging
    - Log cache hits/misses
    - Log PBF parse operations
    - Log routing errors
    - Log performance warnings
    - _Requirements: 1.8, 6.6_

  - [ ]* 17.3 Write property test for logging
    - **Property 29: Data Quality Logging**
    - **Validates: Requirements 6.6**

- [x] 18. Final integration and deployment preparation
  - [x] 18.1 Update Lambda deployment configuration
    - Set memory to 512MB
    - Set timeout to 30 seconds
    - Add environment variables for S3 paths
    - _Requirements: 7.1, 7.2, 5.9_

  - [x] 18.2 Update deployment scripts
    - Add pyosmium, networkx, scipy to Lambda layer
    - Update deploy_lambda.sh to include osm_routing module
    - Update deploy_frontend.sh to include new UI components
    - _Requirements: 5.1, 5.2_

  - [x] 18.3 Create S3 directory structure
    - Create osm/ directory
    - Create osm/cache/ directory
    - Upload northern-zone-260121.osm.pbf to S3
    - _Requirements: 1.5, 1.6_

  - [ ]* 18.4 Write end-to-end integration tests
    - Test complete flow from request to response
    - Test with real Uttarkashi PBF file
    - Test route between Uttarkashi and Gangotri
    - Validate response format and size
    - _Requirements: 5.1, 5.2, 5.7, 5.9_

- [x] 19. Final checkpoint - Ensure all functionality works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties across all inputs
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation maintains full compatibility with existing MAARGDARSHAN functionality
- All AWS resource constraints (512MB memory, 30s timeout, 6MB response) are enforced
- The design uses Python as the implementation language throughout
