# create_tables.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import logging
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create a minimal Flask application
app = Flask(__name__)

# Configure the database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "app.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Define the User model directly here
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    scrape_limit = db.Column(db.Integer, default=20000)
    scrapes_used = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())

def init_db():
    try:
        # Ensure instance directory exists
        os.makedirs('instance', exist_ok=True)
        
        # Remove existing database
        db_path = os.path.join(basedir, 'instance', 'app.db')
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info(f"Removed existing database: {db_path}")
        
        # Create all tables
        with app.app_context():
            logger.info("Creating database tables...")
            db.create_all()

            # Verify tables
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Created tables: {tables}")

            if 'users' not in tables:
                logger.error("Users table not created!")
                return False
            
            # Log column details of all tables
            for table in tables:
                columns = inspector.get_columns(table)
                logger.info(f"Table '{table}' structure:")
                for column in columns:
                    logger.info(f"  - {column['name']}: {column['type']}")

            # Create admin user
            from werkzeug.security import generate_password_hash
            admin = User(
                username="admin",
                email="admin@example.com",
                password=generate_password_hash("admin123"),
                is_admin=True
            )
            
            db.session.add(admin)
            db.session.commit()
            logger.info("Admin user created successfully.")
            
            # Verify admin user
            admin_check = User.query.filter_by(username="admin").first()
            if admin_check:
                logger.info(f"Admin user verified: ID={admin_check.id}, Email={admin_check.email}")
                return True
            else:
                logger.error("Admin user verification failed.")
                return False
                
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    if init_db():
        print("Database initialized successfully!")
    else:
        print("Database initialization failed!")
        exit(1)
