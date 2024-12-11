# check_users.py
from app import create_app
from app.models import User
from app.extensions import db

def check_users():
    app = create_app()
    with app.app_context():
        users = User.query.all()
        print(f"\nTotal users: {len(users)}")
        
        for user in users:
            print(f"\nUser ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Scrapes used: {user.scrapes_used}")
            print(f"Scrape limit: {user.scrape_limit}")
            print(f"Is admin: {user.is_admin}")
            print(f"Created at: {user.created_at}")

if __name__ == '__main__':
    check_users()