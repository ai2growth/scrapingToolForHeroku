from flask import Flask
from flask.cli import FlaskGroup
from app import create_app
from app.extensions import db, PasswordHasher
from flask_migrate import Migrate
from app.models import User
import logging
import os
from sqlalchemy import inspect

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    with app.app_context():
        try:
            # Initialize migrations
            if not os.path.exists("migrations"):
                os.system("flask db init")
            
            # Create migration
            os.system("flask db migrate")
            
            # Apply migration
            os.system("flask db upgrade")
            print("Database migration completed successfully")
        except Exception as e:
            print(f"Error during database migration: {e}")@cli.command("reset")
def reset_command():
    """Reset the database."""
    print("Resetting database...")
    if reset_db():
        print("Database reset successfully!")
    else:
        print("Database reset failed!")

@cli.command("verify")
def verify_command():
    """Verify the database state."""
    print("Verifying database...")
    if verify_db():
        print("Database verification successful!")
    else:
        print("Database verification failed!")

if __name__ == "__main__":
    cli()