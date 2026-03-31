#!/usr/bin/env python3
"""Simple test to debug login"""

import requests
import time
import json

time.sleep(2)

# Try login
session = requests.Session()

print("Testing login...")
response = session.post(
    "http://localhost:5000/login",
    data={
        'email': 'patient@hospital.com',
        'password': 'Patient@123'
    },
    allow_redirects=False  # Don't follow redirects
)

print(f"Status Code: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print(f"\nResponse Content Length: {len(response.content)}")
print(f"\nFirst 500 chars of response:\n{response.text[:500]}")

# Check if cookies are set
print(f"\nCookies: {session.cookies}")

# Try accessing a protected endpoint
print("\n\nTrying to access AI engine...")
response2 = session.post(
    "http://localhost:5000/ai_engine",
    json={"message": "Hello"},
    allow_redirects=False
)

print(f"Status Code: {response2.status_code}")
print(f"Response: {response2.text[:500]}")
