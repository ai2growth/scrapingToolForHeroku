# check_db.py
from app import create_app
from app.extensions import db
from app.models import User
from sqlalchemy import inspect, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_database():
    """Check database integrity and structure"""
    app = create_app()
    
    with app.app_context():
        try:
            # 1. Check connection
            logger.info("Checking database connection...")
            db.engine.connect()
            logger.info("✓ Database connection successful")

            # 2. Check tables
            logger.info("\nChecking database tables...")
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Found tables: {tables}")

            # 3. Check users table structure
            if 'users' in tables:
                columns = [c['name'] for c in inspector.get_columns('users')]
                logger.info(f"\nUsers table columns: {columns}")
                
                # Expected columns
                expected_columns = [
                    'id', 'username', 'email', 'password', 'reset_token',
                    'reset_token_expiry', 'is_admin', 'created_at',
                    'scrape_limit', 'scrapes_used'
                ]
                
                missing_columns = set(expected_columns) - set(columns)
                if missing_columns:
                    logger.error(f"Missing columns: {missing_columns}")
                else:
                    logger.info("✓ All expected columns present")

                # 4. Check for admin user
                admin = User.query.filter_by(username="admin").first()
                if admin:
                    logger.info("\nAdmin user exists:")
                    logger.info(f"Username: {admin.username}")
                    logger.info(f"Email: {admin.email}")
                    logger.info(f"Is Admin: {admin.is_admin}")
                else:
                    logger.warning("No admin user found")

                # 5. Check for any corrupt records
                try:
                    users = User.query.all()
                    logger.info(f"\nTotal users: {len(users)}")
                    for user in users:
                        # Try to access all fields to check for corruption
                        _ = user.id
                        _ = user.username
                        _ = user.email
                        _ = user.password
                        _ = user.is_admin
                except Exception as e:
                    logger.error(f"Corrupt user record found: {str(e)}")

                # 6. Check indexes
                indexes = inspector.get_indexes('users')
                logger.info(f"\nIndexes on users table: {indexes}")

            else:
                logger.error("Users table not found!")

            # 7. Check database constraints
            for table in tables:
                constraints = inspector.get_foreign_keys(table)
                if constraints:
                    logger.info(f"\nForeign key constraints for {table}: {constraints}")

            logger.info("\nDatabase check completed.")
            return True

        except Exception as e:
            logger.error(f"Error checking database: {str(e)}")
            return False

if __name__ == "__main__":
    if check_database():
        print("\nDatabase check completed successfully!")
    else:
        print("\nDatabase check failed!")