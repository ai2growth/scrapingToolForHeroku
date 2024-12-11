# config.py
import os
from pathlib import Path
from datetime import timedelta  # Add this import at the top

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'AqBFzxtJbkYMZm6GfsyF!#'
    
    # Session configuration (add these lines)
    SESSION_COOKIE_SECURE = True  # For HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    
    # Database configuration
    if os.environ.get('DATABASE_URL'):
        # Heroku database URL
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
        if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    else:
        # Local SQLite database
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(basedir, "instance", "app.db")}'
    
    # Ensure instance folder exists
    INSTANCE_PATH = os.path.join(basedir, 'instance')
    Path(INSTANCE_PATH).mkdir(exist_ok=True)
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File upload settings
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    DOWNLOADS_FOLDER = os.path.join(basedir, 'downloads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Create necessary directories
    Path(UPLOAD_FOLDER).mkdir(exist_ok=True)
    Path(DOWNLOADS_FOLDER).mkdir(exist_ok=True)