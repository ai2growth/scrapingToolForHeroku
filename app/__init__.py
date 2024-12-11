from flask import Flask
from .config import Config
from app.extensions import db, login_manager, mail, socketio
import logging
from app.utils.memory import get_memory_usage

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Add memory usage check before each request
    @app.before_request
    def check_memory():
        memory_usage = get_memory_usage()
        if memory_usage > 500:  # 500MB threshold
            app.logger.warning(f"High memory usage: {memory_usage:.2f}MB")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        logger=True,
        engineio_logger=True
    )

    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Register blueprints
    with app.app_context():
        try:
            from app.routes.auth import bp as auth_bp
            from app.routes.main import bp as main_bp

            app.register_blueprint(auth_bp, url_prefix='/auth')
            app.register_blueprint(main_bp, url_prefix='/')

            logger.info("Blueprints registered successfully.")

        except Exception as e:
            logger.error(f"Error registering blueprints: {str(e)}")
            raise

    return app
