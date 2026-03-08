# Requirements Document: OSM Road Network Routing

## Introduction

This document specifies requirements for implementing realistic road routing in MAARGDARSHAN using OpenStreetMap (OSM) road network data. Currently, the system generates routes using mathematical curves that don't follow existing roads, resulting in unrealistic visualizations. This feature will parse the OSM road network from PBF files, implement graph-based pathfinding algorithms, and integrate road-aware routing into the existing system while maintaining performance constraints.

## Glossary

- **OSM**: OpenStreetMap, a collaborative mapping project providing free geographic data
- **PBF**: Protocol Buffer Format, a compressed binary format for OSM data
- **Road_Network**: A graph structure representing roads as nodes (intersections) and edges (road segments)
- **Road_Node**: An intersection or endpoint in the road network graph
- **Road_Edge**: A road segment connecting two Road_Nodes with associated metadata
- **Route_Calculator**: The component responsible for pathfinding on the Road_Network
- **OSM_Parser**: The component that extracts road data from PBF files
- **Road_Renderer**: The component that displays roads on the map interface
- **Snap_Point**: The nearest Road_Node to a given geographic coordinate
- **Route_Segment**: A portion of a calculated route consisting of one or more Road_Edges
- **Construction_Type**: Classification of a Route_Segment as either "new construction" or "upgrade existing"
- **MAARGDARSHAN**: The road planning system being enhanced
- **DEM**: Digital Elevation Model, terrain height data
- **GeoJSON**: A format for encoding geographic data structures

## Requirements

### Requirement 1: Parse OSM Road Network Data

**User Story:** As a system administrator, I want to parse OSM road network data from PBF files, so that the system has accurate road information for routing calculations.

#### Acceptance Criteria

1. WHEN the OSM_Parser receives a PBF file path, THE OSM_Parser SHALL extract all road features with highway tags
2. THE OSM_Parser SHALL filter roads to include only highway types: primary, secondary, tertiary, unclassified, and track
3. FOR each extracted road, THE OSM_Parser SHALL store node coordinates, road name, highway type, surface type, and condition metadata
4. THE OSM_Parser SHALL construct a Road_Network graph where nodes represent intersections and edges represent road segments
5. WHEN parsing completes, THE OSM_Parser SHALL cache the Road_Network to persistent storage
6. WHEN a cached Road_Network exists and the PBF file is unchanged, THE OSM_Parser SHALL load from cache within 2 seconds
7. IF the PBF file exceeds 512MB, THEN THE OSM_Parser SHALL process the file in streaming mode to avoid memory overflow
8. WHEN parsing encounters malformed data, THE OSM_Parser SHALL log the error and continue processing remaining roads

### Requirement 2: Implement Graph-Based Pathfinding

**User Story:** As a road planner, I want the system to calculate routes along existing roads, so that proposed routes are realistic and follow actual road networks.

#### Acceptance Criteria

1. THE Route_Calculator SHALL implement either Dijkstra or A* pathfinding algorithm on the Road_Network
2. WHEN given start and end coordinates, THE Route_Calculator SHALL find the Snap_Point for each coordinate within 500 meters
3. IF no Snap_Point exists within 500 meters, THEN THE Route_Calculator SHALL return an error indicating the location is not accessible by road
4. THE Route_Calculator SHALL calculate four distinct routes with different optimization criteria: shortest distance, safest path, budget-optimized, and social impact
5. FOR the shortest distance route, THE Route_Calculator SHALL minimize total euclidean distance
6. FOR the safest route, THE Route_Calculator SHALL assign lower costs to primary and secondary highways and higher costs to tracks
7. FOR the budget route, THE Route_Calculator SHALL assign lower costs to paved road surfaces
8. FOR the social impact route, THE Route_Calculator SHALL assign lower costs to roads passing within 1 kilometer of settlements
9. WHEN pathfinding completes, THE Route_Calculator SHALL return an ordered sequence of Road_Edges with geographic coordinates
10. THE Route_Calculator SHALL complete all four route calculations within 25 seconds

### Requirement 3: Display Road Network on Map Interface

**User Story:** As a road planner, I want to see existing roads displayed on the map, so that I can understand the current road infrastructure and how proposed routes relate to it.

#### Acceptance Criteria

1. THE Road_Renderer SHALL convert the Road_Network to GeoJSON format
2. THE Road_Renderer SHALL display existing roads as gray lines with 2-pixel width on the base map layer
3. THE Road_Renderer SHALL display calculated routes as colored lines with 4-pixel width on a layer above existing roads
4. THE Road_Renderer SHALL use distinct colors for each route type: blue for shortest, green for safest, yellow for budget, red for social impact
5. THE Road_Renderer SHALL provide a legend distinguishing existing roads from proposed routes
6. THE Road_Renderer SHALL provide a layer toggle control to show or hide the existing roads layer
7. WHEN the existing roads layer is hidden, THE Road_Renderer SHALL display only the proposed routes
8. THE Road_Renderer SHALL render the complete road network within 3 seconds of map load

### Requirement 4: Classify Route Segments by Construction Type

**User Story:** As a cost estimator, I want to know which parts of a route use existing roads versus require new construction, so that I can accurately estimate project costs.

#### Acceptance Criteria

1. FOR each Route_Segment in a calculated route, THE Route_Calculator SHALL determine if it overlaps an existing road within 10 meters
2. WHEN a Route_Segment overlaps an existing road, THE Route_Calculator SHALL classify it as Construction_Type "upgrade existing"
3. WHEN a Route_Segment does not overlap an existing road, THE Route_Calculator SHALL classify it as Construction_Type "new construction"
4. THE Route_Calculator SHALL calculate the total distance of "upgrade existing" segments
5. THE Route_Calculator SHALL calculate the total distance of "new construction" segments
6. THE Route_Calculator SHALL compute the percentage of route distance using existing infrastructure
7. THE Route_Calculator SHALL apply a cost reduction factor of 0.4 to "upgrade existing" segments compared to "new construction"
8. THE Route_Calculator SHALL include Construction_Type classification in the route response data

### Requirement 5: Integrate with Existing MAARGDARSHAN System

**User Story:** As a developer, I want the OSM routing feature to integrate seamlessly with existing MAARGDARSHAN functionality, so that all current features continue to work without disruption.

#### Acceptance Criteria

1. THE Route_Calculator SHALL maintain compatibility with the existing API request structure
2. THE Route_Calculator SHALL maintain compatibility with the existing API response structure
3. THE Route_Calculator SHALL continue to generate construction waypoints at 100-meter intervals along routes
4. THE Route_Calculator SHALL continue to calculate cut and fill volumes using DEM data
5. THE Route_Calculator SHALL continue to perform risk analysis using rainfall and river data
6. THE Route_Calculator SHALL continue to calculate cost estimates including materials and labor
7. THE Route_Calculator SHALL ensure total API response size remains under 6MB
8. WHEN response size approaches 6MB, THE Route_Calculator SHALL reduce waypoint density to maintain the size limit
9. THE Route_Calculator SHALL complete all processing within 30 seconds to avoid Lambda timeout

### Requirement 6: Handle OSM Data Quality Issues

**User Story:** As a system operator, I want the system to handle incomplete or inconsistent OSM data gracefully, so that routing remains functional even with imperfect data.

#### Acceptance Criteria

1. WHEN the OSM_Parser encounters a road with missing name metadata, THE OSM_Parser SHALL assign a default name using the format "Unnamed_Road_{id}"
2. WHEN the OSM_Parser encounters a road with missing surface metadata, THE OSM_Parser SHALL assign a default surface type of "unpaved"
3. WHEN the OSM_Parser encounters disconnected road segments, THE OSM_Parser SHALL create separate graph components
4. IF the Route_Calculator cannot find a path between start and end points, THEN THE Route_Calculator SHALL return an error message indicating no route exists
5. WHEN the Road_Network contains isolated nodes with no connecting edges, THE OSM_Parser SHALL exclude them from the graph
6. THE OSM_Parser SHALL log all data quality issues to a diagnostic file for review

### Requirement 7: Optimize Memory and Performance

**User Story:** As a system administrator, I want the OSM routing feature to operate within Lambda resource constraints, so that the system remains deployable on AWS infrastructure.

#### Acceptance Criteria

1. THE OSM_Parser SHALL limit memory usage to 400MB during PBF file parsing
2. THE Route_Calculator SHALL limit memory usage to 450MB during route calculation
3. WHEN memory usage exceeds 400MB during parsing, THE OSM_Parser SHALL reduce the cached road network by excluding track-type roads
4. THE OSM_Parser SHALL use spatial indexing to enable fast nearest-neighbor searches for Snap_Point calculation
5. THE Route_Calculator SHALL complete Snap_Point searches in under 100 milliseconds per coordinate
6. THE OSM_Parser SHALL compress cached Road_Network data to reduce storage size by at least 50%
7. THE Route_Calculator SHALL reuse cached Road_Network across multiple route requests without reloading

### Requirement 8: Provide Round-Trip Data Integrity

**User Story:** As a developer, I want to ensure data integrity throughout the parsing and serialization pipeline, so that road network data remains accurate and consistent.

#### Acceptance Criteria

1. THE OSM_Parser SHALL serialize the Road_Network to JSON format for caching
2. THE OSM_Parser SHALL deserialize cached JSON back to Road_Network objects
3. FOR all valid Road_Network objects, serializing then deserializing SHALL produce an equivalent Road_Network with identical node coordinates and edge connections
4. THE OSM_Parser SHALL validate that deserialized Road_Network contains the same number of nodes and edges as the original
5. IF deserialization produces a Road_Network with different node or edge counts, THEN THE OSM_Parser SHALL discard the cache and reparse the PBF file

## Non-Functional Requirements

### Performance
- Total processing time: under 30 seconds (Lambda timeout constraint)
- Cache load time: under 2 seconds
- Snap point search: under 100ms per coordinate
- Map rendering: under 3 seconds

### Resource Constraints
- Memory usage: under 512MB (Lambda limit)
- API response size: under 6MB (API Gateway limit)
- PBF file size: up to 500MB

### Reliability
- Graceful handling of malformed OSM data
- Fallback behavior when roads are disconnected
- Error messages for unreachable locations

### Maintainability
- Cached data format versioning
- Diagnostic logging for data quality issues
- Clear separation between parsing, routing, and rendering components
