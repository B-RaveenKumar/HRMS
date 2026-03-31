#!/usr/bin/env python3
"""Test the chatbot with fallback AI responses"""

import requests
import json
import time

# Give the server a moment to start
time.sleep(2)

# Test data
base_url = "http://localhost:5000"
login_url = f"{base_url}/login"
ai_engine_url = f"{base_url}/ai_engine"

# Create a session
session = requests.Session()

# Login as patient
print("=" * 60)
print("STEP 1: Logging in as patient...")
print("=" * 60)

login_data = {
    'email': 'patient@hospital.com',
    'password': 'Patient@123'
}

response = session.post(login_url, data=login_data)
print(f"Login Status: {response.status_code}")
print(f"Redirected to: {response.url}")

# Test the chatbot with different messages
test_messages = [
    "I have a headache",
    "What should I do for a fever?",
    "How do I schedule an appointment?",
    "I'm feeling sick"
]

print("\n" + "=" * 60)
print("STEP 2: Testing AI Chatbot with Fallback System...")
print("=" * 60)

for msg in test_messages:
    print(f"\nUser Message: {msg}")
    print("-" * 40)
    
    response = session.post(
        ai_engine_url,
        json={"message": msg},
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"Status: {response.status_code}")
        print(f"Source: {data.get('source', 'unknown')}")
        print(f"AI Response:\n{data.get('reply', 'No reply')}")
        if 'error' in data:
            print(f"Error Note: {data['error']}")
    else:
        print(f"Error: Status {response.status_code}")
        print(f"Response: {response.text}")
    
    print()

print("=" * 60)
print("Chatbot test completed!")
print("=" * 60)
