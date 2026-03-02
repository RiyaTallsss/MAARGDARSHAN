// MAARGDARSHAN - Interactive Frontend Application
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
    routeLayers: []
};

// Initialize Map - Centered on Uttarakhand
const map = L.map('map').setView([30.0668, 79.0193], 8);  // Uttarakhand center

// Add OpenStreetMap tiles
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 18,
    minZoom: 7
}).addTo(map);

// Uttarakhand boundary (approximate)
const uttarakhandBounds = [
    [28.6, 77.5],  // Southwest
    [31.5, 81.0]   // Northeast
];

// Add boundary rectangle (non-interactive)
L.rectangle(uttarakhandBounds, {
    color: '#667eea',
    weight: 3,
    fillOpacity: 0.05,
    dashArray: '10, 10',
    interactive: false  // Don't intercept clicks
}).addTo(map);

// Restrict map to Uttarakhand region
map.setMaxBounds([
    [28.0, 77.0],  // Southwest with padding
    [32.0, 81.5]   // Northeast with padding
]);

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
    
    console.log(`Clicked: lat=${lat.toFixed(4)}, lng=${lng.toFixed(4)}`);
    
    // Validate coordinates are within Uttarakhand (with generous bounds)
    if (lat < 28.5 || lat > 31.6 || lng < 77.4 || lng > 81.1) {
        console.log('Outside Uttarakhand bounds');
        alert('⚠️ Please select locations within Uttarakhand region.\n\nOther Indian states are under development and will be available soon!');
        return;
    }
    
    console.log('Valid Uttarakhand coordinates');
    
    if (!state.startPoint) {
        // Set start point
        state.startPoint = { lat, lon: lng };
        
        // Add marker
        if (state.markers.start) {
            map.removeLayer(state.markers.start);
        }
        state.markers.start = L.marker([lat, lng], { icon: startIcon })
            .addTo(map)
            .bindPopup('<div class="custom-popup"><div class="popup-title">Start Point</div>Lat: ' + lat.toFixed(4) + '<br>Lon: ' + lng.toFixed(4) + '</div>');
        
        // Update UI
        document.getElementById('start-coord').textContent = lat.toFixed(4) + ', ' + lng.toFixed(4);
        
    } else if (!state.endPoint) {
        // Set end point
        state.endPoint = { lat, lon: lng };
        
        // Add marker
        if (state.markers.end) {
            map.removeLayer(state.markers.end);
        }
        state.markers.end = L.marker([lat, lng], { icon: endIcon })
            .addTo(map)
            .bindPopup('<div class="custom-popup"><div class="popup-title">End Point</div>Lat: ' + lat.toFixed(4) + '<br>Lon: ' + lng.toFixed(4) + '</div>');
        
        // Update UI
        document.getElementById('end-coord').textContent = lat.toFixed(4) + ', ' + lng.toFixed(4);
        document.getElementById('generate-btn').disabled = false;
    }
});

// Generate Routes Button
document.getElementById('generate-btn').addEventListener('click', async function() {
    if (!state.startPoint || !state.endPoint) return;
    
    // Show loading
    document.getElementById('loading').style.display = 'block';
    document.getElementById('routes-container').style.display = 'none';
    document.getElementById('ai-explanation').style.display = 'none';
    this.disabled = true;
    
    try {
        // Call API
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                start: state.startPoint,
                end: state.endPoint,
                context: 'Route planning for rural connectivity in Uttarkashi District'
            })
        });
        
        console.log('Response status:', response.status);
        console.log('Response ok:', response.ok);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Response error:', errorText);
            throw new Error(`API request failed with status ${response.status}: ${errorText}`);
        }
        
        const data = await response.json();
        console.log('Response data:', data);
        
        if (data.success) {
            state.routes = data.routes;
            displayRoutes(data.routes);
            displayAIExplanation(data.ai_explanation);
            
            // Draw all routes on map
            drawRoutes(data.routes);
        } else {
            alert('Error generating routes: ' + (data.message || 'Unknown error'));
        }
        
    } catch (error) {
        console.error('Error details:', error);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
        alert('Failed to generate routes. Error: ' + error.message + '\nCheck browser console for details.');
    } finally {
        document.getElementById('loading').style.display = 'none';
        this.disabled = false;
    }
});

// Clear Button
document.getElementById('clear-btn').addEventListener('click', function() {
    // Clear state
    state.startPoint = null;
    state.endPoint = null;
    state.routes = [];
    state.selectedRoute = null;
    
    // Remove markers
    if (state.markers.start) {
        map.removeLayer(state.markers.start);
        state.markers.start = null;
    }
    if (state.markers.end) {
        map.removeLayer(state.markers.end);
        state.markers.end = null;
    }
    
    // Remove route layers
    state.routeLayers.forEach(layer => map.removeLayer(layer));
    state.routeLayers = [];
    
    // Reset UI
    document.getElementById('start-coord').textContent = 'Click on map';
    document.getElementById('end-coord').textContent = 'Click on map';
    document.getElementById('generate-btn').disabled = true;
    document.getElementById('routes-container').style.display = 'none';
    document.getElementById('ai-explanation').style.display = 'none';
    document.getElementById('routes').innerHTML = '';
});

// Display Routes
function displayRoutes(routes) {
    const container = document.getElementById('routes');
    container.innerHTML = '';
    
    const colors = ['#3b82f6', '#10b981'];  // Blue for shortest, Green for safest
    
    routes.forEach((route, index) => {
        const card = document.createElement('div');
        card.className = 'route-card';
        card.dataset.routeId = route.id;
        
        // Risk badge
        let badgeClass = 'badge-low';
        let riskLabel = 'Low Risk';
        if (route.risk_score > 60) {
            badgeClass = 'badge-high';
            riskLabel = 'High Risk';
        } else if (route.risk_score > 40) {
            badgeClass = 'badge-medium';
            riskLabel = 'Medium Risk';
        }
        
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
                    <span class="metric-value">$${(route.estimated_cost_usd / 1000).toFixed(0)}K</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Duration:</span>
                    <span class="metric-value">${route.estimated_days} days</span>
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
                    <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Monsoon & rainfall impact</div>
                </div>
            </div>
        `;
        
        // Click handler
        card.addEventListener('click', function() {
            // Remove previous selection
            document.querySelectorAll('.route-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            
            // Highlight route on map
            highlightRoute(index);
        });
        
        container.appendChild(card);
    });
    
    document.getElementById('routes-container').style.display = 'block';
}

// Draw Routes on Map
function drawRoutes(routes) {
    // Clear existing routes
    state.routeLayers.forEach(layer => map.removeLayer(layer));
    state.routeLayers = [];
    
    const colors = ['#3b82f6', '#10b981'];  // Blue for shortest, Green for safest
    
    routes.forEach((route, index) => {
        const coordinates = route.waypoints.map(wp => [wp.lat, wp.lon]);
        
        const polyline = L.polyline(coordinates, {
            color: colors[index],
            weight: 4,
            opacity: 0.7
        }).addTo(map);
        
        // Add popup
        polyline.bindPopup(`
            <div class="custom-popup">
                <div class="popup-title">${route.name}</div>
                <strong>Distance:</strong> ${route.distance_km} km<br>
                <strong>Risk Score:</strong> ${route.risk_score}/100<br>
                <strong>Cost:</strong> $${(route.estimated_cost_usd / 1000).toFixed(0)}K
            </div>
        `);
        
        state.routeLayers.push(polyline);
        
        // Add flood risk markers for high-risk waypoints
        route.waypoints.forEach((wp, wpIndex) => {
            // Check if this waypoint has high flood risk (elevation < 1200m)
            if (wp.elevation < 1200) {
                const floodMarker = L.marker([wp.lat, wp.lon], {
                    icon: L.divIcon({
                        className: 'flood-risk-marker',
                        html: '<div style="background: #ef4444; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">⚠</div>',
                        iconSize: [20, 20],
                        iconAnchor: [10, 10]
                    })
                }).addTo(map);
                
                floodMarker.bindPopup(`
                    <div class="custom-popup">
                        <div class="popup-title" style="color: #ef4444;">⚠️ Flood Risk Zone</div>
                        <strong>Elevation:</strong> ${wp.elevation}m<br>
                        <strong>Risk:</strong> High (Low elevation area)<br>
                        <strong>Recommendation:</strong> Requires drainage systems
                    </div>
                `);
                
                state.routeLayers.push(floodMarker);
            }
            
            // Add landslide risk markers for steep terrain
            if (wpIndex > 0) {
                const elevChange = Math.abs(wp.elevation - route.waypoints[wpIndex - 1].elevation);
                if (elevChange > 300) {
                    const landslideMarker = L.marker([wp.lat, wp.lon], {
                        icon: L.divIcon({
                            className: 'landslide-risk-marker',
                            html: '<div style="background: #f59e0b; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">⛰</div>',
                            iconSize: [20, 20],
                            iconAnchor: [10, 10]
                        })
                    }).addTo(map);
                    
                    landslideMarker.bindPopup(`
                        <div class="custom-popup">
                            <div class="popup-title" style="color: #f59e0b;">⛰️ Steep Terrain</div>
                            <strong>Elevation Change:</strong> ${elevChange}m<br>
                            <strong>Risk:</strong> Landslide prone<br>
                            <strong>Recommendation:</strong> Requires retaining walls
                        </div>
                    `);
                    
                    state.routeLayers.push(landslideMarker);
                }
            }
        });
    });
    
    // Fit map to show all routes
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

// Add sample coordinates button for demo
function addSampleCoordinates() {
    // Uttarkashi to Gangotri
    state.startPoint = { lat: 30.7268, lon: 78.4354 };
    state.endPoint = { lat: 30.9993, lon: 78.9394 };
    
    // Add markers
    if (state.markers.start) map.removeLayer(state.markers.start);
    if (state.markers.end) map.removeLayer(state.markers.end);
    
    state.markers.start = L.marker([30.7268, 78.4354], { icon: startIcon })
        .addTo(map)
        .bindPopup('<div class="custom-popup"><div class="popup-title">Uttarkashi Town</div>Start Point</div>');
    
    state.markers.end = L.marker([30.9993, 78.9394], { icon: endIcon })
        .addTo(map)
        .bindPopup('<div class="custom-popup"><div class="popup-title">Gangotri</div>End Point</div>');
    
    // Update UI
    document.getElementById('start-coord').textContent = '30.7268, 78.4354';
    document.getElementById('end-coord').textContent = '30.9993, 78.9394';
    document.getElementById('generate-btn').disabled = false;
    
    // Fit map
    map.fitBounds([[30.7268, 78.4354], [30.9993, 78.9394]]);
}

// Add keyboard shortcut for demo (press 'D' for demo data)
document.addEventListener('keydown', function(e) {
    if (e.key === 'd' || e.key === 'D') {
        addSampleCoordinates();
    }
});

console.log('🗺️ MAARGDARSHAN loaded successfully!');
console.log('💡 Tip: Press "D" to load sample coordinates (Uttarkashi to Gangotri)');
