#!/usr/bin/env python3
"""
End-to-end test script for Nervia AI API
Run this script to verify the API is working correctly
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

def test_api_health():
    """Test API health endpoint"""
    print("Testing API health...")
    response = requests.get("http://localhost:8000/health")
    assert response.status_code == 200
    print("✓ API is healthy")
    return True

def test_register_and_login():
    """Test user registration and login"""
    print("\nTesting user registration...")
    
    # Register
    register_data = {
        "email": f"test_{int(time.time())}@example.com",
        "full_name": "Test User",
        "password": "TestPass123"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    assert response.status_code == 201
    user = response.json()
    print(f"✓ User registered: {user['email']}")
    
    # Login
    print("Testing user login...")
    login_data = {
        "email": register_data["email"],
        "password": register_data["password"]
    }
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    print("✓ User logged in successfully")
    
    return tokens["access_token"]

def test_create_campaign(token):
    """Test campaign creation"""
    print("\nTesting campaign creation...")
    headers = {"Authorization": f"Bearer {token}"}
    
    campaign_data = {
        "name": "Test Campaign",
        "description": "Test Description",
        "language": "es"
    }
    response = requests.post(
        f"{BASE_URL}/campaigns",
        json=campaign_data,
        headers=headers
    )
    assert response.status_code == 201
    campaign = response.json()
    print(f"✓ Campaign created: {campaign['name']}")
    return campaign["id"]

def test_generate_ai_plan(token, campaign_id):
    """Test AI plan generation"""
    print("\nTesting AI plan generation...")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.post(
        f"{BASE_URL}/campaigns/{campaign_id}/generate-plan",
        headers=headers
    )
    assert response.status_code == 200
    campaign = response.json()
    assert campaign["status"] == "ai_plan_created"
    assert campaign["ai_plan"] is not None
    print("✓ AI plan generated")
    return campaign

def main():
    """Run all E2E tests"""
    print("=" * 50)
    print("Nervia AI - End-to-End Tests")
    print("=" * 50)
    
    try:
        # Test 1: Health check
        test_api_health()
        
        # Test 2: Auth
        token = test_register_and_login()
        
        # Test 3: Campaign
        campaign_id = test_create_campaign(token)
        
        # Test 4: AI Plan
        test_generate_ai_plan(token, campaign_id)
        
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
