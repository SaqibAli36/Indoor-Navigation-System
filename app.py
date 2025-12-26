import os
import firebase_admin
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from firebase_admin import credentials, firestore, auth
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flask App Setup
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_flask_secret_here_123')

# Firebase Setup
cred = credentials.Certificate(os.getenv("FIREBASE_CRED"))
firebase_admin.initialize_app(cred)
db = firestore.client()

# Email configuration
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# File Paths
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User Class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

# User Loader Function
@login_manager.user_loader
def load_user(user_id):
    user_ref = db.collection("users").document(user_id).get()
    if user_ref.exists:
        user_data = user_ref.to_dict()
        return User(user_id, user_data.get('username'), user_data.get('email'))
    return None

# ---------------- EMAIL UTILITY ---------------- #
def send_email(recipient_email, subject, body):
    """Send email to the recipient (HTML body)."""
    if not all([EMAIL_HOST, EMAIL_PORT, EMAIL_USERNAME, EMAIL_PASSWORD]):
        print("❌ Email configuration missing.")
        return False

    message = MIMEMultipart()
    message['From'] = EMAIL_USERNAME
    message['To'] = recipient_email
    message['Subject'] = subject
    message.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USERNAME, recipient_email, message.as_string())
        print(f"✅ Email sent to {recipient_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


# ---------------- HOME ---------------- #
@app.route('/')
def home():
    return redirect(url_for('admin'))


# ---------------- ADMIN DASHBOARD ---------------- #
@app.route('/admin')
@login_required
def admin():
    # Rooms
    rooms_ref = db.collection("rooms").stream()
    rooms = []
    for room in rooms_ref:
        d = room.to_dict()
        rooms.append({
            "id": room.id,
            "name": d.get("name", ""),
            "video": d.get("video", ""),
            "created_at": d.get("created_at")
        })

    # Timetable
    timetable_ref = db.collection("timetable").stream()
    timetable = []
    for entry in timetable_ref:
        d = entry.to_dict()
        timetable.append({
            "id": entry.id,
            "day": d.get("day", ""),
            "period": d.get("period", ""),
            "subject": d.get("subject", ""),
            "teacher": d.get("teacher", ""),
            "room": d.get("room", ""),
            "start_time": d.get("start_time", ""),
            "end_time": d.get("end_time", ""),
            "created_at": d.get("created_at")
        })

    # Exams
    exams_ref = db.collection("exams").stream()
    exams = []
    for ex in exams_ref:
        d = ex.to_dict()
        date_val = d.get("date")
        if isinstance(date_val, datetime):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val) if date_val else ""
        exams.append({
            "id": ex.id,
            "name": d.get("name", ""),
            "date": date_str,
            "room": d.get("room", ""),
            "start_time": d.get("start_time", ""),
            "end_time": d.get("end_time", ""),
            "created_at": d.get("created_at")
        })

    return render_template('admin.html', rooms=rooms, timetable=timetable, exams=exams)


# ---------------- ROOMS ---------------- #
@app.route('/add_room', methods=['POST'])
@login_required
def add_room():
    room_id = request.form['id'].strip()
    name = request.form['name'].strip()
    video = request.files.get('video')

    if not room_id or not name or not video:
        flash('Missing required fields for room.', 'danger')
        return redirect(url_for('admin'))

    # Check if room ID exists
    room_ref = db.collection("rooms").document(room_id).get()
    if room_ref.exists:
        flash('Room ID already exists!', 'danger')
        return redirect(url_for('admin'))

    # Check if room name already exists
    name_ref = db.collection("rooms").where("name", "==", name).limit(1).get()
    if name_ref:
        flash('Room name already exists!', 'danger')
        return redirect(url_for('admin'))

    # Save video
    video_filename = secure_filename(f"room_{room_id}.mp4")
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    video.save(video_path)

    # Add room to Firestore
    db.collection("rooms").document(room_id).set({
        "name": name,
        "video": video_filename,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    flash('Room added successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_room/<room_id>', methods=['POST'])
@login_required
def delete_room(room_id):
    room_ref = db.collection("rooms").document(room_id).get()
    if room_ref.exists:
        video_filename = room_ref.to_dict().get("video")
        if video_filename:
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
            if os.path.exists(video_path):
                os.remove(video_path)
        db.collection("rooms").document(room_id).delete()
        flash('Room deleted successfully!', 'success')
    else:
        flash('Room not found!', 'danger')
    return redirect(url_for('admin'))


# ---------------- TIMETABLE ---------------- #
@app.route('/add_timetable', methods=['POST'])
@login_required
def add_timetable():
    day = request.form.get('day', '').strip()
    period = request.form.get('period', '').strip()
    subject = request.form.get('subject', '').strip()
    teacher = request.form.get('teacher', '').strip()
    room = request.form.get('room', '').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()

    if not (day and period and subject and teacher and room and start_time and end_time):
        flash('All timetable fields required!', 'danger')
        return redirect(url_for('admin'))

    try:
        s = datetime.strptime(start_time, '%H:%M')
        e = datetime.strptime(end_time, '%H:%M')
        if e <= s:
            flash('End time must be later than start time!', 'danger')
            return redirect(url_for('admin'))
    except ValueError:
        flash('Invalid time format (HH:MM).', 'danger')
        return redirect(url_for('admin'))

    existing_ref = db.collection("timetable").where("day", "==", day).where("period", "==", period).limit(1).get()
    if existing_ref:
        flash('This time slot already exists!', 'danger')
        return redirect(url_for('admin'))

    db.collection("timetable").add({
        "day": day,
        "period": period,
        "subject": subject,
        "teacher": teacher,
        "room": room,
        "start_time": start_time,
        "end_time": end_time,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    flash('Timetable entry added!', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_timetable/<entry_id>', methods=['POST'])
@login_required
def delete_timetable(entry_id):
    entry_ref = db.collection("timetable").document(entry_id).get()
    if entry_ref.exists:
        db.collection("timetable").document(entry_id).delete()
        flash('Timetable entry deleted!', 'success')
    else:
        flash('Timetable not found!', 'danger')
    return redirect(url_for('admin'))


# ---------------- EXAMS ---------------- #
@app.route('/add_exam', methods=['POST'])
@login_required
def add_exam():
    name = request.form.get('exam_name', '').strip()
    date = request.form.get('exam_date', '').strip()
    room = request.form.get('exam_room', '').strip()
    start_time = request.form.get('exam_start_time', '').strip()
    end_time = request.form.get('exam_end_time', '').strip()

    if not (name and date and room and start_time and end_time):
        flash('All exam fields required!', 'danger')
        return redirect(url_for('admin'))

    try:
        exam_date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid exam date format.', 'danger')
        return redirect(url_for('admin'))

    try:
        s = datetime.strptime(start_time, '%H:%M')
        e = datetime.strptime(end_time, '%H:%M')
        if e <= s:
            flash('End time must be later than start!', 'danger')
            return redirect(url_for('admin'))
    except ValueError:
        flash('Invalid exam time format.', 'danger')
        return redirect(url_for('admin'))

    db.collection("exams").add({
        "name": name,
        "date": exam_date.strftime('%Y-%m-%d'),
        "room": room,
        "start_time": start_time,
        "end_time": end_time,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    flash('Exam added!', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_exam/<exam_id>', methods=['POST'])
@login_required
def delete_exam(exam_id):
    ex_ref = db.collection("exams").document(exam_id).get()
    if ex_ref.exists:
        db.collection("exams").document(exam_id).delete()
        flash('Exam deleted!', 'success')
    else:
        flash('Exam not found!', 'danger')
    return redirect(url_for('admin'))


# ---------------- AUTH ---------------- #
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        try:
            user_record = auth.get_user_by_email(email)
            user_ref = db.collection("users").document(user_record.uid).get()
            if user_ref.exists and check_password_hash(user_ref.to_dict().get('password',''), password):
                user_obj = User(user_record.uid, user_ref.to_dict().get('username'), email)
                login_user(user_obj)
                return jsonify({"success": True})
        except Exception as e:
            print("Login error:", e)
            return jsonify({"success": False, "message": "Invalid email or password"}), 401

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Use form data instead of JSON
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not name or not email or not password or not confirm_password:
            flash("All fields required!", "danger")
            return redirect(url_for('signup_form'))

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('signup_form'))

        try:
            # Create user in Firebase Auth
            user_record = auth.create_user(email=email, password=password)
            user_uid = user_record.uid

            # Save user info in Firestore
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            db.collection("users").document(user_uid).set({
                "username": name,
                "email": email,
                "password": hashed_password,
                "role": "admin",
                "created_at": firestore.SERVER_TIMESTAMP
            })

            # Optional: send welcome email
            send_email(email, "Welcome!", f"Hello {name}, your account is ready!")

            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))

        except firebase_admin.auth.EmailAlreadyExistsError:
            flash("This email is already registered.", "danger")
            return redirect(url_for('signup_form'))
        except Exception as e:
            print("Signup error:", e)
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for('signup_form'))

    return render_template('signup.html')


# ---------------- PASSWORD RESET ---------------- #
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')

        try:
            reset_link = auth.generate_password_reset_link(email)
            subject = "Password Reset Request - Indoor Navigation System"
            body = f"""
            <html><body>
            <p>Click the link below to reset your password:</p>
            <p><a href="{reset_link}">Reset Password</a></p>
            </body></html>
            """
            if send_email(email, subject, body):
                return jsonify({"success": True, "message": "Reset link sent to your email."})
            else:
                return jsonify({"success": False, "message": "Email sending failed. Check config."})
        except Exception as e:
            print("Forgot password error:", e)
            return jsonify({"success": False, "message": "Could not generate reset link."})

    return render_template('forgot_password.html')


# ---------------- LOGOUT ---------------- #
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
