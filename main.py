from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import pandas as pd
import os
import uuid
import logging
from datetime import datetime
import random
import json
from dotenv import load_dotenv
import os
from app import create_app, db, User, bcrypt
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config["SECRET_KEY"] = "your_secret_key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    return app




load_dotenv()  # Load environment variables

# Flask extensions
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
socketio = SocketIO(cors_allowed_origins="*")


def init_db():
    app = create_app()
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create admin user if it doesn't exist
        admin_email = "admin@example.com"
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                username="admin",
                email=admin_email,
                password=bcrypt.generate_password_hash("admin_password").decode("utf-8"),
                is_admin=True,
                scrape_limit=50000  # Higher limit for admin
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created!")

if __name__ == "__main__":
    init_db()

# ScrapOps setup
SCRAPEOPS_API_KEY = "0139316f-c2f9-44ad-948c-f7a3439511c2"
scrapeops_logger = ScrapeOpsRequests(scrapeops_api_key=SCRAPEOPS_API_KEY)
requests_wrapper = scrapeops_logger.RequestsWrapper()

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app_debug.log", mode="w"),
    ],
)

# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    scrape_limit = db.Column(db.Integer, default=20000)
    scrapes_used = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create Flask app
def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "your_secret_key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = "uploads"
    app.config["DOWNLOADS_FOLDER"] = "downloads"

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)

    # Ensure required folders exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["DOWNLOADS_FOLDER"], exist_ok=True)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app


# Initialize app
app = create_app()
login_manager.login_view = "login"  # Redirect to login if unauthorized




# Routes
@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        # Hash password and save user
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    
    # Database configuration
    if os.getenv("FLASK_ENV") == "development":
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
            app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://", 1)
    
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]
        if not file or file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        if file and file.filename.endswith(".csv"):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            df = pd.read_csv(file_path)
            df = df.dropna(axis=1, how="all")
            df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

            # Ensure 'website' column exists
            website_columns = ["Website", "Websites", "website", "websites", "Domain", "Domains", "domain", "domains"]
            found_website_column = next((col for col in website_columns if col in df.columns), None)

            if found_website_column is None:
                return jsonify({"error": "No website column found. Ensure your CSV has a valid column."}), 400

            df.to_csv(file_path, index=False)

            return jsonify({
                "filename": filename,
                "columns": list(df.columns),
                "file_path": file_path,
                "website_column": found_website_column,
            })

        return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400
    except Exception as e:
        logging.error("Error during upload: %s", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/scrape", methods=["POST"])
@login_required
def scrape():
    """Scrape URLs from the uploaded file."""
    try:
        data = request.json
        file_path = data.get("file_path")
        website_col = data.get("website_column")

        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "File not found."}), 400

        # Load CSV and preprocess URLs
        df = pd.read_csv(file_path)
        urls = df[website_col].dropna().tolist()

        scraped_data = []
        for url in urls:
            url = f"https://{url}" if not urlparse(url).scheme else url
            response = requests_wrapper.get(url)
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string if soup.title else "No Title"
                description = soup.find("meta", {"name": "description"})
                description = description["content"] if description else "No Description"

                scraped_data.append({
                    "URL": url,
                    "Title": title,
                    "Description": description
                })
            else:
                scraped_data.append({
                    "URL": url,
                    "Error": "Failed to fetch"
                })

        # Save results
        result_file = os.path.join(app.config["DOWNLOADS_FOLDER"], f"scraped_results_{uuid.uuid4().hex}.csv")
        pd.DataFrame(scraped_data).to_csv(result_file, index=False)

        return jsonify({"message": "Scraping complete.", "result_file": result_file})
    except Exception as e:
        logging.error("Error during scraping: %s", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>", methods=["GET"])
@login_required
def download(filename):
    """Download processed file."""
    try:
        file_path = os.path.join(app.config["DOWNLOADS_FOLDER"], filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Main Entry Point
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use the PORT environment variable or default to 5000
    socketio.run(app, host="0.0.0.0", port=port)
