# OSM Routing Deployment Checklist

## Pre-Deployment Steps

### 1. Upload OSM PBF File to S3
```bash
# Upload the northern zone PBF file
aws s3 cp Maps/northern-zone-260121.osm.pbf \
  s3://maargdarshan-data/osm/northern-zone-260121.osm.pbf

# Verify upload
aws s3 ls s3://maargdarshan-data/osm/
```

### 2. Create S3 Cache Directory
```bash
# Create the cache directory structure
aws s3api put-object \
  --bucket maargdarshan-data \
  --key osm/cache/
```

### 3. Install Dependencies Locally (for testing)
```bash
pip install osmium networkx scipy numpy
```

### 4. Test Locally (Optional)
```bash
# Test the OSM parser
python -c "
from osm_routing.parser import OSMParser
parser = OSMParser()
network = parser.parse_pbf('Maps/northern-zone-260121.osm.pbf')
print(f'Nodes: {len(network.nodes)}, Edges: {len(network.edges)}')
"
```

---

## Deployment Steps

### 1. Deploy Lambda Function
```bash
# Package and deploy Lambda with new dependencies
./deploy_lambda.sh

# This will:
# - Install osmium, networkx, scipy, numpy
# - Package osm_routing/ module
# - Upload to Lambda
# - Update function configuration
```

### 2. Update Lambda Configuration
```bash
# Increase memory to 512MB
aws lambda update-function-configuration \
  --function-name maargdarshan-route-generator \
  --memory-size 512 \
  --timeout 30

# Add environment variables
aws lambda update-function-configuration \
  --function-name maargdarshan-route-generator \
  --environment Variables="{
    S3_BUCKET=maargdarshan-data,
    OSM_PBF_PATH=osm/northern-zone-260121.osm.pbf,
    OSM_CACHE_PATH=osm/cache/road_network.json.gz
  }"
```

### 3. Deploy Frontend
```bash
# Deploy updated frontend with road network visualization
./deploy_frontend.sh

# This will:
# - Upload updated app.js to S3
# - Invalidate CloudFront cache
```

---

## Post-Deployment Testing

### 1. Test OSM Routing
```bash
# Test with Uttarkashi to Gangotri coordinates
curl -X POST https://pma49s9qy8.execute-api.us-east-1.amazonaws.com/prod/routes \
  -H "Content-Type: application/json" \
  -d '{
    "start": {"lat": 30.7268, "lon": 78.4354},
    "end": {"lat": 30.9993, "lon": 78.9394},
    "context": "Test OSM routing"
  }'
```

### 2. Verify Response
Check for:
- ✅ `routing_method: "osm_network"` in metadata
- ✅ `road_network` field with GeoJSON
- ✅ `construction_stats` in each route
- ✅ Routes have realistic waypoints following roads

### 3. Test Frontend
1. Open https://maargdarshan.s3-website-us-east-1.amazonaws.com
2. Click two points in Uttarkashi region
3. Generate routes
4. Verify:
   - ✅ Gray road network layer appears
   - ✅ Routes follow visible roads
   - ✅ Toggle button shows/hides roads
   - ✅ Construction stats display correctly

### 4. Test Fallback
```bash
# Test with coordinates far from roads (should fallback to curves)
curl -X POST https://pma49s9qy8.execute-api.us-east-1.amazonaws.com/prod/routes \
  -H "Content-Type: application/json" \
  -d '{
    "start": {"lat": 30.5, "lon": 78.0},
    "end": {"lat": 30.6, "lon": 78.1},
    "context": "Test fallback"
  }'
```

---

## Monitoring

### 1. Check CloudWatch Logs
```bash
# View Lambda logs
aws logs tail /aws/lambda/maargdarshan-route-generator --follow

# Look for:
# - "OSM network initialized in X.XXs"
# - "Loaded OSM network from cache"
# - "Generated X OSM routes"
```

### 2. Monitor Performance
- Cold start time: Should be <5s with cache
- Route calculation: Should be <25s
- Memory usage: Should be <400MB
- Response size: Should be <6MB

### 3. Check for Errors
```bash
# Search for errors
aws logs filter-pattern "ERROR" \
  --log-group-name /aws/lambda/maargdarshan-route-generator \
  --start-time $(date -u -d '1 hour ago' +%s)000
```

---

## Rollback Plan

If issues occur:

### 1. Revert Lambda
```bash
# List previous versions
aws lambda list-versions-by-function \
  --function-name maargdarshan-route-generator

# Rollback to previous version
aws lambda update-alias \
  --function-name maargdarshan-route-generator \
  --name prod \
  --function-version <PREVIOUS_VERSION>
```

### 2. Revert Frontend
```bash
# Restore previous app.js from git
git checkout HEAD~1 frontend/app.js
./deploy_frontend.sh
```

### 3. Disable OSM Routing
```bash
# Remove OSM PBF file to force fallback
aws s3 rm s3://maargdarshan-data/osm/northern-zone-260121.osm.pbf
```

---

## Success Criteria

✅ Lambda deploys successfully  
✅ OSM network initializes on cold start  
✅ Routes follow actual roads  
✅ Road network layer displays on map  
✅ Construction stats show correctly  
✅ Performance within limits (<30s, <512MB)  
✅ Fallback works if OSM unavailable  

---

## Support

If issues arise:
1. Check CloudWatch logs for errors
2. Verify S3 files exist and are accessible
3. Test Lambda locally with sam local
4. Review implementation docs in `docs/OSM_ROUTING_IMPLEMENTATION_COMPLETE.md`

---

**Deployment Date**: _____________  
**Deployed By**: _____________  
**Status**: _____________
