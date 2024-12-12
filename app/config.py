import os
from pathlib import Path
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'AqBFzxtJbkYMZm6GfsyF!#'
    
    # Session configuration
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
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Ensure instance folder exists
    INSTANCE_PATH = os.path.join(basedir, 'instance')
    Path(INSTANCE_PATH).mkdir(exist_ok=True)
    
    # File upload settings
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    DOWNLOADS_FOLDER = os.path.join(basedir, 'downloads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Create necessary directories
    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    Path(DOWNLOADS_FOLDER).mkdir(parents=True, exist_ok=True)

    # Other optional configurations
    DEBUG = os.environ.get('DEBUG', 'False').lower() in ['true', '1']
    TESTING = os.environ.get('TESTING', 'False').lower() in ['true', '1']

    # Gmail Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', True)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')

        # ... other settings ...
    SQLALCHEMY_POOL_SIZE = 20
    SQLALCHEMY_MAX_OVERFLOW = 10
    SQLALCHEMY_POOL_TIMEOUT = 30
    SQLALCHEMY_POOL_RECYCLE = 1800
    MEMORY_THRESHOLD = 450  # MB
    GC_THRESHOLD = 400
