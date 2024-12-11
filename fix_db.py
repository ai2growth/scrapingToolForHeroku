#fix_db
from app import create_app
from app.extensions import db
from app.models import User

def fix_database():
    app = create_app()
    
    with app.app_context():
        # Drop both tables if they exist
        db.engine.execute('DROP TABLE IF EXISTS users')
        db.engine.execute('DROP TABLE IF EXISTS user')
        
        # Create tables fresh
        db.create_all()
        
        # Verify the fix
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"\nCurrent tables: {tables}")
        
        # Show columns for the users table
        for table in tables:
            print(f"\nColumns in {table}:")
            columns = inspector.get_columns(table)
            for column in columns:
                print(f"  - {column['name']}: {column['type']}")

if __name__ == '__main__':
    fix_database()