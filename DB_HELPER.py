import sqlite3
from datetime import datetime
import os

DB_PATH = 'attendance.db'

def init_db():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create Admins table
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Create Students table
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        qr_code TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Create Courses table
    c.execute('''CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT UNIQUE NOT NULL,
        course_name TEXT NOT NULL,
        instructor TEXT,
        time_slot TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Create Attendance table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        qr_code_scanned TEXT,
        FOREIGN KEY (student_id) REFERENCES students(id),
        FOREIGN KEY (course_id) REFERENCES courses(id)
    )''')
    
    # Create Enrollment table (many-to-many relationship)
    c.execute('''CREATE TABLE IF NOT EXISTS enrollment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students(id),
        FOREIGN KEY (course_id) REFERENCES courses(id),
        UNIQUE(student_id, course_id)
    )''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

# Admin functions
def add_admin(email, password, name):
    """Add a new admin user."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO admins (email, password, name) VALUES (?, ?, ?)',
                  (email, password, name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_admin(email, password):
    """Verify admin login credentials."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, email FROM admins WHERE email = ? AND password = ?',
              (email, password))
    admin = c.fetchone()
    conn.close()
    return admin

# Student functions
def add_student(student_id, name, email, qr_code=None):
    """Add a new student."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO students (student_id, name, email, qr_code) VALUES (?, ?, ?, ?)',
                  (student_id, name, email, qr_code))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_students():
    """Get all students."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, student_id, name, email, qr_code FROM students')
    students = c.fetchall()
    conn.close()
    return students

def get_student_by_qr(qr_code):
    """Get student by QR code."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, student_id, name, email FROM students WHERE qr_code = ?', (qr_code,))
    student = c.fetchone()
    conn.close()
    return student

def update_student_qr(student_id, qr_code):
    """Update student's QR code."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('UPDATE students SET qr_code = ? WHERE id = ?', (qr_code, student_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# Course functions
def add_course(course_code, course_name, instructor, time_slot):
    """Add a new course."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO courses (course_code, course_name, instructor, time_slot) VALUES (?, ?, ?, ?)',
                  (course_code, course_name, instructor, time_slot))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_courses():
    """Get all courses."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, course_code, course_name, instructor, time_slot FROM courses')
    courses = c.fetchall()
    conn.close()
    return courses

# Attendance functions
def record_attendance(student_id, course_id, qr_code_scanned):
    """Record student attendance."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO attendance (student_id, course_id, qr_code_scanned) VALUES (?, ?, ?)',
                  (student_id, course_id, qr_code_scanned))
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()

def get_attendance(course_id, date=None):
    """Get attendance records for a course."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if date:
        c.execute('''SELECT a.id, s.student_id, s.name, a.check_in_time, a.qr_code_scanned
                     FROM attendance a
                     JOIN students s ON a.student_id = s.id
                     WHERE a.course_id = ? AND DATE(a.check_in_time) = ?
                     ORDER BY a.check_in_time''', (course_id, date))
    else:
        c.execute('''SELECT a.id, s.student_id, s.name, a.check_in_time, a.qr_code_scanned
                     FROM attendance a
                     JOIN students s ON a.student_id = s.id
                     WHERE a.course_id = ?
                     ORDER BY a.check_in_time DESC''', (course_id,))
    records = c.fetchall()
    conn.close()
    return records

# Enrollment functions
def enroll_student(student_id, course_id):
    """Enroll a student in a course."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO enrollment (student_id, course_id) VALUES (?, ?)',
                  (student_id, course_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_student_courses(student_id):
    """Get all courses a student is enrolled in."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT c.id, c.course_code, c.course_name, c.instructor, c.time_slot
                 FROM courses c
                 JOIN enrollment e ON c.id = e.course_id
                 WHERE e.student_id = ?''', (student_id,))
    courses = c.fetchall()
    conn.close()
    return courses

def get_course_students(course_id):
    """Get all students enrolled in a course."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT s.id, s.student_id, s.name, s.email
                 FROM students s
                 JOIN enrollment e ON s.id = e.student_id
                 WHERE e.course_id = ?''', (course_id,))
    students = c.fetchall()
    conn.close()
    return students

if __name__ == '__main__':
    init_db()
