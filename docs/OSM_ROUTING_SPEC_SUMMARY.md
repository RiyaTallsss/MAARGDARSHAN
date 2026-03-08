# OSM Road Network Routing - Spec Summary

## Overview

Complete specification created for implementing realistic road-based routing in MAARGDARSHAN using OpenStreetMap data. This will replace the current mathematical curve-based routing with actual road network pathfinding.

## Spec Location

`.kiro/specs/osm-road-network-routing/`

## Documents Created

1. **requirements.md** - 8 main requirements with 48 acceptance criteria
2. **design.md** - Complete system architecture, algorithms, and 32 correctness properties
3. **tasks.md** - 19 top-level tasks with 60+ sub-tasks

## Key Features

### What Will Be Implemented

1. **OSM PBF Parsing**
   - Extract roads from 500MB PBF file
   - Filter highway types: primary, secondary, tertiary, unclassified, track
   - Build graph structure with nodes and edges
   - Cache parsed data to S3 (load in ~2 seconds)

2. **Graph-Based Pathfinding**
   - A* algorithm with custom cost functions
   - 4 route types with different optimizations:
     * Shortest: Minimize distance
     * Safest: Prefer major roads, avoid tracks
     * Budget: Maximize use of paved roads
     * Social Impact: Route through settlements

3. **Snap-to-Road**
   - Find nearest road node within 500m
   - Fast lookups using KDTree spatial index (<100ms)
   - Error handling for unreachable locations

4. **Construction Classification**
   - Classify segments as "new construction" or "upgrade existing"
   - Calculate accurate cost savings (40% reduction for upgrades)
   - Show utilization percentage

5. **Frontend Visualization**
   - Display existing roads as gray lines
   - Display routes in distinct colors (blue, green, yellow, red)
   - Layer toggle to show/hide existing roads
   - Legend distinguishing roads from routes

6. **AWS Integration**
   - Maintain 512MB memory limit
   - Complete within 30 second timeout
   - Keep response under 6MB
   - Full backward compatibility with existing API

## Technical Approach

### Libraries
- **pyosmium**: Parse OSM PBF files
- **networkx**: Graph operations and pathfinding
- **scipy**: Spatial indexing (KDTree)
- **numpy**: Distance calculations

### Architecture
```
Frontend (Leaflet)
    ↓
AWS Lambda
    ├── OSM_Parser (parse PBF, build graph, cache)
    ├── Route_Calculator (A* pathfinding, cost functions)
    └── Road_Renderer (GeoJSON conversion)
    ↓
AWS S3 (PBF file, cached graph, DEM data)
```

### Performance Optimizations
1. **Caching**: Parse once, cache to S3, load in 2s
2. **Spatial Indexing**: KDTree for O(log n) snap point searches
3. **Graph Simplification**: Remove degree-2 nodes, filter by bounding box
4. **Response Management**: Downsample waypoints if approaching 6MB
5. **Parallel Calculation**: Use multiprocessing for 4 routes

## Implementation Phases

### Phase 1: Core Infrastructure (Tasks 1-5)
- Set up dependencies
- Implement OSM parser
- Build graph structure
- Implement caching system
- **Checkpoint**: Parsing and caching work end-to-end

### Phase 2: Pathfinding (Tasks 6-9)
- Implement spatial indexing
- Implement A* algorithm
- Implement 4 cost functions
- **Checkpoint**: Pathfinding works with all cost functions

### Phase 3: Integration (Tasks 10-13)
- Implement segment classification
- Integrate with Lambda function
- Implement error handling
- **Checkpoint**: Lambda integration works end-to-end

### Phase 4: Visualization (Tasks 14-15)
- Implement road rendering
- Add frontend visualization
- Add layer controls

### Phase 5: Optimization & Deployment (Tasks 16-19)
- Optimize memory and performance
- Add logging and monitoring
- Prepare deployment
- **Final Checkpoint**: All functionality works end-to-end

## Testing Strategy

### Property-Based Testing
- 32 correctness properties derived from requirements
- Using Hypothesis library (100+ iterations per property)
- Validates universal correctness across all inputs

### Unit Testing
- Specific examples and edge cases
- Error condition handling
- Integration points (S3, DEM, Bedrock)

### Integration Testing
- End-to-end Lambda execution
- Cold start vs warm start
- Response size validation
- Timeout handling

### Performance Testing
- Parse time: <60s for 500MB file
- Cache load: <2s
- Snap point search: <100ms
- Route calculation: <25s for 4 routes
- Total execution: <30s
- Memory usage: <512MB
- Response size: <6MB

## Estimated Timeline

### Minimum Viable Product (MVP)
- **Core functionality only** (skip optional test tasks marked with `*`)
- **Estimated time**: 8-10 hours
- Includes: parsing, caching, pathfinding, basic integration

### Full Implementation
- **All features including comprehensive testing**
- **Estimated time**: 12-15 hours
- Includes: all property tests, unit tests, integration tests, optimization

### Breakdown by Phase
1. Core Infrastructure: 2-3 hours
2. Pathfinding: 2-3 hours
3. Integration: 2-3 hours
4. Visualization: 1-2 hours
5. Optimization & Deployment: 2-3 hours
6. Testing (if doing all optional tests): +3-4 hours

## Benefits

### User Experience
- ✅ Routes follow actual roads (no more "floating in air")
- ✅ See existing road network on map
- ✅ Understand which parts are new vs upgrades
- ✅ More accurate cost estimates

### Technical
- ✅ Realistic routing using real OSM data
- ✅ Fast performance with caching and spatial indexing
- ✅ Scalable to larger regions
- ✅ Maintains AWS resource constraints

### Business
- ✅ More credible for hackathon presentation
- ✅ Production-ready architecture
- ✅ Extensible for future features (traffic, turn-by-turn, etc.)

## Risks & Mitigations

### Risk 1: PBF File Too Large
- **Mitigation**: Streaming parsing, graph simplification, memory monitoring

### Risk 2: Pathfinding Too Slow
- **Mitigation**: Spatial indexing, A* heuristic, parallel calculation

### Risk 3: Response Size Exceeds 6MB
- **Mitigation**: Waypoint downsampling, remove downloadable formats

### Risk 4: Lambda Timeout
- **Mitigation**: Caching, performance optimization, graceful degradation

## Next Steps

### To Start Implementation

1. **Review the spec files**:
   ```bash
   cat .kiro/specs/osm-road-network-routing/requirements.md
   cat .kiro/specs/osm-road-network-routing/design.md
   cat .kiro/specs/osm-road-network-routing/tasks.md
   ```

2. **Execute tasks sequentially**:
   - Start with Task 1 (dependencies and data structures)
   - Follow checkpoints for validation
   - Skip optional test tasks (marked with `*`) for faster MVP

3. **Use the spec workflow**:
   ```bash
   # To execute a specific task
   # Tell Kiro: "Execute task 1 from osm-road-network-routing spec"
   ```

### Quick Start (MVP Path)

If you want to get something working quickly:

1. **Tasks 1-2**: Set up dependencies and OSM parser (2 hours)
2. **Task 3**: Build graph structure (1 hour)
3. **Task 4**: Implement caching (1 hour)
4. **Tasks 6-7**: Spatial indexing and A* pathfinding (2 hours)
5. **Task 8**: Implement cost functions (1 hour)
6. **Task 11**: Integrate with Lambda (2 hours)
7. **Task 15**: Add frontend visualization (1 hour)

**Total MVP**: ~10 hours

This gives you working OSM routing without comprehensive testing. You can add tests later.

## Files That Will Be Modified

### Backend
- `lambda_function.py` - Add OSM routing integration
- `requirements-lambda.txt` - Add pyosmium, networkx, scipy
- New: `osm_routing/parser.py` - OSM parser
- New: `osm_routing/calculator.py` - Route calculator
- New: `osm_routing/renderer.py` - Road renderer
- New: `osm_routing/models.py` - Data structures

### Frontend
- `frontend/app.js` - Add road layer visualization
- `frontend/index.html` - Add layer toggle controls

### Deployment
- `deploy_lambda.sh` - Include osm_routing module
- `deploy_frontend.sh` - Deploy updated frontend

### S3
- Upload `Maps/northern-zone-260121.osm.pbf` to S3
- Create `osm/cache/` directory for cached graphs

## Success Criteria

### Functional
- ✅ Routes follow actual OSM roads
- ✅ All 4 route types work correctly
- ✅ Existing roads visible on map
- ✅ Construction classification accurate
- ✅ Error handling for unreachable locations

### Performance
- ✅ Cache load time <2s
- ✅ Route calculation <25s
- ✅ Total execution <30s
- ✅ Memory usage <512MB
- ✅ Response size <6MB

### Quality
- ✅ All property tests pass (if implemented)
- ✅ All unit tests pass
- ✅ Integration tests pass
- ✅ No regressions in existing functionality

---

**Status**: Spec complete, ready for implementation
**Date**: March 7, 2026
**Estimated Effort**: 8-15 hours depending on testing scope
