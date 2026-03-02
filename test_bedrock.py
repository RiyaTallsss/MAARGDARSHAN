import boto3
import json

# Create Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Test with Claude Haiku (cheapest model)
try:
    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-haiku-20240307-v1:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": "Say hello!"
                }
            ]
        })
    )
    
    result = json.loads(response['body'].read())
    print("✅ Bedrock is working!")
    print(f"Response: {result['content'][0]['text']}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nIf you see 'use case' error, you need to submit use case details in AWS Console")
