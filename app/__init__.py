from flask import Flask
from app.extensions import db, bcrypt, login_manager, socketio, migrate
from app.config import Config

def create_app(config_class=Config):
    # Explicitly configure static folder and URL path
    app = Flask(
        __name__,
        static_folder="static",  # Path to static folder in the project
        static_url_path="/static"  # URL path for serving static files
    )
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    migrate.init_app(app, db)

    # Configure login manager
    login_manager.login_view = 'main.login'
    login_manager.login_message_category = 'info'

    # Register routes
    from app.routes.routes import bp
    app.register_blueprint(bp)

    return app
