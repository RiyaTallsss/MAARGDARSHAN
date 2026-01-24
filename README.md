# AI-Powered Rural Infrastructure Planning System

A geospatial decision support tool for rural road planning in challenging terrain, specifically designed for Uttarakhand's hilly and flood-prone regions. The system leverages AI and open datasets to provide route recommendations, risk assessments, and alternative analysis before expensive physical surveys are conducted.

## Features

- **Multi-Source Data Integration**: Combines API data with local fallbacks for terrain, weather, flood, and infrastructure information
- **AI-Powered Route Generation**: Uses Amazon Bedrock for intelligent route planning and natural language explanations
- **Comprehensive Risk Assessment**: Evaluates terrain, flood, and seasonal risks with mitigation recommendations
- **Interactive Visualization**: Web-based interface with satellite imagery and risk overlays
- **Export Capabilities**: Supports GeoJSON, KML, Shapefile, and PDF report generation
- **Performance Optimized**: Intelligent caching and rate limiting for API cost management

## Quick Start

### Prerequisites

- Python 3.8 or higher
- GDAL library (system dependency)
- Git

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd rural-infrastructure-planning
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install system dependencies** (Ubuntu/Debian):
   ```bash
   sudo apt-get update
   sudo apt-get install gdal-bin libgdal-dev python3-dev
   ```

   **On macOS** (with Homebrew):
   ```bash
   brew install gdal
   ```

   **On Windows**:
   - Download and install GDAL from OSGeo4W or use conda

4. **Install Python dependencies**:
   ```bash
   pip install -e .
   ```

   **For development**:
   ```bash
   pip install -e .[dev]
   ```

5. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and AWS credentials
   ```

6. **Initialize the system**:
   ```bash
   rural-planning init
   ```

### Configuration

#### Required API Keys

1. **AWS Bedrock** (Required for AI features):
   - Set up AWS account and enable Bedrock access
   - Configure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`

2. **OpenWeatherMap** (Recommended):
   - Free tier: 1000 calls/day
   - Get key at: https://openweathermap.org/api

3. **Optional APIs**:
   - Google Places API (for enhanced infrastructure data)
   - Sentinel Hub API (for satellite imagery)
   - Mapbox API (for enhanced terrain data)

#### Data Setup

The system works with both API data and local datasets:

1. **Local Data** (Optional but recommended):
   - Place DEM files in `Uttarkashi_Terrain/`
   - Place OSM data in `Roads/`
   - Place rainfall data in `Rainfall/`
   - Place flood data in `Floods/`

2. **API Fallback**: System automatically uses APIs when local data is unavailable

### Usage

#### Command Line Interface

```bash
# Check system status
rural-planning status

# Generate a route
rural-planning generate-route 30.5 78.1 30.6 78.2 --output route.json

# Check configuration
rural-planning check-config

# Manage cache
rural-planning cache --show-stats
rural-planning cache --clear-all

# Run tests
rural-planning test
```

#### Python API

```python
from rural_infrastructure_planning.main import initialize_system
from rural_infrastructure_planning.routing import RouteGenerator
from rural_infrastructure_planning.data import APIClient

# Initialize system
initialize_system()

# Create API client
api_client = APIClient()

# Generate routes (implementation in progress)
# route_generator = RouteGenerator(api_client)
# routes = route_generator.generate_routes(start_coord, end_coord)
```

## Development

### Project Structure

```
rural_infrastructure_planning/
├── config/          # Configuration management
├── data/           # Data processing components
├── routing/        # Route generation algorithms
├── risk/           # Risk assessment components
├── ai/             # AI integration (Bedrock)
├── api/            # REST API and web interface
└── utils/          # Utilities (caching, rate limiting)

tests/              # Test suite
├── unit/           # Unit tests
├── integration/    # Integration tests
└── property/       # Property-based tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m property      # Property-based tests only

# Run with coverage
pytest --cov=rural_infrastructure_planning --cov-report=html
```

### Code Quality

```bash
# Format code
black rural_infrastructure_planning/ tests/

# Lint code
flake8 rural_infrastructure_planning/ tests/

# Type checking
mypy rural_infrastructure_planning/
```

## System Architecture

### Data Flow

1. **Data Ingestion**: APIs + local fallbacks → unified data structures
2. **Processing**: DEM analysis, OSM parsing, weather/flood data integration
3. **Route Generation**: A* pathfinding with AI-enhanced cost surfaces
4. **Risk Assessment**: Multi-dimensional risk scoring and mitigation suggestions
5. **AI Reasoning**: Amazon Bedrock for explanations and recommendations
6. **Visualization**: Interactive web interface with export capabilities

### Key Components

- **API_Client**: Multi-source data fetching with intelligent fallbacks
- **DEM_Processor**: Terrain analysis and cost surface generation
- **OSM_Parser**: Road network extraction and infrastructure mapping
- **Route_Generator**: AI-assisted pathfinding algorithms
- **Risk_Assessor**: Comprehensive risk evaluation
- **Bedrock_Client**: AI reasoning and natural language explanations

## API Reference

### Rate Limits

The system implements intelligent rate limiting for cost control:

- OpenWeatherMap: 60 requests/minute (free tier: 1000/day)
- Overpass API: 10 requests/minute (conservative)
- NASA APIs: 100 requests/minute (generous for government APIs)
- Google Places: 100 requests/minute (paid tier)

### Caching Strategy

- **API Responses**: 6-hour cache for weather data, 24-hour for terrain data
- **Processed Data**: 1-week cache for DEM analysis results
- **Smart Eviction**: LRU-based with size limits (default: 1GB)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Format code (`black .`)
7. Commit changes (`git commit -m 'Add amazing feature'`)
8. Push to branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write comprehensive tests (unit + property-based)
- Document all public APIs
- Use type hints throughout
- Maintain backwards compatibility

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **AWS AI for Bharat Hackathon** for the project inspiration
- **OpenStreetMap** community for road network data
- **NASA** and **USGS** for elevation data
- **India Meteorological Department** for weather data
- **GDAL/OGR** community for geospatial processing tools

## Support

For questions, issues, or contributions:

1. Check the [Issues](../../issues) page for existing problems
2. Create a new issue with detailed description
3. Join our community discussions
4. Review the documentation in the `docs/` directory

## Roadmap

- [x] Project structure and API integrations
- [ ] Data processing components (Task 2-5)
- [ ] Route generation algorithms (Task 7)
- [ ] Risk assessment system (Task 8)
- [ ] AI integration with Bedrock (Task 9)
- [ ] Web interface and visualization (Task 11-12)
- [ ] Performance optimization (Task 14)
- [ ] Regional specialization for Uttarkashi (Task 15)
- [ ] Comprehensive testing and validation (Task 16)

---

**Note**: This system is designed for early-stage planning support and should be used in conjunction with professional engineering surveys and local expertise for actual infrastructure development.# PRAGATI-AI-
