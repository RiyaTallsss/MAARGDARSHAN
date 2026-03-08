#!/bin/bash
# MAARGDARSHAN - Lambda Deployment with Layer
# Deploys minimal Lambda function code (dependencies in layer)

set -e

echo "=========================================="
echo "MAARGDARSHAN Lambda Deployment (with Layer)"
echo "=========================================="

FUNCTION_NAME="maargdarshan-api"
REGION="us-east-1"
LAYER_ARN="arn:aws:lambda:us-east-1:273354629315:layer:maargdarshan-osm-dependencies:2"

echo ""
echo "Step 1: Creating Minimal Deployment Package"
echo "--------------------------------------"

# Create deployment directory
rm -rf lambda-package-minimal
mkdir -p lambda-package-minimal

# Copy only our code (no dependencies)
cp lambda_function.py lambda-package-minimal/
cp -r osm_routing lambda-package-minimal/

# Create ZIP file
echo "Creating deployment package..."
cd lambda-package-minimal
zip -r ../lambda-deployment-minimal.zip . -q
cd ..

echo "✓ Deployment package created: lambda-deployment-minimal.zip"
echo "   Size: $(du -h lambda-deployment-minimal.zip | cut -f1)"

echo ""
echo "Step 2: Uploading to S3"
echo "--------------------------------------"

S3_BUCKET="maargdarshan-data"
S3_KEY="lambda/lambda-deployment-minimal.zip"

aws s3 cp lambda-deployment-minimal.zip s3://$S3_BUCKET/$S3_KEY
echo "✓ Uploaded to s3://$S3_BUCKET/$S3_KEY"

echo ""
echo "Step 3: Updating Lambda Function"
echo "--------------------------------------"

# Update function code
echo "Updating function code..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --s3-bucket $S3_BUCKET \
    --s3-key $S3_KEY \
    --region $REGION \
    --no-cli-pager

echo "Waiting for function update to complete..."
aws lambda wait function-updated \
    --function-name $FUNCTION_NAME \
    --region $REGION

# Attach layer
echo "Attaching layer..."
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --layers $LAYER_ARN \
    --region $REGION \
    --no-cli-pager

echo "✓ Function updated with layer"

echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "✓ Lambda Function: $FUNCTION_NAME"
echo "✓ Layer: $LAYER_ARN"
echo ""

# Cleanup
rm -rf lambda-package-minimal
echo "Deployment package cleaned up"
echo ""
