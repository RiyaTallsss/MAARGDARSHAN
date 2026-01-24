"""
Offline capability and graceful degradation for rural infrastructure planning.

This module provides offline operation capabilities, missing data detection,
fallback mechanisms for AI service failures, and user notifications about
data source limitations and API status.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import json

from ..data.api_client import Coordinate, BoundingBox, DataFreshnessInfo
from ..routing.route_generator import RouteAlignment, RouteConstraints
from ..risk.risk_assessor import CompositeRisk, TerrainRisk, FloodRisk, SeasonalRisk
from ..ai.bedrock_client import AIExplanation, RouteComparison, MitigationRecommendation

logger = logging.getLogger(__name__)


@dataclass
class OfflineCapability:
    """Offline capability assessment."""
    can_operate_offline: bool
    available_features: List[str]
    limited_features: List[str]
    unavailable_features: List[str]
    data_limitations: List[str]
    user_impact: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'can_operate_offline': self.can_operate_offline,
            'available_features': self.available_features,
            'limited_features': self.limited_features,
            'unavailable_features': self.unavailable_features,
            'data_limitations': self.data_limitations,
            'user_impact': self.user_impact
        }


@dataclass
class DataAvailability:
    """Data availability assessment."""
    data_type: str
    local_available: bool
    api_available: bool
    cache_available: bool
    freshness_score: float  # 0-1 scale
    completeness_score: float  # 0-1 scale
    quality_impact: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'data_type': self.data_type,
            'local_available': self.local_available,
            'api_available': self.api_available,
            'cache_available': self.cache_available,
            'freshness_score': self.freshness_score,
            'completeness_score': self.completeness_score,
            'quality_impact': self.quality_impact
        }


class OfflineManager:
    """
    Offline capability and graceful degradation manager.
    
    This class manages offline operation, detects missing data impact,
    provides fallback mechanisms, and generates user notifications
    about system limitations and data availability.
    """
    
    def __init__(self):
        """Initialize Offline Manager."""
        self.offline_mode = False
        self.data_cache = {}
        self.last_api_check = None
        self.api_status = {}
        
        logger.info("Initialized OfflineManager with graceful degradation support")
    
    async def assess_offline_capability(self, 
                                      requested_features: List[str]) -> OfflineCapability:
        """
        Assess system's capability to operate offline for requested features.
        
        Args:
            requested_features: List of features user wants to use
            
        Returns:
            OfflineCapability assessment
        """
        try:
            logger.info(f"Assessing offline capability for {len(requested_features)} features")
            
            # Define feature requirements
            feature_requirements = {
                'route_generation': {
                    'required_data': ['elevation', 'road_network'],
                    'optional_data': ['weather', 'traffic'],
                    'requires_api': False
                },
                'risk_assessment': {
                    'required_data': ['elevation', 'flood_data'],
                    'optional_data': ['weather', 'historical_data'],
                    'requires_api': False
                },
                'ai_explanations': {
                    'required_data': ['route_data'],
                    'optional_data': ['real_time_context'],
                    'requires_api': True  # Requires AWS Bedrock
                },
                'real_time_weather': {
                    'required_data': ['weather_api'],
                    'optional_data': [],
                    'requires_api': True
                },
                'export_functionality': {
                    'required_data': ['route_data'],
                    'optional_data': ['maps'],
                    'requires_api': False
                }
            }
            
            # Assess data availability
            data_availability = await self._assess_data_availability()
            
            # Categorize features
            available_features = []
            limited_features = []
            unavailable_features = []
            data_limitations = []
            
            for feature in requested_features:
                if feature not in feature_requirements:
                    unavailable_features.append(feature)
                    continue
                
                requirements = feature_requirements[feature]
                
                # Check if feature requires API and we're offline
                if requirements['requires_api'] and self.offline_mode:
                    unavailable_features.append(feature)
                    data_limitations.append(f"{feature} requires internet connectivity")
                    continue
                
                # Check required data availability
                required_data_available = True
                missing_required_data = []
                
                for data_type in requirements['required_data']:
                    data_info = next((d for d in data_availability if d.data_type == data_type), None)
                    if not data_info or not (data_info.local_available or data_info.cache_available):
                        required_data_available = False
                        missing_required_data.append(data_type)
                
                if not required_data_available:
                    unavailable_features.append(feature)
                    data_limitations.append(f"{feature} missing required data: {', '.join(missing_required_data)}")
                    continue
                
                # Check optional data availability
                optional_data_missing = []
                for data_type in requirements['optional_data']:
                    data_info = next((d for d in data_availability if d.data_type == data_type), None)
                    if not data_info or not (data_info.local_available or data_info.api_available or data_info.cache_available):
                        optional_data_missing.append(data_type)
                
                if optional_data_missing:
                    limited_features.append(feature)
                    data_limitations.append(f"{feature} has limited data: missing {', '.join(optional_data_missing)}")
                else:
                    available_features.append(feature)
            
            # Determine overall capability
            can_operate_offline = len(available_features) > 0 or len(limited_features) > 0
            
            # Assess user impact
            if len(unavailable_features) == 0:
                user_impact = "minimal"
            elif len(available_features) > len(unavailable_features):
                user_impact = "moderate"
            else:
                user_impact = "significant"
            
            capability = OfflineCapability(
                can_operate_offline=can_operate_offline,
                available_features=available_features,
                limited_features=limited_features,
                unavailable_features=unavailable_features,
                data_limitations=data_limitations,
                user_impact=user_impact
            )
            
            logger.info(f"Offline capability assessment: {len(available_features)} available, "
                       f"{len(limited_features)} limited, {len(unavailable_features)} unavailable")
            
            return capability
            
        except Exception as e:
            logger.error(f"Offline capability assessment failed: {e}")
            return OfflineCapability(
                can_operate_offline=False,
                available_features=[],
                limited_features=[],
                unavailable_features=requested_features,
                data_limitations=[f"Assessment failed: {str(e)}"],
                user_impact="critical"
            )
    
    async def _assess_data_availability(self) -> List[DataAvailability]:
        """Assess availability of different data types."""
        data_types = [
            'elevation',
            'road_network', 
            'weather',
            'flood_data',
            'historical_data',
            'real_time_context'
        ]
        
        availability_list = []
        
        for data_type in data_types:
            # Check local data availability
            local_available = await self._check_local_data_availability(data_type)
            
            # Check API availability
            api_available = await self._check_api_data_availability(data_type)
            
            # Check cache availability
            cache_available = self._check_cache_availability(data_type)
            
            # Calculate freshness score
            freshness_score = self._calculate_freshness_score(data_type, local_available, api_available, cache_available)
            
            # Calculate completeness score
            completeness_score = self._calculate_completeness_score(data_type, local_available, api_available)
            
            # Determine quality impact
            quality_impact = self._assess_quality_impact(freshness_score, completeness_score)
            
            availability = DataAvailability(
                data_type=data_type,
                local_available=local_available,
                api_available=api_available,
                cache_available=cache_available,
                freshness_score=freshness_score,
                completeness_score=completeness_score,
                quality_impact=quality_impact
            )
            
            availability_list.append(availability)
        
        return availability_list
    
    async def _check_local_data_availability(self, data_type: str) -> bool:
        """Check if local data is available for data type."""
        local_data_paths = {
            'elevation': 'Uttarkashi_Terrain/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif',
            'road_network': 'Maps/',
            'weather': 'Rainfall/',
            'flood_data': 'Floods/',
            'historical_data': 'Roads/',
            'real_time_context': None  # Not available locally
        }
        
        if data_type not in local_data_paths or local_data_paths[data_type] is None:
            return False
        
        try:
            data_path = Path(local_data_paths[data_type])
            return data_path.exists()
        except Exception:
            return False
    
    async def _check_api_data_availability(self, data_type: str) -> bool:
        """Check if API data is available for data type."""
        if self.offline_mode:
            return False
        
        # Simplified API availability check
        api_endpoints = {
            'elevation': 'nasa_srtm',
            'road_network': 'overpass',
            'weather': 'openweathermap',
            'flood_data': 'disaster_management',
            'historical_data': None,
            'real_time_context': 'multiple_apis'
        }
        
        if data_type not in api_endpoints or api_endpoints[data_type] is None:
            return False
        
        # Check API status from cache
        api_name = api_endpoints[data_type]
        if api_name in self.api_status:
            return self.api_status[api_name].get('status') == 'available'
        
        return False  # Assume unavailable if not checked recently
    
    def _check_cache_availability(self, data_type: str) -> bool:
        """Check if cached data is available for data type."""
        return data_type in self.data_cache and self.data_cache[data_type] is not None
    
    def _calculate_freshness_score(self, data_type: str, local: bool, api: bool, cache: bool) -> float:
        """Calculate data freshness score (0-1 scale)."""
        if api:
            return 1.0  # API data is freshest
        elif cache:
            return 0.7  # Cached data is moderately fresh
        elif local:
            # Local data freshness depends on type
            local_freshness = {
                'elevation': 0.9,  # Elevation data doesn't change much
                'road_network': 0.6,  # Road networks change moderately
                'weather': 0.1,  # Weather data becomes stale quickly
                'flood_data': 0.8,  # Flood zones change slowly
                'historical_data': 0.9,  # Historical data is stable
                'real_time_context': 0.0  # Cannot be local
            }
            return local_freshness.get(data_type, 0.5)
        else:
            return 0.0  # No data available
    
    def _calculate_completeness_score(self, data_type: str, local: bool, api: bool) -> float:
        """Calculate data completeness score (0-1 scale)."""
        if api and local:
            return 1.0  # Both sources available
        elif api or local:
            return 0.7  # One source available
        else:
            return 0.0  # No sources available
    
    def _assess_quality_impact(self, freshness: float, completeness: float) -> str:
        """Assess quality impact based on freshness and completeness."""
        combined_score = (freshness + completeness) / 2
        
        if combined_score >= 0.8:
            return "minimal"
        elif combined_score >= 0.6:
            return "moderate"
        elif combined_score >= 0.3:
            return "significant"
        else:
            return "severe"
    
    def detect_missing_data_impact(self, 
                                 requested_operation: str,
                                 available_data: List[DataAvailability]) -> Dict[str, Any]:
        """
        Detect impact of missing data on requested operation.
        
        Args:
            requested_operation: Operation user wants to perform
            available_data: List of available data assessments
            
        Returns:
            Dictionary with impact analysis and user explanation
        """
        try:
            logger.info(f"Detecting missing data impact for operation: {requested_operation}")
            
            # Define operation requirements
            operation_requirements = {
                'route_generation': {
                    'critical': ['elevation', 'road_network'],
                    'important': ['weather', 'flood_data'],
                    'optional': ['real_time_context']
                },
                'risk_assessment': {
                    'critical': ['elevation', 'flood_data'],
                    'important': ['weather', 'historical_data'],
                    'optional': ['real_time_context']
                },
                'ai_analysis': {
                    'critical': ['elevation', 'road_network'],
                    'important': ['weather', 'flood_data'],
                    'optional': ['historical_data', 'real_time_context']
                }
            }
            
            if requested_operation not in operation_requirements:
                return {
                    'impact_level': 'unknown',
                    'can_proceed': False,
                    'user_explanation': f"Unknown operation: {requested_operation}",
                    'missing_data': [],
                    'available_alternatives': []
                }
            
            requirements = operation_requirements[requested_operation]
            
            # Assess missing data by category
            missing_critical = []
            missing_important = []
            missing_optional = []
            
            for data_type in requirements['critical']:
                data_info = next((d for d in available_data if d.data_type == data_type), None)
                if not data_info or not (data_info.local_available or data_info.api_available or data_info.cache_available):
                    missing_critical.append(data_type)
            
            for data_type in requirements['important']:
                data_info = next((d for d in available_data if d.data_type == data_type), None)
                if not data_info or not (data_info.local_available or data_info.api_available or data_info.cache_available):
                    missing_important.append(data_type)
            
            for data_type in requirements['optional']:
                data_info = next((d for d in available_data if d.data_type == data_type), None)
                if not data_info or not (data_info.local_available or data_info.api_available or data_info.cache_available):
                    missing_optional.append(data_type)
            
            # Determine impact level and ability to proceed
            if missing_critical:
                impact_level = 'critical'
                can_proceed = False
                user_explanation = f"Cannot perform {requested_operation} due to missing critical data: {', '.join(missing_critical)}"
            elif missing_important:
                impact_level = 'significant'
                can_proceed = True
                user_explanation = f"Can perform {requested_operation} with reduced accuracy due to missing data: {', '.join(missing_important)}"
            elif missing_optional:
                impact_level = 'minor'
                can_proceed = True
                user_explanation = f"Can perform {requested_operation} with slightly reduced features due to missing optional data: {', '.join(missing_optional)}"
            else:
                impact_level = 'none'
                can_proceed = True
                user_explanation = f"All required data available for {requested_operation}"
            
            # Suggest alternatives
            alternatives = []
            if not can_proceed:
                if requested_operation == 'route_generation':
                    alternatives = ['Use simplified routing', 'Try different start/end points', 'Wait for data connectivity']
                elif requested_operation == 'risk_assessment':
                    alternatives = ['Use basic risk assessment', 'Focus on available risk factors', 'Use historical averages']
                elif requested_operation == 'ai_analysis':
                    alternatives = ['Use rule-based analysis', 'Generate basic explanations', 'Wait for AI service connectivity']
            
            return {
                'impact_level': impact_level,
                'can_proceed': can_proceed,
                'user_explanation': user_explanation,
                'missing_data': {
                    'critical': missing_critical,
                    'important': missing_important,
                    'optional': missing_optional
                },
                'available_alternatives': alternatives
            }
            
        except Exception as e:
            logger.error(f"Missing data impact detection failed: {e}")
            return {
                'impact_level': 'unknown',
                'can_proceed': False,
                'user_explanation': f"Unable to assess data impact: {str(e)}",
                'missing_data': [],
                'available_alternatives': ['Contact system administrator']
            }
    
    async def create_fallback_ai_explanation(self, 
                                           route: RouteAlignment,
                                           constraints: Optional[RouteConstraints] = None) -> AIExplanation:
        """
        Create fallback AI explanation when Bedrock is unavailable.
        
        Args:
            route: Route alignment to explain
            constraints: Optional routing constraints
            
        Returns:
            Fallback AIExplanation with rule-based analysis
        """
        try:
            logger.info(f"Creating fallback AI explanation for route {route.id}")
            
            # Generate rule-based explanation
            explanation_parts = []
            
            # Distance analysis
            if route.total_distance < 10:
                explanation_parts.append("This is a short-distance route suitable for local connectivity.")
            elif route.total_distance < 50:
                explanation_parts.append("This is a medium-distance route providing regional connectivity.")
            else:
                explanation_parts.append("This is a long-distance route requiring careful planning and phased construction.")
            
            # Cost analysis
            cost_per_km = route.estimated_cost / route.total_distance if route.total_distance > 0 else 0
            if cost_per_km < 50000:
                explanation_parts.append("The construction cost is relatively low due to favorable terrain conditions.")
            elif cost_per_km < 100000:
                explanation_parts.append("The construction cost is moderate, reflecting typical mountain road challenges.")
            else:
                explanation_parts.append("The construction cost is high due to difficult terrain and engineering challenges.")
            
            # Difficulty analysis
            if route.construction_difficulty < 30:
                explanation_parts.append("Construction difficulty is low with standard equipment and techniques suitable.")
            elif route.construction_difficulty < 60:
                explanation_parts.append("Construction difficulty is moderate, requiring experienced contractors and appropriate equipment.")
            else:
                explanation_parts.append("Construction difficulty is high, requiring specialized equipment and expert engineering.")
            
            # Risk analysis
            if route.risk_score < 30:
                explanation_parts.append("Overall risk is low with standard mitigation measures sufficient.")
            elif route.risk_score < 60:
                explanation_parts.append("Overall risk is moderate, requiring careful planning and risk mitigation strategies.")
            else:
                explanation_parts.append("Overall risk is high, requiring comprehensive risk management and contingency planning.")
            
            # Constraints consideration
            if constraints:
                if constraints.budget_limit and route.estimated_cost > constraints.budget_limit * 0.9:
                    explanation_parts.append("The route approaches the budget limit, requiring cost optimization measures.")
                
                if constraints.timeline_limit and route.estimated_duration > constraints.timeline_limit * 0.9:
                    explanation_parts.append("The construction timeline is tight, requiring efficient project management.")
            
            explanation_text = " ".join(explanation_parts)
            
            # Generate reasoning steps
            reasoning_steps = [
                f"Analyzed route distance: {route.total_distance:.1f} km",
                f"Evaluated construction cost: ${route.estimated_cost:,.0f}",
                f"Assessed difficulty score: {route.construction_difficulty:.1f}/100",
                f"Reviewed risk factors: {route.risk_score:.1f}/100 risk score",
                "Applied Uttarakhand-specific construction parameters",
                "Generated recommendations based on rule-based analysis"
            ]
            
            fallback_explanation = AIExplanation(
                explanation_id=f"fallback_{route.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                route_id=route.id,
                explanation_text=explanation_text,
                reasoning_steps=reasoning_steps,
                confidence_score=0.6,  # Lower confidence for rule-based analysis
                data_sources_used=route.data_sources or ['local_analysis'],
                model_used="rule_based_fallback"
            )
            
            logger.info(f"Generated fallback AI explanation with {len(reasoning_steps)} reasoning steps")
            
            return fallback_explanation
            
        except Exception as e:
            logger.error(f"Fallback AI explanation creation failed: {e}")
            # Return minimal explanation
            return AIExplanation(
                explanation_id=f"minimal_{route.id}",
                route_id=route.id,
                explanation_text="Route analysis completed using local data and rule-based assessment.",
                reasoning_steps=["Basic route analysis performed"],
                confidence_score=0.3,
                data_sources_used=['local_data'],
                model_used="minimal_fallback"
            )
    
    def generate_user_notification(self, 
                                 notification_type: str,
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate user notification about system limitations and data availability.
        
        Args:
            notification_type: Type of notification (offline, degraded, limited_data, etc.)
            context: Context information for the notification
            
        Returns:
            Dictionary with notification details
        """
        try:
            notifications = {
                'offline_mode': {
                    'title': 'Operating in Offline Mode',
                    'message': 'The system is currently operating with local data only. Some features may be limited.',
                    'severity': 'warning',
                    'actions': ['Check internet connection', 'Continue with available features']
                },
                'api_degraded': {
                    'title': 'External Data Services Degraded',
                    'message': 'Some external data services are experiencing issues. Using cached and local data.',
                    'severity': 'info',
                    'actions': ['Continue with current data', 'Retry later for updated information']
                },
                'limited_data': {
                    'title': 'Limited Data Available',
                    'message': 'Some data sources are unavailable. Results may have reduced accuracy.',
                    'severity': 'warning',
                    'actions': ['Proceed with available data', 'Wait for full data availability']
                },
                'ai_unavailable': {
                    'title': 'AI Analysis Unavailable',
                    'message': 'AI-powered explanations are currently unavailable. Using rule-based analysis.',
                    'severity': 'info',
                    'actions': ['Continue with rule-based analysis', 'Try again later for AI insights']
                }
            }
            
            base_notification = notifications.get(notification_type, {
                'title': 'System Notification',
                'message': 'System status update',
                'severity': 'info',
                'actions': ['Continue']
            })
            
            # Customize notification with context
            notification = base_notification.copy()
            notification.update({
                'timestamp': datetime.now().isoformat(),
                'context': context,
                'notification_id': f"{notification_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            })
            
            return notification
            
        except Exception as e:
            logger.error(f"User notification generation failed: {e}")
            return {
                'title': 'System Notification',
                'message': 'System status update available',
                'severity': 'info',
                'timestamp': datetime.now().isoformat(),
                'actions': ['Continue'],
                'notification_id': f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            }
    
    def set_offline_mode(self, offline: bool):
        """Set offline mode status."""
        self.offline_mode = offline
        logger.info(f"Offline mode {'enabled' if offline else 'disabled'}")
    
    def update_api_status(self, api_status: Dict[str, Dict[str, Any]]):
        """Update API status information."""
        self.api_status = api_status
        self.last_api_check = datetime.now()
        
        # Determine if we should be in offline mode
        available_apis = sum(1 for status in api_status.values() if status.get('status') == 'available')
        total_apis = len(api_status)
        
        if available_apis == 0:
            self.set_offline_mode(True)
        elif available_apis < total_apis * 0.5:  # Less than 50% APIs available
            logger.warning(f"Limited API availability: {available_apis}/{total_apis} APIs available")
        else:
            self.set_offline_mode(False)


# Global offline manager instance
offline_manager = OfflineManager()