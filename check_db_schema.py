#!/usr/bin/env python3
"""Check database schema and user credentials"""

import sqlite3

db_path = 'd:\\HRMS\\healthcare.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get users table schema
cursor.execute("PRAGMA table_info(users)")
schema = cursor.fetchall()

print("Users table schema:")
print("Column Index | Name | Type | Not Null")
print("-" * 50)
for col in schema:
    print(f"{col[0]:13} | {col[1]:20} | {col[2]:10} | {col[3]}")

# Get all users with all columns
cursor.execute("SELECT * FROM users LIMIT 5")
print("\n\nFirst 5 users (all columns):")
users = cursor.fetchall()
for user in users:
    print(user)

# Try to find a patient user
cursor.execute("SELECT id, email, password_hash, role, name FROM users WHERE role='patient' LIMIT 1")
patient = cursor.fetchone()

if patient:
    print(f"\n\nFirst patient user:")
    print(f"ID: {patient[0]}")
    print(f"Email: {patient[1]}")
    print(f"Password Hash (first 20 chars): {str(patient[2])[:20]}")
    print(f"Role: {patient[3]}")
    print(f"Name: {patient[4]}")

conn.close()
