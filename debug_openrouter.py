#!/usr/bin/env python3
import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
print(f'Testing OpenRouter API key...')
print(f'API Key format: {api_key[:20]}... (valid OpenRouter format)' if api_key and 'sk-or' in api_key else f'Invalid format')

# Test 1: Check if key is valid
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

print('\n1. Testing with different endpoint formats...')

# Try different possible endpoints
endpoints = [
    'https://openrouter.io/api/v1/chat/completions',
    'https://openrouter.io/api/chat/completions',
]

for endpoint in endpoints:
    try:
        print(f'\nTrying: {endpoint}')
        response = requests.post(
            endpoint,
            headers=headers,
            json={'model': 'gpt-3.5-turbo', 'messages': [{'role': 'user', 'content': 'Hi'}]},
            timeout=10
        )
        print(f'  Status: {response.status_code}')
        if response.status_code != 405:
            print(f'  Response: {response.text[:200]}')
    except Exception as e:
        print(f'  Error: {str(e)}')

# Try with 'Authorization' header as string to check if there's an issue
print('\n2. Checking if API key needs adjustments...')
print(f'API Key starts with: {api_key[:10]}')
print(f'Full key validation: {"✓ Looks valid" if len(api_key) > 50 else "✗ Too short"}')
