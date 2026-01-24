"""
Enhanced data export functionality for rural infrastructure planning.

This module provides comprehensive export capabilities including GeoJSON, KML,
Shapefile export, PDF report generation, and data provenance tracking with
API source information and freshness indicators.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pathlib import Path
import json
import tempfile
import zipfile
from io import BytesIO, StringIO

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
import folium
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

from ..routing.route_generator import RouteAlignment, RouteSegment
from ..risk.risk_assessor import CompositeRisk
from ..ai.bedrock_client import AIExplanation, RouteComparison
from ..data.api_client import DataFreshnessInfo

logger = logging.getLogger(__name__)


class DataExporter:
    """
    Enhanced data export functionality with comprehensive format support.
    
    This class provides export capabilities for route data, analysis results,
    and comparative studies with full data provenance tracking and API
    source transparency.
    
    Features:
    - Multi-format export (GeoJSON, KML, Shapefile, CSV, PDF)
    - PDF report generation with maps and analysis
    - Data provenance tracking including API sources and timestamps
    - Comparative analysis table export with freshness indicators
    - Export options for different data freshness levels
    """
    
    def __init__(self):
        """Initialize Data Exporter."""
        self.temp_dir = Path(tempfile.gettempdir()) / "rural_infrastructure_exports"
        self.temp_dir.mkdir(exist_ok=True)
        
        logger.info("Initialized DataExporter with enhanced format support")
    
    async def export_route_geojson(self, 
                                 route: RouteAlignment,
                                 include_segments: bool = True,
                                 include_metadata: bool = True) -> Dict[str, Any]:
        """
        Export route to GeoJSON format with comprehensive metadata.
        
        Args:
            route: Route alignment to export
            include_segments: Include individual route segments
            include_metadata: Include data source and freshness metadata
            
        Returns:
            GeoJSON dictionary with route data
        """
        try:
            logger.info(f"Exporting route {route.id} to GeoJSON format")
            
            # Create main route feature
            route_coordinates = [[wp.longitude, wp.latitude] for wp in route.waypoints]
            
            route_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": route_coordinates
                },
                "properties": {
                    "route_id": route.id,
                    "total_distance_km": route.total_distance,
                    "elevation_gain_m": route.elevation_gain,
                    "elevation_loss_m": route.elevation_loss,
                    "construction_cost_usd": route.estimated_cost,
                    "construction_days": route.estimated_duration,
                    "difficulty_score": route.construction_difficulty,
                    "risk_score": route.risk_score,
                    "algorithm_used": route.algorithm_used
                }
            }
            
            # Add data source information
            if include_metadata and route.data_sources:
                route_feature["properties"]["data_sources"] = route.data_sources
                
                if route.freshness_info:
                    route_feature["properties"]["data_freshness"] = {
                        "source_type": route.freshness_info.source_type,
                        "source_name": route.freshness_info.source_name,
                        "data_age_hours": route.freshness_info.data_age_hours,
                        "is_real_time": route.freshness_info.is_real_time,
                        "quality_score": route.freshness_info.quality_score,
                        "freshness_indicator": route.freshness_info.get_freshness_indicator()
                    }
            
            # Create GeoJSON structure
            geojson = {
                "type": "FeatureCollection",
                "features": [route_feature],
                "metadata": {
                    "export_timestamp": datetime.now().isoformat(),
                    "export_format": "GeoJSON",
                    "coordinate_system": "WGS84",
                    "data_provenance": {
                        "primary_sources": route.data_sources or [],
                        "processing_algorithm": route.algorithm_used,
                        "export_version": "1.0"
                    }
                }
            }
            
            # Add segment features if requested
            if include_segments and route.segments:
                for i, segment in enumerate(route.segments):
                    segment_feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [segment.start.longitude, segment.start.latitude],
                                [segment.end.longitude, segment.end.latitude]
                            ]
                        },
                        "properties": {
                            "segment_id": f"{route.id}_segment_{i}",
                            "parent_route": route.id,
                            "length_m": segment.length,
                            "slope_degrees": segment.slope_grade,
                            "terrain_type": segment.terrain_type,
                            "construction_cost_per_m": segment.construction_cost,
                            "difficulty_score": segment.construction_difficulty,
                            "risk_factors": segment.risk_factors
                        }
                    }
                    geojson["features"].append(segment_feature)
            
            logger.info(f"Generated GeoJSON with {len(geojson['features'])} features")
            
            return geojson
            
        except Exception as e:
            logger.error(f"GeoJSON export failed: {e}")
            raise RuntimeError(f"GeoJSON export failed: {e}") from e
    
    async def export_route_kml(self, 
                             route: RouteAlignment,
                             include_elevation: bool = True) -> str:
        """
        Export route to KML format for Google Earth visualization.
        
        Args:
            route: Route alignment to export
            include_elevation: Include elevation data in coordinates
            
        Returns:
            KML string content
        """
        try:
            logger.info(f"Exporting route {route.id} to KML format")
            
            # Build KML content
            kml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Rural Infrastructure Route: {route.id}</name>
    <description>Generated by Rural Infrastructure Planning System</description>
    
    <!-- Route Style -->
    <Style id="routeStyle">
      <LineStyle>
        <color>ff0000ff</color>
        <width>4</width>
      </LineStyle>
    </Style>
    
    <!-- Route Placemark -->
    <Placemark>
      <name>Route {route.id}</name>
      <description><![CDATA[
        <h3>Route Information</h3>
        <table>
          <tr><td>Distance:</td><td>{route.total_distance:.1f} km</td></tr>
          <tr><td>Elevation Gain:</td><td>{route.elevation_gain:.0f} m</td></tr>
          <tr><td>Construction Cost:</td><td>${route.estimated_cost:,.0f}</td></tr>
          <tr><td>Construction Duration:</td><td>{route.estimated_duration} days</td></tr>
          <tr><td>Difficulty Score:</td><td>{route.construction_difficulty:.1f}/100</td></tr>
          <tr><td>Risk Score:</td><td>{route.risk_score:.1f}/100</td></tr>
        </table>
        <p><strong>Data Sources:</strong> {', '.join(route.data_sources or ['Local data'])}</p>
      ]]></description>
      <styleUrl>#routeStyle</styleUrl>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>
'''
            
            # Add coordinates
            for waypoint in route.waypoints:
                if include_elevation and waypoint.elevation:
                    kml_content += f"          {waypoint.longitude},{waypoint.latitude},{waypoint.elevation}\n"
                else:
                    kml_content += f"          {waypoint.longitude},{waypoint.latitude},0\n"
            
            kml_content += '''        </coordinates>
      </LineString>
    </Placemark>
'''
            
            # Add waypoint markers
            for i, waypoint in enumerate(route.waypoints):
                if i == 0:
                    name = "Start Point"
                    icon = "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"
                elif i == len(route.waypoints) - 1:
                    name = "End Point"
                    icon = "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"
                else:
                    continue  # Skip intermediate waypoints for clarity
                
                kml_content += f'''    <Placemark>
      <name>{name}</name>
      <Point>
        <coordinates>{waypoint.longitude},{waypoint.latitude},{waypoint.elevation or 0}</coordinates>
      </Point>
      <Style>
        <IconStyle>
          <Icon>
            <href>{icon}</href>
          </Icon>
        </IconStyle>
      </Style>
    </Placemark>
'''
            
            kml_content += '''  </Document>
</kml>'''
            
            logger.info(f"Generated KML with route and waypoint data")
            
            return kml_content
            
        except Exception as e:
            logger.error(f"KML export failed: {e}")
            raise RuntimeError(f"KML export failed: {e}") from e
    
    async def export_route_shapefile(self, 
                                   routes: List[RouteAlignment],
                                   output_path: Optional[Path] = None) -> Path:
        """
        Export routes to Shapefile format using geopandas.
        
        Args:
            routes: List of route alignments to export
            output_path: Optional output path for shapefile
            
        Returns:
            Path to generated shapefile
        """
        try:
            logger.info(f"Exporting {len(routes)} routes to Shapefile format")
            
            if not output_path:
                output_path = self.temp_dir / f"routes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.shp"
            
            # Prepare data for GeoDataFrame
            route_data = []
            geometries = []
            
            for route in routes:
                # Create LineString geometry
                coordinates = [(wp.longitude, wp.latitude) for wp in route.waypoints]
                line_geom = LineString(coordinates)
                geometries.append(line_geom)
                
                # Prepare attribute data
                route_attrs = {
                    'route_id': route.id,
                    'distance_km': route.total_distance,
                    'elev_gain_m': route.elevation_gain,
                    'cost_usd': route.estimated_cost,
                    'duration_d': route.estimated_duration,
                    'difficulty': route.construction_difficulty,
                    'risk_score': route.risk_score,
                    'algorithm': route.algorithm_used[:50],  # Truncate for shapefile limits
                    'data_src': ','.join(route.data_sources[:3]) if route.data_sources else 'local'  # Limit length
                }
                
                # Add freshness information if available
                if route.freshness_info:
                    route_attrs.update({
                        'src_type': route.freshness_info.source_type,
                        'data_age_h': route.freshness_info.data_age_hours,
                        'is_realtime': route.freshness_info.is_real_time,
                        'quality': route.freshness_info.quality_score
                    })
                
                route_data.append(route_attrs)
            
            # Create GeoDataFrame
            gdf = gpd.GeoDataFrame(route_data, geometry=geometries, crs='EPSG:4326')
            
            # Export to shapefile
            gdf.to_file(output_path, driver='ESRI Shapefile')
            
            logger.info(f"Exported shapefile to {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Shapefile export failed: {e}")
            raise RuntimeError(f"Shapefile export failed: {e}") from e
    
    async def generate_pdf_report(self, 
                                routes: List[RouteAlignment],
                                risk_assessments: Optional[List[CompositeRisk]] = None,
                                ai_explanations: Optional[List[AIExplanation]] = None,
                                comparison: Optional[RouteComparison] = None,
                                output_path: Optional[Path] = None) -> Path:
        """
        Generate comprehensive PDF report with maps, analysis, and data source information.
        
        Args:
            routes: List of route alignments
            risk_assessments: Optional risk assessments for each route
            ai_explanations: Optional AI explanations for each route
            comparison: Optional route comparison analysis
            output_path: Optional output path for PDF
            
        Returns:
            Path to generated PDF report
        """
        try:
            logger.info(f"Generating PDF report for {len(routes)} routes")
            
            if not output_path:
                output_path = self.temp_dir / f"route_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Create PDF document
            doc = SimpleDocTemplate(str(output_path), pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title and header
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=1  # Center alignment
            )
            
            story.append(Paragraph("Rural Infrastructure Planning Report", title_style))
            story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}", styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Executive Summary
            story.append(Paragraph("Executive Summary", styles['Heading2']))
            
            summary_text = f"""
            This report presents the analysis of {len(routes)} route alternatives for rural road construction 
            in the Uttarakhand region. The analysis incorporates real-time data from multiple sources including 
            elevation data, weather information, and infrastructure mapping to provide comprehensive 
            route recommendations.
            """
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Data Sources Section
            story.append(Paragraph("Data Sources and Freshness", styles['Heading2']))
            
            data_sources_table = self._create_data_sources_table(routes)
            story.append(data_sources_table)
            story.append(Spacer(1, 20))
            
            # Route Analysis Section
            story.append(Paragraph("Route Analysis", styles['Heading2']))
            
            for i, route in enumerate(routes):
                # Route header
                story.append(Paragraph(f"Route {i+1}: {route.id}", styles['Heading3']))
                
                # Route metrics table
                route_table = self._create_route_metrics_table(route)
                story.append(route_table)
                story.append(Spacer(1, 10))
                
                # Risk assessment if available
                if risk_assessments and i < len(risk_assessments):
                    risk_table = self._create_risk_assessment_table(risk_assessments[i])
                    story.append(Paragraph("Risk Assessment", styles['Heading4']))
                    story.append(risk_table)
                    story.append(Spacer(1, 10))
                
                # AI explanation if available
                if ai_explanations and i < len(ai_explanations):
                    story.append(Paragraph("AI Analysis", styles['Heading4']))
                    explanation_text = ai_explanations[i].explanation_text[:1000] + "..." if len(ai_explanations[i].explanation_text) > 1000 else ai_explanations[i].explanation_text
                    story.append(Paragraph(explanation_text, styles['Normal']))
                    story.append(Spacer(1, 10))
                
                story.append(Spacer(1, 20))
            
            # Comparative Analysis Section
            if comparison:
                story.append(Paragraph("Comparative Analysis", styles['Heading2']))
                story.append(Paragraph(comparison.comparison_text, styles['Normal']))
                
                if comparison.recommendation:
                    story.append(Paragraph("Recommendation", styles['Heading3']))
                    story.append(Paragraph(comparison.recommendation, styles['Normal']))
                
                story.append(Spacer(1, 20))
            
            # Generate map and add to report
            map_path = await self._generate_route_map(routes)
            if map_path and map_path.exists():
                story.append(Paragraph("Route Visualization", styles['Heading2']))
                # Note: In a full implementation, you would convert the HTML map to an image
                story.append(Paragraph("Interactive map generated separately (see accompanying HTML file)", styles['Normal']))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Generated PDF report at {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"PDF report generation failed: {e}")
            raise RuntimeError(f"PDF report generation failed: {e}") from e
    
    def _create_data_sources_table(self, routes: List[RouteAlignment]) -> Table:
        """Create table showing data sources and freshness for all routes."""
        # Collect unique data sources
        all_sources = set()
        for route in routes:
            if route.data_sources:
                all_sources.update(route.data_sources)
        
        # Create table data
        table_data = [['Data Source', 'Type', 'Freshness', 'Quality']]
        
        for route in routes:
            if route.freshness_info:
                table_data.append([
                    route.freshness_info.source_name,
                    route.freshness_info.source_type,
                    f"{route.freshness_info.data_age_hours:.1f} hours",
                    f"{route.freshness_info.quality_score:.2f}"
                ])
        
        # If no freshness info, add generic entries
        if len(table_data) == 1:
            for source in list(all_sources)[:5]:  # Limit to 5 sources
                table_data.append([source, 'Mixed', 'Variable', 'Good'])
        
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        return table
    
    def _create_route_metrics_table(self, route: RouteAlignment) -> Table:
        """Create table with route metrics."""
        table_data = [
            ['Metric', 'Value'],
            ['Distance', f"{route.total_distance:.1f} km"],
            ['Elevation Gain', f"{route.elevation_gain:.0f} m"],
            ['Construction Cost', f"${route.estimated_cost:,.0f}"],
            ['Construction Duration', f"{route.estimated_duration} days"],
            ['Difficulty Score', f"{route.construction_difficulty:.1f}/100"],
            ['Risk Score', f"{route.risk_score:.1f}/100"],
            ['Algorithm Used', route.algorithm_used]
        ]
        
        table = Table(table_data, colWidths=[2*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        return table
    
    def _create_risk_assessment_table(self, risk: CompositeRisk) -> Table:
        """Create table with risk assessment details."""
        table_data = [
            ['Risk Category', 'Score', 'Level'],
            ['Terrain Risk', f"{risk.terrain_risk.composite_score:.1f}/100", self._get_risk_level(risk.terrain_risk.composite_score)],
            ['Flood Risk', f"{risk.flood_risk.composite_score:.1f}/100", self._get_risk_level(risk.flood_risk.composite_score)],
            ['Seasonal Risk', f"{risk.seasonal_risk.current_season_risk:.1f}/100", self._get_risk_level(risk.seasonal_risk.current_season_risk)],
            ['Overall Risk', f"{risk.overall_score:.1f}/100", risk.risk_category.title()]
        ]
        
        table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.orange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        return table
    
    def _get_risk_level(self, score: float) -> str:
        """Convert risk score to level description."""
        if score <= 25:
            return "Low"
        elif score <= 50:
            return "Moderate"
        elif score <= 75:
            return "High"
        else:
            return "Extreme"
    
    async def _generate_route_map(self, routes: List[RouteAlignment]) -> Optional[Path]:
        """Generate interactive map for routes."""
        try:
            if not routes:
                return None
            
            # Calculate map center
            all_lats = []
            all_lons = []
            for route in routes:
                for wp in route.waypoints:
                    all_lats.append(wp.latitude)
                    all_lons.append(wp.longitude)
            
            center_lat = sum(all_lats) / len(all_lats)
            center_lon = sum(all_lons) / len(all_lons)
            
            # Create folium map
            m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
            
            # Add routes to map
            colors = ['red', 'blue', 'green', 'purple', 'orange']
            for i, route in enumerate(routes):
                color = colors[i % len(colors)]
                
                # Add route line
                coordinates = [[wp.latitude, wp.longitude] for wp in route.waypoints]
                folium.PolyLine(
                    coordinates,
                    color=color,
                    weight=4,
                    opacity=0.8,
                    popup=f"Route {route.id}<br>Distance: {route.total_distance:.1f} km<br>Cost: ${route.estimated_cost:,.0f}"
                ).add_to(m)
                
                # Add start and end markers
                if route.waypoints:
                    folium.Marker(
                        [route.waypoints[0].latitude, route.waypoints[0].longitude],
                        popup=f"Start - Route {route.id}",
                        icon=folium.Icon(color='green', icon='play')
                    ).add_to(m)
                    
                    folium.Marker(
                        [route.waypoints[-1].latitude, route.waypoints[-1].longitude],
                        popup=f"End - Route {route.id}",
                        icon=folium.Icon(color='red', icon='stop')
                    ).add_to(m)
            
            # Save map
            map_path = self.temp_dir / f"route_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            m.save(str(map_path))
            
            return map_path
            
        except Exception as e:
            logger.warning(f"Map generation failed: {e}")
            return None
    
    async def export_comparative_analysis(self, 
                                        routes: List[RouteAlignment],
                                        comparison: Optional[RouteComparison] = None,
                                        format_type: str = "csv") -> Path:
        """
        Export comparative analysis table with API vs local data indicators.
        
        Args:
            routes: List of routes to compare
            comparison: Optional AI comparison analysis
            format_type: Export format (csv, excel, json)
            
        Returns:
            Path to exported file
        """
        try:
            logger.info(f"Exporting comparative analysis for {len(routes)} routes in {format_type} format")
            
            # Prepare comparison data
            comparison_data = []
            
            for route in routes:
                row_data = {
                    'route_id': route.id,
                    'distance_km': route.total_distance,
                    'elevation_gain_m': route.elevation_gain,
                    'construction_cost_usd': route.estimated_cost,
                    'construction_days': route.estimated_duration,
                    'difficulty_score': route.construction_difficulty,
                    'risk_score': route.risk_score,
                    'algorithm_used': route.algorithm_used,
                    'data_sources': ', '.join(route.data_sources) if route.data_sources else 'Local data'
                }
                
                # Add freshness indicators
                if route.freshness_info:
                    row_data.update({
                        'data_source_type': route.freshness_info.source_type,
                        'data_age_hours': route.freshness_info.data_age_hours,
                        'is_real_time': route.freshness_info.is_real_time,
                        'data_quality_score': route.freshness_info.quality_score,
                        'freshness_indicator': route.freshness_info.get_freshness_indicator()
                    })
                else:
                    row_data.update({
                        'data_source_type': 'local',
                        'data_age_hours': 24.0,
                        'is_real_time': False,
                        'data_quality_score': 0.7,
                        'freshness_indicator': 'moderate'
                    })
                
                comparison_data.append(row_data)
            
            # Create DataFrame
            df = pd.DataFrame(comparison_data)
            
            # Generate output path
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if format_type.lower() == "csv":
                output_path = self.temp_dir / f"route_comparison_{timestamp}.csv"
                df.to_csv(output_path, index=False)
            elif format_type.lower() == "excel":
                output_path = self.temp_dir / f"route_comparison_{timestamp}.xlsx"
                df.to_excel(output_path, index=False, sheet_name='Route Comparison')
            elif format_type.lower() == "json":
                output_path = self.temp_dir / f"route_comparison_{timestamp}.json"
                
                # Add metadata
                export_data = {
                    "metadata": {
                        "export_timestamp": datetime.now().isoformat(),
                        "total_routes": len(routes),
                        "comparison_criteria": ["cost", "safety", "timeline", "data_freshness"],
                        "data_provenance": "Mixed API and local sources"
                    },
                    "routes": comparison_data
                }
                
                if comparison:
                    export_data["ai_comparison"] = comparison.to_dict()
                
                with open(output_path, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format type: {format_type}")
            
            logger.info(f"Exported comparative analysis to {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Comparative analysis export failed: {e}")
            raise RuntimeError(f"Comparative analysis export failed: {e}") from e
    
    async def create_export_package(self, 
                                  routes: List[RouteAlignment],
                                  risk_assessments: Optional[List[CompositeRisk]] = None,
                                  ai_explanations: Optional[List[AIExplanation]] = None,
                                  comparison: Optional[RouteComparison] = None,
                                  formats: List[str] = None) -> Path:
        """
        Create comprehensive export package with multiple formats.
        
        Args:
            routes: List of routes to export
            risk_assessments: Optional risk assessments
            ai_explanations: Optional AI explanations
            comparison: Optional route comparison
            formats: List of formats to include (geojson, kml, shapefile, pdf, csv)
            
        Returns:
            Path to ZIP file containing all exports
        """
        try:
            if formats is None:
                formats = ['geojson', 'kml', 'shapefile', 'pdf', 'csv']
            
            logger.info(f"Creating export package with formats: {', '.join(formats)}")
            
            # Create temporary directory for exports
            export_dir = self.temp_dir / f"export_package_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            export_dir.mkdir(exist_ok=True)
            
            exported_files = []
            
            # Export in requested formats
            for format_type in formats:
                try:
                    if format_type == 'geojson':
                        for i, route in enumerate(routes):
                            geojson_data = await self.export_route_geojson(route)
                            geojson_path = export_dir / f"route_{i+1}_{route.id}.geojson"
                            with open(geojson_path, 'w') as f:
                                json.dump(geojson_data, f, indent=2)
                            exported_files.append(geojson_path)
                    
                    elif format_type == 'kml':
                        for i, route in enumerate(routes):
                            kml_content = await self.export_route_kml(route)
                            kml_path = export_dir / f"route_{i+1}_{route.id}.kml"
                            with open(kml_path, 'w') as f:
                                f.write(kml_content)
                            exported_files.append(kml_path)
                    
                    elif format_type == 'shapefile':
                        shp_path = await self.export_route_shapefile(routes, export_dir / "routes.shp")
                        exported_files.append(shp_path)
                        # Add associated files
                        for ext in ['.shx', '.dbf', '.prj']:
                            assoc_file = shp_path.with_suffix(ext)
                            if assoc_file.exists():
                                exported_files.append(assoc_file)
                    
                    elif format_type == 'pdf':
                        pdf_path = await self.generate_pdf_report(
                            routes, risk_assessments, ai_explanations, comparison,
                            export_dir / "route_report.pdf"
                        )
                        exported_files.append(pdf_path)
                    
                    elif format_type == 'csv':
                        csv_path = await self.export_comparative_analysis(
                            routes, comparison, "csv"
                        )
                        # Move to export directory
                        new_csv_path = export_dir / "route_comparison.csv"
                        csv_path.rename(new_csv_path)
                        exported_files.append(new_csv_path)
                
                except Exception as e:
                    logger.warning(f"Failed to export {format_type} format: {e}")
            
            # Create ZIP package
            zip_path = self.temp_dir / f"route_export_package_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in exported_files:
                    if file_path.exists():
                        zipf.write(file_path, file_path.name)
                
                # Add README
                readme_content = self._generate_export_readme(routes, formats)
                zipf.writestr("README.txt", readme_content)
            
            logger.info(f"Created export package with {len(exported_files)} files at {zip_path}")
            
            return zip_path
            
        except Exception as e:
            logger.error(f"Export package creation failed: {e}")
            raise RuntimeError(f"Export package creation failed: {e}") from e
    
    def _generate_export_readme(self, routes: List[RouteAlignment], formats: List[str]) -> str:
        """Generate README content for export package."""
        readme = f"""Rural Infrastructure Planning System - Export Package
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This package contains route analysis data in multiple formats:

ROUTES INCLUDED:
"""
        
        for i, route in enumerate(routes):
            readme += f"""
Route {i+1}: {route.id}
- Distance: {route.total_distance:.1f} km
- Construction Cost: ${route.estimated_cost:,.0f}
- Construction Duration: {route.estimated_duration} days
- Difficulty Score: {route.construction_difficulty:.1f}/100
- Risk Score: {route.risk_score:.1f}/100
"""
        
        readme += f"""
EXPORT FORMATS:
{', '.join(formats)}

FILE DESCRIPTIONS:
- GeoJSON files: Geographic data in JSON format for web mapping
- KML files: Google Earth compatible format with 3D visualization
- Shapefile: GIS-compatible format (includes .shp, .shx, .dbf, .prj files)
- PDF report: Comprehensive analysis report with maps and recommendations
- CSV file: Tabular comparison data for spreadsheet analysis

DATA SOURCES:
This analysis incorporates data from multiple sources including:
- Real-time API data (elevation, weather, infrastructure)
- Local reference data (terrain models, flood atlases)
- OpenStreetMap road network data

For questions or support, please contact the Rural Infrastructure Planning team.
"""
        
        return readme