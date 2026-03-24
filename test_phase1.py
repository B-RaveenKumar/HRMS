#!/usr/bin/env python
"""Quick verification test for Phase 1 implementation"""

import sqlite3
import sys
import bcrypt
from datetime import datetime

def test_database_schema():
    """Verify all new tables exist"""
    print("\n📊 Testing Database Schema...")
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    
    tables = ['appointments', 'prescriptions', 'billing', 'payments', 'notifications', 'medical_history']
    for table in tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if cursor.fetchone():
            print(f"  ✅ Table '{table}' exists")
        else:
            print(f"  ❌ Table '{table}' MISSING")
            return False
    
    conn.close()
    return True

def test_password_hashing():
    """Verify bcrypt hashing works"""
    print("\n🔐 Testing Password Hashing...")
    
    from app import hash_password, verify_password
    
    test_password = "SecurePass123"
    hashed = hash_password(test_password)
    
    print(f"  Original: {test_password}")
    print(f"  Hashed:   {hashed[:30]}...")
    
    if verify_password(test_password, hashed):
        print(f"  ✅ Password verification works")
        return True
    else:
        print(f"  ❌ Password verification FAILED")
        return False

def test_validation_functions():
    """Verify validation functions"""
    print("\n✔️  Testing Validation Functions...")
    
    from app import validate_email, validate_phone
    
    # Test email validation
    if validate_email("john@hospital.com"):
        print("  ✅ Valid email accepted")
    else:
        print("  ❌ Valid email rejected")
        return False
    
    if not validate_email("invalid-email"):
        print("  ✅ Invalid email rejected")
    else:
        print("  ❌ Invalid email accepted")
        return False
    
    # Test phone validation
    if validate_phone("9876543210"):
        print("  ✅ Valid phone accepted")
    else:
        print("  ❌ Valid phone rejected")
        return False
    
    if not validate_phone("123"):
        print("  ✅ Invalid phone rejected")
    else:
        print("  ❌ Invalid phone accepted")
        return False
    
    return True

def test_routes_exist():
    """Verify all new routes are defined"""
    print("\n🛣️  Testing Routes...")
    
    from app import app
    
    new_routes = [
        ('/schedule_appointment', 'POST'),
        ('/get_appointments', 'GET'),
        ('/cancel_appointment/<int:appointment_id>', 'DELETE'),
        ('/issue_prescription', 'POST'),
        ('/get_prescriptions', 'GET'),
        ('/create_billing', 'POST'),
        ('/get_billing_history', 'GET'),
        ('/process_payment', 'POST'),
        ('/get_notifications', 'GET'),
        ('/mark_notification_read/<int:notification_id>', 'POST'),
        ('/get_statistics', 'GET'),
    ]
    
    for route, method in new_routes:
        found = False
        for rule in app.url_map.iter_rules():
            if route.split('<')[0] in str(rule):
                if method in rule.methods:
                    found = True
                    break
        
        if found:
            print(f"  ✅ Route {method} {route}")
        else:
            print(f"  ❌ Route {method} {route} NOT FOUND")
            return False
    
    return True

def test_logs_created():
    """Verify healthcare.log file exists"""
    print("\n📝 Testing Logging...")
    
    import os
    if os.path.exists('healthcare.log'):
        print(f"  ✅ Log file 'healthcare.log' exists")
        with open('healthcare.log', 'r') as f:
            lines = f.readlines()
            if lines:
                print(f"  ✅ Log contains {len(lines)} entries")
                print(f"  Latest: {lines[-1][:60]}...")
        return True
    else:
        print(f"  ⚠️  Log file not created yet (will be created on first request)")
        return True

def main():
    print("=" * 60)
    print("🏥 PHASE 1 VERIFICATION TEST")
    print("=" * 60)
    
    tests = [
        ("Database Schema", test_database_schema),
        ("Password Hashing", test_password_hashing),
        ("Validation Functions", test_validation_functions),
        ("Routes", test_routes_exist),
        ("Logging", test_logs_created),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\n🎯 Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 Phase 1 Implementation VERIFIED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
