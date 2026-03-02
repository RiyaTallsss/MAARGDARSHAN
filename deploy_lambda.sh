#!/bin/bash
# MAARGDARSHAN - Lambda Deployment Script
# Deploys minimal Lambda function with Bedrock integration

set -e  # Exit on error

echo "=========================================="
echo "MAARGDARSHAN Lambda Deployment"
echo "=========================================="

# Configuration
FUNCTION_NAME="maargdarshan-api"
REGION="us-east-1"
RUNTIME="python3.9"
HANDLER="lambda_function.lambda_handler"
ROLE_NAME="maargdarshan-lambda-role"
TIMEOUT=30
MEMORY=512

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo "Step 1: Creating IAM Role for Lambda"
echo "--------------------------------------"

# Check if role exists
if aws iam get-role --role-name $ROLE_NAME 2>/dev/null; then
    echo -e "${YELLOW}Role $ROLE_NAME already exists${NC}"
    ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
else
    echo "Creating IAM role..."
    
    # Create trust policy
    cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create role
    ROLE_ARN=$(aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file://trust-policy.json \
        --query 'Role.Arn' \
        --output text)
    
    echo -e "${GREEN}✓ Role created: $ROLE_ARN${NC}"
    
    # Attach policies
    echo "Attaching policies..."
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
    
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
    
    echo -e "${GREEN}✓ Policies attached${NC}"
    
    # Wait for role to propagate
    echo "Waiting for role to propagate (10 seconds)..."
    sleep 10
    
    rm trust-policy.json
fi

echo ""
echo "Step 2: Creating Deployment Package"
echo "--------------------------------------"

# Create deployment directory
rm -rf lambda-package
mkdir -p lambda-package

# Copy Lambda function
cp lambda_function.py lambda-package/

# Install dependencies (boto3 is included in Lambda runtime, but we'll add it anyway)
echo "Installing dependencies..."
pip install -r requirements-lambda.txt -t lambda-package/ --quiet

# Create ZIP file
echo "Creating deployment package..."
cd lambda-package
zip -r ../lambda-deployment.zip . -q
cd ..

echo -e "${GREEN}✓ Deployment package created: lambda-deployment.zip${NC}"
echo "   Size: $(du -h lambda-deployment.zip | cut -f1)"

echo ""
echo "Step 3: Deploying Lambda Function"
echo "--------------------------------------"

# Check if function exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>/dev/null; then
    echo "Updating existing function..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://lambda-deployment.zip \
        --region $REGION \
        --no-cli-pager
    
    echo "Updating function configuration..."
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --timeout $TIMEOUT \
        --memory-size $MEMORY \
        --environment "Variables={S3_BUCKET=maargdarshan-data,BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0}" \
        --region $REGION \
        --no-cli-pager
    
    echo -e "${GREEN}✓ Function updated${NC}"
else
    echo "Creating new function..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role $ROLE_ARN \
        --handler $HANDLER \
        --zip-file fileb://lambda-deployment.zip \
        --timeout $TIMEOUT \
        --memory-size $MEMORY \
        --environment "Variables={S3_BUCKET=maargdarshan-data,BEDROCK_MODEL=anthropic.claude-3-haiku-20240307-v1:0}" \
        --region $REGION \
        --no-cli-pager
    
    echo -e "${GREEN}✓ Function created${NC}"
fi

echo ""
echo "Step 4: Creating API Gateway"
echo "--------------------------------------"

# Create REST API
API_NAME="maargdarshan-api"

# Check if API exists
API_ID=$(aws apigateway get-rest-apis --region $REGION --query "items[?name=='$API_NAME'].id" --output text)

if [ -z "$API_ID" ]; then
    echo "Creating API Gateway..."
    API_ID=$(aws apigateway create-rest-api \
        --name $API_NAME \
        --description "MAARGDARSHAN Rural Infrastructure Planning API" \
        --region $REGION \
        --query 'id' \
        --output text)
    echo -e "${GREEN}✓ API created: $API_ID${NC}"
else
    echo -e "${YELLOW}API already exists: $API_ID${NC}"
fi

# Get root resource ID
ROOT_ID=$(aws apigateway get-resources \
    --rest-api-id $API_ID \
    --region $REGION \
    --query 'items[?path==`/`].id' \
    --output text)

# Create /routes resource
ROUTES_ID=$(aws apigateway get-resources \
    --rest-api-id $API_ID \
    --region $REGION \
    --query "items[?pathPart=='routes'].id" \
    --output text)

if [ -z "$ROUTES_ID" ]; then
    echo "Creating /routes resource..."
    ROUTES_ID=$(aws apigateway create-resource \
        --rest-api-id $API_ID \
        --parent-id $ROOT_ID \
        --path-part routes \
        --region $REGION \
        --query 'id' \
        --output text)
    echo -e "${GREEN}✓ Resource created${NC}"
fi

# Create POST method
echo "Setting up POST method..."
aws apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $ROUTES_ID \
    --http-method POST \
    --authorization-type NONE \
    --region $REGION \
    --no-cli-pager 2>/dev/null || echo "Method already exists"

# Set up Lambda integration
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
LAMBDA_ARN="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION_NAME"

aws apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $ROUTES_ID \
    --http-method POST \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations" \
    --region $REGION \
    --no-cli-pager 2>/dev/null || echo "Integration already exists"

# Add Lambda permission for API Gateway
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id apigateway-invoke \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_ID/*/*" \
    --region $REGION \
    --no-cli-pager 2>/dev/null || echo "Permission already exists"

# Enable CORS
echo "Enabling CORS..."
aws apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $ROUTES_ID \
    --http-method OPTIONS \
    --authorization-type NONE \
    --region $REGION \
    --no-cli-pager 2>/dev/null || echo "OPTIONS method already exists"

aws apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $ROUTES_ID \
    --http-method OPTIONS \
    --type MOCK \
    --request-templates '{"application/json": "{\"statusCode\": 200}"}' \
    --region $REGION \
    --no-cli-pager 2>/dev/null || echo "OPTIONS integration already exists"

# Deploy API
echo "Deploying API..."
aws apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name prod \
    --region $REGION \
    --no-cli-pager

echo -e "${GREEN}✓ API deployed${NC}"

# Get API URL
API_URL="https://$API_ID.execute-api.$REGION.amazonaws.com/prod/routes"

echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo -e "${GREEN}✓ Lambda Function:${NC} $FUNCTION_NAME"
echo -e "${GREEN}✓ API Gateway:${NC} $API_ID"
echo -e "${GREEN}✓ API URL:${NC} $API_URL"
echo ""
echo "Test your API:"
echo "curl -X POST $API_URL \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"start\": {\"lat\": 30.7268, \"lon\": 78.4354}, \"end\": {\"lat\": 30.9993, \"lon\": 78.9394}}'"
echo ""
echo "Save this URL for your frontend!"
echo ""

# Save URL to file
echo $API_URL > api-url.txt
echo "API URL saved to: api-url.txt"

# Cleanup
rm -rf lambda-package
echo ""
echo "Deployment package cleaned up"
echo ""
