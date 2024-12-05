from app import create_app
from app.extensions import db, bcrypt
from app.models import User
from datetime import datetime
import pytz
import os

def init_db():
    app = create_app()
    
    with app.app_context():
        # Drop all tables
        db.drop_all()
        
        # Create all tables
        db.create_all()
        
        # Create admin user if it doesn't exist
        admin_email = "admin@example.com"
        admin = User(
            username="admin",
            email=admin_email,
            password=bcrypt.generate_password_hash("admin_password").decode("utf-8"),
            is_admin=True,
            scrape_limit=50000,  # Higher limit for admin
            scrapes_used=0,
            created_at=datetime.now(pytz.UTC)
        )
        
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")

if __name__ == "__main__":
    # Delete existing database file if it exists
    db_file = "instance/users.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"Deleted existing database: {db_file}")
    
    init_db()