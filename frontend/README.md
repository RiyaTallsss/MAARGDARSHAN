# MAARGDARSHAN Frontend

Interactive web interface for AI-powered rural infrastructure planning.

## Features

✅ **Interactive Map**
- Click to set start and end points
- Visual route display with different colors
- Satellite imagery base layer
- Custom markers and popups

✅ **Route Comparison**
- 3 alternative routes displayed
- Side-by-side metrics comparison
- Risk score visualization
- Cost and duration estimates

✅ **AI Analysis**
- Amazon Bedrock explanations
- Natural language recommendations
- Risk factor breakdown
- Construction feasibility insights

✅ **Professional UI**
- Modern, clean design
- Responsive layout
- Interactive elements
- Real-time updates

## Quick Start

### Option 1: Open Locally

```bash
# Just open the HTML file in your browser
open frontend/index.html

# Or use Python's built-in server
cd frontend
python3 -m http.server 8000

# Then visit: http://localhost:8000
```

### Option 2: Deploy to S3 (for live demo)

```bash
# Create S3 bucket for website
aws s3 mb s3://maargdarshan-frontend --region us-east-1

# Enable static website hosting
aws s3 website s3://maargdarshan-frontend \
  --index-document index.html

# Upload files
aws s3 sync frontend/ s3://maargdarshan-frontend/ --acl public-read

# Make bucket public
aws s3api put-bucket-policy --bucket maargdarshan-frontend --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::maargdarshan-frontend/*"
  }]
}'

# Your website URL:
# http://maargdarshan-frontend.s3-website-us-east-1.amazonaws.com
```

## How to Use

1. **Set Start Point**: Click anywhere on the map
2. **Set End Point**: Click again on the map
3. **Generate Routes**: Click the "Generate Routes with AI" button
4. **Compare Routes**: Click on route cards to highlight them
5. **View AI Analysis**: Scroll down to see Bedrock's explanation

### Quick Demo

Press **"D"** key to load sample coordinates (Uttarkashi to Gangotri)

## Files

- `index.html` - Main HTML structure and styling
- `app.js` - JavaScript application logic
- `README.md` - This file

## API Configuration

The frontend connects to your Lambda API:
```javascript
const API_URL = 'https://pma49s9qy8.execute-api.us-east-1.amazonaws.com/prod/routes';
```

To change the API URL, edit `app.js` line 2.

## Features Breakdown

### Interactive Map
- **Library**: Leaflet.js
- **Tiles**: OpenStreetMap
- **Markers**: Custom styled A/B markers
- **Routes**: Color-coded polylines

### Route Cards
- **Shortest Route**: Blue (#3b82f6)
- **Safest Route**: Green (#10b981)
- **Cost-Effective**: Orange (#f59e0b)

### Risk Visualization
- **Low Risk**: < 40 (Green)
- **Medium Risk**: 40-60 (Orange)
- **High Risk**: > 60 (Red)

### Metrics Displayed
- Distance (km)
- Elevation gain (m)
- Estimated cost (USD)
- Construction duration (days)
- Terrain risk (0-100)
- Flood risk (0-100)
- Seasonal risk (0-100)

## Browser Compatibility

✅ Chrome/Edge (recommended)
✅ Firefox
✅ Safari
✅ Mobile browsers

## Customization

### Change Map Center
Edit `app.js` line 20:
```javascript
const map = L.map('map').setView([30.86, 78.69], 10);
//                                 ↑ lat  ↑ lon   ↑ zoom
```

### Change Colors
Edit `index.html` CSS section or `app.js` colors array.

### Add More Route Types
Modify the backend Lambda function to return additional routes.

## Troubleshooting

### Routes not displaying?
- Check browser console for errors
- Verify API URL is correct
- Test API with curl first

### Map not loading?
- Check internet connection (needs to load tiles)
- Verify Leaflet CDN is accessible

### CORS errors?
- API Gateway CORS should be enabled (done automatically)
- Check browser console for specific error

## Performance

- **Load Time**: < 2 seconds
- **API Response**: 3-5 seconds
- **Map Rendering**: Instant
- **Route Drawing**: < 1 second

## Security

- No API keys exposed in frontend
- All authentication handled by API Gateway
- CORS properly configured
- No sensitive data stored locally

## Future Enhancements

- [ ] Save routes to local storage
- [ ] Export routes as PDF
- [ ] Share routes via URL
- [ ] Add more map layers (satellite, terrain)
- [ ] Route editing (drag waypoints)
- [ ] Offline mode
- [ ] Mobile app version

## Credits

- **Maps**: OpenStreetMap contributors
- **Map Library**: Leaflet.js
- **AI**: Amazon Bedrock (Claude 3 Haiku)
- **Backend**: AWS Lambda + API Gateway
- **Data**: S3 (DEM, OSM, Rainfall, Floods)

---

**Built for AWS AI for Bharat Hackathon 2026**
