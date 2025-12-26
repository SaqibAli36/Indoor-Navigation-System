import os
import sqlite3
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'

db_path = 'ims.db'
json_file = 'data.json'

def init_db():
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS admins (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            email TEXT UNIQUE NOT NULL,
                            password TEXT NOT NULL,
                            reset_token TEXT
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS rooms (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            video TEXT NOT NULL
                          )''')
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM rooms")
        if cursor.fetchone()[0] == 0:
            with open(json_file, 'r') as f:
                rooms = json.load(f)
                cursor.executemany("INSERT INTO rooms (id, name, video) VALUES (?, ?, ?)",
                                   [(room['id'], room['name'], room['video']) for room in rooms])
                conn.commit()
init_db()

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def home():
    return redirect(url_for('admin'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin' not in session:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rooms")
        rooms = cursor.fetchall()
    
    if request.method == 'POST':
        room_id = request.form['room_id'].strip()
        room_name = request.form['room_name'].strip()
        video = request.files['video']

        if room_id and room_name and video:
            video_filename = f"{room_id}.mp4"
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
            video.save(video_path)
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO rooms (id, name, video) VALUES (?, ?, ?)", (room_id, room_name, video_filename))
                conn.commit()
                flash('Room added successfully!', 'success')
            return redirect(url_for('admin'))
    
    return render_template('admin.html', rooms=rooms)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO admins (email, password) VALUES (?, ?)", (email, hashed_password))
                conn.commit()
                flash('Signup successful! Please login.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Email already registered!', 'danger')
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admins WHERE email = ?", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user[2], password):
                session['admin'] = user[0]
                flash('Login successful!', 'success')
                return redirect(url_for('admin'))
            else:
                flash('Invalid credentials!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/user', methods=['GET', 'POST'])
def user():
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rooms")
        rooms = cursor.fetchall()

    if request.method == 'POST':
        search_query = request.form['search_query'].strip().lower()
        rooms = [room for room in rooms if search_query in room[1].lower() or search_query in room[0].lower()]

    return render_template('user.html', rooms=rooms)

@app.route('/delete_room/<room_id>', methods=['POST'])
def delete_room(room_id):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        conn.commit()
    flash('Room deleted successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/voice_search', methods=['GET'])
def voice_search():
    query = request.args.get('q', '').lower()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rooms")
        rooms = cursor.fetchall()
    
    filtered_rooms = [room for room in rooms if query in room[1].lower() or query in room[0].lower()]
    return jsonify({"rooms": filtered_rooms})

if __name__ == '__main__':
    app.run(debug=True, port=5002)
