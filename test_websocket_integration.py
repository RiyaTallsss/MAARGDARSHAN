#!/usr/bin/env python3
"""
Simple test script to verify WebSocket integration and background processing.
"""

import asyncio
import json
import websockets
import requests
from datetime import datetime

async def test_websocket_connection():
    """Test WebSocket connection for progress updates."""
    print("Testing WebSocket connection...")
    
    try:
        # Test connection to status WebSocket
        uri = "ws://localhost:8000/ws/status"
        
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket connection established")
            
            # Send ping message
            ping_message = {
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(ping_message))
            print("✓ Ping message sent")
            
            # Wait for pong response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if response_data.get("type") == "pong":
                print("✓ Pong response received")
            else:
                print(f"✗ Unexpected response: {response_data}")
            
            # Test getting queue status
            queue_message = {
                "type": "get_queue_status"
            }
            
            await websocket.send(json.dumps(queue_message))
            print("✓ Queue status request sent")
            
            # Wait for queue status response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if response_data.get("type") == "queue_status":
                print("✓ Queue status received")
                print(f"  Queue length: {response_data.get('data', {}).get('queue_length', 'unknown')}")
            else:
                print(f"✗ Unexpected queue status response: {response_data}")
                
    except Exception as e:
        print(f"✗ WebSocket test failed: {e}")

def test_api_endpoints():
    """Test REST API endpoints."""
    print("\nTesting REST API endpoints...")
    
    base_url = "http://localhost:8000"
    
    try:
        # Test health check
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Health check endpoint working")
        else:
            print(f"✗ Health check failed: {response.status_code}")
        
        # Test data source status
        response = requests.get(f"{base_url}/api/status/data-sources", timeout=10)
        if response.status_code == 200:
            print("✓ Data source status endpoint working")
            data = response.json()
            print(f"  System status: {data.get('system_status', 'unknown')}")
            print(f"  Data sources: {len(data.get('data_sources', []))}")
        else:
            print(f"✗ Data source status failed: {response.status_code}")
        
        # Test cache info
        response = requests.get(f"{base_url}/api/cache/info", timeout=5)
        if response.status_code == 200:
            print("✓ Cache info endpoint working")
            data = response.json()
            print(f"  Cache entries: {data.get('total_entries', 'unknown')}")
        else:
            print(f"✗ Cache info failed: {response.status_code}")
        
        # Test queue status
        response = requests.get(f"{base_url}/api/tasks/queue/status", timeout=5)
        if response.status_code == 200:
            print("✓ Queue status endpoint working")
            data = response.json()
            print(f"  Queue length: {data.get('queue_length', 'unknown')}")
        else:
            print(f"✗ Queue status failed: {response.status_code}")
            
    except Exception as e:
        print(f"✗ API test failed: {e}")

def test_background_task_submission():
    """Test background task submission."""
    print("\nTesting background task submission...")
    
    base_url = "http://localhost:8000"
    
    try:
        # Submit a simple background task
        task_data = {
            "name": "Test Route Generation",
            "function_name": "generate_routes_background",
            "args": [
                {"latitude": 30.0, "longitude": 78.0},
                {"latitude": 30.1, "longitude": 78.1}
            ],
            "kwargs": {"num_alternatives": 2},
            "priority": "normal",
            "timeout_seconds": 60
        }
        
        response = requests.post(
            f"{base_url}/api/tasks/submit",
            json=task_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✓ Background task submitted successfully")
            data = response.json()
            task_id = data.get("task_id")
            print(f"  Task ID: {task_id}")
            
            # Check task status
            if task_id:
                status_response = requests.get(
                    f"{base_url}/api/tasks/{task_id}/status",
                    timeout=5
                )
                
                if status_response.status_code == 200:
                    print("✓ Task status retrieved")
                    status_data = status_response.json()
                    print(f"  Status: {status_data.get('status', 'unknown')}")
                else:
                    print(f"✗ Task status failed: {status_response.status_code}")
        else:
            print(f"✗ Background task submission failed: {response.status_code}")
            print(f"  Response: {response.text}")
            
    except Exception as e:
        print(f"✗ Background task test failed: {e}")

async def main():
    """Run all tests."""
    print("=== WebSocket and Background Processing Integration Test ===")
    print(f"Test started at: {datetime.now().isoformat()}")
    print()
    
    # Test REST API endpoints first
    test_api_endpoints()
    
    # Test background task submission
    test_background_task_submission()
    
    # Test WebSocket connection
    await test_websocket_connection()
    
    print()
    print("=== Test completed ===")

if __name__ == "__main__":
    asyncio.run(main())