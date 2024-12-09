from app import create_app, db, bcrypt  # Import bcrypt here
from app.models import User
import logging
import os
from sqlalchemy import inspect

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def reset_db():
    """Reset the database by creating fresh tables."""
    try:
        app = create_app()
        
        with app.app_context():
            # Remove existing SQLite database
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            if os.path.exists(db_path):
                os.remove(db_path)
                logger.info(f"Removed existing database file: {db_path}")

            # Check metadata before table creation
            logger.debug(f"Metadata tables before creation: {db.metadata.tables.keys()}")

            # Create tables
            db.create_all()
            logger.debug("Tables created successfully.")

            # Check metadata after table creation
            logger.debug(f"Metadata tables after creation: {db.metadata.tables.keys()}")

            # Verify tables in the database
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.debug(f"Available tables: {tables}")

            if 'users' not in tables:
                raise RuntimeError("Users table not created.")
            
            # Create admin user
            hashed_password = bcrypt.generate_password_hash("admin123").decode('utf-8')
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
        app = create_app()
        with app.app_context():
            # Inspect database tables
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Available tables: {tables}")

            if 'users' not in tables:
                logger.error("Users table is missing.")
                return False
            
            # Verify admin user exists
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

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python manage.py [reset|verify]")
        sys.exit(1)
    
    command = sys.argv[1].lower()

    if command == "reset":
        print("Resetting database...")
        if reset_db():
            print("Database reset successfully!")
        else:
            print("Database reset failed!")
    elif command == "verify":
        print("Verifying database...")
        if verify_db():
            print("Database verification successful!")
        else:
            print("Database verification failed!")
    else:
        print(f"Unknown command: {command}")
