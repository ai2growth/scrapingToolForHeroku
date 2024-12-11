# __init__.py
from flask import Flask
from .config import Config
from app.extensions import db, login_manager, bcrypt, mail, socketio 
import logging
from app.utils.memory import get_memory_usage

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.before_request
    def check_memory():
        memory_usage = get_memory_usage()
        if memory_usage > 500:  # 500MB threshold
            app.logger.warning(f"High memory usage: {memory_usage:.2f}MB")


    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
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

    # Add user loader
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))

    with app.app_context():
        # Import models
        from .models import User

        # Create database tables
        db.create_all()

        # Register blueprints
        try:
            from .routes.auth import bp as auth_bp
            from .routes.main import bp as main_bp

            # Register blueprints with URL prefixes if needed
            app.register_blueprint(auth_bp, url_prefix='/auth')
            app.register_blueprint(main_bp, url_prefix='/')

            # Log registered routes
            logger.debug("Registered routes:")
            for rule in app.url_map.iter_rules():
                logger.debug(f"{rule.endpoint}: {rule.rule}")

        except Exception as e:
            logger.error(f"Error registering blueprints: {str(e)}")
            raise

    return app
