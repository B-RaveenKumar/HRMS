import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
print(f"API Key loaded: {api_key[:20]}..." if api_key else "No API key found")

try:
    client = OpenAI(api_key=api_key)
    
    # Test the API
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": "Say 'API key is valid'"}
        ],
        max_tokens=10
    )
    
    print("✅ API Key is VALID!")
    print(f"Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"❌ API Error: {str(e)}")
    print(f"Error type: {type(e).__name__}")
