# app.py
import os
from flask import Flask
import logging
from app.extensions import db, login_manager, bcrypt  # Import extensions

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)

    # Instance and database setup
    instance_path = os.path.join(os.path.dirname(__file__), 'instance')
    app.instance_path = instance_path
    os.makedirs(instance_path, exist_ok=True)

    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(instance_path, 'app.db')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'dev-secret-key'

    logger.debug(f"Database path: {app.config['SQLALCHEMY_DATABASE_URI']}")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    # Configure login behavior
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Register blueprints
    with app.app_context():
        from app.routes.main import bp as main_bp
        from app.routes.auth import bp as auth_bp

        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp, url_prefix="/auth")

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
