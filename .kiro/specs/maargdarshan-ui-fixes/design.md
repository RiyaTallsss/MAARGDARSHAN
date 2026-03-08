# MAARGDARSHAN UI Fixes - Bugfix Design

## Overview

This design addresses five critical bugs in the MAARGDARSHAN rural infrastructure planning system that affect data export, settlement detection, risk calculation consistency, map visualization, and missing geospatial data. The bugs span both frontend (JavaScript) and backend (Python Lambda) components, requiring coordinated fixes to restore full functionality while preserving existing working features.

The fix strategy follows a systematic approach: restore download functionality by re-including format data in API responses, increase settlement detection radius and remove artificial limits, correct risk calculation logic to ensure the Safest Route has the lowest risk scores, fix map rendering to display all 4 routes, and either upload missing GeoJSON files to S3 or extract the data from the existing OSM PBF file.

## Glossary

- **Bug_Condition (C)**: The conditions that trigger each of the 5 bugs - download button clicks, route generation, risk score calculation, map rendering, and S3 data loading
- **Property (P)**: The desired correct behavior - successful downloads, realistic settlement counts (5-10+), lowest risk scores for Safest Route, all 4 routes visible on map, successful GeoJSON loading
- **Preservation**: All existing functionality that must remain unchanged - route calculation accuracy, cost estimates, construction data, bridge detection, user interactions
- **downloadable_formats**: The KML, GPX, and GeoJSON file content generated in `generate_construction_data()` function in lambda_function.py
- **drawRoutes()**: The frontend function in app.js that renders route polylines on the Leaflet map
- **colors array**: The hardcoded color array `['#3b82f6', '#10b981']` in frontend that only defines 2 colors instead of 4
- **find_nearby_settlements()**: The backend function that detects settlements within a radius of route waypoints
- **risk_score calculation**: The logic that computes overall risk scores and individual risk factors (terrain, flood, seasonal) for each route
- **S3_BUCKET**: The S3 bucket 'maargdarshan-data' that should contain GeoJSON files for rivers and settlements

## Bug Details

### Fault Condition

The bugs manifest in five distinct scenarios:

**Bug 1 - Download Functionality**: When a user clicks any download button (KML, GPX, or GeoJSON), the `downloadFormat()` function in app.js checks for `route.construction_data.downloadable_formats` but this property does not exist because the Lambda function explicitly removes it before sending the API response (line 820-824 in lambda_function.py removes the downloadable_formats and replaces it with downloadable_formats_available).

**Bug 2 - Settlement Count**: When the system generates routes, the `find_nearby_settlements()` function uses a default radius of 5km and returns only the top 10 settlements (line 289 in lambda_function.py: `return nearby[:10]`), but the frontend further limits this to 5 settlements (line 798 in lambda_function.py: `'nearby_settlements': nearby_settlements_shortest[:5]`), resulting in only 2 settlements being displayed per route in practice.

**Bug 3 - Risk Scoring Inconsistency**: When calculating risk scores for the Safest Route, the code applies reduction factors to flood and seasonal risk (lines 777-778: `flood_risk_safest = max(20, flood_risk_shortest - 15)` and `rainfall_risk * 0.8`) but the terrain risk for the Safest Route is calculated independently from actual terrain data and can end up HIGHER than other routes due to the curved waypoint generation with curve_factor=0.3 creating steeper terrain.

**Bug 4 - Map Rendering**: When the `drawRoutes()` function renders routes on the map, it only defines 2 colors in the colors array: `const colors = ['#3b82f6', '#10b981']` (line 234 in app.js), so routes at index 2 and 3 (Budget and Social Impact) have undefined colors and are not rendered as visible polylines.

**Bug 5 - Missing S3 Files**: When the Lambda function attempts to load rivers and settlements data via `load_rivers_data()` and `load_settlements_data()` functions (lines 177-206), it tries to fetch from S3 paths `geospatial-data/uttarkashi/rivers/uttarkashi_rivers.geojson` and `geospatial-data/uttarkashi/villages/settlements.geojson`, but these files do not exist in the S3 bucket, causing the functions to catch exceptions and return empty FeatureCollections, which results in no river crossings or settlements being detected from real data.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {action: string, routeIndex: number, routeData: object}
  OUTPUT: boolean
  
  RETURN (input.action == 'download' AND input.routeData.construction_data.downloadable_formats == undefined)
         OR (input.action == 'generate_routes' AND count(input.routeData.nearby_settlements) <= 2)
         OR (input.action == 'calculate_risk' AND input.routeData.name == 'Safest Route' 
             AND (input.routeData.risk_factors.terrain_risk > other_routes.terrain_risk 
                  OR input.routeData.risk_factors.flood_risk > other_routes.flood_risk))
         OR (input.action == 'render_map' AND input.routeIndex >= 2 AND route_polyline_not_visible)
         OR (input.action == 'load_s3_data' AND s3_file_not_found AND returned_empty_features)
END FUNCTION
```

### Examples

- **Bug 1 Example**: User clicks "KML" download button for Shortest Route → `downloadFormat(0, 'kml')` executes → checks `state.routes[0].construction_data.downloadable_formats` → property is undefined → alert shows "Download data not available"

- **Bug 2 Example**: System generates routes for 50km path through populated region → `find_nearby_settlements()` finds 15 settlements within 5km → returns only top 10 → Lambda response limits to 5 → frontend displays only 2 in the UI construction details section

- **Bug 3 Example**: Safest Route is generated with curve_factor=0.3 → waypoints follow curved path through steeper terrain → `calculate_terrain_risk()` computes terrain_risk=65 → Shortest Route has terrain_risk=55 → Safest Route shows HIGHER terrain risk despite being the "safest" option

- **Bug 4 Example**: System generates 4 routes → `drawRoutes()` iterates through all 4 → for routes[2] (Budget Route), colors[2] is undefined → polyline is created but with undefined color → not visible on map → only blue (Shortest) and green (Safest) routes appear

- **Bug 5 Example**: Lambda function calls `load_rivers_data()` → attempts `s3.get_object(Bucket='maargdarshan-data', Key='geospatial-data/uttarkashi/rivers/uttarkashi_rivers.geojson')` → S3 returns NoSuchKey error → exception caught → returns `{'type': 'FeatureCollection', 'features': []}` → no river crossings detected

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Route generation algorithm must continue to calculate distance, elevation gain, cost estimates, and construction days accurately for all 4 routes
- Construction data generation (waypoints, gradients, cut/fill volumes, earthwork calculations) must remain unchanged
- Bridge detection logic and river crossing identification must continue to work correctly
- User interactions (map clicks, route card selection, clear button) must continue to function as before
- Cost calculation considering existing road utilization must remain accurate
- AI explanation generation via Bedrock must continue to work
- All other risk factors and metrics not related to the bugs must remain unchanged

**Scope:**
All inputs and behaviors that do NOT involve the 5 specific bug conditions should be completely unaffected by these fixes. This includes:
- Route waypoint generation and interpolation logic
- Elevation data retrieval from DEM
- Cost calculation formulas
- Construction difficulty scoring
- Social impact score calculation
- Tourism spot detection
- Existing road utilization calculation
- All other API endpoints and Lambda functionality

## Hypothesized Root Cause

Based on the bug analysis and code review, the root causes are:

1. **Download Functionality Bug**: The Lambda function explicitly removes `downloadable_formats` from the construction_data object before sending the API response (lines 820-824 in lambda_function.py). This was likely done to reduce response size, but the frontend code still expects this property to exist. The removal logic deletes the actual format content and replaces it with `downloadable_formats_available` array, but the frontend's `downloadFormat()` function was never updated to handle this change.

2. **Settlement Count Bug**: Multiple limiting factors compound to produce unrealistically low settlement counts:
   - Default radius of 5km in `find_nearby_settlements()` is too small for rural mountainous terrain
   - Function returns only top 10 settlements (`return nearby[:10]` on line 289)
   - Lambda response further limits to 5 settlements for most routes (line 798)
   - Frontend may have additional display limits in the UI rendering
   - The combination results in only 2 settlements being shown per route

3. **Risk Scoring Inconsistency Bug**: The Safest Route uses a higher curve_factor (0.3 vs 0.15 for Shortest) to avoid risks, but this creates a longer, more curved path that can traverse steeper terrain. The `calculate_terrain_risk()` function calculates risk based on actual elevation changes, so the curved path can have higher terrain risk. Additionally, the risk reduction logic only applies to flood and seasonal risks, not terrain risk, creating an inconsistency where the "Safest" route has higher terrain risk than other routes.

4. **Map Rendering Bug**: The `colors` array in the `drawRoutes()` function is hardcoded with only 2 colors: `['#3b82f6', '#10b981']`. When the loop iterates to index 2 and 3 for Budget and Social Impact routes, `colors[2]` and `colors[3]` return undefined. The Leaflet polyline is created with `color: undefined`, which results in no visible line being rendered on the map. The routes exist in the data and appear in the sidebar, but are invisible on the map.

5. **Missing S3 Files Bug**: The GeoJSON files for rivers and settlements do not exist at the specified S3 paths. The code expects them at `geospatial-data/uttarkashi/rivers/uttarkashi_rivers.geojson` and `geospatial-data/uttarkashi/villages/settlements.geojson`, but these files were never uploaded to the S3 bucket. The system has an OSM PBF file (`osm/northern-zone-260121.osm.pbf`) that contains this data, but there's no extraction logic to convert OSM data to GeoJSON format. The fallback behavior returns empty feature collections, causing the system to rely on hardcoded data instead of real geospatial data.

## Correctness Properties

Property 1: Fault Condition - Download Functionality Restored

_For any_ user action where a download button (KML, GPX, or GeoJSON) is clicked for any route, the fixed system SHALL generate and download the corresponding file format with complete route waypoints, elevations, and metadata, successfully creating a downloadable blob and triggering the browser download.

**Validates: Requirements 2.1**

Property 2: Fault Condition - Realistic Settlement Detection

_For any_ route generation request where the route spans 50+ km through populated regions, the fixed system SHALL detect and display 5-10+ settlements per route based on actual proximity to the route path (within 8-10km radius), providing realistic connectivity data for infrastructure planning.

**Validates: Requirements 2.2**

Property 3: Fault Condition - Safest Route Risk Consistency

_For any_ route generation request, the fixed system SHALL ensure that the "Safest Route" has the LOWEST risk scores across all risk metrics (terrain_risk, flood_risk, seasonal_risk) compared to all other route alternatives (Shortest, Budget, Social Impact), fulfilling its safety-focused purpose.

**Validates: Requirements 2.3**

Property 4: Fault Condition - All Routes Visible on Map

_For any_ route generation request that produces 4 route alternatives, the fixed system SHALL render all 4 routes (Shortest, Safest, Budget, Social Impact) as visible polylines on the interactive map with their distinct colors (blue, green, orange, purple), matching the route legend and comparison table.

**Validates: Requirements 2.4**

Property 5: Fault Condition - S3 GeoJSON Data Loading

_For any_ route generation request, the fixed system SHALL successfully load rivers and settlements data either from the correct S3 GeoJSON file paths OR by extracting this data from the existing OSM PBF file, providing accurate river crossing and settlement proximity data instead of returning empty feature collections.

**Validates: Requirements 2.5**

Property 6: Preservation - Route Calculation Accuracy

_For any_ route generation request, the fixed system SHALL continue to calculate distance, elevation gain, cost estimates, construction days, and all other metrics with the same accuracy as the original system, preserving all existing calculation logic not related to the 5 bugs.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `lambda_function.py`

**Function**: `generate_routes_with_real_data()`

**Specific Changes**:

1. **Restore Download Formats in API Response** (Bug 1):
   - Remove or comment out lines 820-824 that delete `downloadable_formats` from construction_data
   - Keep the downloadable formats in the API response so frontend can access them
   - Alternative: Modify frontend to request formats via separate API call if response size is a concern
   - Location: Lines 820-824 in the route generation function

2. **Increase Settlement Detection** (Bug 2):
   - Change default radius parameter in `find_nearby_settlements()` from 5km to 8-10km for better coverage in rural areas
   - Increase the return limit from `[:10]` to `[:20]` to allow more settlements
   - Remove or increase the limits in the route response (lines 798, 806, 814, 822) from `[:5]` to `[:10]` or `[:15]`
   - For Social Impact route, use even wider radius (already 8km, keep it)
   - Location: Line 289 (return limit), lines 798-822 (response limits)

3. **Fix Risk Scoring for Safest Route** (Bug 3):
   - Modify the Safest Route generation to use a smaller curve_factor (0.2 instead of 0.3) to avoid steep terrain
   - Add explicit terrain risk reduction for Safest Route: `terrain_risk_safest = min(terrain_risk_safest, min(terrain_risk_shortest, terrain_risk_budget, terrain_risk_social) - 10)`
   - Ensure all risk factors (terrain, flood, seasonal) for Safest Route are lower than other routes
   - Add validation logic to check and adjust if Safest Route has higher risk than any other route
   - Location: Lines 745-746 (curve factor), lines 765-768 (terrain risk calculation)

**File**: `frontend/app.js` (and `frontend/app_v2.js` if it's the active version)

**Function**: `drawRoutes()`

**Specific Changes**:

4. **Fix Map Rendering for All 4 Routes** (Bug 4):
   - Expand the colors array from 2 colors to 4 colors: `const colors = ['#3b82f6', '#10b981', '#f97316', '#a855f7']`
   - This adds orange (#f97316) for Budget Route and purple (#a855f7) for Social Impact Route
   - Ensure the colors match the route names and legend
   - Location: Line 234 in app.js, line 234 in app_v2.js

**File**: `lambda_function.py` OR new S3 upload script

**Function**: `load_rivers_data()` and `load_settlements_data()`

**Specific Changes**:

5. **Fix Missing S3 GeoJSON Files** (Bug 5):
   - **Option A (Recommended)**: Create a Python script to extract rivers and settlements from the existing OSM PBF file and upload as GeoJSON to S3
     - Use `osmium` or `pyosmium` library to parse `osm/northern-zone-260121.osm.pbf`
     - Extract all features with tags `waterway=river` or `waterway=stream` for rivers
     - Extract all features with tags `place=village`, `place=town`, `place=hamlet` for settlements
     - Convert to GeoJSON format and upload to the expected S3 paths
   - **Option B (Fallback)**: Modify the Lambda function to parse OSM PBF directly when GeoJSON files are not found
     - Add OSM parsing logic in the exception handlers of `load_rivers_data()` and `load_settlements_data()`
     - Cache the extracted data in memory or temporary S3 location
   - **Option C (Quick Fix)**: Update the S3 paths to point to existing GeoJSON files if they exist elsewhere in the bucket
   - Location: Lines 177-206 (load functions), new extraction script needed

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate each bug on unfixed code, then verify the fixes work correctly and preserve existing behavior. Each bug will be tested independently and then together to ensure no regressions.

### Exploratory Fault Condition Checking

**Goal**: Surface counterexamples that demonstrate all 5 bugs BEFORE implementing the fixes. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate user interactions and API calls for each bug scenario. Run these tests on the UNFIXED code to observe failures and understand the root causes.

**Test Cases**:

1. **Download Functionality Test** (will fail on unfixed code):
   - Generate routes via API call
   - Inspect the API response JSON structure
   - Verify that `routes[0].construction_data.downloadable_formats` is undefined
   - Simulate clicking download button in frontend
   - Verify that "Download data not available" alert appears
   - Expected counterexample: downloadable_formats property missing from API response

2. **Settlement Count Test** (will fail on unfixed code):
   - Generate routes for a 50+ km path (e.g., Uttarkashi to Gangotri)
   - Inspect the API response for `nearby_settlements` array length
   - Count settlements displayed in the frontend UI
   - Verify that only 2-5 settlements appear per route despite the region being populated
   - Expected counterexample: Settlement count is 2-5 instead of 10-15+

3. **Risk Scoring Consistency Test** (will fail on unfixed code):
   - Generate all 4 routes via API call
   - Extract risk_factors for each route
   - Compare Safest Route's terrain_risk, flood_risk, and seasonal_risk against other routes
   - Verify that Safest Route has HIGHER terrain_risk or flood_risk than at least one other route
   - Expected counterexample: Safest Route terrain_risk=65, Shortest Route terrain_risk=55

4. **Map Rendering Test** (will fail on unfixed code):
   - Generate routes and render on map
   - Inspect the colors array in drawRoutes() function
   - Verify that colors array has only 2 elements
   - Check map for visible polylines - only blue and green should be visible
   - Verify that Budget Route (orange) and Social Impact Route (purple) are not visible
   - Expected counterexample: Only 2 routes visible on map despite 4 routes in sidebar

5. **S3 GeoJSON Loading Test** (will fail on unfixed code):
   - Trigger Lambda function to load rivers and settlements data
   - Monitor S3 API calls and catch NoSuchKey errors
   - Verify that load_rivers_data() and load_settlements_data() return empty FeatureCollections
   - Check that river_crossings and nearby_settlements arrays are empty or use fallback data
   - Expected counterexample: S3 files not found, empty features returned

**Expected Counterexamples**:
- Download buttons trigger "Download data not available" alert
- Settlement counts are 2-5 per route instead of 10-15+
- Safest Route has higher terrain risk (65) than Shortest Route (55)
- Only 2 routes (blue, green) visible on map instead of 4
- S3 GeoJSON files return NoSuchKey errors, empty features used

### Fix Checking

**Goal**: Verify that for all inputs where the bug conditions hold, the fixed functions produce the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixed_system(input)
  ASSERT expectedBehavior(result)
END FOR

WHERE expectedBehavior(result) IS:
  - Download buttons successfully generate and download files
  - Settlement counts are 5-10+ per route for populated regions
  - Safest Route has lowest risk scores across all metrics
  - All 4 routes are visible on map with correct colors
  - S3 GeoJSON data loads successfully or OSM data is extracted
```

**Test Cases**:

1. **Download Functionality Fix Verification**:
   - Generate routes via API call with fixed Lambda
   - Verify `routes[0].construction_data.downloadable_formats` exists and contains kml, gpx, geojson keys
   - Simulate clicking each download button (KML, GPX, GeoJSON)
   - Verify that files are generated and downloaded successfully
   - Verify file content is valid (KML has proper XML structure, GPX has trackpoints, GeoJSON has valid geometry)

2. **Settlement Count Fix Verification**:
   - Generate routes for 50+ km path with fixed Lambda
   - Verify that `nearby_settlements` array has 10-20 elements in API response
   - Verify that frontend displays 5-10+ settlements per route
   - Verify that settlements are within 8-10km of route path
   - Test with different route lengths and verify settlement count scales appropriately

3. **Risk Scoring Fix Verification**:
   - Generate all 4 routes with fixed Lambda
   - Extract risk_factors for each route
   - Verify that Safest Route has the LOWEST terrain_risk among all routes
   - Verify that Safest Route has the LOWEST flood_risk among all routes
   - Verify that Safest Route has the LOWEST seasonal_risk among all routes
   - Verify that overall risk_score for Safest Route is lowest

4. **Map Rendering Fix Verification**:
   - Generate routes and render on map with fixed frontend
   - Verify that colors array has 4 elements: ['#3b82f6', '#10b981', '#f97316', '#a855f7']
   - Verify that all 4 polylines are visible on the map
   - Verify that each route has the correct color (blue=Shortest, green=Safest, orange=Budget, purple=Social)
   - Verify that clicking on each route card highlights the corresponding polyline

5. **S3 GeoJSON Fix Verification**:
   - Trigger Lambda function with fixed S3 data or OSM extraction
   - Verify that load_rivers_data() returns FeatureCollection with features array length > 0
   - Verify that load_settlements_data() returns FeatureCollection with features array length > 0
   - Verify that river_crossings arrays have detected crossings
   - Verify that nearby_settlements arrays have settlements from real GeoJSON data

### Preservation Checking

**Goal**: Verify that for all inputs where the bug conditions do NOT hold, the fixed system produces the same result as the original system.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT original_system(input) = fixed_system(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for non-bug scenarios, then write property-based tests capturing that behavior.

**Test Cases**:

1. **Route Calculation Preservation**: Verify that distance, elevation gain, cost estimates, and construction days remain unchanged for all routes
   - Generate routes with same start/end coordinates on both unfixed and fixed systems
   - Compare distance_km, elevation_gain_m, estimated_cost_usd, estimated_days for each route
   - Verify that values are identical (within floating point tolerance)

2. **Construction Data Preservation**: Verify that waypoint generation, gradient analysis, cut/fill volumes, and earthwork calculations remain unchanged
   - Compare construction_data.total_waypoints, max_gradient_percent, earthwork volumes
   - Verify that detailed_waypoints have same chainage, elevations, and gradients

3. **Bridge Detection Preservation**: Verify that river crossing detection and bridge requirements remain unchanged
   - Compare river_crossings arrays for each route
   - Verify that bridges_required count is identical

4. **User Interaction Preservation**: Verify that map clicks, route card selection, and clear button continue to work
   - Test clicking on map to set start/end points
   - Test clicking on route cards to highlight routes
   - Test clear button to reset application state
   - Verify all interactions work identically to unfixed version

5. **Cost Calculation Preservation**: Verify that cost calculation considering existing road utilization remains accurate
   - Compare road_utilization data for each route
   - Verify that cost_savings_percent and utilization_percent are unchanged
   - Verify that cost calculation formulas produce same results

6. **AI Explanation Preservation**: Verify that Bedrock AI explanation generation continues to work
   - Compare ai_explanation text for same routes
   - Verify that Bedrock API calls are made successfully
   - Verify that explanation quality and format remain unchanged

### Unit Tests

- Test `downloadFormat()` function with valid route data containing downloadable_formats
- Test `find_nearby_settlements()` with various radius values (5km, 8km, 10km) and verify settlement counts
- Test risk score calculation logic for all 4 routes and verify Safest Route has lowest scores
- Test `drawRoutes()` function with 4-element colors array and verify all polylines are created
- Test `load_rivers_data()` and `load_settlements_data()` with mocked S3 responses (success and failure cases)
- Test OSM data extraction script (if implemented) with sample OSM PBF file

### Property-Based Tests

- Generate random start/end coordinates within Uttarakhand bounds and verify all 4 routes are generated correctly
- Generate random route configurations and verify settlement counts scale with route length and radius
- Generate random elevation profiles and verify Safest Route always has lowest terrain risk
- Generate random route data and verify all 4 routes render on map with distinct colors
- Test S3 data loading with various file availability scenarios and verify graceful fallback

### Integration Tests

- Test full user flow: click map → generate routes → view all 4 routes on map → click download buttons → verify files download
- Test route generation with real S3 data and verify river crossings and settlements are detected from GeoJSON
- Test that fixing one bug does not break the fixes for other bugs (cross-bug regression testing)
- Test with various route lengths (10km, 50km, 100km) and verify all fixes work correctly
- Test with edge cases (routes with no settlements, routes with no river crossings) and verify system handles gracefully
