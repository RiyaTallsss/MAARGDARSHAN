# Bugfix Requirements Document

## Introduction

This document addresses five critical bugs in the MAARGDARSHAN rural infrastructure planning system that affect data export functionality, data accuracy, risk calculation logic, map visualization, and missing geospatial data files. These bugs impact the usability and reliability of the route planning system for field engineers and decision-makers in Uttarakhand's rural infrastructure projects.

The system currently generates 4 route alternatives (Shortest, Safest, Budget, Social Impact) but has defects in download functionality, settlement detection, risk scoring consistency, map rendering, and missing S3 data files that need to be fixed to ensure the system provides accurate and actionable route planning data.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a user clicks any download button (KML, GPX, or GeoJSON) for route data THEN the system displays "Download data not available" error message instead of generating the file

1.2 WHEN the system generates routes THEN it shows only 2 settlements per route in the route comparison table, which is unrealistically low for routes spanning 50-100+ km in populated regions

1.3 WHEN the system calculates risk scores for the "Safest Route" THEN it assigns HIGHER flood risk and terrain risk values than the "Social Impact Route", contradicting the route's safety purpose

1.4 WHEN the system renders all 4 routes on the interactive map THEN only the Shortest Route (blue) and Safest Route (green) are visible, while Budget Route (orange) and Social Impact Route (purple) do not appear on the map despite being present in the route comparison table

1.5 WHEN the system attempts to load rivers and settlements data from S3 THEN it fails because the GeoJSON files (geospatial-data/uttarkashi/rivers/uttarkashi_rivers.geojson and geospatial-data/uttarkashi/villages/settlements.geojson) do not exist in the S3 bucket, causing the system to return empty feature collections and rely on fallback hardcoded data

### Expected Behavior (Correct)

2.1 WHEN a user clicks any download button (KML, GPX, or GeoJSON) for route data THEN the system SHALL generate and download the corresponding file format with complete route waypoints, elevations, and metadata for use in Google Earth, GPS devices, or GIS software

2.2 WHEN the system generates routes THEN it SHALL detect and display 5-10+ settlements per route based on actual proximity to the route path, providing realistic connectivity data for infrastructure planning

2.3 WHEN the system calculates risk scores for the "Safest Route" THEN it SHALL assign the LOWEST risk scores across all risk metrics (terrain, flood, seasonal) compared to other route alternatives, ensuring the route fulfills its safety-focused purpose

2.4 WHEN the system renders all 4 routes on the interactive map THEN it SHALL display all routes (Shortest, Safest, Budget, Social Impact) with their distinct colors (blue, green, orange, purple) as polylines on the map, matching the route legend and comparison table

2.5 WHEN the system attempts to load rivers and settlements data from S3 THEN it SHALL successfully retrieve the GeoJSON files from the correct S3 paths OR extract this data from the existing OSM PBF file (northern-zone-260121.osm.pbf) to provide accurate river crossing and settlement proximity data

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the system generates route alternatives THEN it SHALL CONTINUE TO calculate distance, elevation gain, cost estimates, and construction days accurately for all 4 routes

3.2 WHEN a user clicks on a route card in the sidebar THEN it SHALL CONTINUE TO highlight the selected route on the map and display its details

3.3 WHEN the system displays construction details THEN it SHALL CONTINUE TO show bridges required, waypoints, gradients, and earthwork calculations correctly

3.4 WHEN the system renders bridge markers and settlement markers on the map THEN it SHALL CONTINUE TO display them with appropriate icons and popup information

3.5 WHEN a user clicks the "Clear & Start Over" button THEN it SHALL CONTINUE TO remove all markers, routes, and reset the application state properly

3.6 WHEN the system calculates costs for routes THEN it SHALL CONTINUE TO factor in existing road utilization, terrain difficulty, and bridge requirements accurately
