"""
Cleanup script to remove large qr_code and photo base64 data from students table.
Keeps only photo filenames instead of full base64.
"""
import sqlite3
import json

DB_PATH = 'attendance.db'

def cleanup_students_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get all students with their photo data
    c.execute('SELECT id, photo FROM students')
    rows = c.fetchall()
    
    print(f"Found {len(rows)} students. Cleaning up...")
    
    for student_id, photo_data in rows:
        # Extract filename if photo_data is a data URL or base64
        photo_filename = None
        if photo_data:
            # If it's a data URL, extract nothing (we'll regenerate QR)
            if photo_data.startswith('data:'):
                photo_filename = None
            # If it's already a filename, keep it
            elif not photo_data.startswith('{') and len(photo_data) < 200:
                photo_filename = photo_data
            # Otherwise it's likely huge base64, discard it
            else:
                photo_filename = None
        
        # Update: clear qr_code, keep only filename in photo
        c.execute(
            'UPDATE students SET qr_code = NULL, photo = ? WHERE id = ?',
            (photo_filename, student_id)
        )
    
    conn.commit()
    conn.close()
    print("✓ Cleanup complete! qr_code cleared, photo now stores only filenames.")
    print("✓ QR codes will be regenerated on-the-fly by the app.")

if __name__ == '__main__':
    cleanup_students_table()
