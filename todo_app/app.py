from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
import calendar
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret123'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ✅ Initialize DB and create admin account
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            bio TEXT,
            contact TEXT,
            profile_pic TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task TEXT,
            deadline TEXT,
            filename TEXT,
            status TEXT DEFAULT "pending",
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS class_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            day TEXT,
            subject TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            event TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

   # Check if admin1 exists
    c.execute('SELECT * FROM users WHERE username = ?', ('admin1',))
    if not c.fetchone():
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', ('admin1', 'admin123'))
        print("Admin account restored.")
    else:
        print("Admin already exists.")

    conn.commit()
    conn.close()

init_db()

# ✅ Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT id, password FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()

        if user and user[1] == password:
            session['user_id'] = user[0]
            if user[0] == 1:
                return redirect('/users')
            else:
                return redirect('/')
        else:
            error = "Invalid credentials"

    return render_template('login.html', error=error)

# ✅ Signup Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            error = "Username already exists."
            conn.close()

    return render_template('signup.html', error=error)

# ✅ Index Page (User Dashboard)
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row  # Enables dictionary-style access
    c = conn.cursor()

    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user_info = c.fetchone()

    c.execute('SELECT id, task, deadline, filename, status FROM tasks WHERE user_id = ?', (user_id,))
    tasks = c.fetchall()


    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    overdue_count = sum(1 for task in tasks if task['deadline'] and task['deadline'] < now)

    conn.close()

    return render_template('index.html',
                           tasks=tasks,
                           user_info=user_info,
                           now=now,
                           overdue_count=overdue_count)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    if request.method == 'POST':
        # Get form data
        username = request.form['username']
        password = request.form['password']
        bio = request.form['bio']
        contact = request.form['contact']

        # Handle file upload
        file = request.files['profile_pic']
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

        # Update user info
        c.execute('''
            UPDATE users SET username = ?, password = ?, bio = ?, contact = ?, profile_pic = ?
            WHERE id = ?
        ''', (username, password, bio, contact, filename, user_id))
        conn.commit()
        conn.close()
        return redirect('/')

    # GET request: fetch current user info
    c.execute('SELECT username, password, bio, contact FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()

    return render_template('edit_profile.html', user=user)

@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    if request.method == 'POST':
        day = request.form['day']
        subject = request.form['subject']
        time = request.form['time']
        entry = f"{subject} at {time}"
        c.execute('INSERT INTO class_schedule (user_id, day, subject) VALUES (?, ?, ?)',
                  (user_id, day, entry))
        conn.commit()

    c.execute('SELECT id, day, subject FROM class_schedule WHERE user_id = ?', (user_id,))
    rows = c.fetchall()
    conn.close()

    schedule = {}
    for id, day, subject in rows:
        schedule.setdefault(day, []).append((id, subject))

    return render_template('schedule.html', schedule=schedule)

@app.route('/edit_schedule/<int:sched_id>', methods=['GET', 'POST'])
def edit_schedule(sched_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    if request.method == 'POST':
        new_subject = request.form['subject']
        new_time = request.form['time']
        entry = f"{new_subject} at {new_time}"
        c.execute('UPDATE class_schedule SET subject = ? WHERE id = ?', (entry, sched_id))
        conn.commit()
        conn.close()
        return redirect('/schedule')

    c.execute('SELECT subject FROM class_schedule WHERE id = ?', (sched_id,))
    entry = c.fetchone()
    conn.close()

    # Split subject and time for editing
    if entry and ' at ' in entry[0]:
        subject, time = entry[0].split(' at ')
    else:
        subject, time = entry[0], ''

    return render_template('edit_schedule.html', subject=subject, time=time, sched_id=sched_id)

@app.route('/delete_schedule/<int:sched_id>')
def delete_schedule(sched_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('DELETE FROM class_schedule WHERE id = ?', (sched_id,))
    conn.commit()
    conn.close()

    return redirect('/schedule')

@app.route('/calendar', methods=['GET', 'POST'])
def calendar_view():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    if request.method == 'POST':
        date = request.form['date']
        event = request.form['event']
        c.execute('INSERT INTO calendar_events (user_id, date, event) VALUES (?, ?, ?)',
                  (user_id, date, event))
        conn.commit()

    month = request.args.get('month')
    year = request.args.get('year')
    today = datetime.today()
    selected_month = int(month) if month else today.month
    selected_year = int(year) if year else today.year
    today_date = today.strftime('%Y-%m-%d')

    first_day = datetime(selected_year, selected_month, 1)
    start_weekday = first_day.weekday()
    days_in_month = calendar.monthrange(selected_year, selected_month)[1]

    calendar_data = []
    for day in range(1, days_in_month + 1):
        date_str = f"{selected_year}-{selected_month:02d}-{day:02d}"
        c.execute('SELECT id, event FROM calendar_events WHERE user_id = ? AND date = ?', (user_id, date_str))
        tasks = [{'id': row[0], 'text': row[1]} for row in c.fetchall()]
        calendar_data.append({'day': day, 'tasks': tasks, 'date': date_str})

    conn.close()

    today_date = datetime.today().strftime('%Y-%m-%d')
    return render_template('calendar.html',
                       calendar=calendar_data,
                       current_month=calendar.month_name[selected_month],
                       current_year=selected_year,
                       selected_month=selected_month,
                       selected_year=selected_year,
                       start_weekday=start_weekday,
                       today_date=today_date)

@app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    if request.method == 'POST':
        new_event = request.form['event']
        c.execute('UPDATE calendar_events SET event = ? WHERE id = ?', (new_event, event_id))
        conn.commit()
        conn.close()
        return redirect('/calendar')

    c.execute('SELECT event FROM calendar_events WHERE id = ?', (event_id,))
    event = c.fetchone()
    conn.close()

    return render_template('edit_event.html', event_text=event[0], event_id=event_id)

@app.route('/delete_event/<int:event_id>')
def delete_event(event_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('DELETE FROM calendar_events WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()

    return redirect('/calendar')


@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    task = request.form['task']
    deadline = request.form['deadline']
    file = request.files.get('attachment')
    filename = None

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT INTO tasks (user_id, task, deadline, filename, status) VALUES (?, ?, ?, ?, ?)',
              (user_id, task, deadline, filename, "pending"))
    conn.commit()
    conn.close()

    return redirect('/')

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit(task_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    if request.method == 'POST':
        new_task = request.form['new_task']
        new_deadline = request.form['new_deadline']
        file = request.files.get('new_attachment')
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            c.execute('UPDATE tasks SET task = ?, deadline = ?, filename = ? WHERE id = ?', (new_task, new_deadline, filename, task_id))
        else:
            c.execute('UPDATE tasks SET task = ?, deadline = ? WHERE id = ?', (new_task, new_deadline, task_id))
        conn.commit()
        conn.close()
        return redirect('/')
    c.execute('SELECT task, deadline, filename FROM tasks WHERE id = ?', (task_id,))
    task = c.fetchone()
    conn.close()
    return render_template('edit_task.html', task=task, task_id=task_id)

@app.route('/update/<int:task_id>', methods=['POST'])
def update_task(task_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    new_task = request.form['new_task']
    new_deadline = request.form['new_deadline']
    file = request.files.get('new_attachment')
    filename = None

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        c.execute('UPDATE tasks SET task = ?, deadline = ?, filename = ? WHERE id = ?',
                  (new_task, new_deadline, filename, task_id))
    else:
        c.execute('UPDATE tasks SET task = ?, deadline = ? WHERE id = ?',
                  (new_task, new_deadline, task_id))

    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/delete/<int:task_id>')
def delete(task_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/toggle_status/<int:task_id>')
def toggle_status(task_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT status FROM tasks WHERE id = ?', (task_id,))
    current = c.fetchone()[0]
    new_status = 'done' if current == 'pending' else 'pending'
    c.execute('UPDATE tasks SET status = ? WHERE id = ?', (new_status, task_id))
    conn.commit()
    conn.close()
    return redirect('/')

# ✅ Admin Page: Manage Users
@app.route('/users')
def users():
    if session.get('user_id') != 1:
        return redirect('/')

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT id, username FROM users')
    users = c.fetchall()
    conn.close()

    return render_template('user_list.html', users=users)

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if session.get('user_id') != 1 or user_id == 1:
        return redirect('/')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return redirect('/users')

# ✅ Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ✅ Add more routes here for tasks, calendar, schedule, uploads, etc.

if __name__ == '__main__':
    app.run(debug=True)
