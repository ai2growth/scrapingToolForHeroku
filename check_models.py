# check_models.py
from app import create_app, db
from app.models import User
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def check_models():
    app = create_app()
    with app.app_context():
        # Check if User model is registered
        logger.info(f"SQLAlchemy metadata tables: {db.metadata.tables.keys()}")
        logger.info(f"User model tablename: {User.__tablename__}")
        logger.info(f"User model table in metadata: {'users' in db.metadata.tables}")
        
        # Print model details
        for mapper in db.Model.registry.mappers:
            logger.info(f"Mapped model: {mapper.class_.__name__}")
            for column in mapper.columns:
                logger.info(f"  - {column.name}: {column.type}")

if __name__ == "__main__":
    check_models()