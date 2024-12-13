
#/init_db.py
from app import create_app, db
from app.models import User
from app.utils.password import PasswordHasher  # Update this import
import logging
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize the database with initial data."""
    app = create_app()

    with app.app_context():
        try:
            # Ensure instance directory exists
            os.makedirs('instance', exist_ok=True)
            logger.info(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

            # Drop existing tables
            logger.info("Dropping existing tables...")
            db.drop_all()

            # Create tables
            logger.info("Creating tables...")
            db.create_all()

            # Verify tables
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Created tables: {tables}")

            if 'users' not in tables:
                logger.error("Users table was not created!")
                return False

            # Create admin user
            logger.info("Creating admin user...")
            admin = User(
                username="admin",
                email="admin@example.com",
                password=PasswordHasher.generate_password_hash("admin123"),  # Updated
                is_admin=True,
                scrape_limit=50000,
                scrapes_used=0,
                last_reset_date=datetime.utcnow(),
                created_at=datetime.utcnow()
            )

            # Add and commit with error handling
            try:
                db.session.add(admin)
                db.session.commit()
                logger.info("Admin user committed to database")
            except Exception as commit_error:
                logger.error(f"Error committing admin user: {str(commit_error)}")
                db.session.rollback()
                return False

            # Verify admin user
            admin_check = User.query.filter_by(username="admin").first()
            if admin_check:
                logger.info("Admin user created successfully:")
                logger.info(f"Username: {admin_check.username}")
                logger.info(f"Email: {admin_check.email}")
                logger.info(f"Admin: {admin_check.is_admin}")
                logger.info(f"Scrape Limit: {admin_check.scrape_limit}")
                logger.info(f"Created At: {admin_check.created_at}")
                
                # Verify password hash
                test_password = "admin123"
                if PasswordHasher.check_password_hash(admin_check.password, test_password):
                    logger.info("Password verification successful")
                else:
                    logger.error("Password verification failed!")
                    return False
                
                return True
            else:
                logger.error("Failed to verify admin user creation!")
                return False

        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            if 'db.session' in locals():
                try:
                    db.session.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error during rollback: {str(rollback_error)}")
            return False

if __name__ == "__main__":
    try:
        success = init_database()
        if success:
            logger.info("Database initialized successfully!")
            exit(0)
        else:
            logger.error("Database initialization failed!")
            exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {str(e)}")
        exit(1)