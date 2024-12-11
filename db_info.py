from app import create_app, db
from sqlalchemy import inspect
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_detailed_schema():
    """Fetch detailed schema information for all tables."""
    app = create_app()
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            schema_details = {}
            
            # Fetch all table names
            table_names = inspector.get_table_names()
            if not table_names:
                logger.warning("No tables found in the database.")
                return schema_details
            
            # Gather column details for each table
            for table_name in table_names:
                logger.info(f"Inspecting table: {table_name}")
                columns = inspector.get_columns(table_name)
                schema_details[table_name] = [{
                    "name": col['name'],
                    "type": str(col['type']),
                    "nullable": col['nullable'],
                    "default": col.get('default')
                } for col in columns]
            
            return schema_details
        
        except Exception as e:
            logger.error(f"Error while fetching database schema: {e}", exc_info=True)
            return {}

if __name__ == "__main__":
    schema = get_detailed_schema()
    if schema:
        print("\nDatabase Schema:")
        for table, columns in schema.items():
            print(f"\nTable: {table}")
            for col in columns:
                print(f"  Column: {col['name']} ({col['type']}), Nullable: {col['nullable']}, Default: {col['default']}")
    else:
        print("No schema details available. Please check the database connection and tables.")
