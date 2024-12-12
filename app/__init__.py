#/app/__init__.py
import logging
from flask import Flask
from flask_migrate import Migrate
from .extensions import db, login_manager, bcrypt, socketio
import logging
from app.utils.memory import get_memory_usage

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask-Migrate
migrate = Migrate()
def create_app():
    logger.debug("Starting application creation")
    app = Flask(__name__)
    
    logger.debug("Loading configuration")
    app.config.from_object('config.Config')

    # Initialize extensions
    logger.debug("Initializing database")
    try:
        db.init_app(app)
        logger.debug("Database initialization successful")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise

    logger.debug("Initializing Flask-Migrate")
    try:
        migrate.init_app(app, db)
        logger.debug("Flask-Migrate initialization successful")
    except Exception as e:
        logger.error(f"Flask-Migrate initialization failed: {str(e)}")
        raise

    logger.debug("Initializing login manager")
    login_manager.init_app(app)
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
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        logger.debug("Creating database tables")
        try:
            db.create_all()
            logger.debug("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise

        # Register blueprints
        try:
            logger.debug("Registering blueprints")
            from .routes.auth import bp as auth_bp
            from .routes.main import bp as main_bp

            app.register_blueprint(auth_bp, url_prefix='/auth')
            app.register_blueprint(main_bp, url_prefix='/')

            logger.debug("Registered routes:")
            for rule in app.url_map.iter_rules():
                logger.debug(f"{rule.endpoint}: {rule.rule}")

        except Exception as e:
            logger.error(f"Error registering blueprints: {str(e)}")
            raise

    logger.info("Application creation completed successfully")
    return app