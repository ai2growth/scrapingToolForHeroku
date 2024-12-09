# app/database.py
from app.extensions import db
from app.models import User  # Import all your models here
import logging

logger = logging.getLogger(__name__)

def init_db(app):
    """Initialize the database and create all tables"""
    with app.app_context():
        try:
            logger.info("Creating all database tables...")
            # Ensure all models are imported
            logger.info(f"Registered models: {db.Model.registry.mappers}")
            
            # Create tables
            db.create_all()
            
            # Verify tables were created
            tables = db.engine.table_names()
            logger.info(f"Created tables: {tables}")
            
            return True
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}", exc_info=True)
            return False