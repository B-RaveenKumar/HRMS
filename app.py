import sqlite3
import os
import json
import logging
import re
import bcrypt
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta
import stripe
import hashlib
from collections import defaultdict
import time

load_dotenv()

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('healthcare.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure OpenAI API client (lazy initialization)
api_key_openai = os.getenv("OPENAI_API_KEY")
if not api_key_openai:
    print("⚠️  WARNING: OPENAI_API_KEY not found in .env file!")
    print("   📋 Run: python setup_api.py")
    api_key_openai = "placeholder"

# Lazy initialize the client to avoid SSL issues on startup
client = None

def get_openai_client():
    """Get or create the OpenAI client (lazy initialization)"""
    global client
    if client is None:
        try:
            client = OpenAI(api_key=api_key_openai)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI client: {e}")
            return None
    return client

app = Flask(__name__)

# --- SECURITY CONFIGURATION ---
SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
if not SECRET_KEY:
    logger.error("❌ FLASK_SECRET_KEY not found in .env file!")
    logger.info("   Generate a secure key: python -c \"import os; print(os.urandom(32).hex())\"")
    SECRET_KEY = "temporary-insecure-key-change-in-production"  # Temporary fallback

app.secret_key = SECRET_KEY

# Configure Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# --- VALIDATION & SECURITY HELPERS ---

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, str(email)) is not None

def validate_phone(phone):
    """Validate phone number (basic)"""
    phone = re.sub(r'\D', '', str(phone))
    return len(phone) >= 10

def validate_password_strength(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain number"
    return True, "Password is strong"

def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed):
    """Verify password against hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def sanitize_input(data):
    """Sanitize user input to prevent injections"""
    if isinstance(data, str):
        # Remove potential SQL injection characters (basic sanitization)
        data = data.replace("'", "''").strip()
        # Limit length
        return data[:255]
    return data

def require_login(f):
    """Decorator to require user login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            logger.warning(f"Unauthorized access attempt to {request.endpoint}")
            return jsonify({"error": "Unauthorized - please login first"}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_role(*allowed_roles):
    """Decorator to require specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in allowed_roles:
                logger.warning(f"Forbidden access attempt - role {session.get('role')} to {request.endpoint}")
                return jsonify({"error": f"Forbidden - this action requires role: {', '.join(allowed_roles)}"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- RATE LIMITING & CACHING ---

# In-memory rate limiting storage
rate_limit_storage = defaultdict(lambda: {"count": 0, "reset_time": time.time() + 3600})
request_cache = {}

def rate_limit(max_requests=100, window_seconds=3600):
    """Decorator for rate limiting (100 requests per hour per IPlayer)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP
            client_ip = request.remote_addr or "unknown"
            endpoint = request.endpoint or "unknown"
            key = f"{client_ip}:{endpoint}"
            
            current_time = time.time()
            
            # Reset if window has passed
            if current_time > rate_limit_storage[key]["reset_time"]:
                rate_limit_storage[key] = {"count": 0, "reset_time": current_time + window_seconds}
            
            # Check limit
            if rate_limit_storage[key]["count"] >= max_requests:
                logger.warning(f"Rate limit exceeded for {key}")
                response = make_response(jsonify({"error": "Rate limit exceeded. Wait before retrying."}), 429)
                response.headers['Retry-After'] = str(int(rate_limit_storage[key]["reset_time"] - current_time))
                return response
            
            # Increment counter
            rate_limit_storage[key]["count"] += 1
            
            # Call the function
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def cached(duration=300):
    """Decorator for response caching (default 5 minutes)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Create cache key from route and query parameters
            cache_key = f"{request.path}:{request.query_string.decode()}"
            
            current_time = time.time()
            
            # Check if cached response is still valid
            if cache_key in request_cache:
                cached_response, expiration_time = request_cache[cache_key]
                if current_time < expiration_time:
                    logger.debug(f"Returning cached response for {cache_key}")
                    return cached_response
            
            # Call function and cache result
            response = f(*args, **kwargs)
            request_cache[cache_key] = (response, current_time + duration)
            
            return response
        return decorated_function
    return decorator

def clear_cache():
    """Clear all cached responses"""
    request_cache.clear()
    logger.info("Cache cleared")

# --- 1. SIMPLE INTENT CLASSIFIER (No sklearn needed) ---
def classify_intent(user_query):
    """Simple keyword-based intent classification"""
    query_lower = user_query.lower()
    
    if any(word in query_lower for word in ["doctor", "available", "appointment"]):
        return "availability"
    elif any(word in query_lower for word in ["fever", "pain", "symptom", "sick"]):
        return "first_aid"
    elif any(word in query_lower for word in ["clinic", "hospital", "nearby", "location"]):
        return "location"
    else:
        return "general"

# --- 2. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    
    # Create patient records table
    cursor.execute('''CREATE TABLE IF NOT EXISTS records 
        (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, 
        disease TEXT, admit_date TEXT, stay_days INTEGER, fees INTEGER)''')
    
    # Create users table for registration
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
         role TEXT NOT NULL,
         email TEXT UNIQUE NOT NULL,
         password TEXT NOT NULL,
         name TEXT NOT NULL,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         phone TEXT,
         profile_data TEXT)''')
    
    # Create conversations table for doctor-patient and receptionist-patient chats
    cursor.execute('''CREATE TABLE IF NOT EXISTS conversations 
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         sender_id TEXT NOT NULL,
         sender_role TEXT NOT NULL,
         sender_name TEXT NOT NULL,
         recipient_id TEXT NOT NULL,
         recipient_role TEXT NOT NULL,
         recipient_name TEXT NOT NULL,
         message TEXT NOT NULL,
         timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         is_read INTEGER DEFAULT 0)''')
    
    # Create hospitals table
    cursor.execute('''CREATE TABLE IF NOT EXISTS hospitals 
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT UNIQUE NOT NULL,
         location TEXT NOT NULL,
         phone TEXT NOT NULL,
         email TEXT,
         total_beds INTEGER DEFAULT 100,
         available_beds INTEGER DEFAULT 100,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create doctor-hospital availability table
    cursor.execute('''CREATE TABLE IF NOT EXISTS doctor_availability 
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         doctor_id INTEGER NOT NULL,
         doctor_name TEXT NOT NULL,
         hospital_id INTEGER NOT NULL,
         hospital_name TEXT NOT NULL,
         is_available INTEGER DEFAULT 1,
         start_time TEXT,
         end_time TEXT,
         patients_in_queue INTEGER DEFAULT 0,
         max_patients_per_day INTEGER DEFAULT 30,
         specialty TEXT,
         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY(hospital_id) REFERENCES hospitals(id),
         UNIQUE(doctor_id, hospital_id))''')
    
    # Create appointments table (NEW)
    cursor.execute('''CREATE TABLE IF NOT EXISTS appointments
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         patient_id INTEGER NOT NULL,
         doctor_id INTEGER NOT NULL,
         hospital_id INTEGER NOT NULL,
         appointment_date TEXT NOT NULL,
         appointment_time TEXT NOT NULL,
         reason TEXT,
         status TEXT DEFAULT 'scheduled',
         notes TEXT,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY(patient_id) REFERENCES users(id),
         FOREIGN KEY(doctor_id) REFERENCES users(id),
         FOREIGN KEY(hospital_id) REFERENCES hospitals(id),
         UNIQUE(doctor_id, appointment_date, appointment_time))''')
    
    # Create prescriptions table (NEW)
    cursor.execute('''CREATE TABLE IF NOT EXISTS prescriptions
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         patient_id INTEGER NOT NULL,
         doctor_id INTEGER NOT NULL,
         medication TEXT NOT NULL,
         dosage TEXT NOT NULL,
         frequency TEXT NOT NULL,
         duration TEXT,
         instructions TEXT,
         refills_remaining INTEGER DEFAULT 0,
         status TEXT DEFAULT 'active',
         issued_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         expiry_date TEXT,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY(patient_id) REFERENCES users(id),
         FOREIGN KEY(doctor_id) REFERENCES users(id))''')
    
    # Create billing/invoices table (NEW)
    cursor.execute('''CREATE TABLE IF NOT EXISTS billing
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         patient_id INTEGER NOT NULL,
         amount REAL NOT NULL,
         description TEXT,
         status TEXT DEFAULT 'pending',
         due_date TEXT,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY(patient_id) REFERENCES users(id))''')
    
    # Create payments table (NEW)
    cursor.execute('''CREATE TABLE IF NOT EXISTS payments
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         billing_id INTEGER NOT NULL,
         amount REAL NOT NULL,
         payment_method TEXT,
         transaction_id TEXT,
         status TEXT DEFAULT 'completed',
         payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         receipt_url TEXT,
         FOREIGN KEY(billing_id) REFERENCES billing(id))''')
    
    # Create notifications table (NEW)
    cursor.execute('''CREATE TABLE IF NOT EXISTS notifications
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id INTEGER NOT NULL,
         notification_type TEXT,
         title TEXT NOT NULL,
         message TEXT NOT NULL,
         action_url TEXT,
         is_read INTEGER DEFAULT 0,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    # Create medical history table (NEW)
    cursor.execute('''CREATE TABLE IF NOT EXISTS medical_history
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         patient_id INTEGER NOT NULL,
         condition TEXT NOT NULL,
         diagnosis_date TEXT,
         treatment TEXT,
         doctor_id INTEGER,
         notes TEXT,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY(patient_id) REFERENCES users(id),
         FOREIGN KEY(doctor_id) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

init_db()

# --- INITIALIZE HOSPITAL DATA ---
def init_hospital_data():
    """Initialize hospitals and doctor availability data"""
    conn = sqlite3.connect('healthcare.db')
    cursor = conn.cursor()
    
    # Check if hospitals already exist
    cursor.execute('SELECT COUNT(*) FROM hospitals')
    if cursor.fetchone()[0] == 0:
        # Add sample hospitals
        hospitals = [
            ('City General Hospital', '123 Main St, City Center', '555-0001', 'info@cityhospital.com'),
            ('Metro Medical Center', '456 Park Ave, Downtown', '555-0002', 'contact@metro.com'),
            ('Sunrise Healthcare', '789 Oak Rd, North Side', '555-0003', 'admin@sunrise.com'),
            ('Riverside Clinic', '321 River Ln, South District', '555-0004', 'info@riverside.com'),
            ('Central Hospital', '654 Central Ave, Midtown', '555-0005', 'support@central.com')
        ]
        
        for hospital in hospitals:
            cursor.execute('''INSERT INTO hospitals (name, location, phone, email) 
                             VALUES (?, ?, ?, ?)''', hospital)
        
        conn.commit()
    
    # Add sample doctor availability data
    cursor.execute('SELECT COUNT(*) FROM doctor_availability')
    if cursor.fetchone()[0] == 0:
        cursor.execute('SELECT id FROM hospitals')
        hospital_ids = [row[0] for row in cursor.fetchall()]
        
        doctors = [
            (1, 'Dr. Sarah Johnson', 'Cardiology'),
            (2, 'Dr. Michael Chen', 'Neurology'),
            (3, 'Dr. Emily Davis', 'Pediatrics'),
            (4, 'Dr. James Wilson', 'Orthopedics'),
            (5, 'Dr. Lisa Anderson', 'Dermatology')
        ]
        
        for doctor_id, doctor_name, specialty in doctors:
            for hospital_id in hospital_ids:
                cursor.execute('''SELECT name FROM hospitals WHERE id = ?''', (hospital_id,))
                hospital_name = cursor.fetchone()[0]
                
                cursor.execute('''INSERT OR IGNORE INTO doctor_availability 
                                 (doctor_id, doctor_name, hospital_id, hospital_name, is_available, 
                                  start_time, end_time, specialty, patients_in_queue)
                                 VALUES (?, ?, ?, ?, 1, '09:00', '17:00', ?, 0)''',
                              (doctor_id, doctor_name, hospital_id, hospital_name, specialty))
        
        conn.commit()
    
    conn.close()

init_hospital_data()

# --- 3. ROUTES ---

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration with password hashing"""
    if request.method == 'GET':
        return render_template('register.html')
    
    try:
        # Handle POST request
        data = request.json
        role = data.get('role', '').lower().strip()
        email = data.get('email', '').lower().strip()
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        
        # Validate inputs
        if not all([role, email, password, name, phone]):
            logger.warning(f"Registration attempt with missing fields: {role}, {email}, {name}")
            return jsonify({"error": "Missing required fields"}), 400
        
        # Validate email format
        if not validate_email(email):
            return jsonify({"error": "Invalid email format"}), 400
        
        # Validate phone format
        if not validate_phone(phone):
            return jsonify({"error": "Invalid phone number format"}), 400
        
        # Validate password strength
        strong, msg = validate_password_strength(password)
        if not strong:
            return jsonify({"error": msg}), 400
        
        # Validate role
        if role not in ['doctor', 'receptionist', 'patient']:
            return jsonify({"error": "Invalid role"}), 400
        
        # Validate name length
        if len(name) < 2 or len(name) > 100:
            return jsonify({"error": "Name must be between 2 and 100 characters"}), 400
        
        # Store additional profile data
        profile_data = json.dumps({
            'phone': phone,
            'role_specific': {
                'doctor': {
                    'license': sanitize_input(data.get('license', '')),
                    'specialization': sanitize_input(data.get('specialization', '')),
                    'experience': sanitize_input(data.get('experience', ''))
                },
                'receptionist': {
                    'department': sanitize_input(data.get('department', '')),
                    'shift': sanitize_input(data.get('shift', ''))
                },
                'patient': {
                    'dob': sanitize_input(data.get('dob', '')),
                    'gender': sanitize_input(data.get('gender', '')),
                    'address': sanitize_input(data.get('address', '')),
                    'blood_type': sanitize_input(data.get('bloodType', '')),
                    'medical_conditions': sanitize_input(data.get('conditions', ''))
                }
            }[role]
        })
        
        # Hash password
        hashed_password = hash_password(password)
        
        try:
            conn = sqlite3.connect('healthcare.db')
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO users (role, email, password, name, phone, profile_data) 
                              VALUES (?, ?, ?, ?, ?, ?)''',
                          (role, email, hashed_password, name, phone, profile_data))
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            
            logger.info(f"New user registered: {email} with role {role}")
            
            return jsonify({
                "success": True,
                "message": f"Account created successfully! You can now login as {role}.",
                "user_id": user_id
            }), 201
        
        except sqlite3.IntegrityError as e:
            logger.warning(f"Registration failed - email already exists: {email}")
            return jsonify({"error": "Email already registered. Please use a different email or login."}), 400
        except Exception as e:
            logger.error(f"Registration database error: {e}")
            return jsonify({"error": f"Registration failed: {str(e)}"}), 500
    
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({"error": "Registration error"}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Validate user credentials and create session with password hashing"""
    if request.method == 'GET':
        return render_template('login.html')
    
    # Handle POST request
    try:
        data = request.json
        role = data.get('role', '').lower().strip()
        email = data.get('email', '').lower().strip()
        password = data.get('password', '').strip()
        
        # Validate inputs
        if not all([role, email, password]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Validate role exists
        if role not in ['doctor', 'receptionist', 'patient']:
            return jsonify({"error": "Invalid role"}), 400
        
        # Check in registered users database
        try:
            conn = sqlite3.connect('healthcare.db')
            cursor = conn.cursor()
            cursor.execute('''SELECT id, name, phone, password FROM users 
                              WHERE role = ? AND email = ?''',
                          (role, email))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                user_id, name, phone, hashed_password = user
                # Verify password using bcrypt
                if verify_password(password, hashed_password):
                    # Login successful
                    session['user_id'] = user_id
                    session['role'] = role
                    session['email'] = email
                    session['name'] = name
                    session['phone'] = phone
                    session['login_time'] = datetime.now().isoformat()
                    
                    logger.info(f"User logged in: {email} ({role})")
                    
                    return jsonify({
                        "success": True,
                        "message": f"Welcome {name}!",
                        "redirect": "/dashboard"
                    }), 200
        except Exception as e:
            logger.error(f"Login database error: {e}")
        
        # Invalid credentials
        logger.warning(f"Failed login attempt: {email} ({role})")
        return jsonify({"error": "Invalid email or password"}), 401
    
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Login error"}), 500

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    # Check if user is logged in
    if 'role' not in session:
        return redirect(url_for('index'))
    
    role = session.get('role')
    return render_template('dashboard.html', role=role)

@app.route('/logout')
def logout():
    """Logout user and clear session"""
    session.clear()
    return redirect(url_for('index'))

# This route is now only called by the Patient's chat UI
@app.route('/ai_engine', methods=['POST'])
def ai_engine():
    user_query = request.json.get("message", "").lower()
    intent = classify_intent(user_query)
    replies = {
        "availability": "The doctor is currently available in the clinic.",
        "first_aid": "Rest and keep hydrated. Consult the doctor for medicine.",
        "location": "Our partner hospital is Metro General.",
        "general": "How can I help you today?"
    }
    return jsonify({"reply": replies.get(intent, "How can I help you today?")})

@app.route('/save_data', methods=['POST'])
@require_login
def save_data():
    """Save patient record with validation"""
    try:
        d = request.json
        
        # Validate required fields
        if not all([d.get('sno'), d.get('name'), d.get('age'), d.get('disease'), d.get('date'), d.get('stay'), d.get('fees')]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Validate and sanitize inputs
        try:
            record_id = int(d['sno'])
            name = sanitize_input(d['name'])
            age = int(d['age'])
            disease = sanitize_input(d['disease'])
            admit_date = d['date']
            stay_days = int(d['stay'])
            fees = float(d['fees'])
        except ValueError as e:
            return jsonify({"error": f"Invalid data format: {str(e)}"}), 400
        
        # Validate ranges
        if age < 0 or age > 150:
            return jsonify({"error": "Invalid age"}), 400
        if stay_days < 0 or stay_days > 365:
            return jsonify({"error": "Invalid stay duration"}), 400
        if fees < 0:
            return jsonify({"error": "Invalid fees amount"}), 400
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO records (id, name, age, disease, admit_date, stay_days, fees) VALUES (?,?,?,?,?,?,?)",
                       (record_id, name, age, disease, admit_date, stay_days, int(fees)))
        conn.commit()
        conn.close()
        
        logger.info(f"Patient record created: {name} (ID: {record_id})")
        return jsonify({"status": "success", "message": "Patient record saved"}), 201
    
    except Exception as e:
        logger.error(f"Error saving patient data: {e}")
        return jsonify({"error": f"Failed to save record: {str(e)}"}), 500

@app.route('/fetch_records', methods=['GET'])
@require_login
def fetch_records():
    """Fetch all patient records"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM records ORDER BY id ASC")
        data = cursor.fetchall()
        conn.close()
        logger.info(f"Patient records fetched - {len(data)} records")
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error fetching records: {e}")
        return jsonify({"error": "Failed to fetch records"}), 500

@app.route('/delete_record/<int:rec_id>', methods=['DELETE'])
@require_login
@require_role('receptionist', 'doctor')
def delete_record(rec_id):
    """Delete patient record (receptionist/doctor only)"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM records WHERE id = ?", (rec_id,))
        conn.commit()
        conn.close()
        logger.info(f"Patient record deleted: ID {rec_id}")
        return jsonify({"status": "success", "message": "Record deleted"}), 200
    except Exception as e:
        logger.error(f"Error deleting record: {e}")
        return jsonify({"error": "Failed to delete record"}), 500

# --- PHASE 2: APPOINTMENT SCHEDULING SYSTEM ---

@app.route('/schedule_appointment', methods=['POST'])
@require_login
@require_role('patient')
def schedule_appointment():
    """Schedule a new appointment"""
    try:
        data = request.json
        patient_id = session.get('user_id')
        doctor_id = data.get('doctor_id')
        hospital_id = data.get('hospital_id')
        appointment_date = data.get('appointment_date')
        appointment_time = data.get('appointment_time')
        reason = sanitize_input(data.get('reason', ''))
        
        if not all([doctor_id, hospital_id, appointment_date, appointment_time]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Validate appointment date is in future
        appt_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
        if appt_datetime <= datetime.now():
            return jsonify({"error": "Appointment must be in the future"}), 400
        
        # Check doctor availability
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Check if doctor has capacity
        cursor.execute('''SELECT patients_in_queue, max_patients_per_day FROM doctor_availability
                         WHERE doctor_id = ? AND hospital_id = ?''', (doctor_id, hospital_id))
        availability = cursor.fetchone()
        
        if not availability:
            conn.close()
            return jsonify({"error": "Doctor not available at this hospital"}), 400
        
        queue, max_patients = availability
        if queue >= max_patients:
            conn.close()
            return jsonify({"error": "Doctor has no available slots for this day"}), 400
        
        # Check for duplicate appointment time
        cursor.execute('''SELECT id FROM appointments 
                         WHERE doctor_id = ? AND appointment_date = ? AND appointment_time = ?''',
                      (doctor_id, appointment_date, appointment_time))
        
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "This time slot is already booked"}), 400
        
        # Create appointment
        cursor.execute('''INSERT INTO appointments (patient_id, doctor_id, hospital_id, 
                         appointment_date, appointment_time, reason, status)
                         VALUES (?, ?, ?, ?, ?, ?, 'scheduled')''',
                      (patient_id, doctor_id, hospital_id, appointment_date, appointment_time, reason))
        
        appointment_id = cursor.lastrowid
        
        # Update doctor queue
        cursor.execute('''UPDATE doctor_availability SET patients_in_queue = patients_in_queue + 1
                         WHERE doctor_id = ? AND hospital_id = ?''',
                      (doctor_id, hospital_id))
        
        # Create notification for doctor
        cursor.execute('''INSERT INTO notifications (user_id, notification_type, title, message, action_url)
                         VALUES (?, 'appointment', 'New Appointment Scheduled', 
                                'A new appointment has been scheduled', '/appointments')''',
                      (doctor_id,))
        
        # Create notification for patient
        cursor.execute('''INSERT INTO notifications (user_id, notification_type, title, message, action_url)
                         VALUES (?, 'appointment', 'Appointment Confirmed', 
                                'Your appointment has been confirmed', '/my_appointments')''',
                      (patient_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Appointment scheduled: ID {appointment_id}, Doctor {doctor_id}, Patient {patient_id}")
        
        return jsonify({
            "status": "success",
            "message": "Appointment scheduled successfully",
            "appointment_id": appointment_id
        }), 201
    
    except Exception as e:
        logger.error(f"Error scheduling appointment: {e}")
        return jsonify({"error": f"Failed to schedule appointment: {str(e)}"}), 500

@app.route('/get_appointments', methods=['GET'])
@require_login
def get_appointments():
    """Get appointments for current user"""
    try:
        user_id = session.get('user_id')
        user_role = session.get('role')
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        if user_role == 'patient':
            cursor.execute('''SELECT a.id, a.appointment_date, a.appointment_time, a.reason, a.status,
                                     u.name as doctor_name, h.name as hospital_name
                              FROM appointments a
                              JOIN users u ON a.doctor_id = u.id
                              JOIN hospitals h ON a.hospital_id = h.id
                              WHERE a.patient_id = ?
                              ORDER BY a.appointment_date DESC, a.appointment_time DESC''', (user_id,))
        else:  # doctor or receptionist
            cursor.execute('''SELECT a.id, a.appointment_date, a.appointment_time, a.reason, a.status,
                                     u.name as patient_name, h.name as hospital_name
                              FROM appointments a
                              JOIN users u ON a.patient_id = u.id
                              JOIN hospitals h ON a.hospital_id = h.id
                              WHERE a.doctor_id = ? OR a.doctor_id IN (SELECT id FROM users WHERE role = 'doctor')
                              ORDER BY a.appointment_date DESC, a.appointment_time DESC
                              LIMIT 100''', (user_id,))
        
        appointments = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "status": "success",
            "appointments": [{
                "id": a[0],
                "date": a[1],
                "time": a[2],
                "reason": a[3],
                "status": a[4],
                "participant": a[5],
                "hospital": a[6]
            } for a in appointments]
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching appointments: {e}")
        return jsonify({"error": "Failed to fetch appointments"}), 500

@app.route('/cancel_appointment/<int:appointment_id>', methods=['DELETE'])
@require_login
def cancel_appointment(appointment_id):
    """Cancel an appointment"""
    try:
        user_id = session.get('user_id')
        user_role = session.get('role')
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Check appointment exists and user has permission
        cursor.execute('''SELECT patient_id, doctor_id, hospital_id FROM appointments WHERE id = ?''',
                      (appointment_id,))
        appointment = cursor.fetchone()
        
        if not appointment:
            conn.close()
            return jsonify({"error": "Appointment not found"}), 404
        
        patient_id, doctor_id, hospital_id = appointment
        
        # Check permissions
        if user_role == 'patient' and patient_id != user_id:
            conn.close()
            return jsonify({"error": "Unauthorized"}), 403
        elif user_role == 'doctor' and doctor_id != user_id:
            conn.close()
            return jsonify({"error": "Unauthorized"}), 403
        
        # Cancel appointment
        cursor.execute('''UPDATE appointments SET status = 'cancelled' WHERE id = ?''',
                      (appointment_id,))
        
        # Update doctor queue
        cursor.execute('''UPDATE doctor_availability SET patients_in_queue = MAX(0, patients_in_queue - 1)
                         WHERE doctor_id = ? AND hospital_id = ?''',
                      (doctor_id, hospital_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Appointment cancelled: ID {appointment_id}")
        
        return jsonify({"status": "success", "message": "Appointment cancelled"}), 200
    
    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        return jsonify({"error": "Failed to cancel appointment"}), 500

# --- PRESCRIPTION MANAGEMENT SYSTEM ---

@app.route('/issue_prescription', methods=['POST'])
@require_login
@require_role('doctor')
def issue_prescription():
    """Issue a prescription to a patient"""
    try:
        data = request.json
        doctor_id = session.get('user_id')
        patient_id = data.get('patient_id')
        medication = sanitize_input(data.get('medication', ''))
        dosage = sanitize_input(data.get('dosage', ''))
        frequency = sanitize_input(data.get('frequency', ''))
        duration = sanitize_input(data.get('duration', ''))
        instructions = sanitize_input(data.get('instructions', ''))
        refills = int(data.get('refills', 0))
        
        if not all([patient_id, medication, dosage, frequency]):
            return jsonify({"error": "Missing required fields"}), 400
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Verify patient exists
        cursor.execute('SELECT name FROM users WHERE id = ? AND role = ?', (patient_id, 'patient'))
        patient = cursor.fetchone()
        
        if not patient:
            conn.close()
            return jsonify({"error": "Patient not found"}), 404
        
        # Create prescription
        cursor.execute('''INSERT INTO prescriptions 
                         (patient_id, doctor_id, medication, dosage, frequency, duration, instructions, refills_remaining)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (patient_id, doctor_id, medication, dosage, frequency, duration, instructions, refills))
        
        prescription_id = cursor.lastrowid
        
        # Create notification
        cursor.execute('''INSERT INTO notifications (user_id, notification_type, title, message, action_url)
                         VALUES (?, 'prescription', 'New Prescription', 
                                'You have a new prescription from your doctor', '/prescriptions')''',
                      (patient_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Prescription issued: ID {prescription_id}, Doctor {doctor_id}, Patient {patient_id}")
        
        return jsonify({
            "status": "success",
            "message": "Prescription issued successfully",
            "prescription_id": prescription_id
        }), 201
    
    except Exception as e:
        logger.error(f"Error issuing prescription: {e}")
        return jsonify({"error": f"Failed to issue prescription: {str(e)}"}), 500

@app.route('/get_prescriptions', methods=['GET'])
@require_login
def get_prescriptions():
    """Get prescriptions for current user"""
    try:
        user_id = session.get('user_id')
        user_role = session.get('role')
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        if user_role == 'patient':
            cursor.execute('''SELECT id, medication, dosage, frequency, duration, instructions, 
                                     refills_remaining, status, issued_date
                              FROM prescriptions
                              WHERE patient_id = ?
                              ORDER BY issued_date DESC''', (user_id,))
        else:  # doctor
            cursor.execute('''SELECT id, medication, dosage, frequency, duration, instructions,
                                     refills_remaining, status, issued_date
                              FROM prescriptions
                              WHERE doctor_id = ?
                              ORDER BY issued_date DESC''', (user_id,))
        
        prescriptions = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "status": "success",
            "prescriptions": [{
                "id": p[0],
                "medication": p[1],
                "dosage": p[2],
                "frequency": p[3],
                "duration": p[4],
                "instructions": p[5],
                "refills": p[6],
                "status": p[7],
                "issued_date": p[8]
            } for p in prescriptions]
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching prescriptions: {e}")
        return jsonify({"error": "Failed to fetch prescriptions"}), 500

# --- BILLING AND PAYMENT SYSTEM ---

@app.route('/create_billing', methods=['POST'])
@require_login
@require_role('receptionist', 'doctor')
def create_billing():
    """Create a billing invoice for a patient"""
    try:
        data = request.json
        patient_id = data.get('patient_id')
        amount = float(data.get('amount', 0))
        description = sanitize_input(data.get('description', 'Medical services'))
        due_date = data.get('due_date')
        
        if not patient_id or amount <= 0:
            return jsonify({"error": "Invalid patient or amount"}), 400
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Verify patient exists
        cursor.execute('SELECT name FROM users WHERE id = ? AND role = ?', (patient_id, 'patient'))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Patient not found"}), 404
        
        # Create billing record
        cursor.execute('''INSERT INTO billing (patient_id, amount, description, status, due_date)
                         VALUES (?, ?, ?, 'pending', ?)''',
                      (patient_id, amount, description, due_date))
        
        billing_id = cursor.lastrowid
        
        # Create notification
        cursor.execute('''INSERT INTO notifications (user_id, notification_type, title, message, action_url)
                         VALUES (?, 'billing', 'New Invoice', 
                                'You have a new invoice. Amount due: ${:.2f}', '/billing')'''.format(amount),
                      (patient_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Billing created: ID {billing_id}, Patient {patient_id}, Amount {amount}")
        
        return jsonify({
            "status": "success",
            "message": "Invoice created successfully",
            "billing_id": billing_id
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating billing: {e}")
        return jsonify({"error": f"Failed to create invoice: {str(e)}"}), 500

@app.route('/get_billing_history', methods=['GET'])
@require_login
def get_billing_history():
    """Get billing history for current user"""
    try:
        user_id = session.get('user_id')
        user_role = session.get('role')
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        if user_role == 'patient':
            cursor.execute('''SELECT id, amount, description, status, due_date, created_at
                              FROM billing
                              WHERE patient_id = ?
                              ORDER BY created_at DESC''', (user_id,))
        else:
            cursor.execute('''SELECT id, amount, description, status, due_date, created_at
                              FROM billing
                              ORDER BY created_at DESC
                              LIMIT 100''')
        
        bills = cursor.fetchall()
        conn.close()
        
        total_amount = sum(b[1] for b in bills if b[3] == 'pending')
        
        return jsonify({
            "status": "success",
            "billing_history": [{
                "id": b[0],
                "amount": b[1],
                "description": b[2],
                "status": b[3],
                "due_date": b[4],
                "created_at": b[5]
            } for b in bills],
            "total_outstanding": total_amount
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching billing history: {e}")
        return jsonify({"error": "Failed to fetch billing history"}), 500

@app.route('/process_payment', methods=['POST'])
@require_login
@require_role('patient')
def process_payment():
    """Process payment for a billing invoice"""
    try:
        data = request.json
        billing_id = data.get('billing_id')
        payment_method = sanitize_input(data.get('payment_method', 'card'))
        stripe_token = data.get('stripe_token')
        
        if not billing_id:
            return jsonify({"error": "Missing billing ID"}), 400
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Get billing info
        cursor.execute('''SELECT patient_id, amount FROM billing WHERE id = ? AND status = 'pending' ''',
                      (billing_id,))
        billing = cursor.fetchone()
        
        if not billing:
            conn.close()
            return jsonify({"error": "Billing record not found or already paid"}), 404
        
        patient_id, amount = billing
        
        # Check user owns this billing
        if patient_id != session.get('user_id'):
            conn.close()
            return jsonify({"error": "Unauthorized"}), 403
        
        # Process Stripe payment if payment method is card
        if payment_method == 'card' and stripe_token and STRIPE_SECRET_KEY:
            try:
                charge = stripe.Charge.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency='usd',
                    source=stripe_token,
                    description=f"Payment for billing #{billing_id}"
                )
                transaction_id = charge.id
                payment_status = 'completed'
            except stripe.error.CardError as e:
                conn.close()
                logger.warning(f"Card payment failed: {e}")
                return jsonify({"error": f"Payment failed: {str(e)}"}), 400
        else:
            # For testing or other payment methods
            transaction_id = f"TXN-{billing_id}-{datetime.now().timestamp()}"
            payment_status = 'completed'
        
        # Update billing status
        cursor.execute('''UPDATE billing SET status = 'paid', updated_at = CURRENT_TIMESTAMP
                         WHERE id = ?''', (billing_id,))
        
        # Create payment record
        cursor.execute('''INSERT INTO payments (billing_id, amount, payment_method, transaction_id, status)
                         VALUES (?, ?, ?, ?, ?)''',
                      (billing_id, amount, payment_method, transaction_id, payment_status))
        
        # Create notification
        cursor.execute('''INSERT INTO notifications (user_id, notification_type, title, message, action_url)
                         VALUES (?, 'payment', 'Payment Received', 
                                'Your payment has been received and confirmed', '/billing')''',
                      (patient_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Payment processed: Billing {billing_id}, Amount {amount}, Transaction {transaction_id}")
        
        return jsonify({
            "status": "success",
            "message": "Payment processed successfully",
            "transaction_id": transaction_id
        }), 200
    
    except Exception as e:
        logger.error(f"Error processing payment: {e}")
        return jsonify({"error": f"Payment processing failed: {str(e)}"}), 500

# --- NOTIFICATIONS SYSTEM ---

@app.route('/get_notifications', methods=['GET'])
@require_login
def get_notifications():
    """Get notifications for current user"""
    try:
        user_id = session.get('user_id')
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT id, notification_type, title, message, is_read, created_at
                         FROM notifications
                         WHERE user_id = ?
                         ORDER BY created_at DESC
                         LIMIT 50''', (user_id,))
        
        notifications = cursor.fetchall()
        conn.close()
        
        unread_count = sum(1 for n in notifications if not n[4])
        
        return jsonify({
            "status": "success",
            "notifications": [{
                "id": n[0],
                "type": n[1],
                "title": n[2],
                "message": n[3],
                "is_read": bool(n[4]),
                "created_at": n[5]
            } for n in notifications],
            "unread_count": unread_count
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        return jsonify({"error": "Failed to fetch notifications"}), 500

@app.route('/mark_notification_read/<int:notification_id>', methods=['POST'])
@require_login
def mark_notification_read(notification_id):
    """Mark notification as read"""
    try:
        user_id = session.get('user_id')
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        cursor.execute('''UPDATE notifications SET is_read = 1 
                         WHERE id = ? AND user_id = ?''',
                      (notification_id, user_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success"}), 200
    
    except Exception as e:
        logger.error(f"Error marking notification: {e}")
        return jsonify({"error": "Failed to mark notification"}), 500

# --- ANALYTICS & STATISTICS ---

@app.route('/get_statistics', methods=['GET'])
@require_login
def get_statistics():
    """Get system statistics for dashboard"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Get various statistics
        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "patient"')
        total_patients = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM appointments WHERE status = "scheduled"')
        scheduled_appointments = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM appointments WHERE DATE(appointment_date) = DATE("now")')
        todays_appointments = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM prescriptions WHERE status = "active"')
        active_prescriptions = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM billing WHERE status = "pending"')
        pending_bills = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount) FROM billing WHERE status = "pending"')
        outstanding_revenue = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM conversations')
        total_messages = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(available_beds) FROM hospitals')
        available_beds = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "statistics": {
                "total_patients": total_patients,
                "scheduled_appointments": scheduled_appointments,
                "todays_appointments": todays_appointments,
                "active_prescriptions": active_prescriptions,
                "pending_bills": pending_bills,
                "outstanding_revenue": outstanding_revenue,
                "total_messages": total_messages,
                "available_beds": available_beds
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        return jsonify({"error": "Failed to fetch statistics"}), 500


@app.route('/diagnose', methods=['POST'])
def diagnose():
    """
    AI-powered disease diagnosis based on symptoms (Patient feature only)
    Input: user symptoms
    Output: possible conditions and recommendations
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        symptoms = data.get('symptoms', '').strip()
        
        if not symptoms:
            return jsonify({"error": "Please provide symptoms"}), 400
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "placeholder":
            return jsonify({"error": "❌ Invalid API key - please check your configuration", "details": "API key not configured"}), 401
        
        openai_client = get_openai_client()
        if not openai_client:
            return jsonify({"error": "❌ Failed to initialize OpenAI client"}), 500
        
        prompt = f"""You are a medical AI assistant. A patient reports the following symptoms:
        
"{symptoms}"

Based on these symptoms, provide:
1. Possible conditions (most likely to least likely)
2. Recommended next steps (self-care or when to see a doctor)
3. Warning signs that require immediate medical attention

IMPORTANT: Always remind the user that this is NOT a substitute for professional medical advice."""

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful medical information assistant. Provide educational information only, not medical diagnosis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        diagnosis = response.choices[0].message.content
        
        return jsonify({
            "status": "success",
            "diagnosis": diagnosis,
            "disclaimer": "⚠️ This is AI-generated information for educational purposes only. Always consult with a licensed healthcare provider for medical advice."
        })
    
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "authentication" in error_msg.lower() or "invalid_api_key" in error_msg.lower():
            return jsonify({
                "error": "❌ Invalid API key - please check your configuration",
                "details": "Your OpenAI API key is invalid or expired",
                "solution": "Run 'python setup_api.py' to update your API key"
            }), 401
        elif "429" in error_msg or "rate_limit" in error_msg.lower():
            return jsonify({
                "error": "API rate limit exceeded",
                "details": "Too many requests in a short time",
                "solution": "Please wait a few minutes before trying again"
            }), 429
        else:
            return jsonify({
                "error": f"Service error: {error_msg}",
                "details": "Something went wrong with the API call"
            }), 500

# --- 5. CHAT & MESSAGING SYSTEM ---
@app.route('/get_doctors', methods=['GET'])
@require_login
def get_doctors():
    """Get list of all doctors for patient to chat with"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT id, name, email FROM users WHERE role = 'doctor' ''')
        doctors = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "status": "success",
            "doctors": [{"id": d[0], "name": d[1], "email": d[2]} for d in doctors]
        }), 200
    except Exception as e:
        logger.error(f"Error fetching doctors: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_receptionists', methods=['GET'])
@require_login
def get_receptionists():
    """Get list of all receptionists for patient to chat with"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT id, name, email FROM users WHERE role = 'receptionist' ''')
        receptionists = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "status": "success",
            "receptionists": [{"id": r[0], "name": r[1], "email": r[2]} for r in receptionists]
        }), 200
    except Exception as e:
        logger.error(f"Error fetching receptionists: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_patients', methods=['GET'])
@require_login
@require_role('doctor', 'receptionist')
def get_patients():
    """Get list of all patients (for doctor/receptionist)"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT id, name, email FROM users WHERE role = 'patient' ''')
        patients = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "status": "success",
            "patients": [{"id": p[0], "name": p[1], "email": p[2]} for p in patients]
        }), 200
    except Exception as e:
        logger.error(f"Error fetching patients: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/send_message', methods=['POST'])
@require_login
def send_message():
    """Send a message in conversation"""
    try:
        data = request.json
        sender_id = session.get('user_id')
        sender_role = session.get('role')
        sender_name = session.get('name')
        recipient_id = data.get('recipient_id')
        recipient_role = data.get('recipient_role')
        recipient_name = data.get('recipient_name')
        message = sanitize_input(data.get('message', '')).strip()
        
        if not all([sender_id, sender_role, recipient_id, recipient_role, message]):
            return jsonify({"error": "Missing required fields"}), 400
        
        if len(message) > 1000:
            return jsonify({"error": "Message too long (max 1000 characters)"}), 400
        
        if len(message) < 1:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO conversations 
                          (sender_id, sender_role, sender_name, recipient_id, recipient_role, recipient_name, message) 
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (sender_id, sender_role, sender_name, recipient_id, recipient_role, recipient_name, message))
        
        message_id = cursor.lastrowid
        
        # Create notification for recipient
        cursor.execute('''INSERT INTO notifications (user_id, notification_type, title, message, action_url)
                         VALUES (?, 'message', 'New Message', 
                                'You have a new message from {sender_name}', '/messages')'''.format(sender_name=sender_name),
                      (recipient_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Message sent: {sender_name} -> {recipient_name}")
        
        return jsonify({
            "status": "success",
            "message": "Message sent successfully",
            "message_id": message_id
        }), 201
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_conversation/<int:recipient_id>/<recipient_role>', methods=['GET'])
@require_login
def get_conversation(recipient_id, recipient_role):
    """Get conversation history between two users"""
    try:
        sender_id = session.get('user_id')
        sender_role = session.get('role')
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Get all messages between these two users (both directions)
        cursor.execute('''SELECT sender_id, sender_name, message, timestamp, sender_role 
                          FROM conversations 
                          WHERE ((sender_id = ? AND recipient_id = ? AND sender_role = ? AND recipient_role = ?)
                                 OR
                                 (sender_id = ? AND recipient_id = ? AND sender_role = ? AND recipient_role = ?))
                          ORDER BY timestamp ASC''',
                      (sender_id, recipient_id, sender_role, recipient_role,
                       recipient_id, sender_id, recipient_role, sender_role))
        
        messages = cursor.fetchall()
        
        # Mark messages as read
        cursor.execute('''UPDATE conversations 
                          SET is_read = 1 
                          WHERE recipient_id = ? AND sender_id = ? AND is_read = 0''',
                      (sender_id, recipient_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Conversation fetched - Sender {sender_id}, Recipient {recipient_id}, Messages: {len(messages)}")
        
        return jsonify({
            "status": "success",
            "messages": [
                {
                    "sender_id": m[0],
                    "sender_name": m[1],
                    "message": m[2],
                    "timestamp": m[3],
                    "sender_role": m[4]
                } for m in messages
            ]
        }), 200
    except Exception as e:
        logger.error(f"Error fetching conversation: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_conversations', methods=['GET'])
@require_login
def get_conversations():
    """Get all unique conversations for current user"""
    try:
        user_id = session.get('user_id')
        user_role = session.get('role')
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Get unique conversation partners and last message
        cursor.execute('''SELECT DISTINCT 
                            CASE WHEN sender_id = ? THEN recipient_id ELSE sender_id END as other_user_id,
                            CASE WHEN sender_id = ? THEN recipient_name ELSE sender_name END as other_user_name,
                            CASE WHEN sender_id = ? THEN recipient_role ELSE sender_role END as other_user_role,
                            (SELECT MAX(timestamp) FROM conversations c2 
                             WHERE (c2.sender_id = ? AND c2.recipient_id = other_user_id) OR 
                                   (c2.recipient_id = ? AND c2.sender_id = other_user_id))
                          FROM conversations c
                          WHERE sender_id = ? OR recipient_id = ?
                          ORDER BY timestamp DESC''',
                      (user_id, user_id, user_id, user_id, user_id, user_id, user_id))
        
        conversations = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "status": "success",
            "conversations": [
                {
                    "user_id": c[0],
                    "user_name": c[1],
                    "user_role": c[2],
                    "last_message_time": c[3]
                } for c in conversations
            ]
        }), 200
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        return jsonify({"error": str(e)}), 500

# --- 6. REAL-TIME HOSPITAL DOCTOR AVAILABILITY SYSTEM ---
@app.route('/get_all_hospitals', methods=['GET'])
def get_all_hospitals():
    """Get list of all hospitals"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT id, name, location, phone, available_beds, total_beds 
                         FROM hospitals ORDER BY name''')
        hospitals = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "status": "success",
            "hospitals": [
                {
                    "id": h[0],
                    "name": h[1],
                    "location": h[2],
                    "phone": h[3],
                    "available_beds": h[4],
                    "total_beds": h[5]
                } for h in hospitals
            ]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/check_doctor_availability/<doctor_name>', methods=['GET'])
def check_doctor_availability(doctor_name):
    """Check which hospitals have a specific doctor available"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        cursor.execute('''SELECT hospital_id, hospital_name, is_available, start_time, end_time, 
                                 patients_in_queue, max_patients_per_day, specialty
                          FROM doctor_availability 
                          WHERE doctor_name LIKE ? 
                          ORDER BY is_available DESC, hospital_name''',
                      (f'%{doctor_name}%',))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return jsonify({
                "status": "no_doctor_found",
                "message": f"Doctor '{doctor_name}' not found in system"
            }), 404
        
        availability_list = [
            {
                "hospital_id": r[0],
                "hospital_name": r[1],
                "is_available": bool(r[2]),
                "status": "Available" if r[2] else "Not Available",
                "start_time": r[3],
                "end_time": r[4],
                "patients_in_queue": r[5],
                "max_patients_per_day": r[6],
                "specialty": r[7],
                "slots_available": max(0, r[6] - r[5]) if r[2] else 0
            } for r in results
        ]
        
        return jsonify({
            "status": "success",
            "doctor_name": doctor_name,
            "availability": availability_list
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/check_doctor_in_hospital/<doctor_name>/<int:hospital_id>', methods=['GET'])
def check_doctor_in_hospital(doctor_name, hospital_id):
    """Check if a specific doctor is available in a specific hospital"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        cursor.execute('''SELECT id, doctor_name, is_available, start_time, end_time, 
                                 patients_in_queue, max_patients_per_day, specialty, hospital_name
                          FROM doctor_availability 
                          WHERE doctor_name LIKE ? AND hospital_id = ?''',
                      (f'%{doctor_name}%', hospital_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            # Doctor not in this hospital, suggest alternatives
            return check_doctor_availability(doctor_name)
        
        doctor_id, name, is_available, start_time, end_time, queue, max_patients, specialty, hospital = result
        
        return jsonify({
            "status": "success",
            "doctor_found": True,
            "doctor": {
                "name": name,
                "specialty": specialty,
                "hospital": hospital,
                "is_available": bool(is_available),
                "status": "Available" if is_available else "Not Available",
                "working_hours": f"{start_time} - {end_time}",
                "patients_in_queue": queue,
                "slots_available": max(0, max_patients - queue) if is_available else 0,
                "wait_time_estimate": f"{queue * 15} minutes" if is_available else "Not available"
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_hospital_doctors/<int:hospital_id>', methods=['GET'])
def get_hospital_doctors(hospital_id):
    """Get all doctors in a specific hospital"""
    try:
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Get hospital info
        cursor.execute('SELECT name, location FROM hospitals WHERE id = ?', (hospital_id,))
        hospital_info = cursor.fetchone()
        
        if not hospital_info:
            return jsonify({"status": "error", "message": "Hospital not found"}), 404
        
        # Get doctors in this hospital
        cursor.execute('''SELECT DISTINCT doctor_id, doctor_name, specialty, is_available, 
                                 start_time, end_time, patients_in_queue, max_patients_per_day
                          FROM doctor_availability 
                          WHERE hospital_id = ? 
                          ORDER BY is_available DESC, doctor_name''',
                      (hospital_id,))
        
        doctors = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "status": "success",
            "hospital": {
                "id": hospital_id,
                "name": hospital_info[0],
                "location": hospital_info[1]
            },
            "doctors": [
                {
                    "doctor_id": d[0],
                    "name": d[1],
                    "specialty": d[2],
                    "is_available": bool(d[3]),
                    "status": "Available" if d[3] else "Not Available",
                    "working_hours": f"{d[4]} - {d[5]}",
                    "patients_in_queue": d[6],
                    "slots_available": max(0, d[7] - d[6]) if d[3] else 0
                } for d in doctors
            ]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/update_doctor_availability', methods=['POST'])
@require_login
@require_role('receptionist', 'doctor')
def update_doctor_availability():
    """Update doctor availability status (for receptionist/admin)"""
    try:
        data = request.json
        doctor_id = data.get('doctor_id')
        hospital_id = data.get('hospital_id')
        is_available = int(data.get('is_available', 1))
        patients_in_queue = data.get('patients_in_queue')
        
        if not all([doctor_id, hospital_id]):
            return jsonify({"error": "Missing required fields"}), 400
        
        if is_available not in [0, 1]:
            return jsonify({"error": "Invalid availability value"}), 400
        
        if patients_in_queue is not None:
            try:
                patients_in_queue = int(patients_in_queue)
                if patients_in_queue < 0:
                    return jsonify({"error": "Queue cannot be negative"}), 400
            except ValueError:
                return jsonify({"error": "Invalid queue value"}), 400
        
        conn = sqlite3.connect('healthcare.db')
        cursor = conn.cursor()
        
        # Check doctor availability record exists
        cursor.execute('''SELECT id FROM doctor_availability WHERE doctor_id = ? AND hospital_id = ?''',
                      (doctor_id, hospital_id))
        
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Doctor availability record not found"}), 404
        
        # Update doctor availability
        update_fields = ['is_available = ?']
        params = [is_available]
        
        if patients_in_queue is not None:
            update_fields.append('patients_in_queue = ?')
            params.append(patients_in_queue)
        
        params.extend([doctor_id, hospital_id])
        
        cursor.execute(f'''UPDATE doctor_availability 
                          SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                          WHERE doctor_id = ? AND hospital_id = ?''',
                      params)
        conn.commit()
        conn.close()
        
        logger.info(f"Doctor availability updated: Doctor {doctor_id}, Hospital {hospital_id}, Available: {is_available}")
        
        return jsonify({
            "status": "success",
            "message": "Doctor availability updated"
        }), 200
    except Exception as e:
        logger.error(f"Error updating doctor availability: {e}")
        return jsonify({"error": f"Failed to update availability: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)