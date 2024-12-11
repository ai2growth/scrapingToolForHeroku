#checkconfig.py

from app import create_app, db
from app.models import User

def check_database_config():
    app = create_app()
    with app.app_context():
        print(f"\nDatabase URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"Database Tables: {db.engine.table_names()}")
        
        # Check User model configuration
        print(f"\nUser Model Table Name: {User.__tablename__}")
        
        # Check current users
        users = User.query.all()
        print(f"\nCurrent Users:")
        for user in users:
            print(f"Username: {user.username}, Scrapes Used: {user.scrapes_used}")

if __name__ == "__main__":
    check_database_config()