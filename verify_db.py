# verify_db.py
from app import create_app, db
from app.models import User
import logging
from sqlalchemy import inspect

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def verify_database():
    app = create_app()
    
    with app.app_context():
        try:
            # Check database URI
            logger.info(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            # Check tables
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Database tables: {tables}")
            
            if 'users' not in tables:
                logger.error("Users table not found in database!")
                return False
            
            # Check admin user
            admin = User.query.filter_by(username="admin").first()
            if admin:
                logger.info("Admin user exists:")
                logger.info(f"Username: {admin.username}")
                logger.info(f"Email: {admin.email}")
                logger.info(f"Is Admin: {admin.is_admin}")
                return True
            else:
                logger.error("Admin user not found")
                return False
                
        except Exception as e:
            logger.error(f"Verification error: {str(e)}")
            return False

if __name__ == "__main__":
    if verify_database():
        print("Database verification successful!")
    else:
        print("Database verification failed!")