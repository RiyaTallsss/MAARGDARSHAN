# 🚀 Deploy Backend NOW - 30 Minute Guide

**Time:** 22:30 IST  
**Goal:** Get your API live in 30 minutes!

---

## ✅ What I Just Created:

1. **`lambda_function.py`** - Minimal Lambda function with:
   - Mock route generation (3 alternatives)
   - Real Bedrock AI explanations
   - S3 data source references
   - CORS enabled

2. **`deploy_lambda.sh`** - Automated deployment script
   - Creates IAM role
   - Packages Lambda
   - Deploys to AWS
   - Sets up API Gateway
   - Returns live API URL

3. **`test_lambda_local.py`** - Local test before deployment

4. **`requirements-lambda.txt`** - Minimal dependencies

---

## 🎯 30-Minute Deployment Steps

### Step 1: Test Locally (5 minutes)

```bash
# Make sure you're in venv
source venv/bin/activate

# Test the Lambda function locally
python test_lambda_local.py
```

**Expected output:**
```
✅ SUCCESS!

Routes Generated:
  - Shortest Route: 95.5 km, Risk: 65/100
  - Safest Route: 114.6 km, Risk: 40/100
  - Most Cost-Effective: 105.05 km, Risk: 55/100

AI Explanation:
  This route offers optimal balance between distance and safety...
```

**If this works, proceed to Step 2!**

---

### Step 2: Deploy to AWS (10 minutes)

```bash
# Make deployment script executable
chmod +x deploy_lambda.sh

# Run deployment
./deploy_lambda.sh
```

**What it does:**
1. Creates IAM role with permissions (2 min)
2. Packages Lambda function (1 min)
3. Deploys to AWS Lambda (2 min)
4. Creates API Gateway (3 min)
5. Configures CORS (1 min)
6. Returns API URL (1 min)

**Expected output:**
```
==========================================
DEPLOYMENT COMPLETE!
==========================================

✓ Lambda Function: maargdarshan-api
✓ API Gateway: abc123xyz
✓ API URL: https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/routes

Test your API:
curl -X POST https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/routes \
  -H 'Content-Type: application/json' \
  -d '{"start": {"lat": 30.7268, "lon": 78.4354}, "end": {"lat": 30.9993, "lon": 78.9394}}'
```

**Save that API URL!** You'll need it for the frontend.

---

### Step 3: Test Live API (5 minutes)

```bash
# The deployment script will show you a curl command
# Copy and run it to test

# Or use this test script:
cat > test_api.sh << 'EOF'
#!/bin/bash
API_URL=$(cat api-url.txt)

curl -X POST $API_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "start": {"lat": 30.7268, "lon": 78.4354},
    "end": {"lat": 30.9993, "lon": 78.9394},
    "context": "Route from Uttarkashi to Gangotri"
  }' | python -m json.tool
EOF

chmod +x test_api.sh
./test_api.sh
```

**Expected:** JSON response with 3 routes and AI explanation

---

### Step 4: Save API URL (1 minute)

```bash
# API URL is saved in api-url.txt
cat api-url.txt

# Add to .env file
echo "API_URL=$(cat api-url.txt)" >> .env
```

---

## 🎉 You're Done!

**Total Time:** ~20-30 minutes

**What You Have:**
- ✅ Live Lambda function
- ✅ Public API endpoint
- ✅ Bedrock AI integration working
- ✅ CORS enabled for frontend
- ✅ Mock route generation (good enough for demo!)

---

## 🧪 Testing Checklist

Test these scenarios:

### Test 1: Uttarkashi to Gangotri
```json
{
  "start": {"lat": 30.7268, "lon": 78.4354},
  "end": {"lat": 30.9993, "lon": 78.9394}
}
```

### Test 2: Uttarkashi to Harsil
```json
{
  "start": {"lat": 30.7268, "lon": 78.4354},
  "end": {"lat": 31.0500, "lon": 78.5667}
}
```

### Test 3: Custom Route
```json
{
  "start": {"lat": 30.5, "lon": 78.2},
  "end": {"lat": 31.2, "lon": 79.0}
}
```

---

## 🐛 Troubleshooting

### Error: "Role not found"
**Solution:** Wait 10 seconds and try again (IAM propagation delay)

### Error: "Access Denied"
**Solution:** Check AWS credentials:
```bash
aws sts get-caller-identity
```

### Error: "Function already exists"
**Solution:** Script will update existing function automatically

### Error: "Bedrock access denied"
**Solution:** Make sure Bedrock is enabled (we tested this earlier!)

### Lambda times out
**Solution:** Increase timeout in script (line 13: `TIMEOUT=60`)

---

## 📊 What's Next?

After deployment:

1. **Frontend** (tomorrow morning, 2 hours)
   - Create simple HTML + Leaflet map
   - Call your API
   - Display routes
   - Deploy to S3

2. **Demo Video** (tomorrow afternoon, 1 hour)
   - Record screen showing:
     - Enter coordinates
     - Generate routes
     - Show AI explanation
     - Display on map

3. **PPT** (tomorrow evening, 1 hour)
   - 8 slides
   - Architecture diagram
   - Demo screenshots
   - AWS services used

---

## 💡 Pro Tips

1. **Test locally first** - Saves debugging time on AWS
2. **Save API URL** - You'll need it multiple times
3. **Check CloudWatch Logs** - If something fails:
   ```bash
   aws logs tail /aws/lambda/maargdarshan-api --follow
   ```
4. **API Gateway has caching** - Changes may take 30 seconds to appear

---

## 🎯 Success Criteria

You're successful if:
- ✅ `test_lambda_local.py` returns routes
- ✅ Deployment script completes without errors
- ✅ curl test returns JSON with 3 routes
- ✅ AI explanation is present in response
- ✅ API URL is saved

---

## 📞 Quick Commands Reference

```bash
# Test locally
python test_lambda_local.py

# Deploy
./deploy_lambda.sh

# Test API
./test_api.sh

# Check logs
aws logs tail /aws/lambda/maargdarshan-api --follow

# Update function
aws lambda update-function-code \
  --function-name maargdarshan-api \
  --zip-file fileb://lambda-deployment.zip

# Delete everything (if you want to start over)
aws lambda delete-function --function-name maargdarshan-api
aws apigateway delete-rest-api --rest-api-id $(aws apigateway get-rest-apis --query "items[?name=='maargdarshan-api'].id" --output text)
aws iam detach-role-policy --role-name maargdarshan-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam detach-role-policy --role-name maargdarshan-lambda-role --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
aws iam detach-role-policy --role-name maargdarshan-lambda-role --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
aws iam delete-role --role-name maargdarshan-lambda-role
```

---

## 🚀 Ready? Let's Deploy!

**Run these commands NOW:**

```bash
# 1. Test locally
python test_lambda_local.py

# 2. If test passes, deploy!
chmod +x deploy_lambda.sh
./deploy_lambda.sh

# 3. Test live API
./test_api.sh
```

**Time to complete:** 20-30 minutes

**Let's do this!** 🎉
