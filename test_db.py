# list_users.py
from app import create_app
from app.models import User
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def list_users():
    app = create_app()
    
    with app.app_context():
        try:
            # Fetch all users
            users = User.query.all()
            print("\nList of users:")
            for user in users:
                print(f"Username: {user.username}, Email: {user.email}, Admin: {user.is_admin}, Created At: {user.created_at}")
        except Exception as e:
            print(f"Error fetching users: {str(e)}")

if __name__ == "__main__":
    list_users()
