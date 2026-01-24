"""
FastAPI REST API for Rural Infrastructure Planning System.

This module provides the main FastAPI application with geospatial endpoints
for route generation, analysis, comparison, and data source status monitoring.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import aiohttp

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from ..data.api_client import API_Client, Coordinate, BoundingBox
from ..data.dem_processor import DEM_Processor
from ..data.osm_parser import OSM_Parser
from ..routing.route_generator import Route_Generator, RouteConstraints, RouteAlignment
from ..risk.risk_assessor import Risk_Assessor, CompositeRisk
from ..ai.bedrock_client import Bedrock_Client, AIExplanation, RouteComparison
from ..config.settings import config

logger = logging.getLogger(__name__)

# FastAPI app initialization
app = FastAPI(
    title="Rural Infrastructure Planning API",
    description="AI-powered geospatial decision support system for rural road planning in Uttarakhand",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instances
api_client = None
route_generator = None
risk_assessor = None
bedrock_client = None

# Pydantic models for API requests/responses
class CoordinateModel(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    elevation: Optional[float] = Field(None, description="Elevation in meters")

class RouteConstraintsModel(BaseModel):
    max_slope_degrees: float = Field(35.0, ge=0, le=90, description="Maximum acceptable slope in degrees")
    max_elevation_gain: float = Field(2000.0, ge=0, description="Maximum elevation gain in meters")
    max_distance_km: float = Field(100.0, ge=0, description="Maximum route distance in kilometers")
    min_road_width: float = Field(3.0, ge=0, description="Minimum road width in meters")
    budget_limit: Optional[float] = Field(None, ge=0, description="Budget limit in USD")
    timeline_limit: Optional[int] = Field(None, ge=0, description="Timeline limit in days")
    avoid_flood_zones: bool = Field(True, description="Avoid high flood risk areas")
    prefer_existing_roads: bool = Field(True, description="Prefer routes near existing infrastructure")
    construction_season: Optional[str] = Field(None, description="Preferred construction season")
    priority_factors: List[str] = Field(["cost", "safety", "speed"], description="Priority factors for optimization")

class RouteGenerationRequest(BaseModel):
    start: CoordinateModel
    end: CoordinateModel
    constraints: Optional[RouteConstraintsModel] = None
    num_alternatives: int = Field(3, ge=1, le=10, description="Number of route alternatives to generate")
    include_ai_explanation: bool = Field(True, description="Include AI-generated explanations")
    include_risk_assessment: bool = Field(True, description="Include comprehensive risk assessment")

class RouteComparisonRequest(BaseModel):
    route_ids: List[str] = Field(..., min_items=2, description="List of route IDs to compare")
    comparison_criteria: List[str] = Field(["cost", "safety", "timeline"], description="Criteria for comparison")
    include_ai_analysis: bool = Field(True, description="Include AI-powered trade-off analysis")

class DataSourceStatus(BaseModel):
    source_name: str
    source_type: str  # api, local, cache
    status: str  # available, unavailable, degraded
    last_updated: Optional[datetime] = None
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    data_freshness_hours: Optional[float] = None

class APIStatusResponse(BaseModel):
    system_status: str  # healthy, degraded, unavailable
    timestamp: datetime
    data_sources: List[DataSourceStatus]
    api_version: str = "1.0.0"
    uptime_seconds: float

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global api_client, route_generator, risk_assessor, bedrock_client
    
    try:
        logger.info("Initializing Rural Infrastructure Planning API services...")
        
        # Initialize core services
        api_client = API_Client()
        route_generator = Route_Generator(api_client)
        risk_assessor = Risk_Assessor(api_client)
        bedrock_client = Bedrock_Client()
        
        # Start background services
        await background_processor.start_processing()
        await smart_cache.start()
        await performance_monitor.start_monitoring()
        
        # Start WebSocket services
        await startup_websocket_services()
        
        logger.info("API services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize API services: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Rural Infrastructure Planning API...")
    
    try:
        # Stop background services
        await background_processor.stop_processing()
        await smart_cache.stop()
        await performance_monitor.stop_monitoring()
        
        # Stop WebSocket services
        await shutdown_websocket_services()
        
        logger.info("API services shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# WebSocket endpoints for real-time updates
@app.websocket("/ws/progress/{task_id}")
async def websocket_progress_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for task progress updates."""
    await handle_progress_websocket(websocket, task_id)

@app.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket):
    """WebSocket endpoint for system status updates."""
    await handle_status_websocket(websocket)

@app.websocket("/ws/performance")
async def websocket_performance_endpoint(websocket: WebSocket):
    """WebSocket endpoint for performance monitoring updates."""
    await handle_performance_websocket(websocket)

@app.websocket("/ws/cache")
async def websocket_cache_endpoint(websocket: WebSocket):
    """WebSocket endpoint for cache status updates."""
    await handle_cache_websocket(websocket)

# Background task endpoints
@app.post("/api/tasks/submit")
async def submit_background_task(
    name: str,
    function_name: str,
    args: List[Any] = [],
    kwargs: Dict[str, Any] = {},
    priority: str = "normal",
    timeout_seconds: Optional[float] = None
):
    """Submit a task for background processing."""
    try:
        # Map priority string to enum
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.CRITICAL
        }
        
        task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
        
        # For security, only allow specific predefined functions
        allowed_functions = {
            "generate_routes_background": _generate_routes_background,
            "calculate_risk_assessment": _calculate_risk_assessment_background,
            "generate_ai_explanation": _generate_ai_explanation_background,
            "export_route_data": _export_route_data_background
        }
        
        if function_name not in allowed_functions:
            raise HTTPException(
                status_code=400,
                detail=f"Function '{function_name}' not allowed for background execution"
            )
        
        function = allowed_functions[function_name]
        
        task_id = background_processor.submit_task(
            name=name,
            function=function,
            args=tuple(args),
            kwargs=kwargs,
            priority=task_priority,
            timeout_seconds=timeout_seconds
        )
        
        return JSONResponse(content={
            "task_id": task_id,
            "status": "submitted",
            "message": f"Task '{name}' submitted for background processing"
        })
        
    except Exception as e:
        logger.error(f"Failed to submit background task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get status of a background task."""
    try:
        task_status = background_processor.get_task_status(task_id)
        
        if task_status is None:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return JSONResponse(content=task_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """Get result of a completed background task."""
    try:
        task_result = background_processor.get_task_result(task_id)
        
        if task_result is None:
            raise HTTPException(status_code=404, detail="Task result not found")
        
        return JSONResponse(content=task_result.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task result: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a background task."""
    try:
        success = background_processor.cancel_task(task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
        
        return JSONResponse(content={
            "task_id": task_id,
            "status": "cancelled",
            "message": "Task cancelled successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/queue/status")
async def get_queue_status():
    """Get current background task queue status."""
    try:
        queue_status = background_processor.get_queue_status()
        return JSONResponse(content=queue_status)
        
    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Smart cache endpoints
@app.get("/api/cache/info")
async def get_cache_info():
    """Get smart cache information and metrics."""
    try:
        cache_info = smart_cache.get_cache_info()
        return JSONResponse(content=cache_info)
        
    except Exception as e:
        logger.error(f"Failed to get cache info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cache/invalidate")
async def invalidate_cache(
    tag: Optional[str] = None,
    dependency: Optional[str] = None,
    key: Optional[str] = None
):
    """Invalidate cache entries by tag, dependency, or specific key."""
    try:
        invalidated_count = 0
        
        if key:
            success = smart_cache.delete(key)
            invalidated_count = 1 if success else 0
        elif tag:
            invalidated_count = smart_cache.invalidate_by_tag(tag)
        elif dependency:
            invalidated_count = smart_cache.invalidate_by_dependency(dependency)
        else:
            raise HTTPException(
                status_code=400,
                detail="Must specify either 'key', 'tag', or 'dependency' parameter"
            )
        
        return JSONResponse(content={
            "invalidated_count": invalidated_count,
            "message": f"Invalidated {invalidated_count} cache entries"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to invalidate cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cache/warm")
async def warm_cache():
    """Warm cache with critical data."""
    try:
        # Define cache warming functions
        warm_functions = [
            lambda: ("elevation_data_uttarkashi", {"region": "uttarkashi", "cached": True}, 3600),
            lambda: ("osm_data_uttarkashi", {"roads": [], "settlements": []}, 1800),
            lambda: ("weather_data_current", {"temperature": 15, "cached": True}, 900)
        ]
        
        smart_cache.warm_cache(warm_functions)
        
        return JSONResponse(content={
            "message": "Cache warming completed",
            "warmed_entries": len(warm_functions)
        })
        
    except Exception as e:
        logger.error(f"Failed to warm cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task functions
async def _generate_routes_background(start_coord: Dict[str, float], 
                                    end_coord: Dict[str, float], 
                                    constraints: Optional[Dict[str, Any]] = None,
                                    num_alternatives: int = 3,
                                    progress_tracker=None):
    """Background task for route generation."""
    try:
        if progress_tracker:
            progress_tracker.update_progress("Initializing route generation")
        
        # Convert coordinates
        start = Coordinate(**start_coord)
        end = Coordinate(**end_coord)
        
        # Convert constraints if provided
        route_constraints = None
        if constraints:
            route_constraints = RouteConstraints(**constraints)
        
        if progress_tracker:
            progress_tracker.update_progress("Generating route alternatives")
        
        # Generate routes
        routes = await route_generator.generate_routes(
            start, end, route_constraints, num_alternatives
        )
        
        if progress_tracker:
            progress_tracker.update_progress("Processing route results")
        
        # Convert routes to dict format
        route_results = [route.to_dict() for route in routes]
        
        if progress_tracker:
            progress_tracker.update_progress("Route generation completed")
        
        return {
            "routes": route_results,
            "total_routes": len(route_results),
            "generation_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Background route generation failed: {e}")
        raise

async def _calculate_risk_assessment_background(coordinate: Dict[str, float], 
                                              progress_tracker=None):
    """Background task for risk assessment calculation."""
    try:
        if progress_tracker:
            progress_tracker.update_progress("Initializing risk assessment")
        
        coord = Coordinate(**coordinate)
        
        if progress_tracker:
            progress_tracker.update_progress("Calculating composite risk")
        
        risk_assessment = await risk_assessor.calculate_composite_risk(coord)
        
        if progress_tracker:
            progress_tracker.update_progress("Risk assessment completed")
        
        return risk_assessment.to_dict()
        
    except Exception as e:
        logger.error(f"Background risk assessment failed: {e}")
        raise

async def _generate_ai_explanation_background(route_data: Dict[str, Any], 
                                           constraints: Optional[Dict[str, Any]] = None,
                                           progress_tracker=None):
    """Background task for AI explanation generation."""
    try:
        if progress_tracker:
            progress_tracker.update_progress("Initializing AI explanation")
        
        # Convert route data back to RouteAlignment object
        # This is a simplified conversion - in practice you'd need proper deserialization
        from ..routing.route_generator import RouteAlignment
        
        route = RouteAlignment(
            id=route_data.get('id', 'unknown'),
            waypoints=[],  # Would need proper conversion
            segments=[],
            total_distance=route_data.get('total_distance', 0),
            elevation_gain=route_data.get('elevation_gain', 0),
            elevation_loss=route_data.get('elevation_loss', 0),
            construction_difficulty=route_data.get('construction_difficulty', 0),
            estimated_cost=route_data.get('estimated_cost', 0),
            estimated_duration=route_data.get('estimated_duration', 0),
            risk_score=route_data.get('risk_score', 0),
            algorithm_used=route_data.get('algorithm_used', 'unknown'),
            data_sources=route_data.get('data_sources', [])
        )
        
        # Convert constraints if provided
        route_constraints = None
        if constraints:
            route_constraints = RouteConstraints(**constraints)
        
        if progress_tracker:
            progress_tracker.update_progress("Generating AI explanation")
        
        explanation = await bedrock_client.generate_route_explanation(route, route_constraints)
        
        if progress_tracker:
            progress_tracker.update_progress("AI explanation completed")
        
        return explanation.to_dict()
        
    except Exception as e:
        logger.error(f"Background AI explanation failed: {e}")
        raise

async def _export_route_data_background(route_data: Dict[str, Any], 
                                      export_format: str = "geojson",
                                      progress_tracker=None):
    """Background task for route data export."""
    try:
        if progress_tracker:
            progress_tracker.update_progress("Initializing data export")
        
        # Convert route data back to RouteAlignment object (simplified)
        from ..routing.route_generator import RouteAlignment
        
        route = RouteAlignment(
            id=route_data.get('id', 'unknown'),
            waypoints=[],  # Would need proper conversion
            segments=[],
            total_distance=route_data.get('total_distance', 0),
            elevation_gain=route_data.get('elevation_gain', 0),
            elevation_loss=route_data.get('elevation_loss', 0),
            construction_difficulty=route_data.get('construction_difficulty', 0),
            estimated_cost=route_data.get('estimated_cost', 0),
            estimated_duration=route_data.get('estimated_duration', 0),
            risk_score=route_data.get('risk_score', 0),
            algorithm_used=route_data.get('algorithm_used', 'unknown'),
            data_sources=route_data.get('data_sources', [])
        )
        
        if progress_tracker:
            progress_tracker.update_progress(f"Exporting to {export_format} format")
        
        if export_format.lower() == "geojson":
            result = await data_exporter.export_route_geojson(route)
        elif export_format.lower() == "kml":
            result = await data_exporter.export_route_kml(route)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
        
        if progress_tracker:
            progress_tracker.update_progress("Export completed")
        
        return {
            "format": export_format,
            "data": result,
            "export_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Background export failed: {e}")
        raise

# Health check endpoint
@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Rural Infrastructure Planning API"
    }

# Data source status endpoint
@app.get("/api/status/data-sources", response_model=APIStatusResponse)
async def get_data_source_status():
    """
    Get comprehensive status of all data sources including API availability and freshness.
    """
    try:
        logger.info("Checking data source status...")
        
        data_sources = []
        system_healthy = True
        
        # Check API client status
        if api_client:
            api_status = await _check_api_client_status()
            data_sources.extend(api_status)
            
            # System is degraded if any critical APIs are down
            critical_apis_down = any(
                source.status == "unavailable" and "nasa" in source.source_name.lower() 
                for source in api_status
            )
            if critical_apis_down:
                system_healthy = False
        
        # Check local data availability
        local_status = _check_local_data_status()
        data_sources.extend(local_status)
        
        # Determine overall system status
        if system_healthy and all(source.status != "unavailable" for source in data_sources):
            system_status = "healthy"
        elif any(source.status == "available" for source in data_sources):
            system_status = "degraded"
        else:
            system_status = "unavailable"
        
        return APIStatusResponse(
            system_status=system_status,
            timestamp=datetime.now(),
            data_sources=data_sources,
            uptime_seconds=0.0  # Would track actual uptime in production
        )
        
    except Exception as e:
        logger.error(f"Data source status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

# Import validation and error handling
from ..utils.validation import InputValidator, APIResponseValidator, NetworkValidator
from ..utils.error_handling import ErrorHandler, ErrorContext, ErrorCategory

# Initialize validation and error handling
input_validator = InputValidator()
api_response_validator = APIResponseValidator()
network_validator = NetworkValidator()
error_handler = ErrorHandler()

# Import offline capabilities
from ..utils.offline_mode import offline_manager, OfflineManager

# Enhanced error handling middleware
@app.middleware("http")
async def error_handling_middleware(request, call_next):
    """Middleware for comprehensive error handling and user feedback."""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Unhandled error in request {request.url}: {e}")
        
        # Create user-friendly error response
        error_response = {
            "error": "An unexpected error occurred. Please try again or contact support.",
            "error_id": f"SYS_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "suggestions": [
                "Check your internet connection",
                "Try again in a few moments", 
                "Contact support if the problem persists"
            ]
        }
        
        return JSONResponse(
            status_code=500,
            content=error_response
        )

# Enhanced system status endpoint
@app.get("/api/status/system")
async def get_system_status():
    """
    Get comprehensive system status including offline capabilities and user notifications.
    """
    try:
        logger.info("Checking comprehensive system status...")
        
        # Check offline capability
        requested_features = [
            'route_generation', 'risk_assessment', 'ai_explanations', 
            'export_functionality', 'real_time_weather'
        ]
        
        offline_capability = await offline_manager.assess_offline_capability(requested_features)
        
        # Get data source status
        data_source_response = await get_data_source_status()
        
        # Update offline manager with API status
        api_status = {}
        for source in data_source_response.data_sources:
            if source.source_type == "api":
                api_status[source.source_name] = {
                    'status': source.status,
                    'response_time_ms': source.response_time_ms,
                    'error': source.error_message
                }
        
        offline_manager.update_api_status(api_status)
        
        # Generate user notifications
        notifications = []
        
        if offline_manager.offline_mode:
            notification = offline_manager.generate_user_notification('offline_mode', {
                'available_features': offline_capability.available_features,
                'limited_features': offline_capability.limited_features
            })
            notifications.append(notification)
        
        if offline_capability.user_impact in ['significant', 'critical']:
            notification = offline_manager.generate_user_notification('limited_data', {
                'impact_level': offline_capability.user_impact,
                'data_limitations': offline_capability.data_limitations
            })
            notifications.append(notification)
        
        # Check AI service availability
        ai_available = any(source.source_name == "AWS Bedrock" and source.status == "available" 
                          for source in data_source_response.data_sources)
        
        if not ai_available:
            notification = offline_manager.generate_user_notification('ai_unavailable', {
                'fallback_available': True,
                'impact': 'AI explanations will use rule-based analysis'
            })
            notifications.append(notification)
        
        system_status = {
            "system_health": data_source_response.system_status,
            "timestamp": datetime.now().isoformat(),
            "offline_capability": offline_capability.to_dict(),
            "data_sources": [source.dict() for source in data_source_response.data_sources],
            "notifications": notifications,
            "user_guidance": {
                "can_operate_offline": offline_capability.can_operate_offline,
                "recommended_actions": _get_recommended_actions(offline_capability, data_source_response.system_status),
                "feature_availability": {
                    "available": offline_capability.available_features,
                    "limited": offline_capability.limited_features,
                    "unavailable": offline_capability.unavailable_features
                }
            }
        }
        
        return JSONResponse(content=system_status)
        
    except Exception as e:
        logger.error(f"System status check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Unable to check system status",
                "timestamp": datetime.now().isoformat(),
                "fallback_status": "unknown"
            }
        )

def _get_recommended_actions(offline_capability: OfflineCapability, system_status: str) -> List[str]:
    """Get recommended actions based on system status."""
    actions = []
    
    if system_status == "unavailable":
        actions.extend([
            "Check internet connectivity",
            "Verify external service availability",
            "Use offline features if available"
        ])
    elif system_status == "degraded":
        actions.extend([
            "Some features may be slower than usual",
            "Consider using cached data",
            "Monitor system status for improvements"
        ])
    
    if offline_capability.user_impact == "significant":
        actions.extend([
            "Review available features before proceeding",
            "Consider waiting for full service restoration",
            "Use alternative data sources if available"
        ])
    elif offline_capability.user_impact == "critical":
        actions.extend([
            "Limited functionality available",
            "Contact system administrator",
            "Wait for service restoration"
        ])
    
    if not actions:
        actions.append("All systems operating normally")
    
    return actions

# Enhanced route generation with offline support
@app.post("/api/routes/generate/offline")
async def generate_routes_offline(request: RouteGenerationRequest):
    """
    Generate routes with offline capability and graceful degradation.
    """
    request_id = str(uuid.uuid4())
    context = ErrorContext(
        operation="offline_route_generation",
        component="api_endpoint",
        request_id=request_id
    )
    
    try:
        logger.info(f"[{request_id}] Generating routes in offline-capable mode")
        
        # Assess offline capability for route generation
        offline_capability = await offline_manager.assess_offline_capability(['route_generation'])
        
        if not offline_capability.can_operate_offline:
            # Detect missing data impact
            data_availability = await offline_manager._assess_data_availability()
            impact_analysis = offline_manager.detect_missing_data_impact('route_generation', data_availability)
            
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Route generation unavailable in current conditions",
                    "impact_analysis": impact_analysis,
                    "offline_capability": offline_capability.to_dict(),
                    "request_id": request_id
                }
            )
        
        # Validate input with enhanced feedback
        route_params = {
            'start': request.start.dict(),
            'end': request.end.dict(),
            'constraints': request.constraints.dict() if request.constraints else None,
            'num_alternatives': request.num_alternatives
        }
        
        validation_result = input_validator.validate_route_parameters(route_params)
        
        if not validation_result.is_valid:
            error_details = error_handler.handle_validation_error(validation_result, context)
            
            # Enhanced validation error response
            raise HTTPException(
                status_code=400,
                detail={
                    "error": error_details.user_message,
                    "error_id": error_details.error_id,
                    "validation_details": validation_result.to_dict(),
                    "suggestions": error_details.suggested_actions,
                    "user_guidance": "Please correct the input errors and try again"
                }
            )
        
        # Generate routes with fallback handling
        try:
            # Convert to internal types
            start_coord = Coordinate(
                latitude=request.start.latitude,
                longitude=request.start.longitude,
                elevation=request.start.elevation
            )
            
            end_coord = Coordinate(
                latitude=request.end.latitude,
                longitude=request.end.longitude,
                elevation=request.end.elevation
            )
            
            constraints = None
            if request.constraints:
                constraints = RouteConstraints(
                    max_slope_degrees=request.constraints.max_slope_degrees,
                    max_elevation_gain=request.constraints.max_elevation_gain,
                    max_distance_km=request.constraints.max_distance_km,
                    min_road_width=request.constraints.min_road_width,
                    budget_limit=request.constraints.budget_limit,
                    timeline_limit=request.constraints.timeline_limit,
                    avoid_flood_zones=request.constraints.avoid_flood_zones,
                    prefer_existing_roads=request.constraints.prefer_existing_roads,
                    construction_season=request.constraints.construction_season,
                    priority_factors=request.constraints.priority_factors
                )
            
            # Generate routes
            routes = await route_generator.generate_routes(
                start_coord, end_coord, constraints, request.num_alternatives
            )
            
        except Exception as e:
            error_details = error_handler.handle_api_error("route_generator", e, context, fallback_available=True)
            
            # Try simplified route generation as fallback
            try:
                logger.info(f"[{request_id}] Attempting simplified route generation")
                simplified_constraints = RouteConstraints()
                routes = await route_generator.generate_routes(
                    start_coord, end_coord, simplified_constraints, 1
                )
                
                # Add fallback notification
                fallback_notification = offline_manager.generate_user_notification('api_degraded', {
                    'fallback_used': 'simplified_routing',
                    'original_error': str(e)
                })
                
            except Exception as fallback_error:
                error_details = error_handler.handle_api_error("route_generator_fallback", fallback_error, context)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": error_details.user_message,
                        "error_id": error_details.error_id,
                        "fallback_attempted": True,
                        "user_guidance": "Route generation failed with both primary and fallback methods. Please try with different parameters or contact support."
                    }
                )
        
        if not routes:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "No feasible routes found",
                    "user_guidance": "Try adjusting your route parameters or constraints",
                    "suggestions": [
                        "Increase maximum slope tolerance",
                        "Expand budget or timeline constraints", 
                        "Try alternative start or end points",
                        "Reduce number of route alternatives requested"
                    ]
                }
            )
        
        # Prepare enhanced response
        response_data = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "routes": [],
            "system_status": {
                "offline_mode": offline_manager.offline_mode,
                "data_limitations": offline_capability.data_limitations,
                "feature_availability": {
                    "route_generation": "available",
                    "risk_assessment": "available" if "risk_assessment" in offline_capability.available_features else "limited",
                    "ai_explanations": "available" if "ai_explanations" in offline_capability.available_features else "fallback"
                }
            },
            "user_notifications": []
        }
        
        # Process routes with enhanced error handling
        for route in routes:
            route_data = route.to_dict()
            
            # Add risk assessment with fallback
            if request.include_risk_assessment:
                try:
                    if risk_assessor:
                        risk_assessment = await risk_assessor.calculate_composite_risk(start_coord)
                        route_data["risk_assessment"] = risk_assessment.to_dict()
                except Exception as e:
                    logger.warning(f"Risk assessment failed, using basic assessment: {e}")
                    route_data["risk_assessment"] = {
                        "overall_score": 50.0,
                        "risk_category": "moderate",
                        "note": "Basic risk assessment used due to data limitations"
                    }
            
            # Add AI explanation with fallback
            if request.include_ai_explanation:
                try:
                    if bedrock_client and not offline_manager.offline_mode:
                        explanation = await bedrock_client.generate_route_explanation(route, constraints)
                        route_data["ai_explanation"] = explanation.to_dict()
                    else:
                        # Use fallback explanation
                        fallback_explanation = await offline_manager.create_fallback_ai_explanation(route, constraints)
                        route_data["ai_explanation"] = fallback_explanation.to_dict()
                        route_data["ai_explanation"]["note"] = "Rule-based analysis used (AI service unavailable)"
                except Exception as e:
                    logger.warning(f"AI explanation failed, using minimal explanation: {e}")
                    route_data["ai_explanation"] = {
                        "explanation_text": "Route analysis completed using available data",
                        "confidence_score": 0.5,
                        "note": "Minimal explanation due to service limitations"
                    }
            
            response_data["routes"].append(route_data)
        
        # Add user notifications about system status
        if offline_manager.offline_mode:
            notification = offline_manager.generate_user_notification('offline_mode', {
                'routes_generated': len(routes),
                'data_sources': 'local_only'
            })
            response_data["user_notifications"].append(notification)
        
        if offline_capability.data_limitations:
            notification = offline_manager.generate_user_notification('limited_data', {
                'limitations': offline_capability.data_limitations[:3],  # Show first 3
                'impact': offline_capability.user_impact
            })
            response_data["user_notifications"].append(notification)
        
        logger.info(f"[{request_id}] Generated {len(routes)} routes with offline capability")
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        error_details = error_handler.handle_api_error("offline_route_generation", e, context)
        logger.error(f"[{request_id}] Offline route generation failed: {error_details.message}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": error_details.user_message,
                "error_id": error_details.error_id,
                "request_id": request_id,
                "user_guidance": "The system encountered an unexpected error. Please try again or contact support.",
                "fallback_options": [
                    "Try with simplified parameters",
                    "Use basic route generation",
                    "Contact support for assistance"
                ]
            }
        )
@app.post("/api/routes/generate")
async def generate_routes(request: RouteGenerationRequest, background_tasks: BackgroundTasks):
    """
    Generate multiple route alternatives with comprehensive analysis and validation.
    Uses background processing for improved UI responsiveness.
    """
    request_id = str(uuid.uuid4())
    context = ErrorContext(
        operation="route_generation",
        component="api_endpoint",
        request_id=request_id
    )
    
    try:
        logger.info(f"[{request_id}] Generating routes from {request.start.latitude:.4f},{request.start.longitude:.4f} "
                   f"to {request.end.latitude:.4f},{request.end.longitude:.4f}")
        
        # Validate input parameters
        route_params = {
            'start': request.start.dict(),
            'end': request.end.dict(),
            'constraints': request.constraints.dict() if request.constraints else None,
            'num_alternatives': request.num_alternatives
        }
        
        validation_result = input_validator.validate_route_parameters(route_params)
        
        if not validation_result.is_valid:
            error_details = error_handler.handle_validation_error(validation_result, context)
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": error_details.user_message,
                    "error_id": error_details.error_id,
                    "validation_details": validation_result.to_dict()
                }
            )
        
        # Log validation warnings if any
        if validation_result.warnings:
            logger.warning(f"[{request_id}] Route generation proceeding with {len(validation_result.warnings)} warnings")
        
        # Submit background task for route generation
        task_id = background_processor.submit_task(
            name=f"Route Generation {request_id}",
            function=_generate_routes_background,
            args=(
                request.start.dict(),
                request.end.dict(),
                request.constraints.dict() if request.constraints else None,
                request.num_alternatives
            ),
            priority=TaskPriority.HIGH,
            timeout_seconds=300.0  # 5 minutes timeout
        )
        
        # Return immediate response with task ID for tracking
        response_data = {
            "request_id": request_id,
            "task_id": task_id,
            "status": "processing",
            "message": "Route generation started in background",
            "timestamp": datetime.now().isoformat(),
            "websocket_url": f"/ws/progress/{task_id}",
            "status_check_url": f"/api/tasks/{task_id}/status",
            "result_url": f"/api/tasks/{task_id}/result"
        }
        
        # If risk assessment or AI explanation requested, queue additional tasks
        if request.include_risk_assessment:
            risk_task_id = background_processor.submit_task(
                name=f"Risk Assessment {request_id}",
                function=_calculate_risk_assessment_background,
                args=(request.start.dict(),),
                dependencies=[task_id],  # Wait for route generation
                priority=TaskPriority.NORMAL
            )
            response_data["risk_assessment_task_id"] = risk_task_id
        
        logger.info(f"[{request_id}] Route generation task submitted: {task_id}")
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        error_details = error_handler.handle_api_error("route_generation_system", e, context)
        logger.error(f"[{request_id}] Unexpected error in route generation: {error_details.message}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": error_details.user_message,
                "error_id": error_details.error_id,
                "request_id": request_id
            }
        )

# Synchronous route generation endpoint for immediate results
@app.post("/api/routes/generate/sync")
async def generate_routes_sync(request: RouteGenerationRequest, background_tasks: BackgroundTasks):
    """
    Generate routes synchronously for immediate results (legacy endpoint).
    Use /api/routes/generate for better UI responsiveness with background processing.
    """
    request_id = str(uuid.uuid4())
    context = ErrorContext(
        operation="route_generation_sync",
        component="api_endpoint",
        request_id=request_id
    )
    
    try:
        logger.info(f"[{request_id}] Synchronous route generation requested")
        
        # Validate input parameters
        route_params = {
            'start': request.start.dict(),
            'end': request.end.dict(),
            'constraints': request.constraints.dict() if request.constraints else None,
            'num_alternatives': request.num_alternatives
        }
        
        validation_result = input_validator.validate_route_parameters(route_params)
        
        if not validation_result.is_valid:
            error_details = error_handler.handle_validation_error(validation_result, context)
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": error_details.user_message,
                    "error_id": error_details.error_id,
                    "validation_details": validation_result.to_dict()
                }
            )
        
        # Convert request models to internal types
        start_coord = Coordinate(
            latitude=request.start.latitude,
            longitude=request.start.longitude,
            elevation=request.start.elevation
        )
        
        end_coord = Coordinate(
            latitude=request.end.latitude,
            longitude=request.end.longitude,
            elevation=request.end.elevation
        )
        
        constraints = None
        if request.constraints:
            constraints = RouteConstraints(
                max_slope_degrees=request.constraints.max_slope_degrees,
                max_elevation_gain=request.constraints.max_elevation_gain,
                max_distance_km=request.constraints.max_distance_km,
                min_road_width=request.constraints.min_road_width,
                budget_limit=request.constraints.budget_limit,
                timeline_limit=request.constraints.timeline_limit,
                avoid_flood_zones=request.constraints.avoid_flood_zones,
                prefer_existing_roads=request.constraints.prefer_existing_roads,
                construction_season=request.constraints.construction_season,
                priority_factors=request.constraints.priority_factors
            )
        
        # Generate routes synchronously
        routes = await route_generator.generate_routes(
            start_coord, end_coord, constraints, request.num_alternatives
        )
        
        if not routes:
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": "No feasible routes found for the given parameters",
                    "suggestions": [
                        "Try relaxing the constraints",
                        "Check start and end point accessibility",
                        "Consider alternative locations"
                    ]
                }
            )
        
        # Prepare response data
        response_data = {
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "routes": [],
            "summary": {
                "total_routes": len(routes),
                "generation_algorithm": "astar_multi_strategy",
                "constraints_applied": constraints.to_dict() if constraints else None,
                "processing_mode": "synchronous"
            }
        }
        
        # Process each route
        for route in routes:
            route_data = route.to_dict()
            
            # Add risk assessment if requested (background task)
            if request.include_risk_assessment:
                background_tasks.add_task(_add_risk_assessment_with_validation, route_data, route, start_coord, context)
            
            # Add AI explanation if requested (background task)
            if request.include_ai_explanation:
                background_tasks.add_task(_add_ai_explanation_with_validation, route_data, route, constraints, context)
            
            response_data["routes"].append(route_data)
        
        logger.info(f"[{request_id}] Generated {len(routes)} routes synchronously")
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        error_details = error_handler.handle_api_error("route_generation_sync", e, context)
        logger.error(f"[{request_id}] Synchronous route generation failed: {error_details.message}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": error_details.user_message,
                "error_id": error_details.error_id,
                "request_id": request_id
            }
        )

# Route analysis endpoint
@app.get("/api/routes/{route_id}/analysis")
async def get_route_analysis(route_id: str, include_ai_explanation: bool = True):
    """
    Get detailed analysis for a specific route.
    """
    try:
        logger.info(f"Getting analysis for route {route_id}")
        
        # In a real implementation, you would retrieve the route from storage
        # For now, return a mock response structure
        
        analysis_data = {
            "route_id": route_id,
            "timestamp": datetime.now().isoformat(),
            "analysis": {
                "feasibility_score": 85.0,
                "construction_complexity": "moderate",
                "environmental_impact": "low",
                "community_benefit": "high"
            },
            "recommendations": [
                "Implement slope stabilization at km 5.2-5.8",
                "Install drainage culverts at three identified locations",
                "Plan construction during October-March optimal window"
            ]
        }
        
        if include_ai_explanation:
            analysis_data["ai_explanation"] = {
                "explanation_id": f"exp_{uuid.uuid4().hex[:8]}",
                "explanation_text": "This route provides optimal balance of construction feasibility and cost-effectiveness...",
                "confidence_score": 0.87
            }
        
        return JSONResponse(content=analysis_data)
        
    except Exception as e:
        logger.error(f"Route analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Route analysis failed: {str(e)}")

# Route comparison endpoint
@app.post("/api/routes/compare")
async def compare_routes(request: RouteComparisonRequest):
    """
    Compare multiple route alternatives with AI-powered analysis.
    """
    try:
        logger.info(f"Comparing {len(request.route_ids)} routes")
        
        # In a real implementation, you would retrieve routes from storage
        # For now, generate a mock comparison response
        
        comparison_data = {
            "comparison_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "route_ids": request.route_ids,
            "comparison_criteria": request.comparison_criteria,
            "summary": {
                "recommended_route": request.route_ids[0],
                "key_differentiators": ["cost", "construction_timeline", "risk_level"]
            },
            "detailed_comparison": {
                "cost_analysis": {
                    "lowest_cost": request.route_ids[1],
                    "cost_range": "$750,000 - $1,200,000",
                    "cost_drivers": ["terrain_difficulty", "material_transport"]
                },
                "safety_analysis": {
                    "safest_route": request.route_ids[0],
                    "risk_factors": ["slope_stability", "flood_zones", "seismic_activity"]
                },
                "timeline_analysis": {
                    "fastest_construction": request.route_ids[2],
                    "timeline_range": "180 - 320 days",
                    "timeline_factors": ["weather_windows", "equipment_access"]
                }
            }
        }
        
        if request.include_ai_analysis:
            comparison_data["ai_analysis"] = {
                "comparison_id": f"comp_{uuid.uuid4().hex[:8]}",
                "analysis_text": "Comprehensive trade-off analysis reveals Route A provides optimal balance...",
                "recommendation": f"Route {request.route_ids[0]} is recommended based on overall risk-adjusted value",
                "confidence_score": 0.82
            }
        
        return JSONResponse(content=comparison_data)
        
    except Exception as e:
        logger.error(f"Route comparison failed: {e}")
        raise HTTPException(status_code=500, detail=f"Route comparison failed: {str(e)}")

# Enhanced helper functions with validation
async def _add_risk_assessment_with_validation(route_data: Dict[str, Any], 
                                             route: RouteAlignment, 
                                             coordinate: Coordinate,
                                             context: ErrorContext):
    """Background task to add risk assessment with validation."""
    try:
        if risk_assessor:
            risk_assessment = await risk_assessor.calculate_composite_risk(coordinate)
            
            # Validate risk assessment data
            if risk_assessment.overall_score < 0 or risk_assessment.overall_score > 100:
                logger.warning(f"Invalid risk score: {risk_assessment.overall_score}")
                return
            
            route_data["risk_assessment"] = risk_assessment.to_dict()
            logger.debug(f"Added risk assessment for route {route.id}")
    except Exception as e:
        error_details = error_handler.handle_api_error("risk_assessment", e, context)
        logger.warning(f"Failed to add risk assessment: {error_details.message}")

async def _add_ai_explanation_with_validation(route_data: Dict[str, Any], 
                                            route: RouteAlignment, 
                                            constraints: Optional[RouteConstraints],
                                            context: ErrorContext):
    """Background task to add AI explanation with validation."""
    try:
        if bedrock_client:
            explanation = await bedrock_client.generate_route_explanation(route, constraints)
            
            # Validate explanation data
            if not explanation.explanation_text or len(explanation.explanation_text.strip()) == 0:
                logger.warning(f"Empty AI explanation for route {route.id}")
                return
            
            route_data["ai_explanation"] = explanation.to_dict()
            logger.debug(f"Added AI explanation for route {route.id}")
    except Exception as e:
        error_details = error_handler.handle_api_error("ai_explanation", e, context)
        logger.warning(f"Failed to add AI explanation: {error_details.message}")

# Enhanced data source status endpoint with validation
@app.get("/api/status/data-sources", response_model=APIStatusResponse)
async def get_data_source_status():
    """
    Get comprehensive status of all data sources with enhanced validation and error handling.
    """
    context = ErrorContext(
        operation="data_source_status",
        component="api_endpoint"
    )
    
    try:
        logger.info("Checking data source status with comprehensive validation...")
        
        data_sources = []
        system_healthy = True
        
        # Check API client status with validation
        if api_client:
            try:
                api_status = await _check_api_client_status_with_validation()
                data_sources.extend(api_status)
                
                # System is degraded if any critical APIs are down
                critical_apis_down = any(
                    source.status == "unavailable" and any(keyword in source.source_name.lower() 
                    for keyword in ["nasa", "elevation", "weather"]) 
                    for source in api_status
                )
                if critical_apis_down:
                    system_healthy = False
                    
            except Exception as e:
                error_details = error_handler.handle_api_error("api_status_check", e, context)
                logger.error(f"API status check failed: {error_details.message}")
                system_healthy = False
        
        # Check local data availability with validation
        try:
            local_status = _check_local_data_status_with_validation()
            data_sources.extend(local_status)
        except Exception as e:
            error_details = error_handler.handle_data_error("local_data_check", e, context)
            logger.error(f"Local data status check failed: {error_details.message}")
        
        # Validate mixed data scenarios
        api_sources = [s for s in data_sources if s.source_type == "api"]
        local_sources = [s for s in data_sources if s.source_type == "local"]
        
        if api_sources and local_sources:
            # Mixed data scenario validation
            mixed_validation = network_validator.validate_mixed_data_scenario(
                {"api_sources": len(api_sources)}, 
                {"local_sources": len(local_sources)}, 
                "infrastructure_data"
            )
            
            if mixed_validation.warnings:
                logger.info("Mixed data scenario detected - API and local sources available")
        
        # Determine overall system status with validation
        available_sources = [s for s in data_sources if s.status == "available"]
        unavailable_sources = [s for s in data_sources if s.status == "unavailable"]
        
        if system_healthy and len(unavailable_sources) == 0:
            system_status = "healthy"
        elif len(available_sources) > len(unavailable_sources):
            system_status = "degraded"
        else:
            system_status = "unavailable"
        
        # Validate response data
        if len(data_sources) == 0:
            logger.warning("No data sources found in status check")
            system_status = "unavailable"
        
        response = APIStatusResponse(
            system_status=system_status,
            timestamp=datetime.now(),
            data_sources=data_sources,
            uptime_seconds=0.0  # Would track actual uptime in production
        )
        
        logger.info(f"Data source status check completed: {system_status} with {len(data_sources)} sources")
        
        return response
        
    except Exception as e:
        error_details = error_handler.handle_api_error("data_source_status_system", e, context)
        logger.error(f"Data source status check failed: {error_details.message}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error": error_details.user_message,
                "error_id": error_details.error_id
            }
        )

async def _check_api_client_status_with_validation() -> List[DataSourceStatus]:
    """Check status of API client data sources with enhanced validation."""
    sources = []
    
    # Define API endpoints for testing
    api_tests = [
        {
            "name": "NASA SRTM Elevation API",
            "test_url": "https://cloud.sdsc.edu/v1/srtm90",
            "timeout": 5
        },
        {
            "name": "OpenWeatherMap API", 
            "test_url": "https://api.openweathermap.org/data/2.5/weather",
            "timeout": 3
        },
        {
            "name": "Overpass API (OpenStreetMap)",
            "test_url": "https://overpass-api.de/api/status",
            "timeout": 5
        }
    ]
    
    for api_test in api_tests:
        try:
            # Test API connectivity with validation
            start_time = datetime.now()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=api_test["timeout"])) as session:
                async with session.get(api_test["test_url"]) as response:
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds() * 1000
                    
                    # Validate response
                    status = "available"
                    error_message = None
                    
                    if response.status == 429:
                        status = "degraded"
                        error_message = "Rate limited"
                    elif response.status >= 500:
                        status = "degraded" 
                        error_message = f"Server error: {response.status}"
                    elif response.status >= 400:
                        status = "unavailable"
                        error_message = f"Client error: {response.status}"
                    
                    # Validate response time
                    if response_time > 10000:  # 10 seconds
                        status = "degraded" if status == "available" else status
                        error_message = f"Slow response: {response_time:.0f}ms"
                    
                    sources.append(DataSourceStatus(
                        source_name=api_test["name"],
                        source_type="api",
                        status=status,
                        last_updated=datetime.now(),
                        response_time_ms=response_time,
                        error_message=error_message,
                        data_freshness_hours=1.0 if status == "available" else None
                    ))
                    
        except asyncio.TimeoutError:
            sources.append(DataSourceStatus(
                source_name=api_test["name"],
                source_type="api",
                status="timeout",
                error_message=f"Request timeout after {api_test['timeout']}s"
            ))
            
        except Exception as e:
            sources.append(DataSourceStatus(
                source_name=api_test["name"],
                source_type="api", 
                status="unavailable",
                error_message=str(e)
            ))
    
    return sources

def _check_local_data_status_with_validation() -> List[DataSourceStatus]:
    """Check status of local data sources with validation."""
    sources = []
    
    # Check local data files with validation
    local_data_checks = [
        {
            "name": "Uttarkashi DEM (Local)",
            "path": "Uttarkashi_Terrain/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif",
            "expected_size_mb": 50
        },
        {
            "name": "India OSM PBF Files (Local)", 
            "path": "Maps/",
            "expected_files": 6
        },
        {
            "name": "Flood Hazard Atlas (Local)",
            "path": "Floods/",
            "expected_files": 5
        }
    ]
    
    for data_check in local_data_checks:
        try:
            from pathlib import Path
            
            data_path = Path(data_check["path"])
            status = "available"
            error_message = None
            last_updated = None
            
            if data_path.exists():
                if data_path.is_file():
                    # Check file size if specified
                    if "expected_size_mb" in data_check:
                        file_size_mb = data_path.stat().st_size / (1024 * 1024)
                        if file_size_mb < data_check["expected_size_mb"] * 0.5:  # Less than 50% expected size
                            status = "degraded"
                            error_message = f"File size {file_size_mb:.1f}MB is smaller than expected"
                    
                    last_updated = datetime.fromtimestamp(data_path.stat().st_mtime)
                    
                elif data_path.is_dir():
                    # Check number of files if specified
                    if "expected_files" in data_check:
                        file_count = len(list(data_path.glob("*")))
                        if file_count < data_check["expected_files"]:
                            status = "degraded"
                            error_message = f"Found {file_count} files, expected {data_check['expected_files']}"
                    
                    # Get most recent file modification time
                    files = list(data_path.glob("*"))
                    if files:
                        last_updated = max(datetime.fromtimestamp(f.stat().st_mtime) for f in files)
                
                # Calculate data age
                data_freshness_hours = None
                if last_updated:
                    data_freshness_hours = (datetime.now() - last_updated).total_seconds() / 3600
                    
                    # Warn if data is very old
                    if data_freshness_hours > 8760:  # More than a year
                        if status == "available":
                            status = "degraded"
                        error_message = f"Data is {data_freshness_hours/24:.0f} days old"
                
            else:
                status = "unavailable"
                error_message = "Data file/directory not found"
            
            sources.append(DataSourceStatus(
                source_name=data_check["name"],
                source_type="local",
                status=status,
                last_updated=last_updated,
                error_message=error_message,
                data_freshness_hours=data_freshness_hours
            ))
            
        except Exception as e:
            sources.append(DataSourceStatus(
                source_name=data_check["name"],
                source_type="local",
                status="unavailable", 
                error_message=f"Validation error: {str(e)}"
            ))
    
    return sources

# Run the application
if __name__ == "__main__":
    uvicorn.run(
        "rural_infrastructure_planning.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
# Import export functionality
from .export import DataExporter

# Import WebSocket handlers and background processing
from .websocket_handlers import (
    connection_manager, 
    handle_progress_websocket,
    handle_status_websocket, 
    handle_performance_websocket,
    handle_cache_websocket,
    startup_websocket_services,
    shutdown_websocket_services
)
from ..utils.background_processor import get_background_processor, TaskPriority, background_task
from ..utils.smart_cache import get_smart_cache
from ..utils.performance_monitor import get_performance_monitor
from ..utils.api_optimizer import get_api_optimizer

# Initialize services
data_exporter = DataExporter()
background_processor = get_background_processor()
smart_cache = get_smart_cache()
performance_monitor = get_performance_monitor()
api_optimizer = get_api_optimizer()

# Export endpoints
@app.get("/api/routes/{route_id}/export/{format_type}")
async def export_route(route_id: str, format_type: str):
    """
    Export a specific route in the requested format.
    
    Supported formats: geojson, kml, shapefile, csv
    """
    try:
        logger.info(f"Exporting route {route_id} in {format_type} format")
        
        # In a real implementation, you would retrieve the route from storage
        # For now, create a mock route for demonstration
        from ..data.api_client import Coordinate
        from ..routing.route_generator import RouteAlignment, RouteSegment
        
        mock_route = RouteAlignment(
            id=route_id,
            waypoints=[
                Coordinate(30.0, 78.0, 1000),
                Coordinate(30.1, 78.1, 1200),
                Coordinate(30.2, 78.2, 1100)
            ],
            segments=[],
            total_distance=25.5,
            elevation_gain=200,
            elevation_loss=100,
            construction_difficulty=45.0,
            estimated_cost=850000,
            estimated_duration=180,
            risk_score=35.0,
            algorithm_used="astar_balanced",
            data_sources=["NASA_SRTM_API", "OpenWeatherMap_API", "Local_DEM"]
        )
        
        if format_type.lower() == "geojson":
            geojson_data = await data_exporter.export_route_geojson(mock_route)
            return JSONResponse(content=geojson_data)
        
        elif format_type.lower() == "kml":
            kml_content = await data_exporter.export_route_kml(mock_route)
            return Response(content=kml_content, media_type="application/vnd.google-earth.kml+xml")
        
        elif format_type.lower() == "csv":
            csv_path = await data_exporter.export_comparative_analysis([mock_route], format_type="csv")
            return FileResponse(
                path=str(csv_path),
                filename=f"route_{route_id}.csv",
                media_type="text/csv"
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format_type}")
        
    except Exception as e:
        logger.error(f"Route export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.post("/api/routes/export/package")
async def create_export_package(
    route_ids: List[str],
    formats: List[str] = ["geojson", "kml", "pdf", "csv"],
    include_analysis: bool = True
):
    """
    Create comprehensive export package for multiple routes.
    """
    try:
        logger.info(f"Creating export package for {len(route_ids)} routes")
        
        # Mock routes for demonstration
        mock_routes = []
        for i, route_id in enumerate(route_ids):
            mock_route = RouteAlignment(
                id=route_id,
                waypoints=[
                    Coordinate(30.0 + i*0.1, 78.0 + i*0.1, 1000 + i*100),
                    Coordinate(30.1 + i*0.1, 78.1 + i*0.1, 1200 + i*100),
                    Coordinate(30.2 + i*0.1, 78.2 + i*0.1, 1100 + i*100)
                ],
                segments=[],
                total_distance=25.5 + i*5,
                elevation_gain=200 + i*50,
                elevation_loss=100 + i*25,
                construction_difficulty=45.0 + i*10,
                estimated_cost=850000 + i*100000,
                estimated_duration=180 + i*30,
                risk_score=35.0 + i*5,
                algorithm_used=f"astar_strategy_{i}",
                data_sources=["NASA_SRTM_API", "OpenWeatherMap_API", "Local_DEM"]
            )
            mock_routes.append(mock_route)
        
        # Create export package
        package_path = await data_exporter.create_export_package(
            mock_routes, formats=formats
        )
        
        return FileResponse(
            path=str(package_path),
            filename=f"route_export_package_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            media_type="application/zip"
        )
        
    except Exception as e:
        logger.error(f"Export package creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Package creation failed: {str(e)}")

# Add missing imports at the top of the file
from fastapi.responses import Response, FileResponse

# Performance monitoring and optimization endpoints
@app.get("/api/performance/status")
async def get_performance_status():
    """
    Get comprehensive performance monitoring status and metrics.
    """
    try:
        logger.info("Getting performance monitoring status")
        
        if api_client:
            # Get comprehensive performance report
            performance_report = api_client.get_performance_optimization_report()
            
            return JSONResponse(content=performance_report)
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Performance monitoring not available",
                    "message": "API client not initialized"
                }
            )
            
    except Exception as e:
        logger.error(f"Performance status check failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Performance status check failed: {str(e)}"
        )

@app.get("/api/performance/metrics")
async def get_performance_metrics():
    """
    Get detailed performance metrics and API usage statistics.
    """
    try:
        logger.info("Getting detailed performance metrics")
        
        if api_client:
            # Get performance monitor instance
            performance_monitor = get_performance_monitor()
            
            # Get comprehensive performance report
            performance_report = performance_monitor.get_performance_report()
            
            # Get API optimization analytics
            api_optimizer = get_api_optimizer()
            optimization_analytics = api_optimizer.get_optimization_analytics()
            
            # Get cost projection
            cost_projection = api_optimizer.get_cost_projection(days_ahead=30)
            
            metrics_data = {
                "timestamp": datetime.now().isoformat(),
                "performance_report": performance_report,
                "optimization_analytics": optimization_analytics,
                "cost_projection": cost_projection,
                "monitoring_status": {
                    "active": performance_monitor._monitoring_active,
                    "metrics_collected": len(performance_monitor.metrics_history),
                    "apis_tracked": len(performance_monitor.api_metrics)
                }
            }
            
            return JSONResponse(content=metrics_data)
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Performance metrics not available",
                    "message": "API client not initialized"
                }
            )
            
    except Exception as e:
        logger.error(f"Performance metrics retrieval failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Performance metrics retrieval failed: {str(e)}"
        )

@app.post("/api/performance/optimize")
async def optimize_system_performance():
    """
    Perform automated system performance optimization.
    """
    try:
        logger.info("Starting automated performance optimization")
        
        if api_client:
            # Perform system optimization
            optimization_results = api_client.optimize_system_performance()
            
            return JSONResponse(content=optimization_results)
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Performance optimization not available",
                    "message": "API client not initialized"
                }
            )
            
    except Exception as e:
        logger.error(f"Performance optimization failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Performance optimization failed: {str(e)}"
        )

@app.get("/api/performance/export")
async def export_performance_metrics():
    """
    Export performance metrics to JSON file for analysis.
    """
    try:
        logger.info("Exporting performance metrics")
        
        if api_client:
            # Get performance monitor instance
            performance_monitor = get_performance_monitor()
            
            # Export metrics to file
            export_path = performance_monitor.export_metrics()
            
            return FileResponse(
                path=str(export_path),
                filename=f"performance_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                media_type="application/json"
            )
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Performance metrics export not available",
                    "message": "API client not initialized"
                }
            )
            
    except Exception as e:
        logger.error(f"Performance metrics export failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Performance metrics export failed: {str(e)}"
        )

@app.post("/api/performance/reset")
async def reset_performance_metrics():
    """
    Reset performance monitoring metrics and start fresh.
    """
    try:
        logger.info("Resetting performance metrics")
        
        if api_client:
            # Get performance monitor instance
            performance_monitor = get_performance_monitor()
            
            # Reset metrics
            performance_monitor.reset_metrics()
            
            return JSONResponse(content={
                "message": "Performance metrics reset successfully",
                "timestamp": datetime.now().isoformat()
            })
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Performance metrics reset not available",
                    "message": "API client not initialized"
                }
            )
            
    except Exception as e:
        logger.error(f"Performance metrics reset failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Performance metrics reset failed: {str(e)}"
        )

@app.get("/api/optimization/recommendations")
async def get_optimization_recommendations():
    """
    Get intelligent optimization recommendations based on current system performance.
    """
    try:
        logger.info("Getting optimization recommendations")
        
        if api_client:
            # Get API optimizer instance
            api_optimizer = get_api_optimizer()
            
            # Get optimization recommendations
            optimization_results = api_optimizer.optimize_api_usage()
            
            return JSONResponse(content=optimization_results)
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Optimization recommendations not available",
                    "message": "API client not initialized"
                }
            )
            
    except Exception as e:
        logger.error(f"Optimization recommendations failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Optimization recommendations failed: {str(e)}"
        )

@app.post("/api/optimization/batch")
async def optimize_batch_requests(
    requests: List[Dict[str, Any]],
    strategy: str = "balanced"
):
    """
    Optimize a batch of API requests for cost and performance.
    """
    try:
        logger.info(f"Optimizing batch of {len(requests)} requests with {strategy} strategy")
        
        if api_client:
            # Get API optimizer instance
            api_optimizer = get_api_optimizer()
            
            # Convert strategy string to enum
            from ..utils.api_optimizer import OptimizationStrategy
            strategy_enum = OptimizationStrategy(strategy.lower())
            
            # Optimize batch requests
            optimization_plan = api_optimizer.optimize_batch_requests(
                requests, strategy=strategy_enum
            )
            
            return JSONResponse(content=optimization_plan)
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Batch optimization not available",
                    "message": "API client not initialized"
                }
            )
            
    except Exception as e:
        logger.error(f"Batch optimization failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Batch optimization failed: {str(e)}"
        )