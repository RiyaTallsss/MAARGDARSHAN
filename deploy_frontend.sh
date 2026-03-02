#!/bin/bash
# MAARGDARSHAN - Frontend Deployment to S3
# Deploys static website to S3 with public access

set -e  # Exit on error

echo "=========================================="
echo "MAARGDARSHAN Frontend Deployment"
echo "=========================================="

# Configuration
BUCKET_NAME="maargdarshan-frontend"
REGION="us-east-1"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "Step 1: Creating S3 Bucket for Website"
echo "--------------------------------------"

# Check if bucket exists
if aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null; then
    echo -e "${YELLOW}Bucket $BUCKET_NAME already exists${NC}"
else
    echo "Creating bucket..."
    aws s3 mb s3://$BUCKET_NAME --region $REGION
    echo -e "${GREEN}✓ Bucket created${NC}"
fi

echo ""
echo "Step 2: Configuring Static Website Hosting"
echo "--------------------------------------"

aws s3 website s3://$BUCKET_NAME \
    --index-document index.html \
    --error-document index.html

echo -e "${GREEN}✓ Website hosting enabled${NC}"

echo ""
echo "Step 3: Setting Bucket Policy (Public Read)"
echo "--------------------------------------"

# Create bucket policy
cat > /tmp/bucket-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
    --bucket $BUCKET_NAME \
    --policy file:///tmp/bucket-policy.json

rm /tmp/bucket-policy.json

echo -e "${GREEN}✓ Bucket policy applied${NC}"

echo ""
echo "Step 4: Uploading Frontend Files"
echo "--------------------------------------"

# Upload files
aws s3 sync frontend/ s3://$BUCKET_NAME/ \
    --cache-control "max-age=300" \
    --exclude "README.md"

echo -e "${GREEN}✓ Files uploaded${NC}"

echo ""
echo "Step 5: Setting Content Types"
echo "--------------------------------------"

# Set correct content types
aws s3 cp s3://$BUCKET_NAME/index.html s3://$BUCKET_NAME/index.html \
    --content-type "text/html" \
    --metadata-directive REPLACE

aws s3 cp s3://$BUCKET_NAME/app.js s3://$BUCKET_NAME/app.js \
    --content-type "application/javascript" \
    --metadata-directive REPLACE

echo -e "${GREEN}✓ Content types set${NC}"

# Get website URL
WEBSITE_URL="http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"

echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo -e "${GREEN}✓ Frontend deployed successfully!${NC}"
echo ""
echo "Your Live Website URL:"
echo "$WEBSITE_URL"
echo ""
echo "Test your website:"
echo "1. Open the URL in your browser"
echo "2. Press 'D' to load sample coordinates"
echo "3. Click 'Generate Routes with AI'"
echo "4. Watch the magic happen!"
echo ""

# Save URL to file
echo $WEBSITE_URL > website-url.txt
echo "Website URL saved to: website-url.txt"
echo ""

# Test if website is accessible
echo "Testing website accessibility..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $WEBSITE_URL)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Website is live and accessible!${NC}"
else
    echo -e "${YELLOW}⚠ Website returned HTTP $HTTP_CODE (may take a minute to propagate)${NC}"
fi

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Open: $WEBSITE_URL"
echo "2. Test the interactive map"
echo "3. Record demo video"
echo "4. Create PPT presentation"
echo "5. Submit to hackathon!"
echo ""
echo "🎉 You're almost done!"
echo ""
