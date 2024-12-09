# clean_db.py
from app import create_app, db
from app.models import User

def check_and_clean_database():
    app = create_app()
    
    with app.app_context():
        print("\nCurrent users in database:")
        users = User.query.all()
        for user in users:
            print(f"""
User ID: {user.id}
Username: {user.username}
Email: {user.email}
Password Hash: {user.password[:50]}...
""")
        
        # Delete test user if exists
        test_user = User.query.filter_by(username='testuser').first()
        if test_user:
            db.session.delete(test_user)
            db.session.commit()
            print("\nTest user deleted.")
        else:
            print("\nNo test user found.")
        
        print("\nRemaining users:")
        users = User.query.all()
        for user in users:
            print(f"- {user.username} ({user.email})")

if __name__ == "__main__":
    check_and_clean_database()