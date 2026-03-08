"""
Road Renderer

Converts road data to frontend-compatible formats (GeoJSON).
"""

from typing import List
from .models import RoadNetwork, Route


class RoadRenderer:
    """Renderer for road networks and routes"""
    
    def to_geojson(self, network: RoadNetwork, max_roads: int = 1000) -> dict:
        """
        Convert road network to GeoJSON
        
        Args:
            network: RoadNetwork to convert
            max_roads: Maximum number of roads to include (for size management)
            
        Returns:
            GeoJSON FeatureCollection
        """
        features = []
        
        # Convert edges to LineString features
        for i, (edge_id, edge) in enumerate(network.edges.items()):
            if i >= max_roads:
                break
            
            # Create LineString geometry
            coordinates = [[lon, lat] for lon, lat in edge.coordinates]
            
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': coordinates
                },
                'properties': {
                    'id': edge.id,
                    'name': edge.name,
                    'highway_type': edge.highway_type,
                    'surface': edge.surface,
                    'distance_m': edge.distance_m
                }
            }
            
            features.append(feature)
        
        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }
        
        return geojson
    
    def format_route(self, route: Route) -> dict:
        """
        Format route for frontend display
        
        Args:
            route: Route to format
            
        Returns:
            Formatted route dictionary
        """
        return route.to_dict()
    
    def create_layer_config(self, routes: List[Route]) -> dict:
        """
        Create Leaflet layer configuration
        
        Args:
            routes: List of routes
            
        Returns:
            Layer configuration dictionary
        """
        return {
            'routes': [self.format_route(r) for r in routes],
            'colors': {
                'shortest': '#3b82f6',  # blue
                'safest': '#10b981',    # green
                'budget': '#f97316',    # orange
                'social': '#a855f7'     # purple
            }
        }
