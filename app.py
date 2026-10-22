
import os
from functools import wraps
from decimal import Decimal, InvalidOperation

import click
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", "change-this-secret-key"
)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from your .env file.")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql://", 1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ==================================================
# DATABASE MODELS
# ==================================================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20), nullable=False, default="customer"
    )


class Construction(db.Model):
    __tablename__ = "construction"

    id = db.Column(db.BigInteger, primary_key=True)
    project_name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(300))
    description = db.Column(db.Text)
    project_type = db.Column(db.String(100))
    status = db.Column(
        db.String(50), nullable=False, default="Completed"
    )
    area_sqft = db.Column(db.Numeric(12, 2), default=0)
    cost_per_sqft = db.Column(db.Numeric(12, 2), default=0)
    total_cost = db.Column(db.Numeric(14, 2), default=0)
    image_url = db.Column(db.Text)


# ==================================================
# LOGIN AND ROLE PROTECTION
# ==================================================

def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapper


def role_required(required_role):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(
                    url_for("login", account_type=required_role)
                )

            if session.get("role") != required_role:
                flash("You are not authorized to access this page.", "danger")

                if session.get("role") == "admin":
                    return redirect(url_for("dashboard"))

                return redirect(url_for("customer_home"))

            return view(*args, **kwargs)
        return wrapper
    return decorator


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def index():
    if session.get("role") == "admin":
        return redirect(url_for("dashboard"))

    if session.get("role") == "customer":
        return redirect(url_for("customer_home"))

    return render_template("welcome.html")


# ==================================================
# SEPARATE ADMIN AND CUSTOMER LOGIN
# ==================================================

@app.route("/login")
def default_login():
    return redirect(
        url_for("login", account_type="customer")
    )


@app.route("/login/<account_type>", methods=["GET", "POST"])
def login(account_type):
    if account_type not in ("admin", "customer"):
        return redirect(url_for("index"))

    if session.get("user_id"):
        if session.get("role") == "admin":
            return redirect(url_for("dashboard"))
        if session.get("role") == "customer":
            return redirect(url_for("customer_home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if (
            user
            and check_password_hash(user.password_hash, password)
            and user.role == account_type
        ):
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role

            flash("Login successful!", "success")

            if user.role == "admin":
                return redirect(url_for("dashboard"))

            return redirect(url_for("customer_home"))

        flash(
            f"Invalid {account_type} username or password.",
            "danger"
        )

    return render_template(
        "login.html", account_type=account_type
    )


# ==================================================
# CUSTOMER REGISTRATION
# ==================================================

@app.route("/customer-register", methods=["GET", "POST"])
def customer_register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or len(password) < 8:
            flash(
                "Enter a username and a password of at least 8 characters.",
                "danger"
            )
            return render_template("customer_register.html")

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:
            flash("Username already exists.", "danger")
            return render_template("customer_register.html")

        customer = User(
            username=username,
            password_hash=generate_password_hash(password),
            role="customer"
        )

        db.session.add(customer)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")

        return redirect(
            url_for("login", account_type="customer")
        )

    return render_template("customer_register.html")


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# ==================================================
# CUSTOMER WEBSITE
# ==================================================

@app.route("/customer-home")
@login_required
@role_required("customer")
def customer_home():
    completed_projects = Construction.query.filter_by(
        status="Completed"
    ).order_by(Construction.id.desc()).all()

    ongoing_projects = Construction.query.filter_by(
        status="Ongoing"
    ).order_by(Construction.id.desc()).all()

    return render_template(
        "customer_home.html",
        completed_projects=completed_projects,
        ongoing_projects=ongoing_projects
    )


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    total_projects = Construction.query.count()

    completed_projects = Construction.query.filter_by(
        status="Completed"
    ).count()

    ongoing_projects = Construction.query.filter_by(
        status="Ongoing"
    ).count()

    total_area = db.session.query(
        db.func.coalesce(
            db.func.sum(Construction.area_sqft), 0
        )
    ).scalar()

    total_value = db.session.query(
        db.func.coalesce(
            db.func.sum(Construction.total_cost), 0
        )
    ).scalar()

    recent_projects = Construction.query.order_by(
        Construction.id.desc()
    ).limit(5).all()

    return render_template(
        "dashboard.html",
        total_projects=total_projects,
        completed_projects=completed_projects,
        ongoing_projects=ongoing_projects,
        total_area=total_area,
        total_value=total_value,
        recent_projects=recent_projects
    )


# ==================================================
# ABOUT
# ==================================================

@app.route("/about")
@login_required
@role_required("admin")
def about():
    return render_template("about.html")


# ==================================================
# PROJECT LIST
# ==================================================

@app.route("/projects")
@login_required
@role_required("admin")
def projects():
    project_list = Construction.query.order_by(
        Construction.id.desc()
    ).all()

    return render_template(
        "projects.html", projects=project_list
    )


# ==================================================
# VALIDATE PROJECT FORM
# ==================================================

def get_project_form_data():
    project_name = request.form.get(
        "project_name", ""
    ).strip()

    if not project_name:
        raise ValueError("Project name is required.")

    status = request.form.get("status", "Completed").strip()

    if status not in ("Completed", "Ongoing"):
        raise ValueError("Choose Completed or Ongoing status.")

    try:
        area = Decimal(
            request.form.get("area_sqft", "0") or "0"
        )
        cost = Decimal(
            request.form.get("cost_per_sqft", "0") or "0"
        )

        if area < 0 or cost < 0:
            raise ValueError("Area and cost cannot be negative.")

    except InvalidOperation:
        raise ValueError("Area and cost must be valid numbers.")

    return {
        "project_name": project_name,
        "location": request.form.get("location", "").strip(),
        "description": request.form.get("description", "").strip(),
        "project_type": request.form.get("project_type", "").strip(),
        "status": status,
        "area_sqft": area,
        "cost_per_sqft": cost,
        "total_cost": area * cost,
        "image_url": request.form.get("image_url", "").strip()
    }


# ==================================================
# ADD PROJECT
# ==================================================

@app.route("/projects/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_project():
    if request.method == "POST":
        try:
            project = Construction(**get_project_form_data())

            db.session.add(project)
            db.session.commit()

            flash("Project added successfully!", "success")
            return redirect(url_for("projects"))

        except ValueError as error:
            flash(str(error), "danger")

    return render_template("project_form.html", project=None)


# ==================================================
# EDIT PROJECT
# ==================================================

@app.route(
    "/projects/edit/<int:project_id>",
    methods=["GET", "POST"]
)
@login_required
@role_required("admin")
def edit_project(project_id):
    project = Construction.query.get_or_404(project_id)

    if request.method == "POST":
        try:
            form_data = get_project_form_data()

            for key, value in form_data.items():
                setattr(project, key, value)

            db.session.commit()

            flash("Project updated successfully!", "success")
            return redirect(url_for("projects"))

        except ValueError as error:
            flash(str(error), "danger")

    return render_template(
        "project_form.html", project=project
    )


# ==================================================
# DELETE PROJECT
# ==================================================

@app.route(
    "/projects/delete/<int:project_id>",
    methods=["POST"]
)
@login_required
@role_required("admin")
def delete_project(project_id):
    project = Construction.query.get_or_404(project_id)

    db.session.delete(project)
    db.session.commit()

    flash("Project deleted successfully!", "success")
    return redirect(url_for("projects"))


# ==================================================
# ONGOING PROJECTS (ADMIN)
# ==================================================

@app.route("/ongoing")
@login_required
@role_required("admin")
def ongoing():
    project_list = Construction.query.filter_by(
        status="Ongoing"
    ).order_by(Construction.id.desc()).all()

    return render_template(
        "ongoing.html", projects=project_list
    )


# ==================================================
# MATERIALS
# ==================================================

@app.route("/materials")
@login_required
@role_required("admin")
def materials():
    return render_template("materials.html")


# ==================================================
# ESTIMATION
# ==================================================

@app.route("/estimate")
@login_required
@role_required("admin")
def estimate():
    return render_template("estimate.html")


# ==================================================
# CONTACT
# ==================================================

@app.route("/contact")
@login_required
def contact():
    return render_template("contact.html")


# ==================================================
# CREATE OR UPDATE ADMIN
# ==================================================

@app.cli.command("create-admin")
def create_admin():
    username = click.prompt("Admin username").strip()

    password = click.prompt(
        "Admin password",
        hide_input=True,
        confirmation_prompt=True
    )

    if len(password) < 8:
        raise click.ClickException(
            "Password must contain at least 8 characters."
        )

    user = User.query.filter_by(username=username).first()

    if user:
        user.password_hash = generate_password_hash(password)
        user.role = "admin"
    else:
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role="admin"
        )
        db.session.add(user)

    db.session.commit()
    click.echo(f"Admin account '{username}' is ready.")


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
