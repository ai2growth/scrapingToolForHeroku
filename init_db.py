from app import create_app, db
from app.models import User
from app.extensions import bcrypt
import logging
import os
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def init_database():
    app = create_app()

    with app.app_context():
        try:
            # Ensure instance directory exists
            os.makedirs('instance', exist_ok=True)

            # Log database configuration
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

            # Create admin user with all new fields
            logger.info("Creating admin user...")
            admin = User(
                username="admin",
                email="admin@example.com",
                password=bcrypt.generate_password_hash("admin123").decode('utf-8'),
                is_admin=True,
                scrape_limit=50000,  # Higher limit for admin
                scrapes_used=0,
                last_reset_date=datetime.utcnow(),
                created_at=datetime.utcnow()
            )

            db.session.add(admin)
            db.session.commit()

            # Verify admin user was created
            admin_check = User.query.filter_by(username="admin").first()
            if admin_check:
                logger.info("Admin user created successfully with:")
                logger.info(f"Username: {admin_check.username}")
                logger.info(f"Email: {admin_check.email}")
                logger.info(f"Admin: {admin_check.is_admin}")
                logger.info(f"Scrape Limit: {admin_check.scrape_limit}")
                logger.info(f"Created At: {admin_check.created_at}")
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
    success = init_database()
    if success:
        print("Database initialized successfully!")
    else:
        print("Database initialization failed!")
        exit(1)