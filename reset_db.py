# reset_db.py
from app import create_app, db
from app.models import User
from app.extensions import bcrypt
import logging
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def reset_database():
    app = create_app()
    
    with app.app_context():
        try:
            # Get database path
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            logger.info(f"Database path: {db_path}")
            
            # Remove existing database file
            if os.path.exists(db_path):
                os.remove(db_path)
                logger.info("Removed existing database file")
            
            # Create instance directory if it doesn't exist
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            logger.info("Ensured instance directory exists")
            
            # Create all tables
            logger.info("Creating database tables...")
            db.create_all()
            
            # Verify tables were created
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Created tables: {tables}")
            
            if 'users' not in tables:
                raise Exception("Users table was not created!")
            
            # Create admin user
            logger.info("Creating admin user...")
            admin = User(
                username="admin",
                email="admin@example.com",
                password=bcrypt.generate_password_hash("admin123").decode('utf-8'),
                is_admin=True
            )
            
            db.session.add(admin)
            db.session.commit()
            
            # Verify admin user was created
            admin_check = User.query.filter_by(username="admin").first()
            if admin_check:
                logger.info(f"Admin user created successfully (ID: {admin_check.id})")
                return True
            else:
                raise Exception("Failed to create admin user")
            
        except Exception as e:
            logger.error(f"Database reset error: {str(e)}")
            if 'db.session' in locals():
                db.session.rollback()
            return False

if __name__ == "__main__":
    success = reset_database()
    if success:
        print("\nDatabase reset and initialized successfully!")
    else:
        print("\nDatabase reset failed!")
        exit(1)