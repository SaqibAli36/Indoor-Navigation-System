import os
from flask import Flask, render_template
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from dotenv import load_dotenv

# Load .env
load_dotenv()

app = Flask(__name__)

# Resolve Firebase credential path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cred_filename = os.getenv("FIREBASE_CRED")
cred_path = os.path.join(BASE_DIR, cred_filename)

if not cred_filename or not os.path.exists(cred_path):
    raise RuntimeError(f"Firebase credential file not found: {cred_path}")

# Firebase Setup (initialize only once)
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()


@app.route('/')
@app.route('/user')
def user():
    # Fetch all rooms
    rooms_ref = db.collection("rooms").stream()
    rooms = [{"id": doc.id, **doc.to_dict()} for doc in rooms_ref]

    # Fetch timetable
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
            "end_time": d.get("end_time", "")
        })

    # Fetch exams
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
            "end_time": d.get("end_time", "")
        })

    return render_template(
        'user.html',
        rooms=rooms,
        timetable=timetable,
        exams=exams
    )


if __name__ == '__main__':
    app.run(debug=True, port=5002)
