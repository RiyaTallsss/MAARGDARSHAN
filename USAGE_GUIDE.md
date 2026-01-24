# Rural Infrastructure Planning System - Usage Guide

This guide shows you how to use the AI-powered rural infrastructure planning system we just built.

## 🚀 Quick Start Options

### Option 1: Web API Interface (Recommended)

Start the web server and use the interactive API:

```bash
# Navigate to project directory
cd rural_infrastructure_planning

# Install dependencies (if not already done)
pip install -r requirements.txt

# Start the web server
python -m rural_infrastructure_planning.api.main
```

The server will start at `http://localhost:8000`

**Available endpoints:**
- **Interactive docs**: `http://localhost:8000/docs` (Swagger UI)
- **API docs**: `http://localhost:8000/redoc` (ReDoc)
- **Generate routes**: `POST /api/routes/generate`
- **Route analysis**: `GET /api/routes/{id}/analysis`
- **Compare routes**: `POST /api/routes/compare`
- **System status**: `GET /api/status/data-sources`

### Option 2: Python Script (Programmatic)

Run the example script to see the system in action:

```bash
# Run the route generator example
python examples/route_generator_example.py
```

### Option 3: Interactive Python Session

```python
import asyncio
from rural_infrastructure_planning.routing.route_generator import Route_Generator, RouteConstraints, Coordinate
from rural_infrastructure_planning.data.api_client import API_Client

async def quick_demo():
    # Define coordinates (Uttarkashi region)
    start = Coordinate(30.7268, 78.4354, elevation=1158)  # Uttarkashi town
    end = Coordinate(30.8500, 78.5500, elevation=1800)    # Higher elevation
    
    # Initialize system
    api_client = API_Client(prefer_local_for_testing=True)
    route_generator = Route_Generator(api_client=api_client)
    
    # Set constraints
    constraints = RouteConstraints(
        max_slope_degrees=25.0,
        max_elevation_gain=1500.0,
        priority_factors=["safety", "cost"]
    )
    
    # Generate routes
    routes = await route_generator.generate_routes(start, end, constraints, num_alternatives=3)
    
    # Display results
    for i, route in enumerate(routes, 1):
        print(f"Route {i}: {route.total_distance:.2f}km, ${route.estimated_cost:,.0f}")
    
    return routes

# Run the demo
routes = asyncio.run(quick_demo())
```

## 🎯 Key Features You Can Use

### 1. Route Generation with Regional Analysis
```python
# The system now includes Uttarkashi-specific analysis:
# - Terrain classification for high-altitude conditions
# - Construction difficulty with altitude effects
# - Seasonal analysis with real-time weather
# - Regional cost estimation with local factors
# - Geological hazard assessment (landslides, seismic, GLOF)

routes = await route_generator.generate_routes(start, end, constraints)
```

### 2. Seasonal Construction Analysis
```python
# Analyze optimal construction timing
seasonal_analysis = await route_generator.analyze_seasonal_construction_feasibility(
    route, target_date=datetime(2024, 10, 1)  # October start
)

print(f"Feasibility: {seasonal_analysis['feasibility_category']}")
print(f"Optimal window: {seasonal_analysis['next_optimal_window']}")
```

### 3. Real-Time Risk Assessment
```python
# Get current risk assessment with weather data
risk_assessment = await route_generator.integrate_real_time_risk_assessment(route)

print(f"Overall risk: {risk_assessment['overall_risk_category']}")
print(f"Critical segments: {len(risk_assessment['critical_segments'])}")
```

### 4. Regional Cost Analysis
```python
# Get Uttarkashi-specific cost estimates
from rural_infrastructure_planning.config.regional_config import UttarkashiAnalyzer

analyzer = UttarkashiAnalyzer()
cost_analysis = analyzer.calculate_regional_cost_estimate(
    base_cost=500000, 
    coordinate=start
)

print(f"Total cost: ${cost_analysis['total_cost']:,.0f}")
print(f"Cost factors: {cost_analysis['regional_factors_applied']}")
```

## 🌐 Web API Usage Examples

### Generate Routes via API

```bash
curl -X POST "http://localhost:8000/api/routes/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "start": {
      "latitude": 30.7268,
      "longitude": 78.4354,
      "elevation": 1158
    },
    "end": {
      "latitude": 30.8500,
      "longitude": 78.5500,
      "elevation": 1800
    },
    "constraints": {
      "max_slope_degrees": 25.0,
      "max_elevation_gain": 1500.0,
      "priority_factors": ["safety", "cost"]
    },
    "num_alternatives": 3,
    "include_risk_assessment": true
  }'
```

### Check System Status

```bash
curl "http://localhost:8000/api/status/data-sources"
```

## 📊 Understanding the Output

### Route Information
- **Distance**: Total route length in kilometers
- **Elevation gain/loss**: Vertical changes along the route
- **Construction cost**: Estimated cost in USD with regional factors
- **Construction time**: Estimated duration in days
- **Difficulty score**: 0-100 scale (higher = more difficult)
- **Risk score**: 0-100 scale (higher = more risky)
- **Terrain types**: Breakdown of terrain along route
- **Data sources**: Whether using API or local data

### Regional Analysis Features
- **Seasonal feasibility**: Best construction timing
- **Weather factors**: Real-time conditions affecting construction
- **Geological hazards**: Landslide, seismic, GLOF risks
- **Cost breakdown**: Regional multipliers and factors
- **Mitigation strategies**: Specific recommendations

### Risk Categories
- **Low (0-25)**: Suitable for standard construction
- **Moderate (25-50)**: Requires careful planning
- **High (50-75)**: Needs specialized equipment/techniques
- **Very High (75-100)**: Requires extensive mitigation

## 🛠️ Configuration

### API Keys (Optional)
Create a `.env` file for API access:
```bash
OPENWEATHER_API_KEY=your_key_here
NASA_API_KEY=your_key_here
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_key_here
```

### Local Data
The system works with local data files:
- **DEM data**: `Uttarkashi_Terrain/` folder
- **OSM data**: `Maps/` folder with PBF files
- **Weather data**: `Rainfall/` folder with CSV files
- **Flood data**: `Floods/` folder with PDF atlases

## 🎯 Example Use Cases

### 1. Planning a Village Connection Road
```python
# Connect remote village to main road
village = Coordinate(30.8000, 78.4000, elevation=2000)
main_road = Coordinate(30.7500, 78.4200, elevation=1500)

constraints = RouteConstraints(
    max_slope_degrees=20.0,  # Conservative for village access
    budget_limit=1000000,    # $1M budget
    avoid_flood_zones=True,
    priority_factors=["accessibility", "cost"]
)
```

### 2. Emergency Access Route
```python
# High-priority route with relaxed constraints
emergency_constraints = RouteConstraints(
    max_slope_degrees=35.0,  # Allow steeper grades
    priority_factors=["speed", "accessibility"],
    construction_season="feasible"  # Accept moderate conditions
)
```

### 3. Seasonal Construction Planning
```python
# Plan construction for optimal weather window
seasonal_analysis = await route_generator.analyze_seasonal_construction_feasibility(
    route, target_date=datetime(2024, 10, 1)
)

# Get construction phases
phases = seasonal_analysis['timeline_recommendations']['seasonal_phases']
for phase in phases:
    print(f"Phase {phase['phase_number']}: {phase['description']}")
    print(f"Duration: {phase['estimated_duration_days']} days")
```

## 🚨 Important Notes

1. **Data Sources**: System works offline with local data, APIs enhance accuracy
2. **Regional Focus**: Optimized for Uttarkashi/Uttarakhand conditions
3. **Cost Estimates**: Include regional multipliers for high-altitude construction
4. **Seasonal Planning**: Critical for mountain construction projects
5. **Risk Assessment**: Includes geological hazards specific to the region

## 🆘 Troubleshooting

### Common Issues:
1. **Import errors**: Ensure you're in the project directory
2. **Missing data**: Check that local data files are present
3. **API failures**: System falls back to local data automatically
4. **Memory issues**: Reduce the area size or number of alternatives

### Getting Help:
- Check the logs for detailed error messages
- Use the `/api/status/data-sources` endpoint to check system health
- Run the example scripts to verify installation

## 🎉 Next Steps

1. **Explore the Web UI**: Visit `http://localhost:8000/docs`
2. **Try Different Scenarios**: Modify coordinates and constraints
3. **Analyze Results**: Use the detailed metrics and risk assessments
4. **Export Data**: Use the export functionality for reports
5. **Integrate**: Use the API in your own applications

The system is now ready to help with rural infrastructure planning in Uttarakhand!