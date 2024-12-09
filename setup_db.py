# setup_db.py
from app import create_app, db
from app.models import User
from flask_bcrypt import Bcrypt
import logging
import os
from sqlalchemy import inspect

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def setup_database():
    try:
        # Create app
        app = create_app()
        bcrypt = Bcrypt(app)
        
        with app.app_context():
            # Get database path
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            logger.info(f"Database path: {db_path}")
            
            # Remove existing database
            if os.path.exists(db_path):
                os.remove(db_path)
                logger.info(f"Removed existing database: {db_path}")
            
            # Create tables
            db.create_all()
            
            # Verify tables
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Created tables: {tables}")
            
            if 'users' not in tables:
                raise Exception("Users table was not created!")
            
            # Create admin user
            admin = User(
                username="admin",
                email="admin@example.com",
                password=bcrypt.generate_password_hash("admin123").decode('utf-8'),
                is_admin=True
            )
            
            db.session.add(admin)
            db.session.commit()
            logger.info("Admin user created successfully")
            
    except Exception as e:
        logger.error(f"Database setup error: {str(e)}", exc_info=True)
