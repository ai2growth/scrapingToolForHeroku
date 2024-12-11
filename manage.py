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

@cli.command()
def db():
    """Database migration commands"""
    pass

def reset_db():
    """Reset the database by creating fresh tables."""
    try:
        with app.app_context():
            # Drop all tables and recreate them
            db.drop_all()
            logger.info("Dropped all tables")

            # Create tables
            db.create_all()
            logger.debug("Tables created successfully.")

            # Verify tables in the database
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.debug(f"Available tables: {tables}")

            if 'users' not in tables:
                raise RuntimeError("Users table not created.")
            
            # Create admin user
            hashed_password = PasswordHasher.generate_password_hash("admin123")
            admin = User(
                username="admin",
                email="admin@example.com",
                password=hashed_password,
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            logger.info("Admin user created successfully.")
        
        return True

    except Exception as e:
        logger.error(f"Error during database reset: {str(e)}", exc_info=True)
        return False

def verify_db():
    """Verify the database state."""
    try:
        with app.app_context():
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Available tables: {tables}")

            if 'users' not in tables:
                logger.error("Users table is missing.")
                return False
            
            admin = User.query.filter_by(username="admin").first()
            if admin:
                logger.info("Admin user exists:")
                logger.info(f"Username: {admin.username}")
                logger.info(f"Email: {admin.email}")
                logger.info(f"Is Admin: {admin.is_admin}")
                return True
            else:
                logger.error("Admin user not found.")
                return False
    except Exception as e:
        logger.error(f"Error during database verification: {str(e)}", exc_info=True)
        return False

@cli.command("reset")
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