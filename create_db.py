# create_db.py
from app import create_app, db
from app.models import User
from flask_bcrypt import Bcrypt
import logging
from sqlalchemy import inspect

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def init_database():
    app = create_app()
    bcrypt = Bcrypt(app)
    
    with app.app_context():
        try:
            logger.info(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            # Drop all tables
            logger.info("Dropping all tables...")
            db.drop_all()
            
            # Create all tables
            logger.info("Creating all tables...")
            db.create_all()
            
            # Verify tables
            inspector = inspect(db.engine)
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
                password=bcrypt.generate_password_hash("admin123").decode('utf-8'),
                is_admin=True
            )
            
            db.session.add(admin)
            db.session.commit()
            logger.info("Admin user created successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}", exc_info=True)
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = init_database()
    if success:
        print("Database initialized successfully!")
    else:
        print("Database initialization failed!")
