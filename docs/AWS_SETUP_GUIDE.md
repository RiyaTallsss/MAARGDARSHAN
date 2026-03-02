# 🔐 AWS Setup Guide for MAARGDARSHAN

## Step 1: Create AWS Account (if you don't have one)

1. Go to: https://aws.amazon.com/
2. Click "Create an AWS Account"
3. Follow the signup process
4. **Important:** You'll need a credit card, but we'll stay within free tier

---

## Step 2: Redeem AWS Credits ($300 for Hackathon)

### Credit 1: $100 AWS Activate Signup Credit
1. Go to: https://aws.amazon.com/activate/
2. Sign up for AWS Activate
3. Apply credit code (if provided by hackathon)

### Credit 2: $100 AWS Exploration Credit
1. Check hackathon portal for exploration credit code
2. Go to: AWS Console → Billing → Credits
3. Enter credit code

### Credit 3: $100 Hackathon-Specific Credit
1. Check "AI for Bharat Hackathon" portal
2. Look for AWS credit redemption instructions
3. Apply hackathon-specific code

**Total Available:** $300 (more than enough for this project!)

---

## Step 3: Create IAM User (Security Best Practice)

**Why?** Don't use root account credentials for development.

### 3.1 Create IAM User

1. **Login to AWS Console:** https://console.aws.amazon.com/
2. **Go to IAM:** Search "IAM" in top search bar
3. **Click "Users"** (left sidebar)
4. **Click "Create user"**
5. **User name:** `maargdarshan-dev`
6. **Click "Next"**

### 3.2 Set Permissions

1. **Select:** "Attach policies directly"
2. **Search and check these policies:**
   - ✅ `AmazonS3FullAccess` (for data storage)
   - ✅ `AWSLambda_FullAccess` (for backend deployment)
   - ✅ `AmazonAPIGatewayAdministrator` (for API)
   - ✅ `AmazonBedrockFullAccess` (for AI)
   - ✅ `CloudWatchLogsFullAccess` (for debugging)
3. **Click "Next"**
4. **Click "Create user"**

### 3.3 Create Access Keys

1. **Click on the user** you just created (`maargdarshan-dev`)
2. **Go to "Security credentials" tab**
3. **Scroll to "Access keys"**
4. **Click "Create access key"**
5. **Select:** "Command Line Interface (CLI)"
6. **Check:** "I understand the above recommendation"
7. **Click "Next"**
8. **Description:** "MAARGDARSHAN hackathon development"
9. **Click "Create access key"**

### 3.4 SAVE YOUR CREDENTIALS! 🚨

You'll see:
```
Access key ID: AKIAIOSFODNN7EXAMPLE
Secret access key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**⚠️ CRITICAL:** Save these NOW! You can't see the secret key again!

**Save to a file temporarily:**
```bash
# Create a temporary file (we'll delete this later)
cat > ~/aws-credentials-temp.txt << EOF
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
EOF
```

---

## Step 4: Configure AWS CLI

### 4.1 Install AWS CLI (if not installed)

**Check if installed:**
```bash
aws --version
```

**If not installed:**

**macOS:**
```bash
brew install awscli
```

**Alternative (Python):**
```bash
pip install awscli
```

### 4.2 Configure Credentials

**Method 1: Interactive (Recommended)**
```bash
aws configure
```

**Enter when prompted:**
```
AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
Default region name [None]: us-east-1
Default output format [None]: json
```

**Method 2: Manual File Creation**
```bash
# Create AWS config directory
mkdir -p ~/.aws

# Create credentials file
cat > ~/.aws/credentials << EOF
[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
EOF

# Create config file
cat > ~/.aws/config << EOF
[default]
region = us-east-1
output = json
EOF
```

### 4.3 Test Configuration

```bash
# Test AWS CLI
aws sts get-caller-identity
```

**Expected output:**
```json
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/maargdarshan-dev"
}
```

**If you see this, you're configured! ✅**

---

## Step 5: Enable Amazon Bedrock

### 5.1 Request Model Access

1. **Go to Bedrock Console:** https://console.aws.amazon.com/bedrock/
2. **Click "Model access"** (left sidebar)
3. **Click "Manage model access"** (top right)
4. **Find and enable:**
   - ✅ **Anthropic Claude 3 Sonnet** (recommended)
   - ✅ **Anthropic Claude 3 Haiku** (cheaper alternative)
   - ✅ **Anthropic Claude Instant** (fastest)
5. **Click "Request model access"**
6. **Wait 2-5 minutes** for approval (usually instant)

### 5.2 Verify Bedrock Access

```bash
# List available models
aws bedrock list-foundation-models --region us-east-1
```

**Expected:** JSON list of Claude models

---

## Step 6: Set Up Environment Variables

### 6.1 Create .env File

```bash
# In your project root
cat > .env << EOF
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# S3 Configuration
S3_BUCKET=maargdarshan-data
S3_REGION=us-east-1

# Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1

# API Configuration (for later)
API_KEY=your-demo-api-key-here
EOF
```

### 6.2 Add .env to .gitignore

```bash
# Make sure .env is in .gitignore
echo ".env" >> .gitignore
```

**⚠️ NEVER commit .env to GitHub!**

---

## Step 7: Now Create S3 Bucket and Upload Data

### 7.1 Create Data Folder Structure

```bash
# Create folders
mkdir -p data/uttarkashi/{dem,osm,rainfall,floods}

# Copy files (run each command separately)
cp Uttarkashi_Terrain/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif data/uttarkashi/dem/

cp Maps/northern-zone-260121.osm.pbf data/uttarkashi/osm/

cp Rainfall/Rainfall_2016_districtwise.csv data/uttarkashi/rainfall/

cp Floods/Flood_Affected_Area_Atlas_of_India.pdf data/uttarkashi/floods/
```

### 7.2 Create S3 Bucket

```bash
# Create bucket
aws s3 mb s3://maargdarshan-data --region us-east-1
```

**Expected output:**
```
make_bucket: maargdarshan-data
```

### 7.3 Upload Data to S3

```bash
# Upload all data
aws s3 sync data/uttarkashi/ s3://maargdarshan-data/ --region us-east-1
```

**Expected output:**
```
upload: data/uttarkashi/dem/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif to s3://maargdarshan-data/dem/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif
upload: data/uttarkashi/osm/northern-zone-260121.osm.pbf to s3://maargdarshan-data/osm/northern-zone-260121.osm.pbf
upload: data/uttarkashi/rainfall/Rainfall_2016_districtwise.csv to s3://maargdarshan-data/rainfall/Rainfall_2016_districtwise.csv
upload: data/uttarkashi/floods/Flood_Affected_Area_Atlas_of_India.pdf to s3://maargdarshan-data/floods/Flood_Affected_Area_Atlas_of_India.pdf
```

### 7.4 Verify Upload

```bash
# List files in bucket
aws s3 ls s3://maargdarshan-data/ --recursive --human-readable
```

**Expected:** List of all uploaded files with sizes

### 7.5 Set Bucket Policy (Public Read for Demo)

```bash
# Create policy file
cat > bucket-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::maargdarshan-data/*"
    }
  ]
}
EOF

# Apply policy
aws s3api put-bucket-policy --bucket maargdarshan-data --policy file://bucket-policy.json
```

**⚠️ Note:** This makes data publicly readable (fine for demo, not for production)

---

## Step 8: Update Code to Use S3

### 8.1 Install boto3 (if not installed)

```bash
pip install boto3
```

### 8.2 Update Configuration File

Edit `rural_infrastructure_planning/config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
S3_BUCKET = os.getenv('S3_BUCKET', 'maargdarshan-data')

# Data Paths (S3)
DEM_PATH = f"s3://{S3_BUCKET}/dem/P5_PAN_CD_N30_000_E078_000_DEM_30m.tif"
OSM_PATH = f"s3://{S3_BUCKET}/osm/northern-zone-260121.osm.pbf"
RAINFALL_PATH = f"s3://{S3_BUCKET}/rainfall/Rainfall_2016_districtwise.csv"
FLOOD_PATH = f"s3://{S3_BUCKET}/floods/Flood_Affected_Area_Atlas_of_India.pdf"

# Bedrock Configuration
BEDROCK_MODEL_ID = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')
BEDROCK_REGION = os.getenv('BEDROCK_REGION', 'us-east-1')
```

---

## Step 9: Test Everything Locally

### 9.1 Test S3 Access

```python
# test_s3_access.py
import boto3
from dotenv import load_dotenv
import os

load_dotenv()

s3 = boto3.client('s3', region_name='us-east-1')

# List files in bucket
response = s3.list_objects_v2(Bucket='maargdarshan-data')

print("Files in S3 bucket:")
for obj in response.get('Contents', []):
    print(f"  - {obj['Key']} ({obj['Size']} bytes)")
```

**Run:**
```bash
python test_s3_access.py
```

### 9.2 Test Bedrock Access

```python
# test_bedrock_access.py
import boto3
from dotenv import load_dotenv

load_dotenv()

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Test simple prompt
response = bedrock.invoke_model(
    modelId='anthropic.claude-3-haiku-20240307-v1:0',
    body='{"prompt": "Human: Say hello!\\n\\nAssistant:", "max_tokens_to_sample": 100}'
)

print("Bedrock response:", response)
```

**Run:**
```bash
python test_bedrock_access.py
```

---

## 🎯 Checklist - Are You Ready?

- [ ] AWS account created
- [ ] IAM user created with proper permissions
- [ ] AWS CLI installed and configured
- [ ] `aws sts get-caller-identity` works
- [ ] Amazon Bedrock access enabled
- [ ] S3 bucket created: `maargdarshan-data`
- [ ] Data uploaded to S3 (4 files)
- [ ] `.env` file created with credentials
- [ ] `.env` added to `.gitignore`
- [ ] boto3 installed
- [ ] S3 access test passes
- [ ] Bedrock access test passes

**If all checked, you're ready for deployment! 🚀**

---

## 💰 Cost Tracking

### Expected Costs (within $300 budget)

**S3 Storage:**
- 275 MB data = $0.01/month
- Data transfer: ~$0.50 for demo

**Lambda:**
- Free tier: 1M requests/month
- Expected: <1000 requests = $0

**API Gateway:**
- Free tier: 1M requests/month
- Expected: <1000 requests = $0

**Bedrock (Claude):**
- Input: $0.003 per 1K tokens
- Output: $0.015 per 1K tokens
- Expected: 100 requests × 2K tokens = $3-5

**CloudFront (optional):**
- Free tier: 1 TB transfer
- Expected: <1 GB = $0

**Total Expected: $5-10** (well within $300 budget!)

---

## 🚨 Troubleshooting

### Error: "InvalidToken"
**Solution:** AWS credentials not configured
```bash
aws configure
# Re-enter your credentials
```

### Error: "Access Denied"
**Solution:** IAM user needs more permissions
- Go to IAM Console
- Add missing policy to user

### Error: "Bucket already exists"
**Solution:** Bucket names are globally unique
```bash
# Try a different name
aws s3 mb s3://maargdarshan-data-yourname-2026
```

### Error: "Bedrock model not available"
**Solution:** Request model access
- Go to Bedrock Console → Model access
- Enable Claude models

---

## 🔒 Security Best Practices

1. **Never commit credentials to GitHub**
   - Always use `.env` files
   - Add `.env` to `.gitignore`

2. **Use IAM users, not root account**
   - Root account = full access (dangerous)
   - IAM user = limited permissions (safer)

3. **Rotate credentials after hackathon**
   - Delete access keys when done
   - Create new ones for production

4. **Monitor costs**
   - Set up billing alerts in AWS Console
   - Check costs daily during development

---

## 📞 Need Help?

**AWS Support:**
- Free tier support: https://console.aws.amazon.com/support/
- Documentation: https://docs.aws.amazon.com/

**Hackathon Support:**
- Check hackathon Discord/Slack
- Ask mentors about AWS credit codes

---

**Next Steps:** Once AWS is configured, proceed to backend deployment!
