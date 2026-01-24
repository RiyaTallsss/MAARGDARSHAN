"""
Comprehensive input validation and API error handling.

This module provides validation utilities for coordinates, API responses,
network connectivity, and mixed API/local data scenarios with geographic
bounds checking and error detection.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
import re
import json
from dataclasses import dataclass
import aiohttp
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from ..data.api_client import Coordinate, BoundingBox
from ..config.settings import config

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Validation error details."""
    field: str
    value: Any
    error_type: str
    message: str
    severity: str = "error"  # error, warning, info
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'field': self.field,
            'value': str(self.value),
            'error_type': self.error_type,
            'message': self.message,
            'severity': self.severity
        }


@dataclass
class ValidationResult:
    """Validation result with errors and warnings."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    
    def add_error(self, field: str, value: Any, error_type: str, message: str):
        """Add validation error."""
        self.errors.append(ValidationError(field, value, error_type, message, "error"))
        self.is_valid = False
    
    def add_warning(self, field: str, value: Any, error_type: str, message: str):
        """Add validation warning."""
        self.warnings.append(ValidationError(field, value, error_type, message, "warning"))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'is_valid': self.is_valid,
            'errors': [error.to_dict() for error in self.errors],
            'warnings': [warning.to_dict() for warning in self.warnings],
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings)
        }


class InputValidator:
    """
    Comprehensive input validation for rural infrastructure planning.
    
    This class provides validation for coordinates, routing parameters,
    API responses, and data integrity with geographic bounds checking
    and Uttarakhand-specific validation rules.
    """
    
    def __init__(self):
        """Initialize Input Validator."""
        # Uttarakhand geographic bounds
        self.uttarakhand_bounds = BoundingBox(
            north=31.5,   # Northern boundary
            south=28.5,   # Southern boundary  
            east=81.0,    # Eastern boundary
            west=77.5     # Western boundary
        )
        
        # India geographic bounds (broader validation)
        self.india_bounds = BoundingBox(
            north=37.6,   # Kashmir
            south=6.4,    # Kanyakumari
            east=97.25,   # Arunachal Pradesh
            west=68.7     # Gujarat
        )
        
        logger.info("Initialized InputValidator with Uttarakhand-specific bounds")
    
    def validate_coordinate(self, 
                          coordinate: Union[Coordinate, Dict[str, Any]], 
                          strict_bounds: bool = False) -> ValidationResult:
        """
        Validate coordinate with geographic bounds checking.
        
        Args:
            coordinate: Coordinate to validate
            strict_bounds: Use strict Uttarakhand bounds vs broader India bounds
            
        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        try:
            # Convert dict to Coordinate if needed
            if isinstance(coordinate, dict):
                lat = coordinate.get('latitude')
                lon = coordinate.get('longitude')
                elev = coordinate.get('elevation')
            else:
                lat = coordinate.latitude
                lon = coordinate.longitude
                elev = coordinate.elevation
            
            # Validate latitude
            if lat is None:
                result.add_error('latitude', lat, 'missing_value', 'Latitude is required')
            elif not isinstance(lat, (int, float)):
                result.add_error('latitude', lat, 'invalid_type', 'Latitude must be a number')
            elif lat < -90 or lat > 90:
                result.add_error('latitude', lat, 'out_of_range', 'Latitude must be between -90 and 90 degrees')
            
            # Validate longitude
            if lon is None:
                result.add_error('longitude', lon, 'missing_value', 'Longitude is required')
            elif not isinstance(lon, (int, float)):
                result.add_error('longitude', lon, 'invalid_type', 'Longitude must be a number')
            elif lon < -180 or lon > 180:
                result.add_error('longitude', lon, 'out_of_range', 'Longitude must be between -180 and 180 degrees')
            
            # Validate elevation if provided
            if elev is not None:
                if not isinstance(elev, (int, float)):
                    result.add_error('elevation', elev, 'invalid_type', 'Elevation must be a number')
                elif elev < -500 or elev > 9000:  # Reasonable bounds for Uttarakhand
                    result.add_warning('elevation', elev, 'unusual_value', 
                                     'Elevation outside typical range for Uttarakhand (-500m to 9000m)')
            
            # Geographic bounds checking
            if result.is_valid and lat is not None and lon is not None:
                bounds = self.uttarakhand_bounds if strict_bounds else self.india_bounds
                region_name = "Uttarakhand" if strict_bounds else "India"
                
                if not self._is_within_bounds(lat, lon, bounds):
                    if strict_bounds:
                        result.add_error('coordinate', f"{lat},{lon}", 'out_of_bounds', 
                                       f'Coordinate is outside {region_name} bounds')
                    else:
                        result.add_warning('coordinate', f"{lat},{lon}", 'out_of_bounds',
                                         f'Coordinate is outside {region_name} bounds')
                
                # Additional validation for Uttarakhand context
                if strict_bounds and self._is_within_bounds(lat, lon, self.uttarakhand_bounds):
                    # Check if coordinate is in a reasonable location for infrastructure
                    if elev and elev > 6000:
                        result.add_warning('elevation', elev, 'extreme_altitude',
                                         'Very high altitude may pose significant construction challenges')
                    
                    # Check for coordinates in protected areas (simplified)
                    if self._is_in_protected_area(lat, lon):
                        result.add_warning('coordinate', f"{lat},{lon}", 'protected_area',
                                         'Coordinate may be in or near a protected area')
            
            return result
            
        except Exception as e:
            result.add_error('coordinate', str(coordinate), 'validation_error', f'Validation failed: {str(e)}')
            return result
    
    def validate_bounding_box(self, bounds: Union[BoundingBox, Dict[str, Any]]) -> ValidationResult:
        """Validate bounding box parameters."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        try:
            # Convert dict to BoundingBox if needed
            if isinstance(bounds, dict):
                north = bounds.get('north')
                south = bounds.get('south')
                east = bounds.get('east')
                west = bounds.get('west')
            else:
                north = bounds.north
                south = bounds.south
                east = bounds.east
                west = bounds.west
            
            # Validate individual bounds
            for bound_name, bound_value in [('north', north), ('south', south), ('east', east), ('west', west)]:
                if bound_value is None:
                    result.add_error(bound_name, bound_value, 'missing_value', f'{bound_name.title()} bound is required')
                elif not isinstance(bound_value, (int, float)):
                    result.add_error(bound_name, bound_value, 'invalid_type', f'{bound_name.title()} bound must be a number')
            
            # Validate bound relationships
            if result.is_valid:
                if north <= south:
                    result.add_error('bounds', f"north={north}, south={south}", 'invalid_bounds',
                                   'North bound must be greater than south bound')
                
                if east <= west:
                    result.add_error('bounds', f"east={east}, west={west}", 'invalid_bounds',
                                   'East bound must be greater than west bound')
                
                # Check if bounds are reasonable size
                lat_span = north - south
                lon_span = east - west
                
                if lat_span > 10 or lon_span > 10:  # Very large area
                    result.add_warning('bounds', f"lat_span={lat_span:.2f}, lon_span={lon_span:.2f}",
                                     'large_area', 'Bounding box covers a very large area')
                elif lat_span < 0.001 or lon_span < 0.001:  # Very small area
                    result.add_warning('bounds', f"lat_span={lat_span:.6f}, lon_span={lon_span:.6f}",
                                     'small_area', 'Bounding box covers a very small area')
            
            return result
            
        except Exception as e:
            result.add_error('bounds', str(bounds), 'validation_error', f'Validation failed: {str(e)}')
            return result
    
    def validate_route_parameters(self, parameters: Dict[str, Any]) -> ValidationResult:
        """Validate route generation parameters."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        try:
            # Validate start coordinate
            if 'start' in parameters:
                start_result = self.validate_coordinate(parameters['start'], strict_bounds=True)
                result.errors.extend(start_result.errors)
                result.warnings.extend(start_result.warnings)
                if not start_result.is_valid:
                    result.is_valid = False
            else:
                result.add_error('start', None, 'missing_value', 'Start coordinate is required')
            
            # Validate end coordinate
            if 'end' in parameters:
                end_result = self.validate_coordinate(parameters['end'], strict_bounds=True)
                result.errors.extend(end_result.errors)
                result.warnings.extend(end_result.warnings)
                if not end_result.is_valid:
                    result.is_valid = False
            else:
                result.add_error('end', None, 'missing_value', 'End coordinate is required')
            
            # Validate constraints if provided
            if 'constraints' in parameters and parameters['constraints']:
                constraints_result = self._validate_route_constraints(parameters['constraints'])
                result.errors.extend(constraints_result.errors)
                result.warnings.extend(constraints_result.warnings)
                if not constraints_result.is_valid:
                    result.is_valid = False
            
            # Validate num_alternatives
            if 'num_alternatives' in parameters:
                num_alt = parameters['num_alternatives']
                if not isinstance(num_alt, int):
                    result.add_error('num_alternatives', num_alt, 'invalid_type', 'Number of alternatives must be an integer')
                elif num_alt < 1 or num_alt > 10:
                    result.add_error('num_alternatives', num_alt, 'out_of_range', 'Number of alternatives must be between 1 and 10')
            
            # Check distance between start and end
            if result.is_valid and 'start' in parameters and 'end' in parameters:
                distance = self._calculate_distance(parameters['start'], parameters['end'])
                if distance > 200:  # Very long route
                    result.add_warning('route_distance', f"{distance:.1f}km", 'long_route',
                                     'Route distance is very long, may require multiple construction phases')
                elif distance < 0.1:  # Very short route
                    result.add_warning('route_distance', f"{distance:.3f}km", 'short_route',
                                     'Route distance is very short')
            
            return result
            
        except Exception as e:
            result.add_error('parameters', str(parameters), 'validation_error', f'Parameter validation failed: {str(e)}')
            return result
    
    def _validate_route_constraints(self, constraints: Dict[str, Any]) -> ValidationResult:
        """Validate route constraints."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Validate max_slope_degrees
        if 'max_slope_degrees' in constraints:
            slope = constraints['max_slope_degrees']
            if not isinstance(slope, (int, float)):
                result.add_error('max_slope_degrees', slope, 'invalid_type', 'Max slope must be a number')
            elif slope < 0 or slope > 90:
                result.add_error('max_slope_degrees', slope, 'out_of_range', 'Max slope must be between 0 and 90 degrees')
            elif slope > 45:
                result.add_warning('max_slope_degrees', slope, 'extreme_value', 'Very steep slope limit may be impractical')
        
        # Validate budget_limit
        if 'budget_limit' in constraints and constraints['budget_limit'] is not None:
            budget = constraints['budget_limit']
            if not isinstance(budget, (int, float)):
                result.add_error('budget_limit', budget, 'invalid_type', 'Budget limit must be a number')
            elif budget <= 0:
                result.add_error('budget_limit', budget, 'invalid_value', 'Budget limit must be positive')
            elif budget < 100000:
                result.add_warning('budget_limit', budget, 'low_budget', 'Budget may be insufficient for rural road construction')
        
        # Validate timeline_limit
        if 'timeline_limit' in constraints and constraints['timeline_limit'] is not None:
            timeline = constraints['timeline_limit']
            if not isinstance(timeline, int):
                result.add_error('timeline_limit', timeline, 'invalid_type', 'Timeline limit must be an integer')
            elif timeline <= 0:
                result.add_error('timeline_limit', timeline, 'invalid_value', 'Timeline limit must be positive')
            elif timeline < 30:
                result.add_warning('timeline_limit', timeline, 'short_timeline', 'Timeline may be too short for construction')
        
        return result
    
    def _is_within_bounds(self, lat: float, lon: float, bounds: BoundingBox) -> bool:
        """Check if coordinate is within bounding box."""
        return (bounds.south <= lat <= bounds.north and 
                bounds.west <= lon <= bounds.east)
    
    def _is_in_protected_area(self, lat: float, lon: float) -> bool:
        """Check if coordinate is in a protected area (simplified)."""
        # Simplified check for major protected areas in Uttarakhand
        protected_areas = [
            # Nanda Devi National Park
            {'north': 30.5, 'south': 30.2, 'east': 79.9, 'west': 79.6},
            # Valley of Flowers National Park
            {'north': 30.8, 'south': 30.6, 'east': 79.7, 'west': 79.5},
            # Jim Corbett National Park
            {'north': 29.7, 'south': 29.3, 'east': 79.1, 'west': 78.7}
        ]
        
        for area in protected_areas:
            if (area['south'] <= lat <= area['north'] and 
                area['west'] <= lon <= area['east']):
                return True
        
        return False
    
    def _calculate_distance(self, coord1: Union[Coordinate, Dict], coord2: Union[Coordinate, Dict]) -> float:
        """Calculate distance between two coordinates in kilometers."""
        import math
        
        # Extract coordinates
        if isinstance(coord1, dict):
            lat1, lon1 = coord1['latitude'], coord1['longitude']
        else:
            lat1, lon1 = coord1.latitude, coord1.longitude
            
        if isinstance(coord2, dict):
            lat2, lon2 = coord2['latitude'], coord2['longitude']
        else:
            lat2, lon2 = coord2.latitude, coord2.longitude
        
        # Haversine formula
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c


class APIResponseValidator:
    """
    API response validation and error detection.
    
    This class validates API responses for completeness, format correctness,
    and data integrity with automatic fallback detection.
    """
    
    def __init__(self):
        """Initialize API Response Validator."""
        logger.info("Initialized APIResponseValidator")
    
    def validate_elevation_response(self, response: Dict[str, Any]) -> ValidationResult:
        """Validate elevation API response."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        try:
            # Check required fields
            required_fields = ['elevation_data', 'bounds', 'resolution']
            for field in required_fields:
                if field not in response:
                    result.add_error(field, None, 'missing_field', f'Required field {field} is missing')
            
            # Validate elevation data
            if 'elevation_data' in response:
                elev_data = response['elevation_data']
                if not isinstance(elev_data, (list, dict)):
                    result.add_error('elevation_data', type(elev_data), 'invalid_type', 
                                   'Elevation data must be a list or dictionary')
                elif isinstance(elev_data, list) and len(elev_data) == 0:
                    result.add_error('elevation_data', len(elev_data), 'empty_data', 
                                   'Elevation data is empty')
            
            # Validate bounds
            if 'bounds' in response:
                bounds_result = InputValidator().validate_bounding_box(response['bounds'])
                result.errors.extend(bounds_result.errors)
                result.warnings.extend(bounds_result.warnings)
                if not bounds_result.is_valid:
                    result.is_valid = False
            
            # Check data freshness
            if 'timestamp' in response:
                timestamp = response['timestamp']
                try:
                    if isinstance(timestamp, str):
                        data_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    else:
                        data_time = timestamp
                    
                    age_hours = (datetime.now() - data_time).total_seconds() / 3600
                    if age_hours > 168:  # More than a week old
                        result.add_warning('timestamp', age_hours, 'stale_data', 
                                         f'Data is {age_hours:.1f} hours old')
                except Exception:
                    result.add_warning('timestamp', timestamp, 'invalid_timestamp', 
                                     'Could not parse timestamp')
            
            return result
            
        except Exception as e:
            result.add_error('response', str(response), 'validation_error', 
                           f'Response validation failed: {str(e)}')
            return result
    
    def validate_weather_response(self, response: Dict[str, Any]) -> ValidationResult:
        """Validate weather API response."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        try:
            # Check for weather data
            if 'weather' not in response and 'current' not in response:
                result.add_error('weather_data', None, 'missing_data', 'No weather data found in response')
                return result
            
            weather_data = response.get('weather', response.get('current', {}))
            
            # Validate temperature
            if 'temperature' in weather_data:
                temp = weather_data['temperature']
                if not isinstance(temp, (int, float)):
                    result.add_error('temperature', temp, 'invalid_type', 'Temperature must be a number')
                elif temp < -50 or temp > 60:  # Extreme temperatures
                    result.add_warning('temperature', temp, 'extreme_value', 
                                     f'Temperature {temp}°C is extreme for Uttarakhand')
            
            # Validate precipitation
            if 'precipitation' in weather_data:
                precip = weather_data['precipitation']
                if not isinstance(precip, (int, float)):
                    result.add_error('precipitation', precip, 'invalid_type', 'Precipitation must be a number')
                elif precip < 0:
                    result.add_error('precipitation', precip, 'invalid_value', 'Precipitation cannot be negative')
                elif precip > 500:  # Very heavy rainfall
                    result.add_warning('precipitation', precip, 'extreme_value', 
                                     f'Precipitation {precip}mm is extremely high')
            
            return result
            
        except Exception as e:
            result.add_error('response', str(response), 'validation_error', 
                           f'Weather response validation failed: {str(e)}')
            return result
    
    def validate_osm_response(self, response: Dict[str, Any]) -> ValidationResult:
        """Validate OpenStreetMap API response."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        try:
            # Check for elements
            if 'elements' not in response:
                result.add_error('elements', None, 'missing_field', 'No elements found in OSM response')
                return result
            
            elements = response['elements']
            if not isinstance(elements, list):
                result.add_error('elements', type(elements), 'invalid_type', 'Elements must be a list')
                return result
            
            if len(elements) == 0:
                result.add_warning('elements', len(elements), 'empty_data', 'No OSM elements found')
                return result
            
            # Validate element structure
            for i, element in enumerate(elements[:10]):  # Check first 10 elements
                if 'type' not in element:
                    result.add_error(f'element_{i}', element, 'missing_type', 'Element missing type field')
                
                if element.get('type') in ['node', 'way'] and 'id' not in element:
                    result.add_error(f'element_{i}', element, 'missing_id', 'Element missing ID field')
                
                if element.get('type') == 'node':
                    if 'lat' not in element or 'lon' not in element:
                        result.add_error(f'element_{i}', element, 'missing_coordinates', 
                                       'Node element missing coordinates')
            
            return result
            
        except Exception as e:
            result.add_error('response', str(response), 'validation_error', 
                           f'OSM response validation failed: {str(e)}')
            return result


class NetworkValidator:
    """
    Network connectivity and API availability validation.
    
    This class provides network connectivity testing, API endpoint validation,
    and automatic fallback detection with rate limiting awareness.
    """
    
    def __init__(self):
        """Initialize Network Validator."""
        self.timeout = 10  # seconds
        logger.info("Initialized NetworkValidator")
    
    async def check_api_connectivity(self, api_endpoints: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """
        Check connectivity to multiple API endpoints.
        
        Args:
            api_endpoints: Dictionary of API name to endpoint URL
            
        Returns:
            Dictionary with connectivity status for each API
        """
        results = {}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            for api_name, endpoint in api_endpoints.items():
                try:
                    start_time = datetime.now()
                    async with session.get(endpoint) as response:
                        end_time = datetime.now()
                        response_time = (end_time - start_time).total_seconds() * 1000
                        
                        results[api_name] = {
                            'status': 'available',
                            'response_code': response.status,
                            'response_time_ms': response_time,
                            'error': None,
                            'rate_limited': response.status == 429
                        }
                        
                except asyncio.TimeoutError:
                    results[api_name] = {
                        'status': 'timeout',
                        'response_code': None,
                        'response_time_ms': None,
                        'error': 'Request timeout',
                        'rate_limited': False
                    }
                    
                except Exception as e:
                    results[api_name] = {
                        'status': 'unavailable',
                        'response_code': None,
                        'response_time_ms': None,
                        'error': str(e),
                        'rate_limited': False
                    }
        
        return results
    
    def validate_mixed_data_scenario(self, 
                                   api_data: Optional[Dict[str, Any]], 
                                   local_data: Optional[Dict[str, Any]],
                                   data_type: str) -> ValidationResult:
        """
        Validate mixed API and local data scenarios.
        
        Args:
            api_data: Data from API sources
            local_data: Data from local sources
            data_type: Type of data being validated
            
        Returns:
            ValidationResult with mixed data validation
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        try:
            # Check if we have any data at all
            if not api_data and not local_data:
                result.add_error('data', None, 'no_data', f'No {data_type} data available from any source')
                return result
            
            # Validate API data if available
            if api_data:
                api_result = self._validate_data_structure(api_data, f'api_{data_type}')
                result.errors.extend(api_result.errors)
                result.warnings.extend(api_result.warnings)
                if not api_result.is_valid:
                    result.is_valid = False
            
            # Validate local data if available
            if local_data:
                local_result = self._validate_data_structure(local_data, f'local_{data_type}')
                result.errors.extend(local_result.errors)
                result.warnings.extend(local_result.warnings)
                if not local_result.is_valid and not api_data:  # Only fail if no API data
                    result.is_valid = False
            
            # Check data consistency if both sources available
            if api_data and local_data:
                consistency_result = self._check_data_consistency(api_data, local_data, data_type)
                result.warnings.extend(consistency_result.warnings)
            
            # Determine data source priority
            if api_data and local_data:
                result.add_warning('data_sources', 'mixed', 'multiple_sources', 
                                 f'Both API and local {data_type} data available - using API data as primary')
            elif api_data:
                result.add_warning('data_sources', 'api_only', 'single_source', 
                                 f'Only API {data_type} data available')
            elif local_data:
                result.add_warning('data_sources', 'local_only', 'single_source', 
                                 f'Only local {data_type} data available')
            
            return result
            
        except Exception as e:
            result.add_error('validation', str(e), 'validation_error', 
                           f'Mixed data validation failed: {str(e)}')
            return result
    
    def _validate_data_structure(self, data: Dict[str, Any], data_source: str) -> ValidationResult:
        """Validate basic data structure."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if not isinstance(data, dict):
            result.add_error(data_source, type(data), 'invalid_type', 'Data must be a dictionary')
            return result
        
        if len(data) == 0:
            result.add_error(data_source, len(data), 'empty_data', 'Data dictionary is empty')
        
        return result
    
    def _check_data_consistency(self, api_data: Dict[str, Any], 
                              local_data: Dict[str, Any], 
                              data_type: str) -> ValidationResult:
        """Check consistency between API and local data."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Simple consistency checks
        common_keys = set(api_data.keys()) & set(local_data.keys())
        
        if len(common_keys) == 0:
            result.add_warning('consistency', 'no_common_keys', 'data_mismatch',
                             f'No common fields between API and local {data_type} data')
        
        # Check for significant differences in common numeric fields
        for key in common_keys:
            api_val = api_data[key]
            local_val = local_data[key]
            
            if isinstance(api_val, (int, float)) and isinstance(local_val, (int, float)):
                if abs(api_val - local_val) / max(abs(api_val), abs(local_val), 1) > 0.5:  # 50% difference
                    result.add_warning('consistency', f'{key}: API={api_val}, Local={local_val}',
                                     'significant_difference', 
                                     f'Significant difference in {key} between API and local data')
        
        return result