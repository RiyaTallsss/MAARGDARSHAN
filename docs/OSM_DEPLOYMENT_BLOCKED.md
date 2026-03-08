# OSM Routing Deployment - Blocked by Compiler Compatibility

## Status: Implementation Complete, Deployment Blocked

Date: March 7, 2026

## Summary

The OSM road network routing feature is **fully implemented** with all core modules complete:
- OSM PBF parser with caching
- Graph-based pathfinding with A* algorithm
- 4 cost functions (shortest, safest, budget, social)
- Spatial indexing with KDTree
- Lambda integration with error handling
- Frontend visualization components

However, **deployment to AWS Lambda is blocked** due to a compiler compatibility issue with pyosmium.

## Technical Issue

### Problem
pyosmium requires C++17 `std::filesystem` support, which is not available in Amazon Linux 2's GCC 7.3.1. The compilation fails with:
```
error: 'std::filesystem' has not been declared
```

### Root Cause
- AWS Lambda Python 3.9 runtime uses Amazon Linux 2
- Amazon Linux 2 ships with GCC 7.3.1 (released 2018)
- pyosmium 4.3.0 requires C++17 filesystem (GCC 8+ or Clang 7+)
- Docker cross-compilation from macOS (ARM) to Lambda (x86_64) works, but the old compiler fails

### Attempted Solutions
1. ✅ Built Docker layer with `--platform linux/amd64` for correct architecture
2. ✅ Replaced scipy with scikit-learn to reduce layer size (97MB → 54MB)
3. ✅ Created minimal Lambda package (28KB) with dependencies in layer
4. ❌ pyosmium compilation fails due to GCC version incompatibility

## Current System Status

### What's Working
- ✅ Mathematical curve routing (fully functional fallback)
- ✅ 4 distinct routes with different optimization criteria
- ✅ Real terrain data (DEM), flood risk, rainfall patterns
- ✅ Settlement proximity analysis
- ✅ Cost estimation and construction difficulty
- ✅ Frontend visualization with interactive map
- ✅ AWS deployment (Lambda + API Gateway + S3)
- ✅ Response size management (<6MB)
- ✅ 30-second timeout compliance

### What's Not Working
- ❌ OSM road network routing (blocked by deployment)
- ❌ Routes following actual roads from OpenStreetMap
- ❌ Gray road overlay on map

## Recommendations

### Option 1: Use Python 3.11 Runtime (Recommended)
AWS Lambda now supports Python 3.11, which uses Amazon Linux 2023 with GCC 11.4.

**Steps:**
1. Update Lambda runtime to `python3.11`
2. Rebuild Docker layer with `public.ecr.aws/lambda/python:3.11`
3. Update `requirements-lambda.txt` to ensure Python 3.11 compatibility
4. Redeploy Lambda function and layer

**Pros:**
- Modern compiler with full C++17 support
- Likely to work without code changes
- Better performance and security

**Cons:**
- Requires testing all dependencies on Python 3.11
- May need code updates for Python 3.11 compatibility

### Option 2: Use Pre-Built Wheels
Find or build pre-compiled pyosmium wheels for Amazon Linux 2.

**Steps:**
1. Search PyPI for manylinux wheels compatible with AL2
2. Or build wheels on an Amazon Linux 2 EC2 instance with devtoolset-8 (GCC 8+)
3. Include wheels directly in Lambda layer

**Pros:**
- Stays on Python 3.9 runtime
- No code changes needed

**Cons:**
- Time-consuming to find/build compatible wheels
- May still hit compiler issues

### Option 3: Use Alternative OSM Library
Replace pyosmium with a pure-Python OSM parser.

**Options:**
- `osmium-tool` + subprocess (not ideal for Lambda)
- `imposm.parser` (older, may have similar issues)
- Custom PBF parser using `protobuf` (significant development effort)

**Pros:**
- Avoids C++ compilation entirely

**Cons:**
- Significant code rewrite required
- Performance may be worse
- May not support all OSM features

### Option 4: Keep Current Fallback System
Accept the mathematical curve routing as the production solution.

**Pros:**
- Already working and deployed
- Meets all functional requirements
- Fast and reliable
- No additional development needed

**Cons:**
- Routes don't follow actual roads
- Less realistic for real-world planning

## Recommendation

**Use Option 1 (Python 3.11 Runtime)** - This is the cleanest solution with the highest probability of success. The OSM routing code is complete and tested; it just needs a compatible runtime environment.

If time is critical for the hackathon, **use Option 4** and document OSM routing as a "future enhancement" that's already implemented and ready to deploy once the runtime is upgraded.

## Files Ready for Deployment

All OSM routing code is complete and ready:
- `osm_routing/models.py` - Data structures with KDTree indexing
- `osm_routing/parser.py` - OSM PBF parser with caching
- `osm_routing/calculator.py` - A* pathfinding with 4 cost functions
- `osm_routing/renderer.py` - GeoJSON rendering
- `lambda_function.py` - Integration with Lambda handler
- `frontend/app.js` - Road network visualization
- `requirements-lambda.txt` - Dependencies (with sklearn instead of scipy)
- `Dockerfile.lambda` - Docker build for Lambda layer
- `deploy_lambda_with_layer.sh` - Deployment script

## Next Steps

1. **For Hackathon Demo**: Use current mathematical routing, mention OSM as "implemented but pending runtime upgrade"
2. **Post-Hackathon**: Upgrade to Python 3.11 runtime and deploy OSM routing
3. **Alternative**: Build on EC2 with devtoolset-8 and create compatible wheels

## Conclusion

The OSM routing feature is **100% implemented** and works locally. The only blocker is the AWS Lambda runtime environment. The current fallback system provides full functionality for the hackathon demo, and the OSM upgrade path is clear and straightforward.
