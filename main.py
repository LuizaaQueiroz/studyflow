from __future__ import annotations

from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import Optional

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import func
from flask import render_template

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///vestibulando.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

CORS(app)
db = SQLAlchemy(app)


# =========================
# Helpers
# =========================
def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def calculate_performance(acertos: int, total_questoes: int) -> float:
    if total_questoes <= 0:
        raise ValueError("total_questoes deve ser maior que zero")
    if acertos < 0 or acertos > total_questoes:
        raise ValueError("acertos inválido")
    return round((acertos / total_questoes) * 100, 2)


def calculate_review_interval_days(rendimento: float) -> int:
    if rendimento >= 90:
        return 12
    if rendimento >= 70:
        return 7
    if rendimento >= 50:
        return 3
    return 1


def infer_weakness_flag(rendimento: float) -> bool:
    return rendimento < 60


def model_to_dict(model) -> dict:
    if hasattr(model, "to_dict"):
        return model.to_dict()
    raise TypeError("Modelo sem método to_dict")


# =========================
# Models
# =========================
class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    contents = db.relationship("Content", backref="subject", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
        }


class Content(db.Model):
    __tablename__ = "contents"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name if self.subject else None,
        }


class ExerciseRecord(db.Model):
    __tablename__ = "exercise_records"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    content_id = db.Column(db.Integer, db.ForeignKey("contents.id"), nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, nullable=False)
    wrong_answers = db.Column(db.Integer, nullable=False)
    performance = db.Column(db.Float, nullable=False)
    weak_point = db.Column(db.Boolean, default=False, nullable=False)
    record_date = db.Column(db.Date, nullable=False)
    review_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    subject = db.relationship("Subject", lazy=True)
    content = db.relationship("Content", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name if self.subject else None,
            "content_id": self.content_id,
            "content_name": self.content.name if self.content else None,
            "total_questions": self.total_questions,
            "correct_answers": self.correct_answers,
            "wrong_answers": self.wrong_answers,
            "performance": self.performance,
            "weak_point": self.weak_point,
            "record_date": self.record_date.isoformat(),
            "review_date": self.review_date.isoformat(),
        }


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    exercise_record_id = db.Column(db.Integer, db.ForeignKey("exercise_records.id"), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False)
    completed_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="pending", nullable=False)
    review_type = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    exercise_record = db.relationship("ExerciseRecord", lazy=True)

    def to_dict(self) -> dict:
        record = self.exercise_record
        return {
            "id": self.id,
            "exercise_record_id": self.exercise_record_id,
            "scheduled_date": self.scheduled_date.isoformat(),
            "completed_date": self.completed_date.isoformat() if self.completed_date else None,
            "status": self.status,
            "review_type": self.review_type,
            "notes": self.notes,
            "subject_name": record.subject.name if record and record.subject else None,
            "content_name": record.content.name if record and record.content else None,
            "performance": record.performance if record else None,
        }


class StudySession(db.Model):
    __tablename__ = "study_sessions"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    content_id = db.Column(db.Integer, db.ForeignKey("contents.id"), nullable=True)
    study_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    subject = db.relationship("Subject", lazy=True)
    content = db.relationship("Content", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name if self.subject else None,
            "content_id": self.content_id,
            "content_name": self.content.name if self.content else None,
            "study_date": self.study_date.isoformat(),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": self.duration_minutes,
        }


# =========================
# Database bootstrap
# =========================
@app.route("/setup", methods=["POST"])
def setup_database():
    db.create_all()

    default_subjects = ["Matemática", "Biologia", "História", "Química", "Física", "Português"]
    created = []

    for subject_name in default_subjects:
        existing = Subject.query.filter_by(name=subject_name).first()
        if not existing:
            subject = Subject(name=subject_name)
            db.session.add(subject)
            created.append(subject_name)

    db.session.commit()

    return jsonify({
        "message": "Banco inicializado com sucesso.",
        "created_subjects": created,
    }), 201


# =========================
# Subject and content routes
# =========================
@app.route("/subjects", methods=["GET"])
def list_subjects():
    subjects = Subject.query.order_by(Subject.name.asc()).all()
    return jsonify([subject.to_dict() for subject in subjects])


@app.route("/subjects", methods=["POST"])
def create_subject():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"error": "O campo 'name' é obrigatório."}), 400

    existing = Subject.query.filter(func.lower(Subject.name) == name.lower()).first()
    if existing:
        return jsonify(existing.to_dict()), 200

    subject = Subject(name=name)
    db.session.add(subject)
    db.session.commit()

    return jsonify(subject.to_dict()), 201


@app.route("/contents", methods=["GET"])
def list_contents():
    subject_id = request.args.get("subject_id", type=int)
    query = Content.query

    if subject_id:
        query = query.filter_by(subject_id=subject_id)

    contents = query.order_by(Content.name.asc()).all()
    return jsonify([content.to_dict() for content in contents])


@app.route("/contents", methods=["POST"])
def create_content():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    subject_id = data.get("subject_id")

    if not name or not subject_id:
        return jsonify({"error": "Os campos 'name' e 'subject_id' são obrigatórios."}), 400

    subject = Subject.query.get(subject_id)
    if not subject:
        return jsonify({"error": "Matéria não encontrada."}), 404

    content = Content(name=name, subject_id=subject_id)
    db.session.add(content)
    db.session.commit()

    return jsonify(content.to_dict()), 201


# =========================
# Exercise and review routes
# =========================
@app.route("/exercise-records", methods=["POST"])
def create_exercise_record():
    data = request.get_json() or {}

    try:
        subject_id = int(data.get("subject_id"))
        content_id = int(data.get("content_id"))
        total_questions = int(data.get("total_questions"))
        correct_answers = int(data.get("correct_answers"))
        record_date = parse_date(data.get("record_date")) if data.get("record_date") else date.today()
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Dados inválidos: {exc}"}), 400

    subject = Subject.query.get(subject_id)
    content = Content.query.get(content_id)

    if not subject:
        return jsonify({"error": "Matéria não encontrada."}), 404
    if not content:
        return jsonify({"error": "Conteúdo não encontrado."}), 404
    if content.subject_id != subject.id:
        return jsonify({"error": "O conteúdo não pertence à matéria informada."}), 400

    try:
        performance = calculate_performance(correct_answers, total_questions)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    wrong_answers = total_questions - correct_answers
    review_interval_days = calculate_review_interval_days(performance)
    review_date = record_date + timedelta(days=review_interval_days)
    weak_point = infer_weakness_flag(performance)

    exercise_record = ExerciseRecord(
        subject_id=subject_id,
        content_id=content_id,
        total_questions=total_questions,
        correct_answers=correct_answers,
        wrong_answers=wrong_answers,
        performance=performance,
        weak_point=weak_point,
        record_date=record_date,
        review_date=review_date,
    )
    db.session.add(exercise_record)
    db.session.flush()

    review = Review(
        exercise_record_id=exercise_record.id,
        scheduled_date=review_date,
        status="pending",
    )
    db.session.add(review)
    db.session.commit()

    return jsonify({
        "exercise_record": exercise_record.to_dict(),
        "review": review.to_dict(),
    }), 201


@app.route("/exercise-records", methods=["GET"])
def list_exercise_records():
    records = ExerciseRecord.query.order_by(ExerciseRecord.record_date.desc(), ExerciseRecord.id.desc()).all()
    return jsonify([record.to_dict() for record in records])


@app.route("/reviews", methods=["GET"])
def list_reviews():
    status = request.args.get("status")
    today = date.today()

    query = Review.query
    if status in {"pending", "completed", "late"}:
        if status == "late":
            query = query.filter(Review.status == "pending", Review.scheduled_date < today)
        else:
            query = query.filter(Review.status == status)

    reviews = query.order_by(Review.scheduled_date.asc(), Review.id.asc()).all()

    result = []
    for review in reviews:
        item = review.to_dict()
        if review.status == "pending" and review.scheduled_date < today:
            item["computed_status"] = "late"
        else:
            item["computed_status"] = review.status
        result.append(item)

    return jsonify(result)


@app.route("/reviews/<int:review_id>/complete", methods=["PATCH"])
def complete_review(review_id: int):
    review = Review.query.get(review_id)
    if not review:
        return jsonify({"error": "Revisão não encontrada."}), 404

    data = request.get_json() or {}
    completed_date = parse_date(data.get("completed_date")) if data.get("completed_date") else date.today()
    review_type = data.get("review_type")
    notes = data.get("notes")

    review.completed_date = completed_date
    review.status = "completed"
    review.review_type = review_type
    review.notes = notes
    db.session.commit()

    return jsonify(review.to_dict())


# =========================
# Study session routes
# =========================
@app.route("/study-sessions", methods=["POST"])
def create_study_session():
    data = request.get_json() or {}

    try:
        subject_id = int(data.get("subject_id"))
        content_id = int(data["content_id"]) if data.get("content_id") is not None else None
        start_time = datetime.fromisoformat(data.get("start_time"))
        end_time = datetime.fromisoformat(data.get("end_time"))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Dados inválidos: {exc}"}), 400

    subject = Subject.query.get(subject_id)
    if not subject:
        return jsonify({"error": "Matéria não encontrada."}), 404

    content = None
    if content_id is not None:
        content = Content.query.get(content_id)
        if not content:
            return jsonify({"error": "Conteúdo não encontrado."}), 404
        if content.subject_id != subject.id:
            return jsonify({"error": "O conteúdo não pertence à matéria informada."}), 400

    if end_time <= start_time:
        return jsonify({"error": "end_time deve ser maior que start_time."}), 400

    duration_minutes = int((end_time - start_time).total_seconds() // 60)
    study_date = start_time.date()

    session = StudySession(
        subject_id=subject_id,
        content_id=content_id,
        study_date=study_date,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
    )
    db.session.add(session)
    db.session.commit()

    return jsonify(session.to_dict()), 201


@app.route("/study-sessions", methods=["GET"])
def list_study_sessions():
    sessions = StudySession.query.order_by(StudySession.study_date.desc(), StudySession.start_time.desc()).all()
    return jsonify([session.to_dict() for session in sessions])


@app.route("/calendar-summary", methods=["GET"])
def calendar_summary():
    sessions = StudySession.query.order_by(StudySession.study_date.asc()).all()
    summary: dict[str, dict] = {}

    for session in sessions:
        key = session.study_date.isoformat()
        if key not in summary:
            summary[key] = {
                "date": key,
                "total_minutes": 0,
                "subjects": defaultdict(int),
            }

        summary[key]["total_minutes"] += session.duration_minutes
        subject_name = session.subject.name if session.subject else "Sem matéria"
        summary[key]["subjects"][subject_name] += session.duration_minutes

    result = []
    for item in summary.values():
        result.append({
            "date": item["date"],
            "total_minutes": item["total_minutes"],
            "total_hours": round(item["total_minutes"] / 60, 2),
            "subjects": [
                {
                    "name": name,
                    "minutes": minutes,
                    "hours": round(minutes / 60, 2),
                }
                for name, minutes in sorted(item["subjects"].items())
            ],
        })

    return jsonify(result)


# =========================
# Dashboard route
# =========================
@app.route("/dashboard", methods=["GET"])
def dashboard():
    today = date.today()

    total_sessions_today = db.session.query(func.coalesce(func.sum(StudySession.duration_minutes), 0)).filter(
        StudySession.study_date == today
    ).scalar()

    total_sessions_week = db.session.query(func.coalesce(func.sum(StudySession.duration_minutes), 0)).filter(
        StudySession.study_date >= today - timedelta(days=6),
        StudySession.study_date <= today,
    ).scalar()

    avg_performance = db.session.query(func.avg(ExerciseRecord.performance)).scalar() or 0

    late_reviews_count = Review.query.filter(
        Review.status == "pending",
        Review.scheduled_date < today,
    ).count()

    pending_reviews_today = Review.query.filter(
        Review.status == "pending",
        Review.scheduled_date == today,
    ).count()

    weak_points = (
        db.session.query(
            Subject.name.label("subject_name"),
            Content.name.label("content_name"),
            func.avg(ExerciseRecord.performance).label("avg_performance"),
        )
        .join(Content, ExerciseRecord.content_id == Content.id)
        .join(Subject, ExerciseRecord.subject_id == Subject.id)
        .group_by(Subject.name, Content.name)
        .having(func.avg(ExerciseRecord.performance) < 60)
        .order_by(func.avg(ExerciseRecord.performance).asc())
        .limit(5)
        .all()
    )

    return jsonify({
        "today": today.isoformat(),
        "study_hours_today": round(total_sessions_today / 60, 2),
        "study_hours_last_7_days": round(total_sessions_week / 60, 2),
        "average_performance": round(float(avg_performance), 2),
        "pending_reviews_today": pending_reviews_today,
        "late_reviews": late_reviews_count,
        "weak_points": [
            {
                "subject": item.subject_name,
                "content": item.content_name,
                "average_performance": round(float(item.avg_performance), 2),
            }
            for item in weak_points
        ],
    })


# =========================
# Health check
# =========================

@app.route("/")
def home():
    return render_template("index.html")
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "API vestibulando online"})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
