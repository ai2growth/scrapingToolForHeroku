import os
from app import create_app, db
from app.models import User

def view_users():
    # Create the app instance
    app = create_app()

    with app.app_context():
        print("\nFetching users from database...")

        # Check if database file exists
        db_path = os.path.join('instance', 'smartscrape.db')
        if not os.path.exists(db_path):
            print(f"Database file not found at: {db_path}")
            return

        # Check if 'users' table exists
        inspector = db.inspect(db.engine)
        if 'users' not in inspector.get_table_names():  # Corrected table name
            print("Users table does not exist in the database!")
            print(f"Available tables: {inspector.get_table_names()}")
            return

        # Query users
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
Scrapes Used: {user.scrapes_used}
Scrape Limit: {user.scrape_limit}
Admin: {user.is_admin}
Created At: {user.created_at}
""")

if __name__ == "__main__":
    view_users()
