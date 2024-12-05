from flask import (
    Blueprint, render_template, request, jsonify,
    redirect, url_for, flash, current_app, g
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import os
import logging
from datetime import datetime, timedelta
from functools import wraps
from app.extensions import db, bcrypt
from app.models import User
from app.services.scraper import ScraperService

# Create Blueprint
bp = Blueprint('main', __name__)

# Optional Flask-Limiter for rate limiting
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )
except ImportError:
    limiter = None

# Middleware
@bp.before_request
def log_request_info():
    if not request.path.startswith('/static'):
        logging.info(f"Request: {request.method} {request.path} from {request.remote_addr}")

@bp.before_request
def make_session_permanent():
    current_app.permanent_session_lifetime = timedelta(days=7)

@bp.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

@bp.after_request
def add_rate_limit_headers(response):
    try:
        remaining = getattr(g, 'rate_limit_remaining', None)
        if remaining is not None:
            response.headers['X-RateLimit-Remaining'] = str(remaining)
    except Exception:
        pass
    return response

# Decorators
def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_admin:
            flash("Access denied. Admin privileges required.", "danger")
            return redirect(url_for("main.index"))
        return func(*args, **kwargs)
    return decorated_view

# Helpers
def validate_request_json():
    """Validate JSON request data."""
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415
    return None

# Routes
## Main Routes
@bp.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html")
    return redirect(url_for("main.login"))

@bp.route("/dashboard")
@login_required
def dashboard():
    """User dashboard showing usage stats."""
    return render_template(
        "user_dashboard.html",
        scrapes_used=current_user.scrapes_used,
        scrape_limit=current_user.scrape_limit,
        remaining_scrapes=current_user.scrape_limit - current_user.scrapes_used
    )

@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        try:
            current_password = request.form.get("current_password")
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            if not bcrypt.check_password_hash(current_user.password, current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("main.change_password"))

            if len(new_password) < 8:
                flash("New password must be at least 8 characters long.", "danger")
                return redirect(url_for("main.change_password"))

            if new_password != confirm_password:
                flash("New passwords don't match.", "danger")
                return redirect(url_for("main.change_password"))

            current_user.password = bcrypt.generate_password_hash(new_password).decode("utf-8")
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(url_for("main.dashboard"))

        except Exception as e:
            logging.error(f"Password change error for user {current_user.id}: {e}")
            flash("An error occurred while changing your password.", "danger")

    return render_template("change_password.html")

## Scraping Route
@bp.route("/scrape", methods=["POST"])
@login_required
@limiter.limit("60 per minute") if limiter else lambda x: x  # Apply limit if limiter exists
def scrape():
    """Scrape URLs and return results."""
    validation_error = validate_request_json()
    if validation_error:
        return validation_error

    try:
        data = request.json
        urls = data.get("urls", [])

        if not urls:
            return jsonify({"error": "No URLs provided"}), 400

        remaining_scrapes = current_user.scrape_limit - current_user.scrapes_used
        if len(urls) > remaining_scrapes:
            return jsonify({"error": "Scrape limit exceeded"}), 403

        scraper = ScraperService(current_app.config["SCRAPEOPS_API_KEY"])
        scraped_data, errors = [], []

        for url in urls:
            try:
                result = scraper.scrape_url(url)
                scraped_data.append(result)
                current_user.scrapes_used += 1
                db.session.commit()
            except Exception as e:
                errors.append({"url": url, "error": str(e)})
                logging.error(f"Error scraping URL {url}: {e}")

        response = {
            "message": "Scraping complete",
            "data": scraped_data,
            "errors": errors,
            "scrapes_remaining": current_user.scrape_limit - current_user.scrapes_used
        }
        return jsonify(response)

    except Exception as e:
        logging.error(f"Scraping error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

## Auth Routes
@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute") if limiter else lambda x: x  # Apply limit if limiter exists
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    next_page = request.args.get("next")
    if request.method == "POST":
        try:
            email = request.form.get("email")
            password = request.form.get("password")
            user = User.query.filter_by(email=email).first()

            if user and bcrypt.check_password_hash(user.password, password):
                user.last_seen = datetime.utcnow()
                user.last_login_ip = request.remote_addr
                db.session.commit()
                login_user(user)
                flash("Login successful!", "success")
                return redirect(next_page) if next_page else redirect(url_for("main.index"))
            else:
                flash("Invalid email or password.", "danger")
        except Exception as e:
            logging.error(f"Login error: {e}")
            flash("An error occurred during login.", "danger")

    return render_template("login.html")

@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per hour") if limiter else lambda x: x  # Apply limit if limiter exists
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        try:
            username = request.form.get("username")
            email = request.form.get("email")
            password = request.form.get("password")

            if len(username) < 3:
                flash("Username must be at least 3 characters long.", "danger")
                return redirect(url_for("main.register"))

            if len(password) < 8:
                flash("Password must be at least 8 characters long.", "danger")
                return redirect(url_for("main.register"))

            if '@' not in email:
                flash("Invalid email address.", "danger")
                return redirect(url_for("main.register"))

            if User.query.filter_by(email=email).first():
                flash("Email already registered.", "danger")
                return redirect(url_for("main.register"))

            if User.query.filter_by(username=username).first():
                flash("Username already taken.", "danger")
                return redirect(url_for("main.register"))

            hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
            user = User(username=username, email=email, password=hashed_password)
            db.session.add(user)
            db.session.commit()

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("main.login"))
        except Exception as e:
            logging.error(f"Registration error: {e}")
            flash("An error occurred during registration.", "danger")

    return render_template("register.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.login"))

## Error Handlers
@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template("errors/404.html"), 404

@bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("errors/500.html"), 500

@bp.app_errorhandler(403)
def forbidden_error(error):
    return render_template("errors/403.html"), 403

@bp.app_errorhandler(Exception)
def handle_error(error):
    error_message = str(error)
    app.logger.error(f'An error occurred: {error_message}')
    return render_template('errors/error.html', error_message=error_message), 500