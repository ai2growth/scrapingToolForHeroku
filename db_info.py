from app import create_app, db
from sqlalchemy import inspect

def get_detailed_schema():
    """Fetch detailed schema information for all tables."""
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        schema_details = {}
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            schema_details[table_name] = [{
                "name": col['name'],
                "type": str(col['type']),
                "nullable": col['nullable'],
                "default": col.get('default')
            } for col in columns]
        return schema_details

if __name__ == "__main__":
    schema = get_detailed_schema()
    print("Database Schema:")
    for table, columns in schema.items():
        print(f"\nTable: {table}")
        for col in columns:
            print(f"  Column: {col['name']} ({col['type']}), Nullable: {col['nullable']}, Default: {col['default']}")
