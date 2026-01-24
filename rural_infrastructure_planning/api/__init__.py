"""
REST API module for rural infrastructure planning.

This module provides FastAPI-based REST endpoints for route generation,
analysis, comparison, and data source status monitoring with CORS support
and comprehensive error handling.
"""

from .main import app

__all__ = ['app']