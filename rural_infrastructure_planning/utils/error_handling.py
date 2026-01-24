"""
Comprehensive error handling and graceful fallback mechanisms.

This module provides error handling utilities, graceful degradation,
user-friendly error messages, and automatic fallback strategies for
API failures and network connectivity issues.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import traceback
import functools

from .validation import ValidationResult, ValidationError

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    VALIDATION = "validation"
    NETWORK = "network"
    API = "api"
    DATA = "data"
    PROCESSING = "processing"
    SYSTEM = "system"


@dataclass
class ErrorContext:
    """Context information for errors."""
    operation: str
    component: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class ErrorDetails:
    """Comprehensive error details."""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    user_message: str
    technical_details: str
    context: ErrorContext
    stack_trace: Optional[str] = None
    suggested_actions: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'error_id': self.error_id,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity.value,
            'category': self.category.value,
            'message': self.message,
            'user_message': self.user_message,
            'technical_details': self.technical_details,
            'context': {
                'operation': self.context.operation,
                'component': self.context.component,
                'user_id': self.context.user_id,
                'request_id': self.context.request_id,
                'additional_data': self.context.additional_data
            },
            'stack_trace': self.stack_trace,
            'suggested_actions': self.suggested_actions or []
        }


class ErrorHandler:
    """
    Comprehensive error handling with graceful degradation.
    
    This class provides centralized error handling, user-friendly error
    messages, automatic fallback mechanisms, and detailed error logging
    for the rural infrastructure planning system.
    """
    
    def __init__(self):
        """Initialize Error Handler."""
        self.error_count = 0
        self.error_history = []
        self.fallback_strategies = {}
        
        logger.info("Initialized ErrorHandler with graceful degradation support")
    
    def handle_validation_error(self, 
                               validation_result: ValidationResult,
                               context: ErrorContext) -> ErrorDetails:
        """Handle validation errors with user-friendly messages."""
        try:
            error_id = f"VAL_{self.error_count:06d}"
            self.error_count += 1
            
            # Determine severity based on validation result
            if validation_result.errors:
                severity = ErrorSeverity.ERROR
                primary_error = validation_result.errors[0]
                message = f"Validation failed: {primary_error.message}"
                user_message = self._create_user_friendly_validation_message(validation_result)
            else:
                severity = ErrorSeverity.WARNING
                primary_warning = validation_result.warnings[0] if validation_result.warnings else None
                message = f"Validation warning: {primary_warning.message if primary_warning else 'Unknown warning'}"
                user_message = "Input validation completed with warnings. Please review the data."
            
            # Create error details
            error_details = ErrorDetails(
                error_id=error_id,
                timestamp=datetime.now(),
                severity=severity,
                category=ErrorCategory.VALIDATION,
                message=message,
                user_message=user_message,
                technical_details=self._format_validation_details(validation_result),
                context=context,
                suggested_actions=self._get_validation_suggestions(validation_result)
            )
            
            # Log error
            self._log_error(error_details)
            
            return error_details
            
        except Exception as e:
            logger.error(f"Error handling validation error: {e}")
            return self._create_fallback_error(context, str(e))
    
    def handle_api_error(self, 
                        api_name: str,
                        error: Exception,
                        context: ErrorContext,
                        fallback_available: bool = False) -> ErrorDetails:
        """Handle API errors with fallback information."""
        try:
            error_id = f"API_{self.error_count:06d}"
            self.error_count += 1
            
            # Determine error type and severity
            if "timeout" in str(error).lower():
                severity = ErrorSeverity.WARNING if fallback_available else ErrorSeverity.ERROR
                message = f"API timeout: {api_name}"
                user_message = "The external data service is responding slowly. " + \
                              ("Using local data instead." if fallback_available else "Please try again later.")
            elif "connection" in str(error).lower():
                severity = ErrorSeverity.WARNING if fallback_available else ErrorSeverity.ERROR
                message = f"API connection failed: {api_name}"
                user_message = "Cannot connect to external data service. " + \
                              ("Using local data instead." if fallback_available else "Please check your internet connection.")
            elif "rate limit" in str(error).lower() or "429" in str(error):
                severity = ErrorSeverity.WARNING
                message = f"API rate limit exceeded: {api_name}"
                user_message = "External data service rate limit reached. Using cached or local data."
            else:
                severity = ErrorSeverity.ERROR if not fallback_available else ErrorSeverity.WARNING
                message = f"API error: {api_name} - {str(error)}"
                user_message = "External data service error occurred. " + \
                              ("Using local data instead." if fallback_available else "Please try again later.")
            
            # Create error details
            error_details = ErrorDetails(
                error_id=error_id,
                timestamp=datetime.now(),
                severity=severity,
                category=ErrorCategory.API,
                message=message,
                user_message=user_message,
                technical_details=f"API: {api_name}, Error: {str(error)}, Type: {type(error).__name__}",
                context=context,
                stack_trace=traceback.format_exc(),
                suggested_actions=self._get_api_error_suggestions(api_name, error, fallback_available)
            )
            
            # Log error
            self._log_error(error_details)
            
            return error_details
            
        except Exception as e:
            logger.error(f"Error handling API error: {e}")
            return self._create_fallback_error(context, str(e))
    
    def handle_network_error(self, 
                           error: Exception,
                           context: ErrorContext,
                           offline_mode_available: bool = False) -> ErrorDetails:
        """Handle network connectivity errors."""
        try:
            error_id = f"NET_{self.error_count:06d}"
            self.error_count += 1
            
            severity = ErrorSeverity.WARNING if offline_mode_available else ErrorSeverity.ERROR
            message = f"Network connectivity error: {str(error)}"
            user_message = "Network connectivity issue detected. " + \
                          ("Operating in offline mode with local data." if offline_mode_available else 
                           "Please check your internet connection and try again.")
            
            error_details = ErrorDetails(
                error_id=error_id,
                timestamp=datetime.now(),
                severity=severity,
                category=ErrorCategory.NETWORK,
                message=message,
                user_message=user_message,
                technical_details=f"Network error: {str(error)}, Type: {type(error).__name__}",
                context=context,
                stack_trace=traceback.format_exc(),
                suggested_actions=self._get_network_error_suggestions(offline_mode_available)
            )
            
            self._log_error(error_details)
            return error_details
            
        except Exception as e:
            logger.error(f"Error handling network error: {e}")
            return self._create_fallback_error(context, str(e))
    
    def handle_data_error(self, 
                         data_type: str,
                         error: Exception,
                         context: ErrorContext,
                         impact_level: str = "moderate") -> ErrorDetails:
        """Handle data processing and corruption errors."""
        try:
            error_id = f"DAT_{self.error_count:06d}"
            self.error_count += 1
            
            # Determine severity based on impact
            severity_map = {
                "low": ErrorSeverity.WARNING,
                "moderate": ErrorSeverity.ERROR,
                "high": ErrorSeverity.CRITICAL
            }
            severity = severity_map.get(impact_level, ErrorSeverity.ERROR)
            
            message = f"Data error in {data_type}: {str(error)}"
            user_message = self._create_data_error_message(data_type, impact_level)
            
            error_details = ErrorDetails(
                error_id=error_id,
                timestamp=datetime.now(),
                severity=severity,
                category=ErrorCategory.DATA,
                message=message,
                user_message=user_message,
                technical_details=f"Data type: {data_type}, Error: {str(error)}, Impact: {impact_level}",
                context=context,
                stack_trace=traceback.format_exc(),
                suggested_actions=self._get_data_error_suggestions(data_type, impact_level)
            )
            
            self._log_error(error_details)
            return error_details
            
        except Exception as e:
            logger.error(f"Error handling data error: {e}")
            return self._create_fallback_error(context, str(e))
    
    def _create_user_friendly_validation_message(self, validation_result: ValidationResult) -> str:
        """Create user-friendly validation error message."""
        if not validation_result.errors and not validation_result.warnings:
            return "Input validation completed successfully."
        
        messages = []
        
        if validation_result.errors:
            error_count = len(validation_result.errors)
            if error_count == 1:
                messages.append(f"There is 1 error in your input: {validation_result.errors[0].message}")
            else:
                messages.append(f"There are {error_count} errors in your input. Please check:")
                for error in validation_result.errors[:3]:  # Show first 3 errors
                    messages.append(f"• {error.message}")
                if error_count > 3:
                    messages.append(f"• ... and {error_count - 3} more errors")
        
        if validation_result.warnings:
            warning_count = len(validation_result.warnings)
            if warning_count == 1:
                messages.append(f"Note: {validation_result.warnings[0].message}")
            else:
                messages.append(f"Please note {warning_count} warnings about your input.")
        
        return " ".join(messages)
    
    def _format_validation_details(self, validation_result: ValidationResult) -> str:
        """Format validation details for technical logging."""
        details = []
        
        if validation_result.errors:
            details.append(f"Errors ({len(validation_result.errors)}):")
            for error in validation_result.errors:
                details.append(f"  - {error.field}: {error.error_type} - {error.message}")
        
        if validation_result.warnings:
            details.append(f"Warnings ({len(validation_result.warnings)}):")
            for warning in validation_result.warnings:
                details.append(f"  - {warning.field}: {warning.error_type} - {warning.message}")
        
        return "\n".join(details)
    
    def _get_validation_suggestions(self, validation_result: ValidationResult) -> List[str]:
        """Get suggestions for fixing validation errors."""
        suggestions = []
        
        for error in validation_result.errors:
            if error.error_type == "out_of_range":
                suggestions.append(f"Check that {error.field} is within the valid range")
            elif error.error_type == "missing_value":
                suggestions.append(f"Provide a value for {error.field}")
            elif error.error_type == "invalid_type":
                suggestions.append(f"Ensure {error.field} is the correct data type")
            elif error.error_type == "out_of_bounds":
                suggestions.append(f"Verify that coordinates are within the Uttarakhand region")
        
        if not suggestions:
            suggestions.append("Please review your input data and try again")
        
        return suggestions
    
    def _get_api_error_suggestions(self, api_name: str, error: Exception, fallback_available: bool) -> List[str]:
        """Get suggestions for API errors."""
        suggestions = []
        
        if "timeout" in str(error).lower():
            suggestions.append("Try again in a few moments")
            if fallback_available:
                suggestions.append("Local data is being used as fallback")
        elif "connection" in str(error).lower():
            suggestions.append("Check your internet connection")
            suggestions.append("Verify that external services are accessible")
        elif "rate limit" in str(error).lower():
            suggestions.append("Wait a few minutes before making more requests")
            suggestions.append("Consider using cached data if available")
        else:
            suggestions.append(f"Check the status of {api_name} service")
            if fallback_available:
                suggestions.append("System will continue with local data")
        
        return suggestions
    
    def _get_network_error_suggestions(self, offline_mode_available: bool) -> List[str]:
        """Get suggestions for network errors."""
        suggestions = [
            "Check your internet connection",
            "Verify network settings and firewall configuration"
        ]
        
        if offline_mode_available:
            suggestions.extend([
                "System is operating in offline mode",
                "Some features may be limited without internet access"
            ])
        else:
            suggestions.append("Internet connection is required for this operation")
        
        return suggestions
    
    def _get_data_error_suggestions(self, data_type: str, impact_level: str) -> List[str]:
        """Get suggestions for data errors."""
        suggestions = []
        
        if impact_level == "high":
            suggestions.extend([
                f"Critical error in {data_type} data processing",
                "Contact system administrator",
                "Consider using alternative data sources"
            ])
        elif impact_level == "moderate":
            suggestions.extend([
                f"Data quality issue detected in {data_type}",
                "Results may be affected",
                "Consider refreshing data or using alternative sources"
            ])
        else:
            suggestions.extend([
                f"Minor data issue in {data_type}",
                "Processing can continue with reduced accuracy"
            ])
        
        return suggestions
    
    def _create_data_error_message(self, data_type: str, impact_level: str) -> str:
        """Create user-friendly data error message."""
        if impact_level == "high":
            return f"Critical data error in {data_type}. Operation cannot continue safely."
        elif impact_level == "moderate":
            return f"Data quality issue detected in {data_type}. Results may be less accurate."
        else:
            return f"Minor data issue in {data_type}. Processing continues with reduced precision."
    
    def _create_fallback_error(self, context: ErrorContext, error_message: str) -> ErrorDetails:
        """Create fallback error when error handling itself fails."""
        error_id = f"SYS_{self.error_count:06d}"
        self.error_count += 1
        
        return ErrorDetails(
            error_id=error_id,
            timestamp=datetime.now(),
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.SYSTEM,
            message=f"System error in error handling: {error_message}",
            user_message="An unexpected system error occurred. Please contact support.",
            technical_details=f"Error handling failure: {error_message}",
            context=context,
            suggested_actions=["Contact system administrator", "Try again later"]
        )
    
    def _log_error(self, error_details: ErrorDetails):
        """Log error details with appropriate level."""
        log_message = f"[{error_details.error_id}] {error_details.message}"
        
        if error_details.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, extra={'error_details': error_details.to_dict()})
        elif error_details.severity == ErrorSeverity.ERROR:
            logger.error(log_message, extra={'error_details': error_details.to_dict()})
        elif error_details.severity == ErrorSeverity.WARNING:
            logger.warning(log_message, extra={'error_details': error_details.to_dict()})
        else:
            logger.info(log_message, extra={'error_details': error_details.to_dict()})
        
        # Store in error history (keep last 100 errors)
        self.error_history.append(error_details)
        if len(self.error_history) > 100:
            self.error_history.pop(0)


def with_error_handling(error_handler: ErrorHandler, 
                       operation: str, 
                       component: str,
                       fallback_result: Any = None):
    """
    Decorator for automatic error handling.
    
    Args:
        error_handler: ErrorHandler instance
        operation: Operation name for context
        component: Component name for context
        fallback_result: Result to return on error
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            context = ErrorContext(operation=operation, component=component)
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_details = error_handler.handle_api_error("unknown", e, context)
                logger.error(f"Function {func.__name__} failed: {error_details.message}")
                return fallback_result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            context = ErrorContext(operation=operation, component=component)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_details = error_handler.handle_api_error("unknown", e, context)
                logger.error(f"Function {func.__name__} failed: {error_details.message}")
                return fallback_result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Global error handler instance
global_error_handler = ErrorHandler()