# diagnose_db.py
from app import create_app, db
from app.models import User
from sqlalchemy import inspect
import logging
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def diagnose_database():
    app = create_app()
    
    with app.app_context():
        try:
            # Check configuration
            logger.info("Checking configuration...")
            logger.info(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
            logger.info(f"Debug mode: {app.debug}")
            
            # Check database file
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            logger.info(f"Database path: {db_path}")
            logger.info(f"Database file exists: {os.path.exists(db_path)}")
            
            # Check SQLAlchemy setup
            logger.info("\nChecking SQLAlchemy setup...")
            logger.info(f"Registered models: {db.Model.registry.mappers}")
            logger.info(f"Metadata tables: {db.metadata.tables.keys()}")
            
            # Check database tables
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"\nDatabase tables: {tables}")
            
            # Check User model
            logger.info("\nChecking User model...")
            logger.info(f"User tablename: {User.__tablename__}")
            logger.info(f"User table columns:")
            for column in User.__table__.columns:
                logger.info(f"  - {column.name}: {column.type}")
            
            return True
            
        except Exception as e:
            logger.error(f"Diagnostic error: {str(e)}", exc_info=True)
            return False

if __name__ == "__main__":
    if diagnose_database():
        print("Diagnostics completed successfully!")
    else:
        print("Diagnostics failed!")
        exit(1)