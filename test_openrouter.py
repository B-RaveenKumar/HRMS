#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')
print(f'API Key: {api_key[:30]}...')

headers = {
    'Authorization': f'Bearer {api_key}',
    'HTTP-Referer': 'http://localhost:5000',
    'X-Title': 'Hospital',
    'Content-Type': 'application/json'
}

payload = {
    'model': 'gpt-3.5-turbo',
    'messages': [
        {'role': 'user', 'content': 'What is 2+2?'}
    ],
    'max_tokens': 50
}

try:
    print('Sending request to OpenRouter...')
    response = requests.post(
        'https://openrouter.io/api/v1/chat/completions',
        headers=headers,
        json=payload,
        timeout=30
    )
    print(f'Status Code: {response.status_code}')
    
    if response.status_code == 200:
        print('✅ SUCCESS!')
        data = response.json()
        content = data['choices'][0]['message']['content']
        print(f'Response: {content}')
    else:
        print(f'❌ Error Response:')
        print(response.text[:500])
except Exception as e:
    print(f'❌ Exception: {type(e).__name__}: {str(e)}')
