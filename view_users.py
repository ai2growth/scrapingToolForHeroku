# view_users.py
import os
from app import create_app, db
from app.models import User

def view_users():
    # Create the app instance
    app = create_app()
    
    with app.app_context():
        print("\nFetching users from database...")
        
        # Check if database file exists
        db_path = os.path.join('instance', 'app.db')
        if not os.path.exists(db_path):
            print(f"Database file not found at: {db_path}")
            return
            
        users = User.query.all()
        
        if not users:
            print("No users found in database!")
            return
            
        print(f"\nFound {len(users)} users:")
        print("-" * 50)
        
        for user in users:
            print(f"""
User ID: {user.id}
Username: {user.username}
Email: {user.email}
Password Hash: {user.password}
""")

if __name__ == "__main__":
    view_users()