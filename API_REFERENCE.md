# 🔌 Complete API Reference - MediCare Pro v2.0

**Base URL**: `http://localhost:5000`  
**Authentication**: Session-based via `/login`  
**Response Format**: JSON

---

## 📋 Table of Contents

1. [Authentication](#authentication)
2. [Patient Records](#patient-records)
3. [Appointments](#appointments)
4. [Prescriptions](#prescriptions)
5. [Billing & Payments](#billing--payments)
6. [Notifications](#notifications)
7. [Hospital & Doctor Info](#hospital--doctor-info)
8. [Messaging](#messaging)
9. [AI Features](#ai-features)

---

## 🔑 Authentication

### Register User
Create a new user account

```http
POST /register
Content-Type: application/json

{
  "role": "patient",                    # patient, doctor, receptionist
  "email": "john@hospital.com",         # Unique, valid email
  "password": "SecurePass123",          # Min 8 chars, uppercase, lowercase, number
  "name": "John Doe",                   # User full name
  "phone": "+1234567890",               # 10+ digits
  "dob": "1990-01-15",                  # (patients) Date of birth
  "gender": "male",                     # (patients) male/female
  "blood_type": "O+",                   # (patients) Blood type
  "conditions": "Diabetes, Hypertension" # (patients) Medical conditions
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Account created successfully! You can now login as patient.",
  "user_id": 1
}
```

**Errors**:
- `400` - Missing fields or invalid data
- `400` - "Email already registered"
- `400` - "Password must be at least 8 characters"
- `400` - "Invalid email format"
- `400` - "Invalid phone number format"

---

### Login
Authenticate and create session

```http
POST /login
Content-Type: application/json

{
  "role": "patient",                    # patient, doctor, receptionist
  "email": "john@hospital.com",
  "password": "SecurePass123"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Welcome John Doe!",
  "redirect": "/dashboard"
}
```

**Errors**:
- `400` - "Missing required fields"
- `401` - "Invalid email or password"

---

### Logout
Clear session and logout

```http
GET /logout
```

**Response**: Redirects to login page

---

## 📋 Patient Records

### Save Patient Record
Create new patient admission record

```http
POST /save_data
Content-Type: application/json

{
  "sno": 1,                    # Record ID
  "name": "Jane Smith",        # Patient name
  "age": 35,                   # Age (0-150)
  "disease": "Diabetes",       # Condition/disease
  "date": "2026-03-24",        # Admission date
  "stay": 5,                   # Number of days (0-365)
  "fees": 5000.00              # Amount (positive number)
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Patient record saved"
}
```

**Errors**:
- `401` - Not logged in
- `400` - Invalid data (negative age, invalid amounts, etc.)

---

### Fetch All Records
Get all patient records

```http
GET /fetch_records
```

**Response**:
```json
[
  [1, "Jane Smith", 35, "Diabetes", "2026-03-24", 5, 5000],
  [2, "John Doe", 45, "Hypertension", "2026-03-23", 3, 3500]
]
```

**Errors**:
- `401` - Not logged in

---

### Delete Record
Remove patient record (receptionist/doctor only)

```http
DELETE /delete_record/1
```

**Response**:
```json
{
  "status": "success",
  "message": "Record deleted"
}
```

**Errors**:
- `401` - Not logged in
- `403` - Unauthorized role

---

## 📅 Appointments

### Schedule Appointment
Create new appointment (PATIENT ONLY)

```http
POST /schedule_appointment
Content-Type: application/json
Authorization: Session

{
  "doctor_id": 1,                    # Doctor ID
  "hospital_id": 1,                  # Hospital ID
  "appointment_date": "2026-04-15",  # YYYY-MM-DD
  "appointment_time": "10:30",       # HH:MM (24-hour)
  "reason": "Regular checkup"        # Purpose of visit
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Appointment scheduled successfully",
  "appointment_id": 5
}
```

**Errors**:
- `401` - Not logged in
- `403` - Must be patient
- `400` - "Appointment must be in the future"
- `400` - "Doctor has no available slots"
- `400` - "This time slot is already booked"

---

### Get Appointments
Fetch user's appointments

```http
GET /get_appointments
```

**Response** (for patient):
```json
{
  "status": "success",
  "appointments": [
    {
      "id": 5,
      "date": "2026-04-15",
      "time": "10:30",
      "reason": "Regular checkup",
      "status": "scheduled",
      "participant": "Dr. Sarah Johnson",
      "hospital": "City General Hospital"
    }
  ]
}
```

**Response** (for doctor/receptionist): Shows patients' appointments

**Errors**:
- `401` - Not logged in

---

### Cancel Appointment
Cancel scheduled appointment

```http
DELETE /cancel_appointment/5
```

**Response**:
```json
{
  "status": "success",
  "message": "Appointment cancelled"
}
```

**Errors**:
- `401` - Not logged in
- `404` - "Appointment not found"
- `403` - "Unauthorized"

---

## 💊 Prescriptions

### Issue Prescription
Doctor issues prescription to patient (DOCTOR ONLY)

```http
POST /issue_prescription
Content-Type: application/json

{
  "patient_id": 5,                          # Patient ID
  "medication": "Metformin",                # Medicine name
  "dosage": "500mg",                        # Dosage amount
  "frequency": "Twice daily",               # How often
  "duration": "30 days",                    # How long
  "instructions": "Take with food",        # Usage instructions
  "refills": 3                              # Number of refills allowed
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Prescription issued successfully",
  "prescription_id": 12
}
```

**Errors**:
- `401` - Not logged in
- `403` - Must be doctor
- `404` - "Patient not found"

---

### Get Prescriptions
Fetch all prescriptions

```http
GET /get_prescriptions
```

**Response** (for patient - own prescriptions):
```json
{
  "status": "success",
  "prescriptions": [
    {
      "id": 12,
      "medication": "Metformin",
      "dosage": "500mg",
      "frequency": "Twice daily",
      "duration": "30 days",
      "instructions": "Take with food",
      "refills": 3,
      "status": "active",
      "issued_date": "2026-03-24"
    }
  ]
}
```

**Response** (for doctor - issued prescriptions):
Same format but for patient's prescriptions they issued

**Errors**:
- `401` - Not logged in

---

## 💳 Billing & Payments

### Create Billing Invoice
Create invoice for patient (RECEPTIONIST/DOCTOR ONLY)

```http
POST /create_billing
Content-Type: application/json

{
  "patient_id": 5,                    # Patient to bill
  "amount": 5000.00,                  # Invoice amount
  "description": "Operation fees",    # What is being charged
  "due_date": "2026-04-30"           # When payment is due
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Invoice created successfully",
  "billing_id": 8
}
```

**Errors**:
- `401` - Not logged in
- `403` - Must be receptionist or doctor
- `400` - "Invalid patient or amount"

---

### Get Billing History
Fetch billing records

```http
GET /get_billing_history
```

**Response** (for patient - own bills):
```json
{
  "status": "success",
  "billing_history": [
    {
      "id": 8,
      "amount": 5000.00,
      "description": "Operation fees",
      "status": "pending",
      "due_date": "2026-04-30",
      "created_at": "2026-03-24"
    }
  ],
  "total_outstanding": 5000.00
}
```

**Response** (for staff - all bills):
Shows all billing records

**Errors**:
- `401` - Not logged in

---

### Process Payment
Pay billing invoice with card (Stripe integration)

```http
POST /process_payment
Content-Type: application/json

{
  "billing_id": 8,                    # Invoice to pay
  "payment_method": "card",           # card, cash, transfer
  "stripe_token": "tok_visa"          # Stripe token (if card payment)
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Payment processed successfully",
  "transaction_id": "ch_1234567890"
}
```

**Errors**:
- `401` - Not logged in
- `403` - Must be patient
- `404` - "Billing record not found"
- `400` - "Payment failed: ..."

---

## 🔔 Notifications

### Get Notifications
Fetch user's notifications

```http
GET /get_notifications
```

**Response**:
```json
{
  "status": "success",
  "notifications": [
    {
      "id": 1,
      "type": "appointment",
      "title": "Appointment Confirmed",
      "message": "Your appointment has been scheduled for 2026-04-15",
      "is_read": false,
      "created_at": "2026-03-24 13:30:00"
    }
  ],
  "unread_count": 3
}
```

**Auto-generated notification types**:
- `appointment` - Appointment scheduled/cancelled
- `prescription` - New prescription issued
- `payment` - Payment received
- `billing` - New invoice created
- `message` - New message from staff

**Errors**:
- `401` - Not logged in

---

### Mark Notification Read
Mark notification as read

```http
POST /mark_notification_read/1
```

**Response**:
```json
{
  "status": "success"
}
```

**Errors**:
- `401` - Not logged in

---

## 🏥 Hospital & Doctor Info

### Get All Hospitals
Get hospital directory

```http
GET /get_all_hospitals
```

**Response**:
```json
{
  "status": "success",
  "hospitals": [
    {
      "id": 1,
      "name": "City General Hospital",
      "location": "123 Main St, City Center",
      "phone": "555-0001",
      "available_beds": 45,
      "total_beds": 100
    }
  ]
}
```

---

### Get Hospital Doctors
Get doctors in specific hospital

```http
GET /get_hospital_doctors/1
```

**Response**:
```json
{
  "status": "success",
  "hospital": {
    "id": 1,
    "name": "City General Hospital",
    "location": "123 Main St, City Center"
  },
  "doctors": [
    {
      "doctor_id": 1,
      "name": "Dr. Sarah Johnson",
      "specialty": "Cardiology",
      "status": "Available",
      "working_hours": "09:00 - 17:00",
      "patients_in_queue": 3,
      "slots_available": 27
    }
  ]
}
```

---

### Check Doctor Availability
Search doctor across hospitals

```http
GET /check_doctor_availability/Sarah%20Johnson
```

**Response**:
```json
{
  "status": "success",
  "doctor_name": "Sarah Johnson",
  "availability": [
    {
      "hospital_id": 1,
      "hospital_name": "City General Hospital",
      "is_available": true,
      "start_time": "09:00",
      "end_time": "17:00",
      "patients_in_queue": 3,
      "slots_available": 27,
      "specialty": "Cardiology"
    }
  ]
}
```

---

### Check Doctor in Hospital
Check specific doctor in specific hospital

```http
GET /check_doctor_in_hospital/Sarah%20Johnson/1
```

**Response**:
```json
{
  "status": "success",
  "doctor_found": true,
  "doctor": {
    "name": "Dr. Sarah Johnson",
    "specialty": "Cardiology",
    "hospital": "City General Hospital",
    "is_available": true,
    "status": "Available",
    "working_hours": "09:00 - 17:00",
    "patients_in_queue": 3,
    "slots_available": 27,
    "wait_time_estimate": "45 minutes"
  }
}
```

---

### Update Doctor Availability
Update doctor status (RECEPTIONIST/DOCTOR ONLY)

```http
POST /update_doctor_availability
Content-Type: application/json

{
  "doctor_id": 1,
  "hospital_id": 1,
  "is_available": 1,               # 1=available, 0=not available
  "patients_in_queue": 5           # Optional
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Doctor availability updated"
}
```

---

## 💬 Messaging

### Send Message
Send message to another user

```http
POST /send_message
Content-Type: application/json

{
  "recipient_id": 2,               # User ID to send to
  "recipient_role": "doctor",      # Recipient's role
  "recipient_name": "Dr. Smith",   # Recipient's name
  "message": "When are you available?"  # Message text (max 1000 chars)
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Message sent successfully",
  "message_id": 45
}
```

**Errors**:
- `401` - Not logged in
- `400` - "Message too long"
- `400` - "Message cannot be empty"

---

### Get Conversations
Get list of conversations

```http
GET /get_conversations
```

**Response**:
```json
{
  "status": "success",
  "conversations": [
    {
      "user_id": 2,
      "user_name": "Dr. Sarah Johnson",
      "user_role": "doctor",
      "last_message_time": "2026-03-24 13:30:00"
    }
  ]
}
```

---

### Get Conversation History
Get chat history with specific user

```http
GET /get_conversation/2/doctor
```

**Response**:
```json
{
  "status": "success",
  "messages": [
    {
      "sender_id": 5,
      "sender_name": "John Doe",
      "message": "When are you available?",
      "timestamp": "2026-03-24 13:30:00",
      "sender_role": "patient"
    },
    {
      "sender_id": 2,
      "sender_name": "Dr. Sarah Johnson",
      "message": "Tomorrow at 10:30",
      "timestamp": "2026-03-24 13:35:00",
      "sender_role": "doctor"
    }
  ]
}
```

---

### Get Doctors List
Get all doctors

```http
GET /get_doctors
```

**Response**:
```json
{
  "status": "success",
  "doctors": [
    {
      "id": 1,
      "name": "Dr. Sarah Johnson",
      "email": "sarah@hospital.com"
    }
  ]
}
```

---

### Get Receptionists List
Get all receptionists

```http
GET /get_receptionists
```

**Response**:
```json
{
  "status": "success",
  "receptionists": [
    {
      "id": 3,
      "name": "Jane Receptionist",
      "email": "jane@hospital.com"
    }
  ]
}
```

---

### Get Patients List
Get all patients (DOCTOR/RECEPTIONIST ONLY)

```http
GET /get_patients
```

**Response**:
```json
{
  "status": "success",
  "patients": [
    {
      "id": 5,
      "name": "John Doe",
      "email": "john@hospital.com"
    }
  ]
}
```

---

## 📊 Analytics & Reporting

### Get Statistics
Get system statistics for dashboard

```http
GET /get_statistics
```

**Response**:
```json
{
  "status": "success",
  "statistics": {
    "total_patients": 45,
    "scheduled_appointments": 8,
    "todays_appointments": 3,
    "active_prescriptions": 12,
    "pending_bills": 5,
    "outstanding_revenue": 2500.00,
    "total_messages": 127,
    "available_beds": 42
  }
}
```

---

## 🤖 AI Features

### Simple AI Chat
Basic intent-based chatbot

```http
POST /ai_engine
Content-Type: application/json

{
  "message": "When is Dr. Johnson available?"
}
```

**Response**:
```json
{
  "reply": "The doctor is currently available in the clinic."
}
```

---

### AI Disease Diagnosis
Get diagnosis from OpenAI (requires API key)

```http
POST /diagnose
Content-Type: application/json

{
  "symptoms": "fever, cough, body pain for 3 days"
}
```

**Response**:
```json
{
  "status": "success",
  "diagnosis": "Based on your symptoms, possible conditions include: Common cold, Influenza...",
  "disclaimer": "⚠️ This is AI-generated information for educational purposes only."
}
```

**Errors**:
- `400` - "Please provide symptoms"
- `401` - "Invalid API key"

---

## 🔄 HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created/Success |
| 400 | Bad request (validation error) |
| 401 | Unauthorized (not logged in) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not found |
| 500 | Server error |

---

## 📝 Common Error Responses

**Unauthorized**:
```json
{
  "error": "Unauthorized - please login first"
}
```

**Forbidden**:
```json
{
  "error": "Forbidden - this action requires role: doctor"
}
```

**Validation Error**:
```json
{
  "error": "Invalid email format"
}
```

**Not Found**:
```json
{
  "error": "Patient not found"
}
```

---

## 🧪 Testing Endpoints with cURL

### Create user account
```bash
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{
    "role": "patient",
    "email": "test@hospital.com",
    "password": "SecurePass123",
    "name": "Test User",
    "phone": "1234567890"
  }'
```

### Login
```bash
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{
    "role": "patient",
    "email": "test@hospital.com",
    "password": "SecurePass123"
  }'
```

### Schedule appointment
```bash
curl -X POST http://localhost:5000/schedule_appointment \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "doctor_id": 1,
    "hospital_id": 1,
    "appointment_date": "2026-04-15",
    "appointment_time": "10:30",
    "reason": "Checkup"
  }'
```

### Get statistics
```bash
curl -X GET http://localhost:5000/get_statistics \
  -b cookies.txt
```

---

**API Documentation v2.0** - Updated March 24, 2026
