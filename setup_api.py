#!/usr/bin/env python3
"""
Interactive setup script for OpenAI API key configuration
"""

import os
import sys

def setup_api_key():
    print("\n" + "="*60)
    print("🔧 Healthcare AI - OpenAI API Key Setup")
    print("="*60 + "\n")
    
    print("📋 Before you continue, make sure you have:")
    print("   ✓ Created an OpenAI account (https://openai.com)")
    print("   ✓ Got your API key from https://platform.openai.com/account/api-keys")
    print("   ✓ Enabled billing on your account")
    print()
    
    while True:
        api_key = input("🔑 Enter your OpenAI API key (sk-proj-...): ").strip()
        
        if not api_key:
            print("❌ API key cannot be empty. Please try again.\n")
            continue
            
        if not api_key.startswith("sk-"):
            print("⚠️  Warning: API keys usually start with 'sk-'\n")
            confirm = input("Continue anyway? (y/n): ").lower()
            if confirm != 'y':
                continue
        
        # Ask for confirmation
        print(f"\n✓ API key preview: {api_key[:20]}...{api_key[-4:]}")
        confirm = input("Is this correct? (y/n): ").lower()
        
        if confirm == 'y':
            break
        else:
            print("Let's try again.\n")
    
    # Update .env file
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    try:
        with open(env_path, 'w') as f:
            f.write(f"OPENAI_API_KEY={api_key}\n")
        
        print("\n" + "="*60)
        print("✅ SUCCESS! API key saved to .env")
        print("="*60)
        print(f"📁 File: {env_path}")
        print("\n🚀 Next steps:")
        print("   1. Run: python app.py")
        print("   2. Open: http://localhost:5000")
        print("   3. Try the disease diagnosis feature")
        print("\n💡 To verify the key works, run: python test_api.py\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error writing to .env file: {e}")
        return False

def test_current_key():
    from dotenv import load_dotenv
    from openai import OpenAI
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ No API key found in .env")
        return False
    
    print(f"\n🧪 Testing API key: {api_key[:20]}...")
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5
        )
        print("✅ API Key is VALID! ✓")
        return True
    except Exception as e:
        error_str = str(e).lower()
        if "invalid_api_key" in error_str or "401" in error_str:
            print("❌ API Key is INVALID")
            print("   Please get a new key from: https://platform.openai.com/account/api-keys")
        elif "rate_limit" in error_str or "429" in error_str:
            print("⚠️  API Rate limit exceeded. Try again later.")
        else:
            print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_current_key()
    else:
        setup_api_key()
