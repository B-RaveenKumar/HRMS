#!/usr/bin/env python3
"""Test the server status and database"""

import sqlite3
import os

print("=" * 60)
print("Checking database and test users...")
print("=" * 60)

# Check if database exists
db_path = 'd:\\HRMS\\healthcare.db'
if os.path.exists(db_path):
    print(f"✓ Database found at {db_path}")
    
    # Connect and check users
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all users
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    
    print(f"\nTotal users in database: {len(users)}")
    print("\nUser details:")
    print("ID | Email | Role")
    print("-" * 50)
    for user in users:
        print(f"{user[0]} | {user[1]} | {user[4]}")
    
    conn.close()
else:
    print(f"✗ Database not found at {db_path}")

print("\n" + "=" * 60)
print("Testing server connectivity...")
print("=" * 60)

import requests
import time

time.sleep(1)

try:
    response = requests.get("http://localhost:5000/")
    print(f"Server Status: {response.status_code}")
    print("Server is running!")
except Exception as e:
    print(f"Server error: {e}")
