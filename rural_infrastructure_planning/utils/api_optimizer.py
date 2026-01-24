"""
API optimization module for intelligent cost management and performance optimization.

This module provides advanced API optimization strategies including intelligent
source selection, cost-aware request routing, and performance-based fallback decisions.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import statistics
from collections import defaultdict

from .performance_monitor import get_performance_monitor, PerformanceMonitor

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """API optimization strategies."""
    COST_FIRST = "cost_first"
    PERFORMANCE_FIRST = "performance_first"
    RELIABILITY_FIRST = "reliability_first"
    BALANCED = "balanced"
    ADAPTIVE = "adaptive"


@dataclass
class APISourceConfig:
    """Configuration for an API source."""
    name: str
    cost_per_request: float
    daily_limit: Optional[int]
    rate_limit_per_minute: int
    expected_response_time_ms: float
    reliability_score: float  # 0-1
    quality_score: float  # 0-1
    fallback_priority: int  # Lower number = higher priority
    
    def get_cost_efficiency_score(self) -> float:
        """Calculate cost efficiency (quality per dollar)."""
        if self.cost_per_request == 0:
            return self.quality_score * 10  # Free APIs get bonus
        return self.quality_score / self.cost_per_request
    
    def get_performance_score(self) -> float:
        """Calculate performance score based on speed and reliability."""
        # Normalize response time (lower is better)
        time_score = max(0, 1 - (self.expected_response_time_ms / 10000))  # 10s = 0 score
        return (time_score + self.reliability_score) / 2


@dataclass
class OptimizationDecision:
    """Result of API optimization decision."""
    selected_source: str
    strategy_used: OptimizationStrategy
    confidence_score: float  # 0-1
    reasoning: List[str]
    alternatives: List[str]
    estimated_cost: float
    estimated_response_time_ms: float
    fallback_plan: List[str]


@dataclass
class CostBudget:
    """Cost budget configuration."""
    daily_limit_usd: float
    per_request_limit_usd: float
    monthly_limit_usd: float
    alert_threshold_percent: float = 80.0
    
    def is_within_budget(self, current_daily_cost: float, request_cost: float) -> bool:
        """Check if a request is within budget."""
        if request_cost > self.per_request_limit_usd:
            return False
        if current_daily_cost + request_cost > self.daily_limit_usd:
            return False
        return True
    
    def get_remaining_budget(self, current_daily_cost: float) -> float:
        """Get remaining daily budget."""
        return max(0, self.daily_limit_usd - current_daily_cost)


class APIOptimizer:
    """
    Intelligent API optimization system.
    
    Features:
    - Dynamic source selection based on multiple criteria
    - Cost-aware request routing with budget management
    - Performance-based optimization with adaptive thresholds
    - Intelligent fallback strategies with circuit breaker patterns
    - Real-time optimization based on current system state
    """
    
    def __init__(self, performance_monitor: Optional[PerformanceMonitor] = None):
        self.performance_monitor = performance_monitor or get_performance_monitor()
        
        # API source configurations
        self.api_sources: Dict[str, APISourceConfig] = {}
        self._initialize_default_sources()
        
        # Optimization settings
        self.default_strategy = OptimizationStrategy.BALANCED
        self.cost_budget = CostBudget(
            daily_limit_usd=10.0,
            per_request_limit_usd=0.10,
            monthly_limit_usd=200.0
        )
        
        # Adaptive optimization state
        self.optimization_history: List[Dict[str, Any]] = []
        self.strategy_performance: Dict[OptimizationStrategy, List[float]] = defaultdict(list)
        
        # Circuit breaker state
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        logger.info("API optimizer initialized")
    
    def _initialize_default_sources(self) -> None:
        """Initialize default API source configurations."""
        self.api_sources = {
            'nasa_srtm': APISourceConfig(
                name='nasa_srtm',
                cost_per_request=0.0,
                daily_limit=1000,
                rate_limit_per_minute=100,
                expected_response_time_ms=2000,
                reliability_score=0.95,
                quality_score=0.9,
                fallback_priority=1
            ),
            'usgs_elevation': APISourceConfig(
                name='usgs_elevation',
                cost_per_request=0.0,
                daily_limit=1000,
                rate_limit_per_minute=100,
                expected_response_time_ms=1500,
                reliability_score=0.98,
                quality_score=0.85,
                fallback_priority=2
            ),
            'openweathermap': APISourceConfig(
                name='openweathermap',
                cost_per_request=0.001,
                daily_limit=1000,
                rate_limit_per_minute=60,
                expected_response_time_ms=800,
                reliability_score=0.99,
                quality_score=0.95,
                fallback_priority=1
            ),
            'imd_api': APISourceConfig(
                name='imd_api',
                cost_per_request=0.0,
                daily_limit=500,
                rate_limit_per_minute=30,
                expected_response_time_ms=3000,
                reliability_score=0.85,
                quality_score=0.8,
                fallback_priority=2
            ),
            'overpass': APISourceConfig(
                name='overpass',
                cost_per_request=0.0,
                daily_limit=None,
                rate_limit_per_minute=10,
                expected_response_time_ms=5000,
                reliability_score=0.9,
                quality_score=0.9,
                fallback_priority=1
            ),
            'google_places': APISourceConfig(
                name='google_places',
                cost_per_request=0.05,
                daily_limit=100,
                rate_limit_per_minute=100,
                expected_response_time_ms=1200,
                reliability_score=0.99,
                quality_score=0.98,
                fallback_priority=3
            ),
            'disaster_api': APISourceConfig(
                name='disaster_api',
                cost_per_request=0.0,
                daily_limit=200,
                rate_limit_per_minute=20,
                expected_response_time_ms=4000,
                reliability_score=0.8,
                quality_score=0.75,
                fallback_priority=1
            )
        }
    
    def optimize_api_selection(self, 
                             data_type: str,
                             available_sources: List[str],
                             strategy: Optional[OptimizationStrategy] = None,
                             priority_factors: Optional[Dict[str, float]] = None) -> OptimizationDecision:
        """
        Select optimal API source based on current conditions and strategy.
        
        Args:
            data_type: Type of data being requested (elevation, weather, etc.)
            available_sources: List of available API sources
            strategy: Optimization strategy to use
            priority_factors: Custom priority weights for decision factors
            
        Returns:
            OptimizationDecision with selected source and reasoning
        """
        strategy = strategy or self.default_strategy
        priority_factors = priority_factors or self._get_default_priority_factors(strategy)
        
        # Filter available sources
        valid_sources = [s for s in available_sources if s in self.api_sources]
        if not valid_sources:
            raise ValueError(f"No valid API sources available for {data_type}")
        
        # Get current system state
        current_state = self._get_current_system_state()
        
        # Score each source
        source_scores = {}
        reasoning = []
        
        for source_name in valid_sources:
            source_config = self.api_sources[source_name]
            score_components = self._calculate_source_score(
                source_config, current_state, priority_factors
            )
            
            total_score = sum(
                score_components[factor] * weight 
                for factor, weight in priority_factors.items()
                if factor in score_components
            )
            
            source_scores[source_name] = {
                'total_score': total_score,
                'components': score_components
            }
        
        # Select best source
        best_source = max(source_scores.keys(), key=lambda s: source_scores[s]['total_score'])
        best_score_info = source_scores[best_source]
        
        # Generate reasoning
        reasoning.append(f"Selected {best_source} with score {best_score_info['total_score']:.3f}")
        reasoning.append(f"Strategy: {strategy.value}")
        
        for factor, score in best_score_info['components'].items():
            if priority_factors.get(factor, 0) > 0:
                reasoning.append(f"{factor}: {score:.3f} (weight: {priority_factors[factor]:.2f})")
        
        # Create alternatives list
        alternatives = sorted(
            [s for s in source_scores.keys() if s != best_source],
            key=lambda s: source_scores[s]['total_score'],
            reverse=True
        )
        
        # Create fallback plan
        fallback_plan = self._create_fallback_plan(valid_sources, source_scores)
        
        # Estimate cost and response time
        best_config = self.api_sources[best_source]
        estimated_cost = best_config.cost_per_request
        estimated_response_time = self._estimate_response_time(best_source, current_state)
        
        decision = OptimizationDecision(
            selected_source=best_source,
            strategy_used=strategy,
            confidence_score=best_score_info['total_score'],
            reasoning=reasoning,
            alternatives=alternatives,
            estimated_cost=estimated_cost,
            estimated_response_time_ms=estimated_response_time,
            fallback_plan=fallback_plan
        )
        
        # Record decision for learning
        self._record_optimization_decision(decision, current_state)
        
        return decision
    
    def _get_default_priority_factors(self, strategy: OptimizationStrategy) -> Dict[str, float]:
        """Get default priority factors for a strategy."""
        if strategy == OptimizationStrategy.COST_FIRST:
            return {
                'cost_efficiency': 0.5,
                'performance': 0.2,
                'reliability': 0.2,
                'availability': 0.1
            }
        elif strategy == OptimizationStrategy.PERFORMANCE_FIRST:
            return {
                'performance': 0.5,
                'reliability': 0.3,
                'availability': 0.15,
                'cost_efficiency': 0.05
            }
        elif strategy == OptimizationStrategy.RELIABILITY_FIRST:
            return {
                'reliability': 0.5,
                'availability': 0.3,
                'performance': 0.15,
                'cost_efficiency': 0.05
            }
        elif strategy == OptimizationStrategy.BALANCED:
            return {
                'cost_efficiency': 0.25,
                'performance': 0.25,
                'reliability': 0.25,
                'availability': 0.25
            }
        else:  # ADAPTIVE
            return self._get_adaptive_priority_factors()
    
    def _get_adaptive_priority_factors(self) -> Dict[str, float]:
        """Get adaptive priority factors based on current system state."""
        current_state = self._get_current_system_state()
        
        # Start with balanced weights
        factors = {
            'cost_efficiency': 0.25,
            'performance': 0.25,
            'reliability': 0.25,
            'availability': 0.25
        }
        
        # Adjust based on current conditions
        
        # If high cost, prioritize cost efficiency
        if current_state['daily_cost'] > self.cost_budget.daily_limit_usd * 0.7:
            factors['cost_efficiency'] += 0.2
            factors['performance'] -= 0.1
            factors['reliability'] -= 0.1
        
        # If high error rate, prioritize reliability
        if current_state['error_rate'] > 5.0:  # > 5% error rate
            factors['reliability'] += 0.2
            factors['cost_efficiency'] -= 0.1
            factors['performance'] -= 0.1
        
        # If slow response times, prioritize performance
        if current_state['avg_response_time'] > 3000:  # > 3 seconds
            factors['performance'] += 0.2
            factors['cost_efficiency'] -= 0.1
            factors['reliability'] -= 0.1
        
        # If many sources unavailable, prioritize availability
        if current_state['availability_ratio'] < 0.7:  # < 70% sources available
            factors['availability'] += 0.2
            factors['cost_efficiency'] -= 0.1
            factors['performance'] -= 0.1
        
        # Normalize to ensure sum = 1.0
        total = sum(factors.values())
        factors = {k: v / total for k, v in factors.items()}
        
        return factors
    
    def _get_current_system_state(self) -> Dict[str, Any]:
        """Get current system state for optimization decisions."""
        # Get performance metrics
        perf_report = self.performance_monitor.get_performance_report()
        
        # Calculate current metrics
        daily_cost = perf_report['cost_tracking']['total_cost_today']
        
        # Calculate average response time across APIs
        api_metrics = perf_report['api_performance']
        if api_metrics:
            response_times = [
                metrics['average_response_time_ms'] 
                for metrics in api_metrics.values()
                if metrics['request_count'] > 0
            ]
            avg_response_time = statistics.mean(response_times) if response_times else 0
            
            # Calculate error rate
            total_requests = sum(metrics['request_count'] for metrics in api_metrics.values())
            total_errors = sum(metrics['error_count'] for metrics in api_metrics.values())
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
        else:
            avg_response_time = 0
            error_rate = 0
        
        # Calculate availability ratio
        total_sources = len(self.api_sources)
        available_sources = sum(
            1 for source_name in self.api_sources.keys()
            if not self._is_circuit_breaker_open(source_name)
        )
        availability_ratio = available_sources / total_sources if total_sources > 0 else 1.0
        
        return {
            'daily_cost': daily_cost,
            'avg_response_time': avg_response_time,
            'error_rate': error_rate,
            'availability_ratio': availability_ratio,
            'concurrent_users': perf_report['concurrent_users'],
            'cache_hit_rate': perf_report['cost_tracking']['cache_hit_rate'] if 'cache_hit_rate' in perf_report['cost_tracking'] else 0.75
        }
    
    def _calculate_source_score(self, 
                               source_config: APISourceConfig,
                               current_state: Dict[str, Any],
                               priority_factors: Dict[str, float]) -> Dict[str, float]:
        """Calculate score components for a source."""
        scores = {}
        
        # Cost efficiency score
        if source_config.cost_per_request == 0:
            scores['cost_efficiency'] = 1.0  # Free APIs get max score
        else:
            # Check budget constraints
            remaining_budget = self.cost_budget.get_remaining_budget(current_state['daily_cost'])
            if source_config.cost_per_request > remaining_budget:
                scores['cost_efficiency'] = 0.0  # Can't afford
            else:
                # Score based on cost efficiency
                scores['cost_efficiency'] = min(1.0, source_config.get_cost_efficiency_score() / 10)
        
        # Performance score
        base_performance = source_config.get_performance_score()
        
        # Adjust based on current system load
        if current_state['concurrent_users'] > 20:  # High load
            # Prefer faster APIs under high load
            time_factor = max(0.1, 1.0 - (source_config.expected_response_time_ms / 5000))
            base_performance = (base_performance + time_factor) / 2
        
        scores['performance'] = base_performance
        
        # Reliability score
        base_reliability = source_config.reliability_score
        
        # Adjust based on recent performance
        if source_config.name in self.performance_monitor.api_metrics:
            api_metrics = self.performance_monitor.api_metrics[source_config.name]
            recent_success_rate = api_metrics.get_success_rate() / 100
            # Weighted average of configured and observed reliability
            base_reliability = (base_reliability + recent_success_rate) / 2
        
        scores['reliability'] = base_reliability
        
        # Availability score
        if self._is_circuit_breaker_open(source_config.name):
            scores['availability'] = 0.0
        elif self._is_rate_limited(source_config.name, current_state):
            scores['availability'] = 0.3  # Partially available
        else:
            scores['availability'] = 1.0
        
        return scores
    
    def _is_circuit_breaker_open(self, source_name: str) -> bool:
        """Check if circuit breaker is open for a source."""
        if source_name not in self.circuit_breakers:
            return False
        
        breaker = self.circuit_breakers[source_name]
        if breaker['state'] != 'open':
            return False
        
        # Check if timeout has passed
        timeout_duration = breaker.get('timeout_duration', 300)  # 5 minutes default
        if (datetime.now() - breaker['opened_at']).total_seconds() > timeout_duration:
            # Reset to half-open
            breaker['state'] = 'half_open'
            return False
        
        return True
    
    def _is_rate_limited(self, source_name: str, current_state: Dict[str, Any]) -> bool:
        """Check if source is currently rate limited."""
        if source_name not in self.api_sources:
            return False
        
        source_config = self.api_sources[source_name]
        
        # Check daily limit
        if source_config.daily_limit:
            if source_name in self.performance_monitor.api_metrics:
                api_metrics = self.performance_monitor.api_metrics[source_name]
                # Estimate requests today (simplified)
                if api_metrics.request_count > source_config.daily_limit * 0.9:
                    return True
        
        # Check recent rate limit hits
        if source_name in self.performance_monitor.api_metrics:
            api_metrics = self.performance_monitor.api_metrics[source_name]
            if api_metrics.rate_limit_count > 0:
                # Check if recent (within last hour)
                if (api_metrics.last_request_time and 
                    (datetime.now() - api_metrics.last_request_time).total_seconds() < 3600):
                    return True
        
        return False
    
    def _estimate_response_time(self, source_name: str, current_state: Dict[str, Any]) -> float:
        """Estimate response time for a source based on current conditions."""
        if source_name not in self.api_sources:
            return 5000.0  # Default high value
        
        source_config = self.api_sources[source_name]
        base_time = source_config.expected_response_time_ms
        
        # Adjust based on recent performance
        if source_name in self.performance_monitor.api_metrics:
            api_metrics = self.performance_monitor.api_metrics[source_name]
            if api_metrics.request_count > 0:
                recent_avg = api_metrics.get_average_response_time()
                # Weighted average of expected and recent performance
                base_time = (base_time + recent_avg) / 2
        
        # Adjust based on system load
        load_factor = 1.0
        if current_state['concurrent_users'] > 20:
            load_factor = 1.2  # 20% slower under high load
        elif current_state['concurrent_users'] > 50:
            load_factor = 1.5  # 50% slower under very high load
        
        return base_time * load_factor
    
    def _create_fallback_plan(self, 
                             available_sources: List[str],
                             source_scores: Dict[str, Dict[str, Any]]) -> List[str]:
        """Create fallback plan ordered by preference."""
        # Sort by total score, then by fallback priority
        fallback_sources = sorted(
            available_sources,
            key=lambda s: (
                source_scores[s]['total_score'],
                -self.api_sources[s].fallback_priority  # Lower priority number = higher preference
            ),
            reverse=True
        )
        
        return fallback_sources
    
    def _record_optimization_decision(self, 
                                    decision: OptimizationDecision,
                                    system_state: Dict[str, Any]) -> None:
        """Record optimization decision for learning."""
        record = {
            'timestamp': datetime.now().isoformat(),
            'decision': {
                'selected_source': decision.selected_source,
                'strategy': decision.strategy_used.value,
                'confidence_score': decision.confidence_score
            },
            'system_state': system_state,
            'estimated_cost': decision.estimated_cost,
            'estimated_response_time': decision.estimated_response_time_ms
        }
        
        self.optimization_history.append(record)
        
        # Keep only recent history (last 1000 decisions)
        if len(self.optimization_history) > 1000:
            self.optimization_history = self.optimization_history[-1000:]
    
    def update_circuit_breaker(self, source_name: str, success: bool, response_time_ms: float) -> None:
        """Update circuit breaker state based on request outcome."""
        if source_name not in self.circuit_breakers:
            self.circuit_breakers[source_name] = {
                'state': 'closed',
                'failure_count': 0,
                'success_count': 0,
                'last_failure_time': None,
                'opened_at': None
            }
        
        breaker = self.circuit_breakers[source_name]
        
        if success:
            breaker['success_count'] += 1
            breaker['failure_count'] = max(0, breaker['failure_count'] - 1)  # Gradual recovery
            
            # If half-open and successful, close the breaker
            if breaker['state'] == 'half_open':
                breaker['state'] = 'closed'
                logger.info(f"Circuit breaker closed for {source_name}")
        else:
            breaker['failure_count'] += 1
            breaker['last_failure_time'] = datetime.now()
            
            # Open breaker if failure threshold exceeded
            failure_threshold = 5  # Open after 5 failures
            if breaker['failure_count'] >= failure_threshold and breaker['state'] == 'closed':
                breaker['state'] = 'open'
                breaker['opened_at'] = datetime.now()
                logger.warning(f"Circuit breaker opened for {source_name} after {failure_threshold} failures")
    
    def get_optimization_analytics(self) -> Dict[str, Any]:
        """Get analytics on optimization performance."""
        if not self.optimization_history:
            return {'status': 'no_data'}
        
        # Analyze strategy performance
        strategy_stats = {}
        for strategy in OptimizationStrategy:
            strategy_decisions = [
                d for d in self.optimization_history
                if d['decision']['strategy'] == strategy.value
            ]
            
            if strategy_decisions:
                confidence_scores = [d['decision']['confidence_score'] for d in strategy_decisions]
                strategy_stats[strategy.value] = {
                    'decision_count': len(strategy_decisions),
                    'avg_confidence': statistics.mean(confidence_scores),
                    'min_confidence': min(confidence_scores),
                    'max_confidence': max(confidence_scores)
                }
        
        # Analyze source selection patterns
        source_selection_count = defaultdict(int)
        for decision in self.optimization_history:
            source_selection_count[decision['decision']['selected_source']] += 1
        
        # Calculate cost and performance trends
        recent_decisions = self.optimization_history[-100:]  # Last 100 decisions
        if recent_decisions:
            total_estimated_cost = sum(d['estimated_cost'] for d in recent_decisions)
            avg_estimated_response_time = statistics.mean(
                d['estimated_response_time'] for d in recent_decisions
            )
        else:
            total_estimated_cost = 0
            avg_estimated_response_time = 0
        
        return {
            'status': 'available',
            'total_decisions': len(self.optimization_history),
            'strategy_performance': strategy_stats,
            'source_selection_frequency': dict(source_selection_count),
            'recent_trends': {
                'total_estimated_cost': total_estimated_cost,
                'avg_estimated_response_time_ms': avg_estimated_response_time,
                'decisions_analyzed': len(recent_decisions)
            },
            'circuit_breaker_status': {
                name: {
                    'state': breaker['state'],
                    'failure_count': breaker['failure_count'],
                    'success_count': breaker['success_count']
                }
                for name, breaker in self.circuit_breakers.items()
            }
        }
    
    def optimize_batch_requests(self, 
                               requests: List[Dict[str, Any]],
                               strategy: Optional[OptimizationStrategy] = None) -> Dict[str, Any]:
        """
        Optimize a batch of API requests for cost and performance.
        
        Args:
            requests: List of request specifications
            strategy: Optimization strategy to use
            
        Returns:
            Optimization plan for the batch
        """
        strategy = strategy or self.default_strategy
        
        # Group requests by data type and source requirements
        request_groups = defaultdict(list)
        for i, request in enumerate(requests):
            data_type = request.get('data_type', 'unknown')
            request_groups[data_type].append((i, request))
        
        # Optimize each group
        optimization_plan = {
            'total_requests': len(requests),
            'groups': {},
            'total_estimated_cost': 0.0,
            'total_estimated_time_ms': 0.0,
            'recommendations': []
        }
        
        for data_type, group_requests in request_groups.items():
            group_plan = self._optimize_request_group(data_type, group_requests, strategy)
            optimization_plan['groups'][data_type] = group_plan
            optimization_plan['total_estimated_cost'] += group_plan['estimated_cost']
            optimization_plan['total_estimated_time_ms'] += group_plan['estimated_time_ms']
        
        # Generate batch-level recommendations
        optimization_plan['recommendations'] = self._generate_batch_recommendations(
            optimization_plan, strategy
        )
        
        return optimization_plan
    
    def _optimize_request_group(self, 
                               data_type: str,
                               group_requests: List[Tuple[int, Dict[str, Any]]],
                               strategy: OptimizationStrategy) -> Dict[str, Any]:
        """Optimize a group of requests for the same data type."""
        # Get available sources for this data type
        available_sources = self._get_sources_for_data_type(data_type)
        
        if not available_sources:
            return {
                'data_type': data_type,
                'request_count': len(group_requests),
                'selected_source': 'local_fallback',
                'estimated_cost': 0.0,
                'estimated_time_ms': 1000.0,  # Fallback estimate
                'batching_possible': False
            }
        
        # Optimize source selection for the group
        decision = self.optimize_api_selection(data_type, available_sources, strategy)
        
        # Check if batching is possible
        selected_config = self.api_sources[decision.selected_source]
        batching_possible = self._can_batch_requests(decision.selected_source, group_requests)
        
        # Calculate group estimates
        if batching_possible:
            # Batch requests reduce total time but may increase per-request cost
            estimated_cost = decision.estimated_cost * len(group_requests) * 1.1  # 10% batch overhead
            estimated_time_ms = decision.estimated_response_time_ms * 1.5  # Batch processing time
        else:
            # Sequential requests
            estimated_cost = decision.estimated_cost * len(group_requests)
            estimated_time_ms = decision.estimated_response_time_ms * len(group_requests)
        
        return {
            'data_type': data_type,
            'request_count': len(group_requests),
            'selected_source': decision.selected_source,
            'estimated_cost': estimated_cost,
            'estimated_time_ms': estimated_time_ms,
            'batching_possible': batching_possible,
            'confidence_score': decision.confidence_score,
            'fallback_plan': decision.fallback_plan
        }
    
    def _get_sources_for_data_type(self, data_type: str) -> List[str]:
        """Get available API sources for a data type."""
        source_mapping = {
            'elevation': ['nasa_srtm', 'usgs_elevation'],
            'weather': ['openweathermap', 'imd_api'],
            'osm': ['overpass'],
            'flood': ['disaster_api'],
            'infrastructure': ['overpass', 'google_places']
        }
        
        return source_mapping.get(data_type, [])
    
    def _can_batch_requests(self, source_name: str, requests: List[Tuple[int, Dict[str, Any]]]) -> bool:
        """Check if requests can be batched for a source."""
        # Simple heuristic: APIs that support geographic queries can often batch
        batch_capable_sources = ['google_places', 'overpass', 'openweathermap']
        return source_name in batch_capable_sources and len(requests) > 1
    
    def _generate_batch_recommendations(self, 
                                      optimization_plan: Dict[str, Any],
                                      strategy: OptimizationStrategy) -> List[str]:
        """Generate recommendations for batch optimization."""
        recommendations = []
        
        total_cost = optimization_plan['total_estimated_cost']
        total_time = optimization_plan['total_estimated_time_ms']
        
        # Cost recommendations
        if total_cost > self.cost_budget.daily_limit_usd * 0.5:
            recommendations.append(
                f"High batch cost (${total_cost:.2f}). Consider using more free APIs or caching."
            )
        
        # Performance recommendations
        if total_time > 30000:  # > 30 seconds
            recommendations.append(
                f"Long batch processing time ({total_time/1000:.1f}s). Consider parallel processing."
            )
        
        # Batching recommendations
        batchable_groups = [
            group for group in optimization_plan['groups'].values()
            if group.get('batching_possible', False)
        ]
        
        if batchable_groups:
            recommendations.append(
                f"Consider batching {len(batchable_groups)} request groups for better performance."
            )
        
        return recommendations
    
    def set_cost_budget(self, daily_limit: float, per_request_limit: float, monthly_limit: float) -> None:
        """Update cost budget configuration."""
        self.cost_budget = CostBudget(
            daily_limit_usd=daily_limit,
            per_request_limit_usd=per_request_limit,
            monthly_limit_usd=monthly_limit
        )
        logger.info(f"Cost budget updated: daily=${daily_limit}, per_request=${per_request_limit}, monthly=${monthly_limit}")
    
    def update_source_config(self, source_name: str, **kwargs) -> None:
        """Update configuration for an API source."""
        if source_name not in self.api_sources:
            logger.warning(f"Unknown API source: {source_name}")
            return
        
        source_config = self.api_sources[source_name]
        
        for key, value in kwargs.items():
            if hasattr(source_config, key):
                setattr(source_config, key, value)
                logger.info(f"Updated {source_name}.{key} = {value}")
            else:
                logger.warning(f"Unknown config parameter: {key}")
    
    def get_cost_projection(self, days_ahead: int = 30) -> Dict[str, Any]:
        """Project future costs based on current usage patterns."""
        current_state = self._get_current_system_state()
        daily_cost = current_state['daily_cost']
        
        # Simple linear projection (could be enhanced with ML)
        projected_daily_cost = daily_cost
        projected_monthly_cost = projected_daily_cost * days_ahead
        
        # Calculate budget utilization
        daily_budget_utilization = (daily_cost / self.cost_budget.daily_limit_usd) * 100
        monthly_budget_utilization = (projected_monthly_cost / self.cost_budget.monthly_limit_usd) * 100
        
        # Generate alerts
        alerts = []
        if daily_budget_utilization > self.cost_budget.alert_threshold_percent:
            alerts.append({
                'type': 'daily_budget_alert',
                'message': f"Daily budget {daily_budget_utilization:.1f}% utilized",
                'severity': 'warning' if daily_budget_utilization < 100 else 'critical'
            })
        
        if monthly_budget_utilization > self.cost_budget.alert_threshold_percent:
            alerts.append({
                'type': 'monthly_budget_alert',
                'message': f"Monthly budget {monthly_budget_utilization:.1f}% utilized",
                'severity': 'warning' if monthly_budget_utilization < 100 else 'critical'
            })
        
        return {
            'projection_days': days_ahead,
            'current_daily_cost': daily_cost,
            'projected_daily_cost': projected_daily_cost,
            'projected_monthly_cost': projected_monthly_cost,
            'budget_utilization': {
                'daily_percent': daily_budget_utilization,
                'monthly_percent': monthly_budget_utilization
            },
            'budget_limits': {
                'daily_limit': self.cost_budget.daily_limit_usd,
                'monthly_limit': self.cost_budget.monthly_limit_usd
            },
            'alerts': alerts,
            'recommendations': self._generate_cost_recommendations(
                daily_cost, projected_monthly_cost
            )
        }
    
    def _generate_cost_recommendations(self, daily_cost: float, monthly_cost: float) -> List[str]:
        """Generate cost optimization recommendations."""
        recommendations = []
        
        if daily_cost > self.cost_budget.daily_limit_usd * 0.8:
            recommendations.append("Consider increasing cache TTL to reduce API calls")
            recommendations.append("Use free APIs (IMD, USGS) during non-peak hours")
            recommendations.append("Implement request batching where possible")
        
        if monthly_cost > self.cost_budget.monthly_limit_usd * 0.8:
            recommendations.append("Review API usage patterns for optimization opportunities")
            recommendations.append("Consider upgrading to higher-tier API plans with better rates")
            recommendations.append("Implement more aggressive caching strategies")
        
        return recommendations


# Global API optimizer instance
_api_optimizer: Optional[APIOptimizer] = None


def get_api_optimizer() -> APIOptimizer:
    """Get the global API optimizer instance."""
    global _api_optimizer
    if _api_optimizer is None:
        _api_optimizer = APIOptimizer()
    return _api_optimizer


def optimized_api_call(data_type: str, available_sources: List[str], 
                      strategy: Optional[OptimizationStrategy] = None):
    """
    Decorator for optimized API calls.
    
    Args:
        data_type: Type of data being requested
        available_sources: List of available API sources
        strategy: Optimization strategy to use
    """
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            optimizer = get_api_optimizer()
            
            # Get optimization decision
            decision = optimizer.optimize_api_selection(
                data_type=data_type,
                available_sources=available_sources,
                strategy=strategy
            )
            
            # Add selected source to kwargs
            kwargs['selected_source'] = decision.selected_source
            kwargs['optimization_decision'] = decision
            
            # Execute with fallback logic
            for source in [decision.selected_source] + decision.fallback_plan:
                try:
                    start_time = time.time()
                    result = await func(*args, **kwargs, source=source)
                    end_time = time.time()
                    
                    # Update circuit breaker on success
                    optimizer.update_circuit_breaker(
                        source, True, (end_time - start_time) * 1000
                    )
                    
                    return result
                    
                except Exception as e:
                    # Update circuit breaker on failure
                    optimizer.update_circuit_breaker(source, False, 0)
                    
                    # Try next source in fallback plan
                    if source != decision.fallback_plan[-1]:  # Not the last option
                        logger.warning(f"API call failed for {source}, trying fallback: {e}")
                        continue
                    else:
                        # All sources failed
                        raise
            
            # This should not be reached
            raise RuntimeError("All API sources failed")
        
        def sync_wrapper(*args, **kwargs):
            # For sync functions, just add optimization decision
            optimizer = get_api_optimizer()
            decision = optimizer.optimize_api_selection(
                data_type=data_type,
                available_sources=available_sources,
                strategy=strategy
            )
            
            kwargs['selected_source'] = decision.selected_source
            kwargs['optimization_decision'] = decision
            
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator