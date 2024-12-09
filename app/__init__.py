# app/__init__.py
from flask import Flask
from .config import Config
from .extensions import db, login_manager, bcrypt, socketio
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    with app.app_context():
        # Import models
        from .models import User

        # Create database tables
        db.create_all()

        # Register blueprints
        from .routes.auth import bp as auth_bp
        from .routes.main import bp as main_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(main_bp)

    return app