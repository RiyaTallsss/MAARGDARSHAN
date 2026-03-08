# Implementation Plan

## Phase 1: Exploration Tests (BEFORE Fix)

- [ ] 1. Write bug condition exploration tests
  - **Property 1: Fault Condition** - All 5 Bugs Demonstrated
  - **CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behavior - they will validate the fixes when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate each bug exists

  - [ ] 1.1 Test Bug 1 - Download Functionality Broken
    - Generate routes via API call to Lambda function
    - Inspect API response JSON structure for `routes[0].construction_data.downloadable_formats`
    - Verify that downloadable_formats property is undefined (removed by lines 820-824)
    - Simulate frontend downloadFormat() function call
    - **EXPECTED OUTCOME**: Test FAILS - downloadable_formats is undefined, download alert appears
    - Document counterexample: "downloadable_formats property missing from API response"
    - _Requirements: 2.1_

  - [ ] 1.2 Test Bug 2 - Settlement Count Too Low
    - Generate routes for 50+ km path (Uttarkashi to Gangotri coordinates)
    - Inspect API response for `nearby_settlements` array length for each route
    - Count settlements in the response (should be limited to 5 or fewer)
    - **EXPECTED OUTCOME**: Test FAILS - only 2-5 settlements per route instead of 10-15+
    - Document counterexample: "Settlement count is 2-5 instead of expected 10-15+ for populated region"
    - _Requirements: 2.2_

  - [ ] 1.3 Test Bug 3 - Risk Scoring Inconsistency
    - Generate all 4 routes via API call
    - Extract risk_factors (terrain_risk, flood_risk, seasonal_risk) for each route
    - Compare Safest Route's risk scores against Shortest, Budget, and Social Impact routes
    - **EXPECTED OUTCOME**: Test FAILS - Safest Route has HIGHER terrain_risk than at least one other route
    - Document counterexample: "Safest Route terrain_risk=65, Shortest Route terrain_risk=55"
    - _Requirements: 2.3_

  - [ ] 1.4 Test Bug 4 - Map Rendering Issues
    - Inspect frontend app.js drawRoutes() function colors array (line 234)
    - Verify colors array has only 2 elements: ['#3b82f6', '#10b981']
    - Generate routes and check map for visible polylines
    - **EXPECTED OUTCOME**: Test FAILS - only 2 routes (blue, green) visible on map, Budget and Social Impact routes invisible
    - Document counterexample: "Only 2 routes visible on map despite 4 routes in sidebar"
    - _Requirements: 2.4_

  - [ ] 1.5 Test Bug 5 - Missing S3 GeoJSON Files
    - Trigger Lambda function load_rivers_data() and load_settlements_data()
    - Monitor S3 API calls for NoSuchKey errors
    - Verify that functions return empty FeatureCollections: {'type': 'FeatureCollection', 'features': []}
    - Check that river_crossings arrays are empty or use fallback hardcoded data
    - **EXPECTED OUTCOME**: Test FAILS - S3 files not found, empty features returned
    - Document counterexample: "S3 paths return NoSuchKey, empty FeatureCollections used"
    - _Requirements: 2.5_

## Phase 2: Preservation Tests (BEFORE Fix)

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Functionality Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy scenarios
  - Write property-based tests capturing observed behavior patterns
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)

  - [ ] 2.1 Test Route Calculation Preservation
    - Generate routes with same start/end coordinates on unfixed system
    - Observe and record: distance_km, elevation_gain_m, estimated_cost_usd, estimated_days for each route
    - Write property: for all route generation requests, these metrics remain unchanged (within floating point tolerance)
    - Verify test passes on UNFIXED code
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ] 2.2 Test Construction Data Preservation
    - Generate routes and observe construction_data structure
    - Record: total_waypoints, max_gradient_percent, earthwork volumes, detailed_waypoints
    - Write property: for all routes, construction data calculations remain identical
    - Verify test passes on UNFIXED code
    - _Requirements: 3.4_

  - [ ] 2.3 Test Bridge Detection Preservation
    - Generate routes and observe river_crossings arrays
    - Record: bridges_required count, crossing locations
    - Write property: for all routes, bridge detection logic produces same results
    - Verify test passes on UNFIXED code
    - _Requirements: 3.5_

  - [ ] 2.4 Test User Interaction Preservation
    - Test map clicks to set start/end points on unfixed system
    - Test route card selection and highlighting
    - Test clear button functionality
    - Write property: for all user interactions, behavior remains unchanged
    - Verify test passes on UNFIXED code
    - _Requirements: 3.6_

  - [ ] 2.5 Test Cost Calculation Preservation
    - Generate routes and observe road_utilization data
    - Record: cost_savings_percent, utilization_percent, cost calculation results
    - Write property: for all routes, cost calculations considering existing roads remain accurate
    - Verify test passes on UNFIXED code
    - _Requirements: 3.3_

## Phase 3: Implementation

- [-] 3. Fix all 5 bugs in MAARGDARSHAN UI

  - [x] 3.1 Fix Bug 1 - Restore Download Functionality
    - Open lambda_function.py
    - Locate lines 820-824 that remove downloadable_formats from construction_data
    - Comment out or remove the deletion logic: `del construction_data['downloadable_formats']`
    - Keep downloadable_formats in the API response so frontend can access them
    - Alternative approach if response size is concern: modify frontend to request formats via separate API call
    - _Bug_Condition: input.action == 'download' AND input.routeData.construction_data.downloadable_formats == undefined_
    - _Expected_Behavior: Download buttons successfully generate and download KML, GPX, GeoJSON files_
    - _Preservation: All other construction_data fields and route calculations remain unchanged_
    - _Requirements: 2.1_

  - [x] 3.2 Fix Bug 2 - Increase Settlement Detection
    - Open lambda_function.py
    - Locate find_nearby_settlements() function (around line 289)
    - Change default radius parameter from 5km to 8-10km: `radius_km=10`
    - Change return limit from `return nearby[:10]` to `return nearby[:20]`
    - Locate route response limits (lines 798, 806, 814, 822)
    - Change settlement limits from `[:5]` to `[:10]` or `[:15]` for all routes
    - Keep Social Impact route's wider radius (already 8km)
    - _Bug_Condition: input.action == 'generate_routes' AND count(input.routeData.nearby_settlements) <= 2_
    - _Expected_Behavior: Settlement counts are 5-10+ per route for populated regions_
    - _Preservation: Settlement detection algorithm and proximity calculations remain unchanged_
    - _Requirements: 2.2_

  - [x] 3.3 Fix Bug 3 - Correct Risk Scoring for Safest Route
    - Open lambda_function.py
    - Locate Safest Route generation (around lines 745-746)
    - Reduce curve_factor from 0.3 to 0.2 to avoid steep terrain
    - Locate terrain risk calculation for Safest Route (around lines 765-768)
    - Add explicit terrain risk reduction: `terrain_risk_safest = min(terrain_risk_safest, min(terrain_risk_shortest, terrain_risk_budget, terrain_risk_social) - 10)`
    - Add validation logic to ensure all risk factors (terrain, flood, seasonal) for Safest Route are lower than other routes
    - If Safest Route has higher risk, adjust it to be 10 points lower than the minimum of other routes
    - _Bug_Condition: input.action == 'calculate_risk' AND input.routeData.name == 'Safest Route' AND (terrain_risk > other_routes OR flood_risk > other_routes)_
    - _Expected_Behavior: Safest Route has LOWEST risk scores across all metrics (terrain, flood, seasonal)_
    - _Preservation: Risk calculation formulas for other routes remain unchanged_
    - _Requirements: 2.3_

  - [x] 3.4 Fix Bug 4 - Render All 4 Routes on Map
    - Open frontend/app.js (and frontend/app_v2.js if it's the active version)
    - Locate drawRoutes() function (around line 234)
    - Find colors array: `const colors = ['#3b82f6', '#10b981']`
    - Expand to 4 colors: `const colors = ['#3b82f6', '#10b981', '#f97316', '#a855f7']`
    - This adds orange (#f97316) for Budget Route and purple (#a855f7) for Social Impact Route
    - Verify colors match route names: blue=Shortest, green=Safest, orange=Budget, purple=Social
    - _Bug_Condition: input.action == 'render_map' AND input.routeIndex >= 2 AND route_polyline_not_visible_
    - _Expected_Behavior: All 4 routes visible on map with distinct colors matching legend_
    - _Preservation: Map rendering logic, polyline creation, and route highlighting remain unchanged_
    - _Requirements: 2.4_

  - [x] 3.5 Fix Bug 5 - Load S3 GeoJSON Data or Extract from OSM
    - **Option A (Recommended)**: Create OSM extraction script
      - Create new Python script: extract_osm_to_geojson.py
      - Use osmium or pyosmium library to parse osm/northern-zone-260121.osm.pbf
      - Extract rivers: filter features with tags waterway=river or waterway=stream
      - Extract settlements: filter features with tags place=village, place=town, place=hamlet
      - Convert to GeoJSON format with proper geometry and properties
      - Upload to S3 paths: geospatial-data/uttarkashi/rivers/uttarkashi_rivers.geojson and geospatial-data/uttarkashi/villages/settlements.geojson
      - Run script to populate S3 bucket with real data
    - **Option B (Fallback)**: Modify Lambda to parse OSM directly
      - Open lambda_function.py
      - Locate load_rivers_data() and load_settlements_data() functions (lines 177-206)
      - Add OSM parsing logic in exception handlers when S3 files not found
      - Cache extracted data in memory or temporary S3 location
    - **Option C (Quick Fix)**: Update S3 paths if files exist elsewhere
      - Check S3 bucket for existing GeoJSON files
      - Update file paths in load_rivers_data() and load_settlements_data()
    - _Bug_Condition: input.action == 'load_s3_data' AND s3_file_not_found AND returned_empty_features_
    - _Expected_Behavior: Successfully load rivers and settlements data from S3 or OSM, return FeatureCollections with features.length > 0_
    - _Preservation: Data loading logic, feature processing, and fallback behavior remain unchanged_
    - _Requirements: 2.5_

  - [ ] 3.6 Verify all bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - All 5 Bugs Fixed
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied

    - [ ] 3.6.1 Re-run Bug 1 test - Download Functionality
      - Run test from task 1.1 on FIXED code
      - Verify downloadable_formats property exists in API response
      - Verify download buttons successfully generate and download files
      - **EXPECTED OUTCOME**: Test PASSES (confirms Bug 1 is fixed)
      - _Requirements: 2.1_

    - [ ] 3.6.2 Re-run Bug 2 test - Settlement Count
      - Run test from task 1.2 on FIXED code
      - Verify nearby_settlements array has 10-20 elements
      - Verify frontend displays 5-10+ settlements per route
      - **EXPECTED OUTCOME**: Test PASSES (confirms Bug 2 is fixed)
      - _Requirements: 2.2_

    - [ ] 3.6.3 Re-run Bug 3 test - Risk Scoring
      - Run test from task 1.3 on FIXED code
      - Verify Safest Route has LOWEST terrain_risk, flood_risk, and seasonal_risk
      - Verify Safest Route overall risk_score is lowest among all routes
      - **EXPECTED OUTCOME**: Test PASSES (confirms Bug 3 is fixed)
      - _Requirements: 2.3_

    - [ ] 3.6.4 Re-run Bug 4 test - Map Rendering
      - Run test from task 1.4 on FIXED code
      - Verify colors array has 4 elements
      - Verify all 4 routes are visible on map with correct colors
      - **EXPECTED OUTCOME**: Test PASSES (confirms Bug 4 is fixed)
      - _Requirements: 2.4_

    - [ ] 3.6.5 Re-run Bug 5 test - S3 GeoJSON Loading
      - Run test from task 1.5 on FIXED code
      - Verify load_rivers_data() returns FeatureCollection with features.length > 0
      - Verify load_settlements_data() returns FeatureCollection with features.length > 0
      - **EXPECTED OUTCOME**: Test PASSES (confirms Bug 5 is fixed)
      - _Requirements: 2.5_

  - [ ] 3.7 Verify preservation tests still pass
    - **Property 2: Preservation** - No Regressions
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run all preservation property tests from Phase 2
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions)

    - [ ] 3.7.1 Re-run Route Calculation Preservation test
      - Run test from task 2.1 on FIXED code
      - Verify distance, elevation, cost, and construction days remain unchanged
      - **EXPECTED OUTCOME**: Test PASSES
      - _Requirements: 3.1, 3.2, 3.3_

    - [ ] 3.7.2 Re-run Construction Data Preservation test
      - Run test from task 2.2 on FIXED code
      - Verify waypoints, gradients, and earthwork calculations remain unchanged
      - **EXPECTED OUTCOME**: Test PASSES
      - _Requirements: 3.4_

    - [ ] 3.7.3 Re-run Bridge Detection Preservation test
      - Run test from task 2.3 on FIXED code
      - Verify river crossings and bridge detection remain unchanged
      - **EXPECTED OUTCOME**: Test PASSES
      - _Requirements: 3.5_

    - [ ] 3.7.4 Re-run User Interaction Preservation test
      - Run test from task 2.4 on FIXED code
      - Verify map clicks, route selection, and clear button work identically
      - **EXPECTED OUTCOME**: Test PASSES
      - _Requirements: 3.6_

    - [ ] 3.7.5 Re-run Cost Calculation Preservation test
      - Run test from task 2.5 on FIXED code
      - Verify cost calculations and road utilization remain unchanged
      - **EXPECTED OUTCOME**: Test PASSES
      - _Requirements: 3.3_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Verify all 5 bug condition tests pass (task 3.6)
  - Verify all 5 preservation tests pass (task 3.7)
  - Test full user flow: click map → generate routes → view all 4 routes → download files
  - Test with various route lengths (10km, 50km, 100km) to ensure fixes work across scenarios
  - Test edge cases (routes with no settlements, no river crossings) for graceful handling
  - If any tests fail, investigate and fix before marking complete
  - Ask user if questions arise or if manual testing is needed
