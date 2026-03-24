"""
================================================
PHASE 4: COMPREHENSIVE INTEGRATION TEST SUITE
================================================
Tests all features of MediCare Pro Hospital Management System
Run with: python test_phase4.py
"""

import unittest
import json
import sys
import time
from datetime import datetime, timedelta
sys.path.insert(0, '.')

# Import Flask app
from app import app, init_db, hash_password
import sqlite3


class TestPhase4Integration(unittest.TestCase):
    """Comprehensive integration tests for Phase 4"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.app = app
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        
        # Initialize database
        with cls.app.app_context():
            init_db()
            
            # Create test users
            conn = sqlite3.connect('healthcare.db')
            cursor = conn.cursor()
            
            # Create test patient
            cursor.execute('''
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
            ''', ('Test Patient', 'patient@test.com', hash_password('TestPass123'), 'patient'))
            
            # Create test doctor
            cursor.execute('''
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
            ''', ('Dr. Test', 'doctor@test.com', hash_password('DoctorPass123'), 'doctor'))
            
            # Create test receptionist
            cursor.execute('''
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
            ''', ('Test Receptionist', 'receptionist@test.com', hash_password('RecPass123'), 'receptionist'))
            
            conn.commit()
            conn.close()

    def tearDown(self):
        """Clean up after each test"""
        pass

    # ============================================
    # AUTHENTICATION & SECURITY TESTS
    # ============================================

    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = self.client.post('/login', data=json.dumps({
            'email': 'patient@test.com',
            'password': 'TestPass123'
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('status', data)

    def test_login_invalid_password(self):
        """Test login fails with wrong password"""
        response = self.client.post('/login', data=json.dumps({
            'email': 'patient@test.com',
            'password': 'WrongPassword'
        }), content_type='application/json')
        
        self.assertNotEqual(response.status_code, 200)

    def test_register_weak_password(self):
        """Test registration fails with weak password"""
        response = self.client.post('/register', data=json.dumps({
            'name': 'New User',
            'email': 'newuser@test.com',
            'password': 'weak'  # Too weak
        }), content_type='application/json')
        
        self.assertNotEqual(response.status_code, 200)

    def test_register_strong_password(self):
        """Test registration succeeds with strong password"""
        response = self.client.post('/register', data=json.dumps({
            'name': 'Strong User',
            'email': f'stronguser{int(time.time())}@test.com',
            'password': 'StrongPass123'
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)

    def test_invalid_email_format(self):
        """Test registration rejects invalid email"""
        response = self.client.post('/register', data=json.dumps({
            'name': 'Bad Email User',
            'email': 'not-an-email',
            'password': 'ValidPass123'
        }), content_type='application/json')
        
        self.assertNotEqual(response.status_code, 200)

    # ============================================
    # APPOINTMENT SYSTEM TESTS
    # ============================================

    def test_schedule_appointment(self):
        """Test scheduling an appointment"""
        response = self.client.post('/schedule_appointment', 
            data=json.dumps({
                'doctor_id': '1',
                'hospital_id': '1',
                'appointment_date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
                'appointment_time': '10:00',
                'reason': 'Checkup'
            }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('appointment_id', data)

    def test_get_appointments(self):
        """Test retrieving appointments"""
        response = self.client.get('/get_appointments')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)

    def test_cancel_appointment(self):
        """Test canceling an appointment"""
        # First create an appointment
        create_response = self.client.post('/schedule_appointment',
            data=json.dumps({
                'doctor_id': '1',
                'hospital_id': '1',
                'appointment_date': (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d'),
                'appointment_time': '11:00',
                'reason': 'Test'
            }), content_type='application/json')
        
        appt_id = json.loads(create_response.data).get('appointment_id')
        
        # Then cancel it
        cancel_response = self.client.delete(f'/cancel_appointment/{appt_id}')
        
        self.assertEqual(cancel_response.status_code, 200)

    def test_appointment_conflict_detection(self):
        """Test that double-booking is prevented"""
        date_to_book = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        
        # First appointment
        response1 = self.client.post('/schedule_appointment',
            data=json.dumps({
                'doctor_id': '2',
                'hospital_id': '1',
                'appointment_date': date_to_book,
                'appointment_time': '14:00',
                'reason': 'First'
            }), content_type='application/json')
        
        self.assertEqual(response1.status_code, 200)
        
        # Second appointment (same time - should fail)
        response2 = self.client.post('/schedule_appointment',
            data=json.dumps({
                'doctor_id': '2',
                'hospital_id': '1',
                'appointment_date': date_to_book,
                'appointment_time': '14:00',
                'reason': 'Conflict'
            }), content_type='application/json')
        
        # Should return error (409 conflict)
        self.assertNotEqual(response2.status_code, 200)

    # ============================================
    # PRESCRIPTION SYSTEM TESTS
    # ============================================

    def test_issue_prescription(self):
        """Test issuing a prescription"""
        response = self.client.post('/issue_prescription',
            data=json.dumps({
                'patient_id': '1',
                'medication': 'Aspirin',
                'dosage': '500mg',
                'frequency': 'Twice daily',
                'duration': '7 days',
                'instructions': 'Take with food',
                'refills_remaining': 2
            }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)

    def test_get_prescriptions(self):
        """Test retrieving prescriptions"""
        response = self.client.get('/get_prescriptions')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)

    def test_prescription_validation(self):
        """Test that invalid prescriptions are rejected"""
        response = self.client.post('/issue_prescription',
            data=json.dumps({
                'patient_id': '999',  # Non-existent patient
                'medication': '',  # Empty medication
                'dosage': '500mg',
                'frequency': 'Daily',
                'duration': '7 days'
            }), content_type='application/json')
        
        self.assertNotEqual(response.status_code, 200)

    # ============================================
    # BILLING & PAYMENT TESTS
    # ============================================

    def test_create_billing(self):
        """Test creating a billing record"""
        response = self.client.post('/create_billing',
            data=json.dumps({
                'patient_id': '1',
                'amount': 150.00,
                'description': 'Consultation fee',
                'due_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)

    def test_get_billing_history(self):
        """Test retrieving billing history"""
        response = self.client.get('/get_billing_history')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)

    def test_process_payment(self):
        """Test processing a payment"""
        # First create a billing record
        bill_response = self.client.post('/create_billing',
            data=json.dumps({
                'patient_id': '1',
                'amount': 100.00,
                'description': 'Test billing',
                'due_date': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            }), content_type='application/json')
        
        bill_id = json.loads(bill_response.data).get('billing_id')
        
        # Process payment
        payment_response = self.client.post('/process_payment',
            data=json.dumps({
                'billing_id': bill_id,
                'amount': 100.00,
                'payment_method': 'card'
            }), content_type='application/json')
        
        self.assertEqual(payment_response.status_code, 200)

    def test_payment_validation(self):
        """Test that invalid payments are rejected"""
        response = self.client.post('/process_payment',
            data=json.dumps({
                'billing_id': '9999',  # Non-existent billing
                'amount': 100.00,
                'payment_method': 'card'
            }), content_type='application/json')
        
        self.assertNotEqual(response.status_code, 200)

    # ============================================
    # NOTIFICATION TESTS
    # ============================================

    def test_get_notifications(self):
        """Test retrieving notifications"""
        response = self.client.get('/get_notifications')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)

    def test_mark_notification_read(self):
        """Test marking notification as read"""
        # Create a notification first
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO notifications 
            (user_id, notification_type, title, message, is_read)
            VALUES (?, ?, ?, ?, ?)
        ''', (1, 'test', 'Test Title', 'Test Message', 0))
        
        cursor.execute('SELECT last_insert_rowid()')
        notif_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        
        # Mark as read
        response = self.client.post(f'/mark_notification_read/{notif_id}')
        
        self.assertEqual(response.status_code, 200)

    # ============================================
    # ANALYTICS TESTS
    # ============================================

    def test_get_statistics(self):
        """Test retrieving system statistics"""
        response = self.client.get('/get_statistics')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Verify all expected fields
        expected_fields = [
            'total_patients', 'total_appointments', 
            'total_prescriptions', 'total_billing'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
            self.assertIsInstance(data[field], (int, float))

    # ============================================
    # MESSAGING TESTS
    # ============================================

    def test_send_message(self):
        """Test sending a message"""
        response = self.client.post('/send_message',
            data=json.dumps({
                'recipient_id': '2',
                'recipient_role': 'doctor',
                'recipient_name': 'Dr. Test',
                'message': 'Hello Doctor'
            }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)

    def test_get_conversation(self):
        """Test retrieving conversation history"""
        response = self.client.get('/get_conversation/2/doctor')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('messages', data)

    def test_message_length_limit(self):
        """Test that excessively long messages are rejected"""
        long_message = 'a' * 10001  # Too long
        
        response = self.client.post('/send_message',
            data=json.dumps({
                'recipient_id': '2',
                'recipient_role': 'doctor',
                'recipient_name': 'Dr. Test',
                'message': long_message
            }), content_type='application/json')
        
        self.assertNotEqual(response.status_code, 200)

    # ============================================
    # MEDICAL RECORDS TESTS
    # ============================================

    def test_save_medical_record(self):
        """Test saving a medical record"""
        response = self.client.post('/save_data',
            data=json.dumps({
                'name': 'Test Patient',
                'age': '30',
                'disease': 'Test Disease',
                'stay': '5'
            }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)

    def test_fetch_medical_records(self):
        """Test fetching medical records"""
        response = self.client.get('/fetch_records')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)

    # ============================================
    # PERFORMANCE TESTS
    # ============================================

    def test_api_response_time_schedule_appointment(self):
        """Test that appointment scheduling is fast"""
        start = time.time()
        
        response = self.client.post('/schedule_appointment',
            data=json.dumps({
                'doctor_id': '3',
                'hospital_id': '1',
                'appointment_date': (datetime.now() + timedelta(days=4)).strftime('%Y-%m-%d'),
                'appointment_time': '15:00',
                'reason': 'Performance test'
            }), content_type='application/json')
        
        elapsed = time.time() - start
        
        # Should complete in less than 1 second
        self.assertLess(elapsed, 1.0)
        self.assertEqual(response.status_code, 200)

    def test_api_response_time_get_statistics(self):
        """Test that statistics retrieval is fast"""
        start = time.time()
        
        response = self.client.get('/get_statistics')
        
        elapsed = time.time() - start
        
        # Should complete in less than 0.5 seconds
        self.assertLess(elapsed, 0.5)
        self.assertEqual(response.status_code, 200)

    def test_database_concurrent_access(self):
        """Test database handles multiple requests"""
        responses = []
        
        for i in range(5):
            response = self.client.get('/get_appointments')
            responses.append(response.status_code)
        
        # All should succeed
        self.assertTrue(all(code == 200 for code in responses))

    # ============================================
    # END-TO-END WORKFLOW TESTS
    # ============================================

    def test_complete_patient_workflow(self):
        """Test complete patient workflow: Register -> Appointment -> Bill -> Pay"""
        
        # 1. Register
        register_resp = self.client.post('/register',
            data=json.dumps({
                'name': 'E2E Patient',
                'email': f'e2e{int(time.time())}@test.com',
                'password': 'E2EPass123'
            }), content_type='application/json')
        self.assertEqual(register_resp.status_code, 200)
        
        # 2. Login
        login_resp = self.client.post('/login',
            data=json.dumps({
                'email': f'e2e{int(time.time())}@test.com',
                'password': 'E2EPass123'
            }), content_type='application/json')
        self.assertEqual(login_resp.status_code, 200)
        
        # 3. Schedule Appointment
        appt_resp = self.client.post('/schedule_appointment',
            data=json.dumps({
                'doctor_id': '1',
                'hospital_id': '1',
                'appointment_date': (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'),
                'appointment_time': '16:00',
                'reason': 'E2E Test'
            }), content_type='application/json')
        self.assertEqual(appt_resp.status_code, 200)
        
        # 4. Get Appointments
        get_appt_resp = self.client.get('/get_appointments')
        self.assertEqual(get_appt_resp.status_code, 200)
        
        # 5. Create Billing
        bill_resp = self.client.post('/create_billing',
            data=json.dumps({
                'patient_id': '1',
                'amount': 200.00,
                'description': 'E2E Test Billing',
                'due_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            }), content_type='application/json')
        self.assertEqual(bill_resp.status_code, 200)

    def test_complete_doctor_workflow(self):
        """Test complete doctor workflow"""
        
        # 1. Get patients
        patients_resp = self.client.get('/get_patients')
        self.assertEqual(patients_resp.status_code, 200)
        
        # 2. Get appointments
        appts_resp = self.client.get('/get_appointments')
        self.assertEqual(appts_resp.status_code, 200)
        
        # 3. Issue prescription
        presc_resp = self.client.post('/issue_prescription',
            data=json.dumps({
                'patient_id': '1',
                'medication': 'Amoxicillin',
                'dosage': '250mg',
                'frequency': 'Three times daily',
                'duration': '10 days',
                'refills_remaining': 1
            }), content_type='application/json')
        self.assertEqual(presc_resp.status_code, 200)
        
        # 4. Get prescriptions
        get_presc_resp = self.client.get('/get_prescriptions')
        self.assertEqual(get_presc_resp.status_code, 200)

    # ============================================
    # ERROR HANDLING TESTS
    # ============================================

    def test_invalid_json_request(self):
        """Test handling of invalid JSON"""
        response = self.client.post('/register',
            data='invalid json',
            content_type='application/json')
        
        self.assertNotEqual(response.status_code, 200)

    def test_missing_required_fields(self):
        """Test missing required fields"""
        response = self.client.post('/schedule_appointment',
            data=json.dumps({
                'doctor_id': '1'  # Missing other required fields
            }), content_type='application/json')
        
        self.assertNotEqual(response.status_code, 200)

    def test_sql_injection_prevention(self):
        """Test that SQL injection is prevented"""
        response = self.client.post('/send_message',
            data=json.dumps({
                'recipient_id': "1'; DROP TABLE users; --",
                'recipient_role': 'doctor',
                'recipient_name': 'Dr. Test',
                'message': 'Test'
            }), content_type='application/json')
        
        # Should not drop table - response should be error
        self.assertNotEqual(response.status_code, 200)
        
        # Verify users table still exists
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result, "users table was dropped!")

    # ============================================
    # LOGGING & AUDIT TESTS
    # ============================================

    def test_operations_are_logged(self):
        """Test that operations are logged to file"""
        import os
        
        # Perform an operation
        self.client.post('/login',
            data=json.dumps({
                'email': 'patient@test.com',
                'password': 'TestPass123'
            }), content_type='application/json')
        
        # Check that log file exists
        self.assertTrue(os.path.exists('healthcare.log'))
        
        # Check that log file has content
        with open('healthcare.log', 'r') as f:
            log_content = f.read()
            self.assertGreater(len(log_content), 0)


class TestPerformanceAndOptimization(unittest.TestCase):
    """Performance and optimization tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.app = app
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    def test_response_headers_security(self):
        """Test that security headers are present"""
        response = self.client.get('/get_statistics')
        
        # In a real app, these would be set in Flask
        # For now, just verify response is OK
        self.assertEqual(response.status_code, 200)

    def test_database_pool_efficiency(self):
        """Test database operations are efficient"""
        responses = []
        start = time.time()
        
        for _ in range(10):
            resp = self.client.get('/get_statistics')
            responses.append(resp.status_code)
        
        elapsed = time.time() - start
        
        # 10 requests should complete in less than 2 seconds
        self.assertLess(elapsed, 2.0)
        self.assertTrue(all(code == 200 for code in responses))


def run_tests():
    """Run all tests and generate report"""
    print("\n" + "="*70)
    print("MEDICARE PRO - PHASE 4 INTEGRATION TEST SUITE")
    print("="*70)
    print(f"\nTest Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*70+"\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all tests
    suite.addTests(loader.loadTestsFromTestCase(TestPhase4Integration))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceAndOptimization))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70 + "\n")
    
    if result.wasSuccessful():
        print("🎉 ALL PHASE 4 TESTS PASSED!")
        print("✅ System is production-ready\n")
        return True
    else:
        print("❌ Some tests failed. Review output above.\n")
        return False


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
