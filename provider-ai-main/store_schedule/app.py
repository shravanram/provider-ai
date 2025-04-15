# app.py
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB


from flask import Flask, send_from_directory

app = Flask(__name__, static_folder="public", static_url_path="")

# change password according to setup
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "postgresql://myuser:mypassword@localhost:5432/mydatabase"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)


# 1. Serve our index.html from the "public" folder at the root URL
@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")


# 2. Define a table with doctor_name as PRIMARY KEY
class DoctorSchedule(db.Model):
    __tablename__ = "doctor_schedules"

    # doctor_name is unique, so make it the PK
    doctor_name = db.Column(db.String(100), primary_key=True)
    specialty = db.Column(db.String(100))
    # We store timeSlots in a JSONB column
    time_slots = db.Column(JSONB)


# 3. Create tables if they don't exist
with app.app_context():
    db.create_all()


@app.route("/api/schedule", methods=["POST"])
def save_schedule():
    data = request.get_json()

    # Extract fields from incoming JSON
    doctor_name = data.get("doctorName")
    specialty = data.get("specialty")
    time_slots = data.get("timeSlots")  # This can be a list/dict

    # 4. If a row with doctor_name exists, delete it
    existing = db.session.get(DoctorSchedule, doctor_name)  # get() uses the primary key
    if existing:
        db.session.delete(existing)
        db.session.commit()

    # 5. Create and insert new schedule
    new_doc = DoctorSchedule(
        doctor_name=doctor_name, specialty=specialty, time_slots=time_slots
    )
    db.session.add(new_doc)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Schedule for {doctor_name} saved (replaced if existed).",
            }
        ),
        201,
    )


@app.route("/api/schedule", methods=["GET"])
def list_schedules():
    docs = DoctorSchedule.query.all()
    results = []
    for doc in docs:
        results.append(
            {
                "doctorName": doc.doctor_name,
                "specialty": doc.specialty,
                "timeSlots": doc.time_slots,
            }
        )
    return jsonify(results), 200


if __name__ == "__main__":
    app.run(debug=True)
