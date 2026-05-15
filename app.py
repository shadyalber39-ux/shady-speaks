from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from pathlib import Path
from datetime import datetime
import uuid

app = Flask(__name__, instance_relative_config=True)
app.secret_key = "shady-speaks-clean-v13"

Path(app.instance_path).mkdir(parents=True, exist_ok=True)
import os
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL") or "sqlite:///" + str(Path(app.instance_path) / "shady_speaks.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

PROJECT_UPLOAD_DIR = Path(app.root_path) / "static" / "uploads" / "projects"
REEL_UPLOAD_DIR = Path(app.root_path) / "static" / "uploads" / "reels"
PROJECT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REEL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

db = SQLAlchemy(app)

ADMIN_EMAIL = "shadyalber39@gmail.com"
ADMIN_PASSWORD_HASH = generate_password_hash("shady12345")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(200), nullable=False)
    short_description = db.Column(db.Text, nullable=False)
    long_description = db.Column(db.Text, nullable=False)
    cover_image = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reels = db.relationship("Reel", backref="project", cascade="all, delete-orphan", lazy=True)


class Reel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    instagram_url = db.Column(db.String(700), nullable=False)
    cover_image = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SocialLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=True)
    message = db.Column(db.Text, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ServiceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    service_type = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def make_slug(text):
    raw = "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")
    while "--" in raw:
        raw = raw.replace("--", "-")
    return raw or f"project-{uuid.uuid4().hex[:6]}"


def save_image(file_storage, folder):
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename.replace(" ", "_"))
    ext = Path(filename).suffix.lower() or ".png"
    new_name = f"{uuid.uuid4().hex}{ext}"
    target = folder / new_name
    file_storage.save(target)

    if folder == PROJECT_UPLOAD_DIR:
        return f"uploads/projects/{new_name}"
    return f"uploads/reels/{new_name}"

def seed_projects():
    if Project.query.count() > 0:
        return

    default_projects = [
        ("رسائل لن تُرسل", "Emotional Voice Over",
         "Emotional storytelling and personal voice-over pieces that turn unspoken feelings into words.",
         "A personal emotional series built around the words we never send, the feelings we hide, and the quiet moments that deserve a voice."),
        ("حكاية ترنيمة", "Spiritual Storytelling",
         "A cinematic spiritual storytelling series exploring hymns and the emotions behind them.",
         "A series that opens the meaning behind hymns in a simple, heartfelt way — connecting lyrics, faith, and real life."),
        ("Shady Speaks", "Short Reels",
         "Short emotional reels, thoughts, and quiet conversations that feel personal and real.",
         "Short voice-over pieces made to feel like a conversation with a close friend — direct, honest, and human."),
        ("Ads / Commercial", "Commercial Voice Over",
         "Commercial voice-over work crafted to sound warm, human, and memorable.",
         "Voice-over work for brands, reels, campaigns, and commercial content that needs a clear, warm, and believable voice."),
    ]

    for title, subtitle, short_description, long_description in default_projects:
        slug = make_slug(title)
        base_slug = slug
        count = 2
        while Project.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{count}"
            count += 1
        db.session.add(Project(
            slug=slug,
            title=title,
            subtitle=subtitle,
            short_description=short_description,
            long_description=long_description
        ))
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_projects()


@app.route("/")
def home():
    projects = Project.query.order_by(Project.created_at.asc()).all()
    feedback_items = Feedback.query.order_by(Feedback.created_at.desc()).limit(4).all()
    return render_template("index.html", projects=projects, feedback_items=feedback_items)


@app.route("/projects/<slug>")
def project_page(slug):
    project = Project.query.filter_by(slug=slug).first_or_404()
    feedback_items = Feedback.query.filter_by(project_id=project.id).order_by(Feedback.created_at.desc()).limit(6).all()
    return render_template("project.html", project=project, feedback_items=feedback_items)


@app.route("/feedback", methods=["POST"])
def feedback():
    name = request.form.get("name", "").strip()
    message = request.form.get("message", "").strip()
    project_id = request.form.get("project_id", "").strip()

    if message:
        db.session.add(Feedback(name=name or None, message=message, project_id=int(project_id) if project_id else None))
        db.session.commit()
        flash("Thank you for your feedback.")
    else:
        flash("Please write feedback first.")

    return redirect(request.referrer or url_for("home"))


@app.route("/request-service", methods=["POST"])
def request_service():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    service_type = request.form.get("service_type", "").strip()
    message = request.form.get("message", "").strip()

    if not all([name, phone, email, service_type, message]):
        flash("Please fill in all fields.")
        return redirect(url_for("home") + "#book")

    db.session.add(ServiceRequest(name=name, phone=phone, email=email, service_type=service_type, message=message))
    db.session.commit()
    flash("Your request has been sent.")
    return redirect(url_for("home") + "#book")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if email == ADMIN_EMAIL and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))
        flash("Invalid login details.")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@login_required
def admin():
    projects = Project.query.order_by(Project.created_at.asc()).all()
    requests = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).all()
    feedback_items = Feedback.query.order_by(Feedback.created_at.desc()).all()
    return render_template("admin.html", projects=projects, requests=requests, feedback_items=feedback_items)


@app.route("/admin/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)

    if request.method == "POST":
        project.title = request.form.get("title", "").strip()
        project.subtitle = request.form.get("subtitle", "").strip()
        project.short_description = request.form.get("short_description", "").strip()
        project.long_description = request.form.get("long_description", "").strip()

        uploaded = save_image(request.files.get("cover_image"), PROJECT_UPLOAD_DIR)
        if uploaded:
            project.cover_image = uploaded

        db.session.commit()
        flash("Project saved.")
        return redirect(url_for("edit_project", project_id=project.id))

    return render_template("project_form.html", project=project)


@app.route("/admin/projects/new", methods=["GET", "POST"])
@login_required
def new_project():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subtitle = request.form.get("subtitle", "").strip()
        short_description = request.form.get("short_description", "").strip()
        long_description = request.form.get("long_description", "").strip()

        if not all([title, subtitle, short_description, long_description]):
            flash("Please fill in all fields.")
            return redirect(url_for("new_project"))

        slug = make_slug(title)
        base_slug = slug
        count = 2
        while Project.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{count}"
            count += 1

        cover_image = save_image(request.files.get("cover_image"), PROJECT_UPLOAD_DIR)
        project = Project(
            slug=slug,
            title=title,
            subtitle=subtitle,
            short_description=short_description,
            long_description=long_description,
            cover_image=cover_image
        )
        db.session.add(project)
        db.session.commit()
        flash("Project created.")
        return redirect(url_for("admin"))

    return render_template("project_form.html", project=None)


@app.route("/admin/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.")
    return redirect(url_for("admin"))


@app.route("/admin/projects/<int:project_id>/reels/new", methods=["GET", "POST"])
@login_required
def new_reel(project_id):
    project = Project.query.get_or_404(project_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        instagram_url = request.form.get("instagram_url", "").strip()

        if not all([title, description, instagram_url]):
            flash("Please fill in all fields.")
            return redirect(url_for("new_reel", project_id=project.id))

        cover_image = save_image(request.files.get("cover_image"), REEL_UPLOAD_DIR)
        db.session.add(Reel(
            project_id=project.id,
            title=title,
            description=description,
            instagram_url=instagram_url,
            cover_image=cover_image
        ))
        db.session.commit()
        flash("Reel added.")
        return redirect(url_for("admin"))

    return render_template("reel_form.html", reel=None, project=project)


@app.route("/admin/reels/<int:reel_id>/edit", methods=["GET", "POST"])
@login_required
def edit_reel(reel_id):
    reel = Reel.query.get_or_404(reel_id)

    if request.method == "POST":
        reel.title = request.form.get("title", "").strip()
        reel.description = request.form.get("description", "").strip()
        reel.instagram_url = request.form.get("instagram_url", "").strip()

        uploaded = save_image(request.files.get("cover_image"), REEL_UPLOAD_DIR)
        if uploaded:
            reel.cover_image = uploaded

        db.session.commit()
        flash("Reel saved.")
        return redirect(url_for("edit_reel", reel_id=reel.id))

    return render_template("reel_form.html", reel=reel, project=reel.project)


@app.route("/admin/reels/<int:reel_id>/delete", methods=["POST"])
@login_required
def delete_reel(reel_id):
    reel = Reel.query.get_or_404(reel_id)
    db.session.delete(reel)
    db.session.commit()
    flash("Reel deleted.")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=True)
