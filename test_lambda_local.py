#!/usr/bin/env python3
"""
Test Lambda function locally before deployment
"""

import json
from lambda_function import lambda_handler

# Test event
test_event = {
    'body': json.dumps({
        'start': {
            'lat': 30.7268,
            'lon': 78.4354
        },
        'end': {
            'lat': 30.9993,
            'lon': 78.9394
        },
        'context': 'Planning route from Uttarkashi to Gangotri for rural connectivity'
    })
}

print("=" * 60)
print("Testing Lambda Function Locally")
print("=" * 60)
print()

try:
    result = lambda_handler(test_event, None)
    
    print(f"Status Code: {result['statusCode']}")
    print()
    
    if result['statusCode'] == 200:
        response_data = json.loads(result['body'])
        print("✅ SUCCESS!")
        print()
        print("Routes Generated:")
        for route in response_data['routes']:
            print(f"  - {route['name']}: {route['distance_km']} km, Risk: {route['risk_score']}/100")
        print()
        print("AI Explanation:")
        print(f"  {response_data['ai_explanation']}")
        print()
        print("Full Response:")
        print(json.dumps(response_data, indent=2))
    else:
        print("❌ ERROR!")
        print(result['body'])
        
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()
