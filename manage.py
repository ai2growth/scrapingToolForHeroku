import os
import logging
from flask import Flask
from flask.cli import FlaskGroup
from app import create_app
from app.extensions import db, PasswordHasher
from flask_migrate import Migrate
from app.models import User
from sqlalchemy import inspect

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create CLI app
logger.debug("Setting up Flask app and CLI commands")
def create_cli_app():
    app = create_app()
    return app

app = create_cli_app()
migrate = Migrate(app, db)

# Create CLI group
cli = FlaskGroup(create_app=create_cli_app)

@cli.command("db")
def db_command():
    """Database migration commands"""
    logger.debug("Attempting to run db command")
    try:
        with app.app_context():
            logger.debug("Inside app context")

            # Initialize migrations
            if not os.path.exists("migrations"):
                logger.debug("Creating migrations directory")
                os.system("flask db init")

            # Create migration
            logger.debug("Running db migrate")
            os.system("flask db migrate")

            # Apply migration
            logger.debug("Running db upgrade")
            os.system("flask db upgrade")

            logger.debug("Database migration completed successfully")
    except Exception as e:
        logger.error(f"Error during database migration: {e}", exc_info=True)

@cli.command("reset")
def reset_command():
    """Reset the database."""
    logger.debug("Resetting database...")
    try:
        if reset_db():
            logger.debug("Database reset successfully")
            print("Database reset successfully!")
        else:
            logger.debug("Database reset failed")
            print("Database reset failed!")
    except Exception as e:
        logger.error(f"Error during database reset: {e}", exc_info=True)

@cli.command("verify")
def verify_command():
    """Verify the database state."""
    logger.debug("Verifying database...")
    try:
        if verify_db():
            logger.debug("Database verification successful")
            print("Database verification successful!")
        else:
            logger.debug("Database verification failed")
            print("Database verification failed!")
    except Exception as e:
        logger.error(f"Error during database verification: {e}", exc_info=True)

if __name__ == "__main__":
    logger.debug("Starting CLI")
    cli()