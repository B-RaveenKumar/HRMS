# Role Feature Matrix

This file summarizes available features for each user type in the current system.

## Doctor

### Core access
- Login, logout, dashboard
- View doctor/reception-level analytics

### Patient records
- Create patient record (`POST /save_data`)
- View all patient records (`GET /fetch_records`)
- Delete patient record (`DELETE /delete_record/<id>`)

### Appointments
- View appointments (`GET /get_appointments`)
- Cancel own appointment entries (`DELETE /cancel_appointment/<id>`)

### Prescriptions
- Issue prescription (`POST /issue_prescription`)
- View prescriptions issued by doctor (`GET /get_prescriptions`)

### Billing
- Create invoice (`POST /create_billing`)
- View billing history (`GET /get_billing_history`)

### Messaging
- Get patients list (`GET /get_patients`)
- Send message (`POST /send_message`)
- Get conversation and conversation list (`GET /get_conversation/...`, `GET /get_conversations`)

### Availability
- Update doctor availability (`POST /update_doctor_availability`)

## Receptionist

### Core access
- Login, logout, dashboard
- View receptionist/doctor-level analytics

### Patient records
- Create patient record (`POST /save_data`)
- View all patient records (`GET /fetch_records`)
- Delete patient record (`DELETE /delete_record/<id>`)

### Appointments
- View appointments (`GET /get_appointments`)
- Cancel appointment (`DELETE /cancel_appointment/<id>`)

### Billing
- Create invoice (`POST /create_billing`)
- View billing history (`GET /get_billing_history`)

### Messaging
- Get patients list (`GET /get_patients`)
- Send message (`POST /send_message`)
- Get conversation and conversation list (`GET /get_conversation/...`, `GET /get_conversations`)

### Availability
- Update doctor availability (`POST /update_doctor_availability`)

## Patient

### Core access
- Login, logout, dashboard

### Appointments
- Schedule appointment (`POST /schedule_appointment`)
- View own appointments (`GET /get_appointments`)
- Cancel own appointment (`DELETE /cancel_appointment/<id>`)

### Prescriptions
- View own prescriptions (`GET /get_prescriptions`)

### Billing and payments
- View own billing history (`GET /get_billing_history`)
- Process payment (`POST /process_payment`)

### AI and assistant
- Patient assistant (`POST /ai_engine`)
- Symptom diagnosis endpoint (`POST /diagnose`)

### Messaging
- List doctors (`GET /get_doctors`)
- List receptionists (`GET /get_receptionists`)
- Send message (`POST /send_message`)
- Get conversation and conversation list (`GET /get_conversation/...`, `GET /get_conversations`)

### Notifications
- Get notifications (`GET /get_notifications`)
- Mark notification as read (`POST /mark_notification_read/<id>`)

## Public endpoints (no login required)
- `GET /get_all_hospitals`
- `GET /check_doctor_availability/<doctor_name>`
- `GET /check_doctor_in_hospital/<doctor_name>/<hospital_id>`
- `GET /get_hospital_doctors/<hospital_id>`
