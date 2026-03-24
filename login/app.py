from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

DB_PATH = 'database.db'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT UNIQUE NOT NULL,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            course TEXT NOT NULL,
            course_level TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            address TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            posted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sitin_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            purpose TEXT NOT NULL,
            lab TEXT NOT NULL,
            login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            logout_time DATETIME
        )
    ''')

    # Default admin: username=admin, password=admin123
    cursor.execute('''
        INSERT OR IGNORE INTO admins (username, password) VALUES (?, ?)
    ''', ('admin', 'admin123'))

    conn.commit()
    conn.close()

# ─────────────────────────────────────────
#  LOGIN — same form, checks admin first
# ─────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id_number = request.form['id_number']
        password  = request.form['password']

        conn = get_db()

        # Check admin first
        admin = conn.execute(
            'SELECT * FROM admins WHERE username = ? AND password = ?',
            (id_number, password)
        ).fetchone()

        if admin:
            session['admin_id']   = admin['id']
            session['admin_user'] = admin['username']
            conn.close()
            return redirect(url_for('admin_dashboard'))

        # Check student
        student = conn.execute(
            'SELECT * FROM students WHERE id_number = ? AND password = ?',
            (id_number, password)
        ).fetchone()
        conn.close()

        if student:
            session['student_id']   = student['id_number']
            session['student_name'] = student['first_name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid ID number or password.', 'error')

    return render_template('login.html')

# ─────────────────────────────────────────
#  STUDENT ROUTES
# ─────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        id_number       = request.form['id_number']
        last_name       = request.form['last_name']
        first_name      = request.form['first_name']
        middle_name     = request.form['middle_name']
        course          = request.form['course']
        course_level    = request.form['course_level']
        password        = request.form['password']
        repeat_password = request.form['repeat_password']
        email           = request.form['email']
        address         = request.form['address']

        if password != repeat_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))

        try:
            conn = get_db()
            conn.execute('''
                INSERT INTO students
                (id_number, last_name, first_name, middle_name, course, course_level, password, email, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (id_number, last_name, first_name, middle_name, course, course_level, password, email, address))
            conn.commit()
            conn.close()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('ID Number or Email already exists.', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    student = conn.execute(
        'SELECT * FROM students WHERE id_number = ?',
        (session['student_id'],)
    ).fetchone()
    announcements = conn.execute(
        'SELECT * FROM announcements ORDER BY posted_at DESC'
    ).fetchall()
    conn.close()
    return render_template('dashboard.html', student=student, announcements=announcements)

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    student = conn.execute(
        'SELECT * FROM students WHERE id_number = ?',
        (session['student_id'],)
    ).fetchone()

    photo_path = f"uploads/{session['student_id']}.png"
    has_photo  = os.path.exists(os.path.join('static', photo_path))

    if request.method == 'POST':
        last_name    = request.form['last_name']
        first_name   = request.form['first_name']
        middle_name  = request.form['middle_name']
        course_level = request.form['course_level']
        email        = request.form['email']
        course       = request.form['course']
        address      = request.form['address']

        conn.execute('''
            UPDATE students SET
                last_name = ?, first_name = ?, middle_name = ?,
                course_level = ?, email = ?, course = ?, address = ?
            WHERE id_number = ?
        ''', (last_name, first_name, middle_name, course_level, email, course, address, session['student_id']))
        conn.commit()
        conn.close()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('edit_profile'))

    conn.close()
    return render_template('edit_profile.html', student=student,
                           photo_path=photo_path, has_photo=has_photo)

@app.route('/upload-photo', methods=['POST'])
def upload_photo():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    file = request.files.get('photo')
    if file and allowed_file(file.filename):
        filename = f"{session['student_id']}.png"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash('Profile photo updated successfully!', 'success')
    else:
        flash('Invalid file. Please upload a JPG, PNG, or GIF.', 'error')
    return redirect(url_for('edit_profile'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/students')
def students():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('students.html', students=students)

# ─────────────────────────────────────────
#  ADMIN ROUTES
# ─────────────────────────────────────────

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    students       = conn.execute('SELECT * FROM students').fetchall()
    total_students = len(students)
    announcements  = conn.execute(
        'SELECT * FROM announcements ORDER BY posted_at DESC'
    ).fetchall()
    course_stats   = conn.execute(
        'SELECT course, COUNT(*) as count FROM students GROUP BY course'
    ).fetchall()
    total_sitin   = conn.execute('SELECT COUNT(*) as c FROM sitin_records').fetchone()['c']
    current_sitin = conn.execute(
        'SELECT COUNT(*) as c FROM sitin_records WHERE logout_time IS NULL'
    ).fetchone()['c']
    conn.close()

    return render_template('admin_dashboard.html',
                           students=students,
                           total_students=total_students,
                           announcements=announcements,
                           course_stats=course_stats,
                           total_sitin=total_sitin,
                           current_sitin=current_sitin,
                           admin_user=session['admin_user'])

@app.route('/admin/announce', methods=['POST'])
def admin_announce():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    message = request.form.get('message', '').strip()
    if message:
        conn = get_db()
        conn.execute('INSERT INTO announcements (message) VALUES (?)', (message,))
        conn.commit()
        conn.close()
        flash('Announcement posted!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-announcement/<int:ann_id>', methods=['POST'])
def delete_announcement(ann_id):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
    conn.commit()
    conn.close()
    flash('Announcement deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-student/<id_number>', methods=['POST'])
def delete_student(id_number):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM students WHERE id_number = ?', (id_number,))
    conn.commit()
    conn.close()
    flash(f'Student {id_number} deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)