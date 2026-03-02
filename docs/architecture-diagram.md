# MAARGDARSHAN - System Architecture Diagram

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                           │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Web App    │  │  Mobile App  │  │  API Client  │          │
│  │  (React/Vue) │  │  (Optional)  │  │   (cURL)     │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                   │
└─────────┼──────────────────┼──────────────────┼──────────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                    ┌────────▼────────┐
                    │   FastAPI       │
                    │   REST API      │
                    │   + WebSocket   │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
┌─────────▼─────────┐ ┌─────▼──────┐ ┌────────▼────────┐
│  Route Generator  │ │    Risk    │ │   AI Reasoning  │
│   (A* Algorithm)  │ │  Assessor  │ │  (Bedrock API)  │
│                   │ │            │ │                 │
│ • Cost Surface    │ │ • Terrain  │ │ • Claude Model  │
│ • Pathfinding     │ │ • Flood    │ │ • Explanations  │
│ • Optimization    │ │ • Seasonal │ │ • Trade-offs    │
└─────────┬─────────┘ └─────┬──────┘ └────────┬────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
┌─────────▼─────────┐ ┌─────▼──────┐ ┌────────▼────────┐
│  DEM Processor    │ │    OSM     │ │  Weather API    │
│   (GDAL/Rasterio)│ │   Parser   │ │     Client      │
│                   │ │  (OSMnx)   │ │                 │
│ • Slope Calc     │ │ • Roads    │ │ • Rainfall      │
│ • Elevation      │ │ • Settlements│ │ • Forecasts    │
│ • Terrain        │ │ • Infrastructure│ │ • History   │
└─────────┬─────────┘ └─────┬──────┘ └────────┬────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                    ┌────────▼────────┐
                    │   API Client    │
                    │  (Multi-source) │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
┌─────────▼─────────┐ ┌─────▼──────┐ ┌────────▼────────┐
│  External APIs    │ │  AWS S3    │ │  Local Files    │
│                   │ │  Storage   │ │   (Fallback)    │
│ • NASA SRTM      │ │            │ │                 │
│ • Overpass API   │ │ • DEM Data │ │ • OSM PBF       │
│ • OpenWeather    │ │ • Datasets │ │ • Rainfall CSV  │
│ • IMD APIs       │ │ • Cache    │ │ • Flood PDFs    │
└───────────────────┘ └────────────┘ └─────────────────┘
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                 │
└─────────────────────────────────────────────────────────────────┘

User Input (Start/End Coordinates)
         │
         ▼
┌─────────────────────┐
│  1. Data Ingestion  │
│  ─────────────────  │
│  • Fetch DEM data   │
│  • Query OSM data   │
│  • Get weather data │
│  • Load flood zones │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  2. Preprocessing   │
│  ─────────────────  │
│  • Calculate slopes │
│  • Extract roads    │
│  • Identify risks   │
│  • Build cost map   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  3. Route Gen       │
│  ─────────────────  │
│  • A* pathfinding   │
│  • Generate 3 routes│
│  • Calculate metrics│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  4. Risk Assessment │
│  ─────────────────  │
│  • Terrain risk     │
│  • Flood risk       │
│  • Seasonal risk    │
│  • Composite score  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  5. AI Reasoning    │
│  ─────────────────  │
│  • Compare routes   │
│  • Analyze trade-offs│
│  • Generate explanation│
│  • Recommend best   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  6. Visualization   │
│  ─────────────────  │
│  • Render map       │
│  • Show routes      │
│  • Display risks    │
│  • Present AI text  │
└──────────┬──────────┘
           │
           ▼
    User sees results
```

## AWS Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS CLOUD                                │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    CloudFront CDN                           │ │
│  │              (Static Assets Distribution)                   │ │
│  └────────────────────────┬───────────────────────────────────┘ │
│                           │                                      │
│  ┌────────────────────────▼───────────────────────────────────┐ │
│  │                    API Gateway                              │ │
│  │              (REST API + WebSocket)                         │ │
│  └────────────────────────┬───────────────────────────────────┘ │
│                           │                                      │
│  ┌────────────────────────▼───────────────────────────────────┐ │
│  │                    AWS Lambda                               │ │
│  │                                                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │ │
│  │  │ Route Gen    │  │ Risk Assess  │  │ Data Process │    │ │
│  │  │ Function     │  │ Function     │  │ Function     │    │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │ │
│  └────────────────────────┬───────────────────────────────────┘ │
│                           │                                      │
│  ┌────────────────────────┼───────────────────────────────────┐ │
│  │                        │                                    │ │
│  │  ┌─────────────────────▼──────┐  ┌────────────────────┐   │ │
│  │  │    Amazon Bedrock          │  │    Amazon S3       │   │ │
│  │  │    (Claude Model)          │  │                    │   │ │
│  │  │                            │  │  • DEM Files       │   │ │
│  │  │  • Route Explanations      │  │  • OSM Data        │   │ │
│  │  │  • Trade-off Analysis      │  │  • Rainfall Data   │   │ │
│  │  │  • Recommendations         │  │  • Flood Atlases   │   │ │
│  │  └────────────────────────────┘  │  • Cache           │   │ │
│  │                                   └────────────────────┘   │ │
│  │                                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Interaction Sequence

```
User → Web UI → API Gateway → Lambda → S3 (Get Data)
                                  ↓
                            DEM Processor
                                  ↓
                            Route Generator
                                  ↓
                            Risk Assessor
                                  ↓
                            Bedrock (AI)
                                  ↓
                            Response ← Lambda ← API Gateway ← Web UI ← User
```

## Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| **Frontend** | React/Vue.js, Leaflet/MapBox, HTML5 |
| **API** | FastAPI, WebSocket, REST |
| **Compute** | AWS Lambda, Python 3.9+ |
| **AI** | Amazon Bedrock (Claude 3) |
| **Storage** | Amazon S3 |
| **Geospatial** | GDAL, Rasterio, OSMnx, NetworkX |
| **Data Processing** | NumPy, Pandas, GeoPandas |
| **Routing** | A* Algorithm, NetworkX |
| **Deployment** | AWS CloudFront, API Gateway |
