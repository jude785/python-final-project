from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from DB_HELPER import init_db, get_admin, get_student_by_qr, record_attendance, get_all_students, get_all_courses
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this to a secure key

# Initialize database on startup
if not os.path.exists('attendance.db'):
    init_db()

@app.route('/')
def index():
    return render_template('index.html')

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

@app.route('/admin')
def admin_panel():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    return render_template('admin.html', admin_name=session.get('admin_name'))

@app.route('/scan-qr', methods=['POST'])
def scan_qr():
    """Handle QR code scan and record attendance."""
    data = request.get_json()
    qr_code = data.get('qr_code')
    course_id = data.get('course_id', 1)  # Default to course 1
    
    student = get_student_by_qr(qr_code)
    
    if student:
        student_id = student[0]
        if record_attendance(student_id, course_id, qr_code):
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
    else:
        return jsonify({
            'status': 'error',
            'message': 'Student not found'
        }), 404

@app.route('/students', methods=['GET'])
def get_students():
    """Get all students as JSON."""
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    students = get_all_students()
    return jsonify(students)

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

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)