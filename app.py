from flask import Flask, render_template, request, jsonify, session, redirect, url_for, json
import os
import sqlite3
import base64
import uuid
from werkzeug.security  import generate_password_hash
from DB_HELPER import (
    init_db,
    get_admin,
    get_student_by_qr,
    record_attendance,
    get_all_courses,
    ensure_default_course,
    get_all_admins,
    add_admin,
    delete_admin,
    get_admin_by_id,
    update_admin
)

app = Flask(__name__)
# Prefer environment-provided secret key for session integrity
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-me')

# Reuse the existing attendance database for users as well
USERS_DB = os.path.join(os.path.dirname(__file__), 'attendance.db')

# Initialize DB every startup to ensure tables/seed data exist
init_db()
DEFAULT_COURSE_ID = ensure_default_course()

# Ensure users table exists in app.db
def init_users_db():
    # Ensure admins table exists within attendance.db (handled by DB_HELPER.init_db)
    # No-op here to avoid creating a duplicate users table.
    pass

# Initialize users DB at startup (Flask 3 removed before_first_request)
init_users_db()

@app.route('/')
def index():
    return render_template('index.html')


def require_admin():
    """Redirect to login if admin not authenticated."""
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    return None

@app.route('/check', methods=['GET'])
def check():
    """Handle QR code scan result and display student info."""
    qr_code = request.args.get('qr_code', '')
    print(f"DEBUG: Received QR code: {qr_code}")
    
    if not qr_code:
        return render_template('check.html', error='No QR code provided', student=None)
    
    # Try to parse JSON QR code format (from student.html)
    student_id_to_find = None
    try:
        import json
        qr_data = json.loads(qr_code)
        student_id_to_find = qr_data.get('idno')
        print(f"DEBUG: Parsed JSON QR, extracted student ID: {student_id_to_find}")
    except:
        # Not JSON, use as-is
        student_id_to_find = qr_code
        print(f"DEBUG: QR code is not JSON, using as-is: {student_id_to_find}")
    
    # Look up student by student_id (not qr_code field)
    conn = sqlite3.connect('attendance.db')
    cur = conn.cursor()
    cur.execute(
        'SELECT id, student_id, name, last_name, first_name, email, course, level, photo FROM students WHERE student_id = ?',
        (student_id_to_find,)
    )
    row = cur.fetchone()

    already_present = False
    if row:
        # Check if attendance already recorded today for this student
        cur.execute(
            """
            SELECT id FROM attendance
            WHERE student_id = ? AND date(check_in_time) = date('now','localtime')
            LIMIT 1
            """,
            (row[0],)
        )
        if cur.fetchone():
            already_present = True
    conn.close()
    
    print(f"DEBUG: Database returned: {row}")
    
    if row:
        student_id = row[0]
        course_id = DEFAULT_COURSE_ID
        # Record attendance only if not already present today
        if already_present:
            success = False
            error_msg = 'This student is already present'
        else:
            success = record_attendance(student_id, course_id, qr_code)
            error_msg = None if success else 'Failed to record attendance'
        
        student_data = {
            'id': row[0],
            'student_id': row[1],
            'name': row[2],
            'last_name': row[3] or '',
            'first_name': row[4] or '',
            'email': row[5] or '',
            'course': row[6] or '',
            'level': row[7] or '',
            'photo': row[8] or '',
            'qr_code': qr_code
        }
        print(f"DEBUG: Passing student data: {student_data}")
        
        return render_template('check.html', student=student_data, success=success, error=error_msg)
    else:
        print(f"DEBUG: No student found for QR code: {qr_code}")
        return render_template('check.html', error='Student not found', qr_code=qr_code, student=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        admin = get_admin(email, password)
        
        if admin:
            session['admin_id'] = admin[0]
            session['admin_name'] = admin[1]
            return redirect(url_for('admin_panel'))
        else:
            return render_template('AdminLogin.html', error='Invalid credentials')
    
    return render_template('AdminLogin.html')

@app.route('/admin', methods=['GET'])
def admin_panel():
    auth = require_admin()
    if auth:
        return auth
    error_msg = request.args.get('error')
    # Load admins from attendance.db via helper and render admin page
    rows = get_all_admins()
    users = [
        { 'id': r[0], 'name': r[1], 'email': r[2], 'password': '••••••' }
        for r in rows
    ]
    return render_template('admin.html', users=users, admin_name=session.get('admin_name'), error=error_msg)

# Provide a GET alias for /admin/users to render the same admin table view
@app.route('/admin/users', methods=['GET'])
def admin_users_get():
    auth = require_admin()
    if auth:
        return auth
    return redirect(url_for('admin_panel'))

@app.route('/scan-qr', methods=['POST'])
def scan_qr():
    """Handle QR code scan and record attendance."""
    data = request.get_json()
    qr_code_raw = data.get('qr_code', '')
    course_id = data.get('course_id', 1)  # Default to course 1
    # Align scan payload parsing with /check
    student_lookup_val = qr_code_raw
    try:
        import json
        qr_data = json.loads(qr_code_raw)
        student_lookup_val = qr_data.get('idno', qr_code_raw)
    except Exception:
        pass

    student = get_student_by_qr(student_lookup_val)
    
    if not student:
        return jsonify({
            'status': 'error',
            'message': 'Student not found'
        }), 404

    student_id = student[0]
    course_id_to_use = course_id or DEFAULT_COURSE_ID
    if record_attendance(student_id, course_id_to_use, qr_code_raw):
        return jsonify({
            'status': 'success',
            'message': f'Attendance recorded for {student[2]}',
            'student_name': student[2],
            'student_id': student[1]
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': 'Failed to record attendance'
        }), 500

@app.route('/courses', methods=['GET'])
def get_courses():
    """Get all courses as JSON."""
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    courses = get_all_courses()
    return jsonify(courses)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/studentmngt')
def student_management():
    auth = require_admin()
    if auth:
        return auth
    return render_template('studentmngt.html')

@app.route('/attendance')
def view_attendance():
    """Display attendance records, defaults to today. Can filter by date (YYYY-MM-DD)."""
    auth = require_admin()
    if auth:
        return auth
    from datetime import datetime
    selected_date = request.args.get('date', '').strip()
    # Default to today's date if no date selected
    if not selected_date:
        selected_date = datetime.now().strftime('%Y-%m-%d')

    conn = sqlite3.connect('attendance.db')
    cur = conn.cursor()

    base_query = '''
        SELECT 
            s.student_id,
            s.last_name,
            s.first_name,
            s.course,
            s.level,
            strftime('%Y-%m-%d', a.check_in_time, 'localtime') as date_in,
            strftime('%I:%M %p', a.check_in_time, 'localtime') as time_in
        FROM attendance a
        JOIN students s ON a.student_id = s.id
    '''

    # Build a start/end window for the chosen date to avoid timezone/date() quirks
    start_ts = f"{selected_date} 00:00:00"
    end_ts = f"{selected_date} 23:59:59"
    where_clause = (
        "WHERE datetime(a.check_in_time, 'localtime') BETWEEN datetime(?, 'localtime') "
        "AND datetime(?, 'localtime')"
    )
    params = [start_ts, end_ts]
    order_limit = 'ORDER BY a.check_in_time DESC LIMIT 50'

    cur.execute(' '.join([base_query, where_clause, order_limit]).strip(), params)
    rows = cur.fetchall()
    conn.close()
    
    attendance_records = [
        {
            'student_id': r[0],
            'last_name': r[1] or '',
            'first_name': r[2] or '',
            'course': r[3] or '',
            'level': r[4] or '',
            'date_in': r[5] or '',
            'time_in': r[6] or ''
        }
        for r in rows
    ]
    
    return render_template('attendance.html', attendance_records=attendance_records, selected_date=selected_date)

@app.route('/student')
def student_page():
    auth = require_admin()
    if auth:
        return auth
    return render_template('student.html')

@app.route('/students', methods=['POST'])
def add_student():
    """Save new student to database."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    required = ['idno', 'lastname', 'firstname', 'course', 'level']
    
    if not all(data.get(k) for k in required):
        return jsonify({'success': False, 'message': 'Missing fields'}), 400

    # Normalize fields to avoid whitespace dupes
    idno = str(data.get('idno', '')).strip()
    lastname = str(data.get('lastname', '')).strip()
    firstname = str(data.get('firstname', '')).strip()
    course = str(data.get('course', '')).strip()
    level = str(data.get('level', '')).strip()

    if not idno or not firstname:
        return jsonify({'success': False, 'message': 'IDNO and FIRSTNAME are required'}), 400

    conn = None
    try:
        conn = sqlite3.connect('attendance.db')
        cur = conn.cursor()
        full_name = f"{firstname} {lastname}".strip()

        # Duplicate validations
        cur.execute('SELECT id FROM students WHERE student_id = ? LIMIT 1', (idno,))
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'IDNO already exists'}), 400

        cur.execute('''SELECT id FROM students
                       WHERE lower(first_name) = lower(?) AND lower(last_name) = lower(?)
                       LIMIT 1''', (firstname, lastname))
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'A student with the same first and last name already exists'}), 400

        # Generate unique email if not provided
        email = data.get('email', '').strip()
        if not email:
            email = f"{idno}@student.com"
        
        # Handle photo: if it's base64, save as file; otherwise store as-is
        photo_data = data.get('photo', '')
        photo_filename = None
        if photo_data and photo_data.startswith('data:image'):
            try:
                # Extract base64 data after the comma
                header, encoded = photo_data.split(',', 1)
                photo_bytes = base64.b64decode(encoded)
                # Generate unique filename
                photo_filename = f"{idno}_{uuid.uuid4().hex[:8]}.jpg"
                photo_path = os.path.join('static', 'photos', photo_filename)
                with open(photo_path, 'wb') as f:
                    f.write(photo_bytes)
            except Exception:
                photo_filename = None  # If conversion fails, don't store
        elif photo_data and not photo_data.startswith('data:'):
            # Already a filename
            photo_filename = photo_data
        
        cur.execute(
            '''INSERT INTO students (student_id, name, last_name, first_name, email, qr_code, course, level, photo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                idno,
                full_name,
                lastname,
                firstname,
                email,
                None,  # Don't store QR code in DB
                course,
                level,
                photo_filename
            )
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    finally:
        if conn:
            conn.close()

@app.route('/students', methods=['GET'])
def list_students():
    """Get all students for display."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = sqlite3.connect('attendance.db')
    cur = conn.cursor()
    # Include photo so the management page can preview it
    cur.execute('SELECT id, student_id, last_name, first_name, course, level, photo FROM students')
    rows = cur.fetchall()
    conn.close()
    
    students = [
        {
            'id': r[0],
            'student_id': r[1],
            'last_name': r[2],
            'first_name': r[3],
            'course': r[4],
            'level': r[5],
            'photo': r[6] or ''
        }
        for r in rows
    ]
    return jsonify({'success': True, 'students': students})

@app.route('/students/<int:student_id>', methods=['GET'])
def get_student(student_id):
    """Get a single student by ID for edit form prefill."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = sqlite3.connect('attendance.db')
    cur = conn.cursor()
    cur.execute('SELECT id, student_id, last_name, first_name, course, level, photo FROM students WHERE id = ?', (student_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    
    student = {
        'id': row[0],
        'student_id': row[1],
        'last_name': row[2],
        'first_name': row[3],
        'course': row[4],
        'level': row[5],
        'photo': row[6] or ''
    }
    return jsonify({'success': True, 'student': student})

@app.route('/students/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    """Delete a student."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = None
    try:
        conn = sqlite3.connect('attendance.db')
        cur = conn.cursor()
        cur.execute('DELETE FROM students WHERE id = ?', (student_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    finally:
        if conn:
            conn.close()

@app.route('/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    """Update a student."""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    required = ['idno', 'lastname', 'firstname', 'course', 'level']
    
    if not all(data.get(k) for k in required):
        return jsonify({'success': False, 'message': 'Missing fields'}), 400

    idno = str(data.get('idno', '')).strip()
    lastname = str(data.get('lastname', '')).strip()
    firstname = str(data.get('firstname', '')).strip()
    course = str(data.get('course', '')).strip()
    level = str(data.get('level', '')).strip()

    if not idno or not firstname:
        return jsonify({'success': False, 'message': 'IDNO and FIRSTNAME are required'}), 400

    conn = None
    try:
        conn = sqlite3.connect('attendance.db')
        cur = conn.cursor()
        full_name = f"{firstname} {lastname}".strip()

        # Duplicate validations excluding current record
        cur.execute('SELECT id FROM students WHERE student_id = ? AND id != ? LIMIT 1', (idno, student_id))
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'IDNO already exists'}), 400

        cur.execute('''SELECT id FROM students
                       WHERE lower(first_name) = lower(?) AND lower(last_name) = lower(?) AND id != ?
                       LIMIT 1''', (firstname, lastname, student_id))
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'A student with the same first and last name already exists'}), 400

        # Handle photo: if it's base64, save as file; otherwise keep existing
        photo_data = data.get('photo', '')
        photo_filename = None
        if photo_data and photo_data.startswith('data:image'):
            try:
                # Extract base64 data after the comma
                header, encoded = photo_data.split(',', 1)
                photo_bytes = base64.b64decode(encoded)
                # Generate unique filename
                photo_filename = f"{idno}_{uuid.uuid4().hex[:8]}.jpg"
                photo_path = os.path.join('static', 'photos', photo_filename)
                with open(photo_path, 'wb') as f:
                    f.write(photo_bytes)
            except Exception:
                photo_filename = None  # If conversion fails, keep existing
        elif photo_data and not photo_data.startswith('data:'):
            # Already a filename
            photo_filename = photo_data
        
        # Only update photo if new data provided
        if photo_filename:
            cur.execute('''UPDATE students 
                                  SET student_id = ?, qr_code = ?, name = ?, last_name = ?, first_name = ?, course = ?, level = ?, photo = ?
                                  WHERE id = ?''',
                              (idno, None, full_name, lastname, firstname, course, level, photo_filename, student_id))
        else:
            cur.execute('''UPDATE students 
                                  SET student_id = ?, qr_code = ?, name = ?, last_name = ?, first_name = ?, course = ?, level = ?
                                  WHERE id = ?''',
                              (idno, None, full_name, lastname, firstname, course, level, student_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    finally:
        if conn:
            conn.close()

@app.route('/admin/users', methods=['POST'])
def add_user():
    auth = require_admin()
    if auth:
        return auth
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    if not name or not email or not password:
        return redirect('/admin')
    # insert into admins via helper
    ok = add_admin(email, password, name)
    if not ok:
        return redirect('/admin?error=Email+already+exists')
    return redirect('/admin')

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    auth = require_admin()
    if auth:
        return auth
    delete_admin(user_id)
    return redirect('/admin')

@app.route('/admin/users/<int:user_id>/edit', methods=['GET'])
def edit_user_page(user_id):
    auth = require_admin()
    if auth:
        return auth
    row = get_admin_by_id(user_id)
    if not row:
        return redirect('/admin')
    user = { 'id': row[0], 'name': row[1], 'email': row[2], 'password': '' }
    return render_template('edit_user.html', user=user)

@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
def edit_user_submit(user_id):
    auth = require_admin()
    if auth:
        return auth
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    if not name or not email:
        return redirect(f'/admin/users/{user_id}/edit')
    try:
        update_admin(user_id, name, email, password if password else None)
    except Exception:
        pass
    return redirect('/admin')

# (update route removed to restore previous behavior)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)