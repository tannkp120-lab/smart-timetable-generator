import json
import random
import os
import datetime
import re
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

# --- App Configuration ---
app = Flask(__name__)
CORS(app)

# Get the directory of the current script
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Database Configuration ---
DB_CONFIG = {
    'host': 'localhost',
    'database': 'timetable_db',
    'user': 'root',
    'password': '' # Default for XAMPP
}

# --- Database Connection Helper ---
def create_connection():
    """Create a database connection to the MySQL database."""
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
    return connection

# --- Database Initialization (Migrations) ---
def init_db():
    """Initializes the database tables if they don't exist."""
    conn = create_connection()
    if conn is None:
        return
    
    cursor = conn.cursor()
    
    # 1. Timeslots Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS timeslots (
        id INT AUTO_INCREMENT PRIMARY KEY,
        day_of_week VARCHAR(20) NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        type VARCHAR(20) DEFAULT 'Both' 
    )
    """)

    # 2. Attendance Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id INT NOT NULL,
        course_id INT NOT NULL,
        class_id INT,
        division_id INT,
        date DATE NOT NULL,
        status VARCHAR(20) NOT NULL,
        taken_by_user_id INT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_attendance (student_id, course_id, date)
    )
    """)

    # 3. Substitutions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS substitutions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        original_teacher_id INT NOT NULL,
        proxy_teacher_id INT NOT NULL,
        course_id INT NOT NULL,
        class_id INT NOT NULL,
        division_id INT NOT NULL,
        date DATE NOT NULL,
        timeslot_id INT NOT NULL,
        status ENUM('Pending', 'Approved', 'Rejected') DEFAULT 'Pending',
        FOREIGN KEY (original_teacher_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (proxy_teacher_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
        FOREIGN KEY (division_id) REFERENCES divisions(id) ON DELETE CASCADE,
        FOREIGN KEY (timeslot_id) REFERENCES timeslots(id) ON DELETE CASCADE
    )
    """)
    
    # --- MIGRATION: Add new columns if they don't exist ---
    try:
        cursor.execute("ALTER TABLE courses ADD COLUMN lecture_times VARCHAR(255)")
    except Error:
        pass # Column likely exists

    try:
        cursor.execute("ALTER TABLE courses ADD COLUMN practical_times VARCHAR(255)")
    except Error:
        pass # Column likely exists

    # Seed Timeslots if empty
    cursor.execute("SELECT COUNT(*) FROM timeslots")
    if cursor.fetchone()[0] == 0:
        default_slots = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        times = [
            ("09:00:00", "10:00:00", "Lecture"),
            ("10:00:00", "11:00:00", "Lecture"),
            ("11:00:00", "12:00:00", "Lecture"),
            ("12:00:00", "13:00:00", "Break"),
            ("13:00:00", "14:00:00", "Lecture"),
            ("14:00:00", "15:00:00", "Practical"),
            ("15:00:00", "16:00:00", "Practical")
        ]
        for day in days:
            for start, end, t_type in times:
                default_slots.append((day, start, end, t_type))
        cursor.executemany("INSERT INTO timeslots (day_of_week, start_time, end_time, type) VALUES (%s, %s, %s, %s)", default_slots)
        conn.commit()
        print("Seeded default timeslots.")

    conn.close()

# Run DB Init
init_db()

# --- Static File Serving ---
@app.route('/')
def serve_root():
    return send_from_directory(APP_ROOT, 'user_login.html')

@app.route('/<path:filename>')
def serve_static_file(filename):
    known_files = ['index.html', 'admin_auth.html', 'user_login.html', 'style.css', 'timetable.jpg']
    if filename in known_files:
        return send_from_directory(APP_ROOT, filename)
    return "File not found", 404

# --- Helper: Normalize Time String ---
def normalize_time_str(t_input):
    """
    Converts inputs like "2pm", "14", "14:00" into "14:00:00".
    """
    if not t_input: return None
    
    # Convert timedelta to string if needed
    if isinstance(t_input, datetime.timedelta):
        total_seconds = int(t_input.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02}:{minutes:02}:00"

    t_str = str(t_input).lower().strip()
    
    # Detect AM/PM
    is_pm = 'pm' in t_str
    is_am = 'am' in t_str
    
    # Clean string
    t_str = t_str.replace('am', '').replace('pm', '').strip()
    
    try:
        h = 0
        m = 0
        s = 0
        
        if ':' in t_str:
            parts = t_str.split(':')
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            s = int(parts[2]) if len(parts) > 2 else 0
        else:
            h = int(t_str)
            
        # 12-hour to 24-hour conversion
        if is_pm and h < 12:
            h += 12
        if is_am and h == 12:
            h = 0
            
        return f"{h:02}:{m:02}:{s:02}"
    except ValueError:
        return None

def get_duration_minutes(start, end):
    """Calculates duration in minutes between two time objects or strings."""
    def to_seconds(t):
        if isinstance(t, datetime.timedelta):
            return t.total_seconds()
        # Handle string "HH:MM:SS"
        h, m, s = map(int, str(t).split(':'))
        return h*3600 + m*60 + s

    try:
        return (to_seconds(end) - to_seconds(start)) / 60
    except:
        return 0

# --- API Endpoints ---

@app.route('/api/admin/signup', methods=['POST'])
def admin_signup():
    data = request.get_json()
    name, email, password = data.get('name'), data.get('email'), data.get('password')
    if not all([name, email, password]): return jsonify({'error': 'Missing required fields'}), 400

    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'error': 'An account with this email already exists'}), 409
        query = "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'admin')"
        cursor.execute(query, (name, email, password))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        new_user = cursor.fetchone()
        return jsonify({'user': new_user}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email, password = data.get('email'), data.get('password')
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.*, d.name as department_name, c.name as class_name, dvn.name as division_name
        FROM users u 
        LEFT JOIN departments d ON u.department_id = d.id
        LEFT JOIN classes c ON u.class_id = c.id
        LEFT JOIN divisions dvn ON u.division_id = dvn.id
        WHERE u.email = %s AND u.password = %s
    """, (email, password))
    user = cursor.fetchone()
    conn.close()
    if user: return jsonify({'user': user})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/data', methods=['GET'])
def get_all_data():
    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT id, name FROM users WHERE role = 'lecturer'")
    lecturers = cursor.fetchall()
    
    cursor.execute("SELECT * FROM rooms")
    rooms = cursor.fetchall()
    
    cursor.execute("""
        SELECT c.*, u.name as lecturer_name, d.name as department_name, s.name as stream_name, dvn.name as division_name
        FROM courses c
        LEFT JOIN users u ON c.lecturer_id = u.id
        LEFT JOIN classes cl ON c.class_id = cl.id
        LEFT JOIN departments d ON cl.department_id = d.id
        LEFT JOIN streams s ON d.stream_id = s.id
        LEFT JOIN divisions dvn ON c.division_id = dvn.id
    """)
    courses = cursor.fetchall()
    
    cursor.execute("SELECT cl.id, cl.name, d.name as department_name, cl.department_id, s.name as stream_name, s.id as stream_id FROM classes cl LEFT JOIN departments d ON cl.department_id = d.id LEFT JOIN streams s ON d.stream_id = s.id")
    classes = cursor.fetchall()
    
    cursor.execute("SELECT * FROM divisions")
    divisions = cursor.fetchall()
    
    cursor.execute("SELECT * FROM streams")
    streams = cursor.fetchall()
    
    cursor.execute("SELECT d.id, d.name, s.name as stream_name, d.stream_id FROM departments d LEFT JOIN streams s ON d.stream_id = s.id")
    departments = cursor.fetchall()
    
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.department_id, u.class_id, u.division_id, 
        d.name as department_name, c.name as class_name, dvn.name as division_name
        FROM users u 
        LEFT JOIN departments d ON u.department_id = d.id
        LEFT JOIN classes c ON u.class_id = c.id
        LEFT JOIN divisions dvn ON u.division_id = dvn.id
    """)
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM timeslots ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'), start_time")
    timeslots = cursor.fetchall()
    for ts in timeslots:
        ts['start_time'] = str(ts['start_time'])
        ts['end_time'] = str(ts['end_time'])
    
    conn.close()

    return jsonify({
        'lecturers': lecturers, 'rooms': rooms, 'courses': courses, 'classes': classes,
        'divisions': divisions, 'timeslots': timeslots, 'users': users, 'streams': streams,
        'departments': departments
    })

def add_item(table_name, columns, values):
    try:
        conn = create_connection()
        cursor = conn.cursor()
        query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(values))})"
        cursor.execute(query, tuple(values))
        conn.commit()
        return jsonify({'success': True}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.get_json()
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (data['email'],))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'An account with this email already exists'}), 409
    cols = ['name', 'email', 'password', 'role', 'department_id', 'class_id', 'division_id']
    vals = [data.get(c) for c in cols]
    query = f"INSERT INTO users ({', '.join(cols)}) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    cursor.execute(query, tuple(vals))
    conn.commit()
    conn.close()
    return jsonify({'success': True}), 201

@app.route('/api/streams', methods=['POST'])
def add_stream(): return add_item('streams', ['name'], [request.json.get('name')])

@app.route('/api/departments', methods=['POST'])
def add_department(): return add_item('departments', ['name', 'stream_id'], [request.json.get('name'), request.json.get('stream_id')])

@app.route('/api/rooms', methods=['POST'])
def add_room(): return add_item('rooms', ['name', 'capacity', 'type'], [request.json.get(k) for k in ['name', 'capacity', 'type']])

@app.route('/api/classes', methods=['POST'])
def add_class(): return add_item('classes', ['name', 'department_id'], [request.json.get('name'), request.json.get('department_id')])

@app.route('/api/divisions', methods=['POST'])
def add_division(): return add_item('divisions', ['name'], [request.json.get('name')])

@app.route('/api/courses', methods=['POST'])
def add_course():
    cols = ['name', 'lecturer_id', 'class_id', 'division_id', 'lectures_per_week', 'practicals_per_week', 'lecture_times', 'practical_times']
    return add_item('courses', cols, [request.json.get(c) for c in cols])

@app.route('/api/timeslots', methods=['POST'])
def add_timeslot():
    data = request.get_json()
    start = data.get('start_time')
    end = data.get('end_time')
    if len(start) == 5: start += ":00"
    if len(end) == 5: end += ":00"
    
    return add_item('timeslots', 
                   ['day_of_week', 'start_time', 'end_time', 'type'], 
                   [data.get('day_of_week'), start, end, data.get('type')])

@app.route('/api/users/<int:id>', methods=['PUT'])
def update_user(id):
    data = request.get_json()
    password = data.get('password')
    cols_to_update = ['name', 'email', 'role', 'department_id', 'class_id', 'division_id']
    values = [data.get(c) for c in cols_to_update]
    set_clause = ", ".join([f"{col} = %s" for col in cols_to_update])
    if password:
        set_clause += ", password = %s"
        values.append(password)
    values.append(id)
    try:
        conn = create_connection()
        cursor = conn.cursor()
        query = f"UPDATE users SET {set_clause} WHERE id = %s"
        cursor.execute(query, tuple(values))
        conn.commit()
        return jsonify({'success': True}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/courses/<int:id>', methods=['PUT'])
def update_course(id):
    data = request.get_json()
    cols_to_update = ['name', 'lecturer_id', 'class_id', 'division_id', 'lectures_per_week', 'practicals_per_week', 'lecture_times', 'practical_times']
    values = [data.get(c) for c in cols_to_update]
    values.append(id)
    set_clause = ", ".join([f"{col} = %s" for col in cols_to_update])
    try:
        conn = create_connection()
        cursor = conn.cursor()
        query = f"UPDATE courses SET {set_clause} WHERE id = %s"
        cursor.execute(query, tuple(values))
        conn.commit()
        return jsonify({'success': True}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 400
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/delete/<string:item_type>/<int:item_id>', methods=['DELETE'])
def delete_item(item_type, item_id):
    allowed_tables = {
        "users": "users", "courses": "courses", "streams": "streams",
        "departments": "departments", "classes": "classes", "divisions": "divisions",
        "rooms": "rooms", "timeslots": "timeslots", "substitutions": "substitutions"
    }
    table_name = allowed_tables.get(item_type)
    if not table_name: return jsonify({'error': 'Invalid item type'}), 400
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", (item_id,))
        conn.commit()
        return ('', 204)
    except Error as e:
        if e.errno == 1451: return jsonify({'error': 'Cannot delete item because it is used by other records.'}), 409
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

# --- Attendance ---
@app.route('/api/attendance', methods=['POST'])
def add_attendance():
    data = request.get_json()
    try:
        conn = create_connection()
        cursor = conn.cursor()
        insert_query = """INSERT INTO attendance (student_id, course_id, date, status, taken_by_user_id, class_id, division_id) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE status = VALUES(status), taken_by_user_id = VALUES(taken_by_user_id)"""
        records = [(s['student_id'], data['course_id'], data['date'], s['status'], data['taken_by_user_id'], data['class_id'], data['division_id']) for s in data['students_status']]
        cursor.executemany(insert_query, records)
        conn.commit()
        return jsonify({'success': True, 'message': f"Attendance for {data['date']} submitted."}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    filters = []
    params = []
    base_query = "SELECT a.*, s.name as student_name, c.name as course_name FROM attendance a JOIN users s ON a.student_id = s.id JOIN courses c ON a.course_id = c.id WHERE 1=1"
    
    for key in ['student_id', 'class_id', 'division_id', 'course_id']:
        if request.args.get(key):
            filters.append(f"a.{key} = %s")
            params.append(request.args.get(key))
    if request.args.get('start_date'): filters.append("a.date >= %s"); params.append(request.args.get('start_date'))
    if request.args.get('end_date'): filters.append("a.date <= %s"); params.append(request.args.get('end_date'))
    
    if filters: base_query += " AND " + " AND ".join(filters)
    base_query += " ORDER BY a.date DESC, s.name ASC"

    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(base_query, tuple(params))
        records = cursor.fetchall()
        for r in records: 
            if isinstance(r['date'], datetime.date): r['date'] = r['date'].isoformat()
        return jsonify({'attendance': records})
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/attendance/stats', methods=['GET'])
def get_attendance_stats():
    student_id = request.args.get('student_id')
    class_id = request.args.get('class_id')
    division_id = request.args.get('division_id')
    course_id = request.args.get('course_id')
    teacher_id = request.args.get('teacher_id')
    
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                a.student_id, 
                u.name as student_name,
                a.course_id, 
                c.name as course_name,
                COUNT(*) as total_lectures,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as attended_lectures
            FROM attendance a
            JOIN users u ON a.student_id = u.id
            JOIN courses c ON a.course_id = c.id
            WHERE 1=1
        """
        params = []
        if student_id:
            query += " AND a.student_id = %s"
            params.append(student_id)
        if class_id:
            query += " AND a.class_id = %s"
            params.append(class_id)
        if division_id:
            query += " AND a.division_id = %s"
            params.append(division_id)
        if course_id:
            query += " AND a.course_id = %s"
            params.append(course_id)
        if teacher_id:
            query += " AND c.lecturer_id = %s"
            params.append(teacher_id)
            
        query += " GROUP BY a.student_id, a.course_id ORDER BY u.name, c.name"
        cursor.execute(query, tuple(params))
        stats = cursor.fetchall()
        results = []
        for row in stats:
            total = int(row['total_lectures'])
            attended = int(row['attended_lectures']) if row['attended_lectures'] is not None else 0
            percentage = round((attended / total * 100), 2) if total > 0 else 0
            row['total_lectures'] = total
            row['attended_lectures'] = attended
            row['percentage'] = percentage
            results.append(row)
        return jsonify({'stats': results})
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

# --- Substitutions API ---
@app.route('/api/substitutions', methods=['POST'])
def add_substitution():
    data = request.get_json()
    cols = ['original_teacher_id', 'proxy_teacher_id', 'course_id', 'class_id', 'division_id', 'date', 'timeslot_id']
    try:
        conn = create_connection()
        cursor = conn.cursor()
        status = data.get('status', 'Pending')
        vals = [data.get(c) for c in cols]
        vals.append(status)
        query = f"INSERT INTO substitutions ({', '.join(cols)}, status) VALUES ({', '.join(['%s']*len(cols))}, %s)"
        cursor.execute(query, tuple(vals))
        conn.commit()
        return jsonify({'success': True}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/substitutions', methods=['GET'])
def get_substitutions():
    teacher_id = request.args.get('teacher_id')
    class_id = request.args.get('class_id')
    division_id = request.args.get('division_id')
    status = request.args.get('status')
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT s.*, 
                   u1.name as original_teacher_name, 
                   u2.name as proxy_teacher_name,
                   c.name as course_name,
                   cl.name as class_name,
                   d.name as division_name,
                   ts.day_of_week, ts.start_time, ts.end_time
            FROM substitutions s
            JOIN users u1 ON s.original_teacher_id = u1.id
            JOIN users u2 ON s.proxy_teacher_id = u2.id
            JOIN courses c ON s.course_id = c.id
            JOIN classes cl ON s.class_id = cl.id
            JOIN divisions d ON s.division_id = d.id
            JOIN timeslots ts ON s.timeslot_id = ts.id
            WHERE 1=1
        """
        params = []
        if teacher_id:
            query += " AND (s.original_teacher_id = %s OR s.proxy_teacher_id = %s)"
            params.extend([teacher_id, teacher_id])
        if class_id:
            query += " AND s.class_id = %s"
            params.append(class_id)
        if division_id:
            query += " AND s.division_id = %s"
            params.append(division_id)
        if status:
            query += " AND s.status = %s"
            params.append(status)
        query += " ORDER BY s.date DESC"
        cursor.execute(query, tuple(params))
        subs = cursor.fetchall()
        for s in subs:
            if isinstance(s['date'], datetime.date): s['date'] = s['date'].isoformat()
            if isinstance(s['start_time'], datetime.timedelta): s['start_time'] = str(s['start_time'])
            if isinstance(s['end_time'], datetime.timedelta): s['end_time'] = str(s['end_time'])
        return jsonify({'substitutions': subs})
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/substitutions/<int:id>/status', methods=['PUT'])
def update_substitution_status(id):
    data = request.get_json()
    status = data.get('status')
    if status not in ['Approved', 'Rejected']: return jsonify({'error': 'Invalid status'}), 400
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE substitutions SET status = %s WHERE id = %s", (status, id))
        if status == 'Approved':
            cursor.execute("""
                SELECT s.*, u.name as proxy_teacher_name
                FROM substitutions s
                JOIN users u ON s.proxy_teacher_id = u.id
                WHERE s.id = %s
            """, (id,))
            sub = cursor.fetchone()
            if sub:
                cursor.execute("SELECT schedule_data FROM timetables WHERE class_id = %s AND division_id = %s", (sub['class_id'], sub['division_id']))
                result = cursor.fetchone()
                if result and result['schedule_data']:
                    schedule = json.loads(result['schedule_data'])
                    updated = False
                    for entry in schedule:
                        if entry['course_id'] == sub['course_id'] and entry['timeslot_id'] == sub['timeslot_id']:
                            entry['teacher'] = sub['proxy_teacher_name'] 
                            entry['is_substitution'] = True 
                            updated = True
                            break 
                    if updated:
                        cursor.execute("UPDATE timetables SET schedule_data = %s WHERE class_id = %s AND division_id = %s", 
                                     (json.dumps(schedule), sub['class_id'], sub['division_id']))
        conn.commit()
        return jsonify({'success': True}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

# --- Existing Schedule & Timetable Endpoints ---

@app.route('/api/teacher/schedule/<int:teacher_id>', methods=['GET'])
def get_teacher_schedule(teacher_id):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT t.class_id, t.division_id, t.schedule_data, c.name as class_name, d.name as division_name FROM timetables t JOIN classes c ON t.class_id = c.id JOIN divisions d ON t.division_id = d.id")
        all_timetables = cursor.fetchall()
        teacher_schedule = []
        cursor.execute("SELECT name FROM users WHERE id = %s", (teacher_id,))
        teacher_user = cursor.fetchone()
        if teacher_user:
            teacher_name = teacher_user['name']
            for record in all_timetables:
                if not record['schedule_data']: continue
                schedule = json.loads(record['schedule_data'])
                for entry in schedule:
                    if entry.get('teacher') == teacher_name:
                        entry['class_name'] = record['class_name']
                        entry['division_name'] = record['division_name']
                        entry['class_id'] = record['class_id']
                        entry['division_id'] = record['division_id']
                        teacher_schedule.append(entry)
        return jsonify({'schedule': teacher_schedule})
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/timetables/<int:class_id>/<int:division_id>', methods=['GET'])
def get_timetable(class_id, division_id):
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT schedule_data FROM timetables WHERE class_id = %s AND division_id = %s", (class_id, division_id))
        result = cursor.fetchone()
        if result and result['schedule_data']:
            return jsonify({'timetable': json.loads(result['schedule_data'])})
        else:
            return jsonify({'error': 'Timetable not found.'}), 404
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/timetable/customize', methods=['PUT'])
def customize_timetable():
    data = request.get_json()
    try:
        conn = create_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT schedule_data FROM timetables WHERE class_id = %s AND division_id = %s", (data['class_id'], data['division_id']))
        result = cursor.fetchone()
        if not result: return jsonify({'error': 'No timetable found'}), 404
        
        schedule = json.loads(result['schedule_data'])
        entry_to_move = data['entry_to_move']
        new_timeslot_id = int(data['new_timeslot_id'])
        new_room_name = data.get('new_room_name')
        
        idx = next((i for i, e in enumerate(schedule) if e['course_id'] == entry_to_move['course_id'] and e['timeslot_id'] == entry_to_move['timeslot_id']), -1)
        if idx == -1: return jsonify({'error': 'Session not found'}), 404

        for i, entry in enumerate(schedule):
            if i == idx: continue
            if entry['timeslot_id'] == new_timeslot_id: 
                return jsonify({'error': 'Time slot already occupied in this class.'}), 409
            
        schedule[idx]['timeslot_id'] = new_timeslot_id
        if new_room_name:
            schedule[idx]['room'] = new_room_name
        
        cursor.execute("UPDATE timetables SET schedule_data = %s WHERE class_id = %s AND division_id = %s", (json.dumps(schedule), data['class_id'], data['division_id']))
        conn.commit()
        return jsonify({'success': True, 'timetable': schedule})
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/generate', methods=['POST'])
def generate_timetable():
    data = request.get_json()
    class_id, division_id = data.get('class_id'), data.get('division_id')

    conn = create_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM rooms")
    rooms = cursor.fetchall()
    
    cursor.execute("""
        SELECT c.*, u.name as lecturer_name 
        FROM courses c JOIN users u ON c.lecturer_id = u.id 
        WHERE c.class_id = %s AND c.division_id = %s
    """, (class_id, division_id))
    courses_for_class = cursor.fetchall()
    
    cursor.execute("SELECT * FROM timeslots ORDER BY FIELD(day_of_week, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'), start_time")
    all_timeslots = cursor.fetchall()
    
    cursor.execute("SELECT schedule_data FROM timetables WHERE NOT (class_id = %s AND division_id = %s)", (class_id, division_id))
    existing_timetables = cursor.fetchall()
    
    global_teacher_occupied = {} 
    for row in existing_timetables:
        if not row['schedule_data']: continue
        s_data = json.loads(row['schedule_data'])
        for entry in s_data:
            global_teacher_occupied[(entry['teacher'], entry['timeslot_id'])] = True
            
    conn.close() 

    lecture_rooms = [r for r in rooms if r['type'] == 'Lecture']
    lab_rooms = [r for r in rooms if r['type'] == 'Lab']
    
    lecture_sessions = []
    practical_sessions = []
    
    timeslot_lookup = {}
    for ts in all_timeslots:
        norm_time = normalize_time_str(ts['start_time'])
        if norm_time:
            timeslot_lookup[(ts['day_of_week'], norm_time)] = ts

    def parse_specified_times(time_string):
        if not time_string: return []
        specific_slots = []
        entries = [e.strip() for e in time_string.split(',') if e.strip()]
        for entry in entries:
            parts = entry.split()
            if len(parts) >= 2:
                day_part = parts[0]
                time_raw = "".join(parts[1:])
            else:
                continue 
            full_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            matched_day = next((d for d in full_days if d.lower().startswith(day_part.lower())), None)
            norm_time_input = normalize_time_str(time_raw)
            if matched_day and norm_time_input:
                if (matched_day, norm_time_input) in timeslot_lookup:
                    specific_slots.append(timeslot_lookup[(matched_day, norm_time_input)])
        return specific_slots

    for c in courses_for_class:
        specified_l_slots = parse_specified_times(c.get('lecture_times'))
        specified_count = len(specified_l_slots)
        for ts in specified_l_slots:
            lecture_sessions.append({'course': c, 'is_practical': False, 'fixed_timeslot': ts})
        remaining_lectures = c['lectures_per_week'] - specified_count
        if remaining_lectures > 0:
            lecture_sessions.extend([{'course': c, 'is_practical': False, 'fixed_timeslot': None}] * remaining_lectures)

        specified_p_slots = parse_specified_times(c.get('practical_times'))
        specified_p_count = len(specified_p_slots)
        for ts in specified_p_slots:
            practical_sessions.append({'course': c, 'is_practical': True, 'fixed_timeslot': ts})
        remaining_practicals = c['practicals_per_week'] - specified_p_count
        if remaining_practicals > 0:
            practical_sessions.extend([{'course': c, 'is_practical': True, 'fixed_timeslot': None}] * remaining_practicals)
    
    lecture_sessions.sort(key=lambda x: 0 if x['fixed_timeslot'] else 1)
    practical_sessions.sort(key=lambda x: 0 if x['fixed_timeslot'] else 1)

    used_teacher_slots = {} 
    used_room_slots = {}    
    used_student_slots = {} 
    daily_course_counts = {}
    schedule = []
    current_schedule_map = {} 

    # --- 1. Assign Practicals ---
    for session in practical_sessions:
        course = session['course']
        teacher_name = course['lecturer_name']
        fixed_ts = session.get('fixed_timeslot')
        assigned = False
        
        candidates = []
        if fixed_ts:
            idx = next((i for i, t in enumerate(all_timeslots) if t['id'] == fixed_ts['id']), -1)
            if idx != -1:
                candidates.append(idx)
        else:
            candidates = list(range(len(all_timeslots)))
            random.shuffle(candidates)

        for i in candidates:
            ts1 = all_timeslots[i]
            
            # Constraints
            if not fixed_ts:
                if ts1['type'] not in ['Practical', 'Both']: continue
                if ts1['type'] == 'Break': continue

            # Conflict check ts1
            conflict1 = False
            t_key1 = (teacher_name, ts1['id'])
            if t_key1 in global_teacher_occupied or t_key1 in used_teacher_slots: conflict1 = True
            if ts1['id'] in used_student_slots: conflict1 = True
            if conflict1: continue

            # Check duration of TS1 to see if it fits practical alone
            duration1 = get_duration_minutes(ts1['start_time'], ts1['end_time'])
            
            use_single_slot = False
            use_pair_slot = False
            ts2 = None

            if duration1 >= 100: # Approx 2 hours (allows 1h40m+)
                use_single_slot = True
            else:
                # Try to pair with next slot
                if i + 1 < len(all_timeslots):
                    ts2 = all_timeslots[i+1]
                    # Pair validity
                    if ts1['day_of_week'] == ts2['day_of_week'] and \
                       ts2['type'] != 'Break' and \
                       (fixed_ts or ts2['type'] in ['Practical', 'Both']):
                        
                        # Conflict check ts2
                        conflict2 = False
                        t_key2 = (teacher_name, ts2['id'])
                        if t_key2 in global_teacher_occupied or t_key2 in used_teacher_slots: conflict2 = True
                        if ts2['id'] in used_student_slots: conflict2 = True
                        
                        if not conflict2:
                            use_pair_slot = True

            target_slots = []
            if use_single_slot: target_slots = [ts1]
            elif use_pair_slot: target_slots = [ts1, ts2]
            else: continue

            # Room Assignment
            random.shuffle(lab_rooms)
            for room in lab_rooms:
                r_conflict = False
                for ts in target_slots:
                    if (room['id'], ts['id']) in used_room_slots: r_conflict = True; break
                
                if not r_conflict:
                    # Assign
                    for ts in target_slots:
                        schedule.append({
                            "course_id": course['id'],
                            "course_name": course['name'],
                            "teacher": teacher_name,
                            "room": room['name'],
                            "timeslot_id": ts['id'],
                            "is_practical": True
                        })
                        used_teacher_slots[(teacher_name, ts['id'])] = True
                        used_room_slots[(room['id'], ts['id'])] = True
                        used_student_slots[ts['id']] = True
                    assigned = True
                    break
            if assigned: break
        
        if not assigned: print(f"Warning: Could not assign Practical for {course['name']}")

    # --- 2. Assign Lectures (1-Hour Blocks) ---
    def get_prev_slot_course(current_ts_id):
        curr_idx = next((i for i, t in enumerate(all_timeslots) if t['id'] == current_ts_id), -1)
        if curr_idx <= 0: return None
        prev_ts = all_timeslots[curr_idx - 1]
        current_ts = all_timeslots[curr_idx]
        if prev_ts['day_of_week'] != current_ts['day_of_week']: return None
        return current_schedule_map.get(prev_ts['id'])

    for session in lecture_sessions:
        course = session['course']
        teacher_name = course['lecturer_name']
        fixed_ts = session.get('fixed_timeslot')
        
        if fixed_ts:
            valid_slots = [fixed_ts]
        else:
            valid_slots = [t for t in all_timeslots if t['type'] in ['Lecture', 'Both']]
            random.shuffle(valid_slots)
        
        assigned = False
        for timeslot in valid_slots:
            ts_id = timeslot['id']
            day = timeslot['day_of_week']
            t_key = (teacher_name, ts_id)
            
            if t_key in global_teacher_occupied or t_key in used_teacher_slots: continue
            if ts_id in used_student_slots: continue
            
            if not fixed_ts and daily_course_counts.get((course['id'], day), 0) >= 1: continue
            if not fixed_ts and get_prev_slot_course(ts_id) == course['id']: continue

            random.shuffle(lecture_rooms)
            for room in lecture_rooms:
                r_key = (room['id'], ts_id)
                if r_key not in used_room_slots:
                    schedule.append({
                        "course_id": course['id'],
                        "course_name": course['name'],
                        "teacher": teacher_name,
                        "room": room['name'],
                        "timeslot_id": ts_id,
                        "is_practical": False
                    })
                    used_teacher_slots[t_key] = True
                    used_room_slots[r_key] = True
                    used_student_slots[ts_id] = True
                    current_schedule_map[ts_id] = course['id']
                    daily_course_counts[(course['id'], day)] = daily_course_counts.get((course['id'], day), 0) + 1
                    assigned = True
                    break 
            
            if assigned: break
            
        if not assigned: print(f"Warning: Could not assign Lecture for {course['name']}")

    try:
        conn = create_connection()
        cursor = conn.cursor()
        query = "INSERT INTO timetables (class_id, division_id, schedule_data) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE schedule_data = VALUES(schedule_data)"
        cursor.execute(query, (class_id, division_id, json.dumps(schedule)))
        conn.commit()
    except Error as e:
        print(e)
    finally:
        if conn and conn.is_connected(): conn.close()
    
    return jsonify({"timetable": schedule})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
