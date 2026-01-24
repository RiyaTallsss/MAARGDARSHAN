"""
AI integration module for rural infrastructure planning.

This module provides AI-powered analysis capabilities including route explanations,
alternative comparisons, and risk-based recommendations using AWS Bedrock and
foundation models like Claude.
"""

from .bedrock_client import (
    Bedrock_Client,
    AIExplanation,
    RouteComparison,
    MitigationRecommendation
)

__all__ = [
    'Bedrock_Client',
    'AIExplanation',
    'RouteComparison',
    'MitigationRecommendation'
]