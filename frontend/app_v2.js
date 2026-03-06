// MAARGDARSHAN - Interactive Frontend Application v2.0
// With Construction Data Display and Download Features

// API Configuration
const API_URL = 'https://pma49s9qy8.execute-api.us-east-1.amazonaws.com/prod/routes';

// State Management
const state = {
    startPoint: null,
    endPoint: null,
    routes: [],
    selectedRoute: null,
    markers: {
        start: null,
        end: null
    },
    routeLayers: [],
    bridgeMarkers: [],
    settlementMarkers: []
};

// Initialize Map - Centered on Uttarakhand
const map = L.map('map').setView([30.0668, 79.0193], 8);

// Add OpenStreetMap tiles
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 18,
    minZoom: 7
}).addTo(map);

// Uttarakhand boundary
const uttarakhandBounds = [[28.6, 77.5], [31.5, 81.0]];
L.rectangle(uttarakhandBounds, {
    color: '#667eea',
    weight: 3,
    fillOpacity: 0.05,
    dashArray: '10, 10',
    interactive: false
}).addTo(map);

map.setMaxBounds([[28.0, 77.0], [32.0, 81.5]]);

// Custom marker icons
const startIcon = L.divIcon({
    className: 'custom-marker',
    html: '<div style="background: #3b82f6; width: 30px; height: 30px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">A</div>',
    iconSize: [30, 30],
    iconAnchor: [15, 15]
});

const endIcon = L.divIcon({
    className: 'custom-marker',
    html: '<div style="background: #ef4444; width: 30px; height: 30px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">B</div>',
    iconSize: [30, 30],
    iconAnchor: [15, 15]
});

// Map Click Handler
map.on('click', function(e) {
    const { lat, lng } = e.latlng;
    
    if (lat < 28.5 || lat > 31.6 || lng < 77.4 || lng > 81.1) {
        alert('⚠️ Please select locations within Uttarakhand region.');
        return;
    }
    
    if (!state.startPoint) {
        state.startPoint = { lat, lon: lng };
        if (state.markers.start) map.removeLayer(state.markers.start);
        state.markers.start = L.marker([lat, lng], { icon: startIcon }).addTo(map);
        document.getElementById('start-coord').textContent = lat.toFixed(4) + ', ' + lng.toFixed(4);
    } else if (!state.endPoint) {
        state.endPoint = { lat, lon: lng };
        if (state.markers.end) map.removeLayer(state.markers.end);
        state.markers.end = L.marker([lat, lng], { icon: endIcon }).addTo(map);
        document.getElementById('end-coord').textContent = lat.toFixed(4) + ', ' + lng.toFixed(4);
        document.getElementById('generate-btn').disabled = false;
    }
});

// Generate Routes Button
document.getElementById('generate-btn').addEventListener('click', async function() {
    if (!state.startPoint || !state.endPoint) return;
    
    document.getElementById('loading').style.display = 'block';
    document.getElementById('routes-container').style.display = 'none';
    document.getElementById('ai-explanation').style.display = 'none';
    this.disabled = true;
    
    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start: state.startPoint,
                end: state.endPoint,
                context: 'Route planning for rural connectivity in Uttarkashi District'
            })
        });
        
        if (!response.ok) throw new Error(`API request failed: ${response.status}`);
        
        const data = await response.json();
        
        if (data.success) {
            state.routes = data.routes;
            displayRoutes(data.routes);
            displayAIExplanation(data.ai_explanation);
            drawRoutes(data.routes);
        } else {
            alert('Error generating routes: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to generate routes: ' + error.message);
    } finally {
        document.getElementById('loading').style.display = 'none';
        this.disabled = false;
    }
});

// Clear Button
document.getElementById('clear-btn').addEventListener('click', function() {
    state.startPoint = null;
    state.endPoint = null;
    state.routes = [];
    
    if (state.markers.start) map.removeLayer(state.markers.start);
    if (state.markers.end) map.removeLayer(state.markers.end);
    state.markers.start = null;
    state.markers.end = null;
    
    state.routeLayers.forEach(layer => map.removeLayer(layer));
    state.bridgeMarkers.forEach(marker => map.removeLayer(marker));
    state.settlementMarkers.forEach(marker => map.removeLayer(marker));
    state.routeLayers = [];
    state.bridgeMarkers = [];
    state.settlementMarkers = [];
    
    document.getElementById('start-coord').textContent = 'Click on map';
    document.getElementById('end-coord').textContent = 'Click on map';
    document.getElementById('generate-btn').disabled = true;
    document.getElementById('routes-container').style.display = 'none';
    document.getElementById('ai-explanation').style.display = 'none';
    document.getElementById('routes').innerHTML = '';
});

// Display Routes with Construction Data
function displayRoutes(routes) {
    const container = document.getElementById('routes');
    container.innerHTML = '';
    
    const colors = ['#3b82f6', '#10b981'];
    
    routes.forEach((route, index) => {
        const card = document.createElement('div');
        card.className = 'route-card';
        
        const badgeClass = route.risk_score > 60 ? 'badge-high' : route.risk_score > 40 ? 'badge-medium' : 'badge-low';
        const riskLabel = route.risk_score > 60 ? 'High Risk' : route.risk_score > 40 ? 'Medium Risk' : 'Low Risk';
        
        const constructionData = route.construction_data || {};
        const earthwork = constructionData.earthwork || {};
        const bridges = route.bridges_required || 0;
        const settlements = (route.nearby_settlements || []).length;
        
        card.innerHTML = `
            <div class="route-header">
                <div class="route-name" style="color: ${colors[index]}">${route.name}</div>
                <div class="route-badge ${badgeClass}">${riskLabel}</div>
            </div>
            <div class="route-metrics">
                <div class="metric">
                    <span class="metric-label">Distance:</span>
                    <span class="metric-value">${route.distance_km} km</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Elevation:</span>
                    <span class="metric-value">${route.elevation_gain_m} m</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Cost:</span>
                    <span class="metric-value">₹${(route.estimated_cost_usd / 100000).toFixed(1)}Cr</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Duration:</span>
                    <span class="metric-value">${route.estimated_days} days</span>
                </div>
            </div>
            
            <div class="construction-details">
                <div class="construction-header">🚧 Construction Details</div>
                <div class="construction-grid">
                    <div class="construction-item">
                        <span class="construction-icon">🌉</span>
                        <span class="construction-label">Bridges:</span>
                        <span class="construction-value">${bridges}</span>
                    </div>
                    <div class="construction-item">
                        <span class="construction-icon">🏘️</span>
                        <span class="construction-label">Settlements:</span>
                        <span class="construction-value">${settlements}</span>
                    </div>
                    <div class="construction-item">
                        <span class="construction-icon">📏</span>
                        <span class="construction-label">Waypoints:</span>
                        <span class="construction-value">${constructionData.total_waypoints || 0}</span>
                    </div>
                    <div class="construction-item">
                        <span class="construction-icon">📐</span>
                        <span class="construction-label">Max Gradient:</span>
                        <span class="construction-value">${(constructionData.max_gradient_percent || 0).toFixed(1)}%</span>
                    </div>
                </div>
                
                ${earthwork.total_cut_m3 ? `
                <div class="earthwork-summary">
                    <div class="earthwork-title">⛏️ Earthwork</div>
                    <div class="earthwork-row">
                        <span>Cut:</span>
                        <span class="earthwork-value">${formatVolume(earthwork.total_cut_m3)}</span>
                    </div>
                    <div class="earthwork-row">
                        <span>Fill:</span>
                        <span class="earthwork-value">${formatVolume(earthwork.total_fill_m3)}</span>
                    </div>
                    <div class="earthwork-row">
                        <span>Balance:</span>
                        <span class="earthwork-value ${earthwork.balance_status}">${(earthwork.balance_status || '').replace(/_/g, ' ')}</span>
                    </div>
                </div>
                ` : ''}
                
                <div class="download-section">
                    <div class="download-title">📥 Download for Field Use</div>
                    <div class="download-buttons">
                        <button class="download-btn" onclick="downloadFormat(${index}, 'kml')">
                            <span>📍</span> KML
                        </button>
                        <button class="download-btn" onclick="downloadFormat(${index}, 'gpx')">
                            <span>🗺️</span> GPX
                        </button>
                        <button class="download-btn" onclick="downloadFormat(${index}, 'geojson')">
                            <span>🌐</span> GeoJSON
                        </button>
                    </div>
                    <div class="download-hint">For Google Earth, GPS devices, and GIS software</div>
                </div>
            </div>
            
            <div class="risk-bars">
                <div class="risk-item">
                    <div class="risk-label">
                        <span>Terrain Risk</span>
                        <span>${route.risk_factors.terrain_risk}/100</span>
                    </div>
                    <div class="risk-bar">
                        <div class="risk-fill ${getRiskClass(route.risk_factors.terrain_risk)}" 
                             style="width: ${route.risk_factors.terrain_risk}%"></div>
                    </div>
                </div>
                <div class="risk-item">
                    <div class="risk-label">
                        <span>Flood Risk</span>
                        <span>${route.risk_factors.flood_risk}/100</span>
                    </div>
                    <div class="risk-bar">
                        <div class="risk-fill ${getRiskClass(route.risk_factors.flood_risk)}" 
                             style="width: ${route.risk_factors.flood_risk}%"></div>
                    </div>
                </div>
                <div class="risk-item">
                    <div class="risk-label">
                        <span>Seasonal Risk</span>
                        <span>${route.risk_factors.seasonal_risk}/100</span>
                    </div>
                    <div class="risk-bar">
                        <div class="risk-fill ${getRiskClass(route.risk_factors.seasonal_risk)}" 
                             style="width: ${route.risk_factors.seasonal_risk}%"></div>
                    </div>
                </div>
            </div>
        `;
        
        card.addEventListener('click', function() {
            document.querySelectorAll('.route-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            highlightRoute(index);
        });
        
        container.appendChild(card);
    });
    
    document.getElementById('routes-container').style.display = 'block';
}

// Draw Routes on Map with Bridges and Settlements
function drawRoutes(routes) {
    state.routeLayers.forEach(layer => map.removeLayer(layer));
    state.bridgeMarkers.forEach(marker => map.removeLayer(marker));
    state.settlementMarkers.forEach(marker => map.removeLayer(marker));
    state.routeLayers = [];
    state.bridgeMarkers = [];
    state.settlementMarkers = [];
    
    const colors = ['#3b82f6', '#10b981'];
    
    routes.forEach((route, index) => {
        const coordinates = route.waypoints.map(wp => [wp.lat, wp.lon]);
        const polyline = L.polyline(coordinates, {
            color: colors[index],
            weight: 4,
            opacity: 0.7
        }).addTo(map);
        
        polyline.bindPopup(`
            <div class="custom-popup">
                <div class="popup-title">${route.name}</div>
                <strong>Distance:</strong> ${route.distance_km} km<br>
                <strong>Bridges:</strong> ${route.bridges_required || 0}<br>
                <strong>Cost:</strong> ₹${(route.estimated_cost_usd / 100000).toFixed(1)}Cr
            </div>
        `);
        
        state.routeLayers.push(polyline);
        
        // Add bridge markers
        if (route.river_crossings) {
            route.river_crossings.forEach(crossing => {
                const bridgeMarker = L.marker([crossing.lat, crossing.lon], {
                    icon: L.divIcon({
                        className: 'bridge-marker',
                        html: '<div style="background: #8b5cf6; width: 24px; height: 24px; border-radius: 50%; border: 2px solid white; display: flex; align-items: center; justify-content: center; font-size: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">🌉</div>',
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    })
                }).addTo(map);
                
                bridgeMarker.bindPopup(`
                    <div class="custom-popup">
                        <div class="popup-title">🌉 Bridge Required</div>
                        <strong>River:</strong> ${crossing.river_name}<br>
                        <strong>Span:</strong> ~${crossing.estimated_span_m}m<br>
                        <strong>Cost:</strong> ₹1 crore
                    </div>
                `);
                
                state.bridgeMarkers.push(bridgeMarker);
            });
        }
        
        // Add settlement markers
        if (route.nearby_settlements) {
            route.nearby_settlements.slice(0, 5).forEach(settlement => {
                const settlementMarker = L.marker([settlement.lat, settlement.lon], {
                    icon: L.divIcon({
                        className: 'settlement-marker',
                        html: '<div style="background: #f59e0b; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; display: flex; align-items: center; justify-content: center; font-size: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">🏘️</div>',
                        iconSize: [20, 20],
                        iconAnchor: [10, 10]
                    })
                }).addTo(map);
                
                settlementMarker.bindPopup(`
                    <div class="custom-popup">
                        <div class="popup-title">🏘️ ${settlement.name}</div>
                        <strong>Type:</strong> ${settlement.type}<br>
                        <strong>Distance:</strong> ${settlement.distance_from_route_km} km
                    </div>
                `);
                
                state.settlementMarkers.push(settlementMarker);
            });
        }
    });
    
    if (state.routeLayers.length > 0) {
        const group = L.featureGroup(state.routeLayers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

// Highlight Route
function highlightRoute(index) {
    state.routeLayers.forEach((layer, i) => {
        if (i === index) {
            layer.setStyle({ weight: 6, opacity: 1 });
            layer.bringToFront();
        } else {
            layer.setStyle({ weight: 4, opacity: 0.4 });
        }
    });
}

// Display AI Explanation
function displayAIExplanation(explanation) {
    document.getElementById('ai-text').textContent = explanation;
    document.getElementById('ai-explanation').style.display = 'block';
}

// Helper Functions
function getRiskClass(score) {
    if (score > 60) return 'risk-high';
    if (score > 40) return 'risk-medium';
    return 'risk-low';
}

function formatVolume(volume) {
    if (volume > 1000000) return (volume / 1000000).toFixed(2) + 'M m³';
    if (volume > 1000) return (volume / 1000).toFixed(1) + 'K m³';
    return volume.toFixed(0) + ' m³';
}

// Download format handler
function downloadFormat(routeIndex, format) {
    const route = state.routes[routeIndex];
    if (!route || !route.construction_data || !route.construction_data.downloadable_formats) {
        alert('Download data not available');
        return;
    }
    
    const content = route.construction_data.downloadable_formats[format];
    if (!content) {
        alert(`${format.toUpperCase()} format not available`);
        return;
    }
    
    const blob = new Blob([content], { 
        type: format === 'geojson' ? 'application/json' : 'application/xml' 
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${route.name.replace(/\s+/g, '_')}_route.${format === 'geojson' ? 'json' : format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    console.log(`Downloaded ${format.toUpperCase()} for ${route.name}`);
}

// Sample coordinates (press 'D')
function addSampleCoordinates() {
    state.startPoint = { lat: 30.7268, lon: 78.4354 };
    state.endPoint = { lat: 30.9993, lon: 78.9394 };
    
    if (state.markers.start) map.removeLayer(state.markers.start);
    if (state.markers.end) map.removeLayer(state.markers.end);
    
    state.markers.start = L.marker([30.7268, 78.4354], { icon: startIcon }).addTo(map);
    state.markers.end = L.marker([30.9993, 78.9394], { icon: endIcon }).addTo(map);
    
    document.getElementById('start-coord').textContent = '30.7268, 78.4354';
    document.getElementById('end-coord').textContent = '30.9993, 78.9394';
    document.getElementById('generate-btn').disabled = false;
    
    map.fitBounds([[30.7268, 78.4354], [30.9993, 78.9394]]);
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'd' || e.key === 'D') addSampleCoordinates();
});

console.log('🗺️ MAARGDARSHAN v2.0 loaded!');
console.log('💡 Press "D" for demo coordinates');
