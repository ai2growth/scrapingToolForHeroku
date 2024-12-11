
from concurrent.futures import ThreadPoolExecutor, as_completed
# Standard Library Imports
import os
import uuid
import json
import logging
import time
import threading
import io
from datetime import datetime, timedelta
import re

# Third-Party Library Imports
import requests
import pandas as pd
import openai
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    current_app,
    Blueprint,
    make_response
)
from flask_login import (
    LoginManager,
    login_required,
    current_user
    UserMixin  # Add this
)

from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Disable retries for requests and urllib3
import urllib3.util.retry
from requests.adapters import HTTPAdapter

# Attempt to import ScrapeOps client
try:
    from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
    SCRAPEOPS_ENABLED = True
except ImportError:
    SCRAPEOPS_ENABLED = False
    logging.warning("ScrapeOps not available. Using fallback scraping method.")

# Constants
SCRAPEOPS_API_KEY = '0139316f-c2f9-44ad-948c-f7a3439511c2'
CHUNK_SIZE = 10  # Example value; can be adjusted based on user tier
MAX_WORKERS = 10  # Example value; can be adjusted based on user tier

# Initialize Flask app
app = Flask(__name__)
app.config.from_object('app.config.Config')  # Ad

# Configure Flask app
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smartscrape.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.update(
    #SECRET_KEY='your_secret_key_here',
    UPLOAD_FOLDER=os.path.abspath(os.path.join(os.getcwd(), 'uploads')),
    DOWNLOADS_FOLDER=os.path.abspath(os.path.join(os.getcwd(), 'downloads')),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max file size
)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    scrapes_used = db.Column(db.Integer, default=0)
    scrape_limit = db.Column(db.Integer, default=20000)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def __repr__(self):
        return f'<User {self.username}>'

# Create all database tables
with app.app_context():
    db.create_all()

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOADS_FOLDER'], exist_ok=True)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Replace with your actual login view

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Define Blueprint
bp = Blueprint('main', __name__)

# Register Blueprint
app.register_blueprint(bp)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =========================
# Helper Functions & Classes
# =========================

def get_socketio():
    """Retrieve the shared SocketIO instance."""
    return current_app.extensions['socketio']

def get_scrapeops_client():
    """Initialize and return the ScrapeOps client."""
    if SCRAPEOPS_ENABLED:
        try:
            scrapeops_client = ScrapeOpsRequests(
                scrapeops_api_key=SCRAPEOPS_API_KEY
            )
            return scrapeops_client.RequestsWrapper()
        except Exception as e:
            logger.error(f"Error initializing ScrapeOps client: {str(e)}")
            return None
    return None

@bp.route('/get_scrape_count')
@login_required
def get_scrape_count():
    """Get current scrape count for user."""
    return jsonify({
        'scrapes_used': current_user.scrapes_used,
        'scrape_limit': current_user.scrape_limit
    })

def process_gpt_analysis(scraped_content, instructions, gpt_model):
    """Process GPT analysis in parallel with scraping."""
    try:
        if not scraped_content or scraped_content == "No data scraped":
            return "No content to analyze"
            
        prompt = f"""
        Analyze the following content based on the instructions:
        {instructions}
        Content: {scraped_content}
        """
        return get_openai_response(prompt, gpt_model)
    except Exception as e:
        logger.error(f"GPT analysis error: {str(e)}")
        return f"Analysis error: {str(e)}"

def get_openai_response(prompt, model="gpt-3.5-turbo"):
    """Fast OpenAI response with no retries."""
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a data analysis assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7,
            request_timeout=10
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return f"Analysis error: {str(e)}"

def handle_single_row_with_additional_columns(row, instructions, additional_columns, gpt_model, scrapeops_client=None):
    """Fast row processing with parallel analysis."""
    result = {
        'Websites': row.get('Websites', ''),
        'Scraped_Content': ''  # Initialize scraped content
    }
    
    try:
        # Single scrape attempt
        scrape_result = scrape_single_site(row.get('Websites', ''), scrapeops_client)
        
        if scrape_result.get('success'):
            result['Scraped_Content'] = scrape_result['scraped_content']
            
            # Process all analyses in parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {}
                
                # Submit main analysis
                if instructions:
                    prompt = f"Analyze: {scrape_result['scraped_content']}\nInstructions: {instructions}"
                    futures['Analysis'] = executor.submit(get_openai_response, prompt, gpt_model)
                
                # Submit additional analyses
                for col in additional_columns:
                    if col.get('name') and col.get('instructions'):
                        prompt = f"Analyze: {scrape_result['scraped_content']}\nInstructions: {col.get('instructions')}"
                        futures[col['name']] = executor.submit(get_openai_response, prompt, gpt_model)
                
                # Collect results
                for name, future in futures.items():
                    result[name] = future.result()
        else:
            result['Error'] = scrape_result.get('error', 'Failed to scrape')
            
    except Exception as e:
        result['Error'] = str(e)
    
    return result

def scrape_single_site(url, scrapeops_client=None):
    """Fast, single-attempt scraping with clean output."""
    try:
        if not url or pd.isna(url):
            return {"success": False, "error": "No URL provided"}

        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
        }

        # Single attempt, no retries
        response = scrapeops_client.get(url, headers=headers, timeout=10) if scrapeops_client else requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for tag in soup(['script', 'style', 'meta', 'noscript', 'header', 'footer', 'nav']):
                tag.decompose()

            # Get and clean text
            text = soup.get_text(separator=' ')
            # Fast text cleaning
            text = re.sub(r'[^\w\s.,!?-]', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            text = text[:1500]  # Limit to 1500 characters
            
            return {
                "success": True,
                "scraped_content": text.strip()
            }
        return {"success": False, "error": f"Status: {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}

from app import create_app, db
from app.models import User
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def update_user_scrape_count(current_user, total_rows):
    """
    Updates the scrape count for the given user.

    Args:
        current_user (User): The user object to update.
        total_rows (int): Number of rows to add to the scrape count.

    Returns:
        dict: Updated scrape count and scrape limit.
    """
    try:
        # Log the state before the update
        logger.info(f"Before update: User {current_user.username} has {current_user.scrapes_used} scrapes out of {current_user.scrape_limit}")

        # Update the user's scrape count
        current_user.scrapes_used += total_rows

        # Explicitly add the user to the session
        db.session.add(current_user)

        # Commit the changes to the database
        db.session.commit()

        # Refresh the user object to ensure it reflects the latest state
        db.session.refresh(current_user)

        # Log the updated state
        logger.info(f"After update: User {current_user.username} now has {current_user.scrapes_used} scrapes out of {current_user.scrape_limit}")
        logger.info("Database commit successful")

        return {
            'scrapes_used': current_user.scrapes_used,
            'scrape_limit': current_user.scrape_limit
        }

    except Exception as db_error:
        # Log and handle database errors
        logger.error(f"Database update error: {str(db_error)}", exc_info=True)

        # Rollback the session to maintain database integrity
        db.session.rollback()
        raise

if __name__ == "__main__":
    # Create the app and get app context
    app = create_app()
    with app.app_context():
        # Example: Fetch the user
        username = 'example_user'
        user = User.query.filter_by(username=username).first()

        if user:
            logger.info(f"User found: {user.username} (Scrapes Used: {user.scrapes_used}, Scrape Limit: {user.scrape_limit})")

            try:
                # Update the scrape count for the user
                total_rows_to_add = 50
                result = update_user_scrape_count(user, total_rows_to_add)
                logger.info(f"Updated user scrape count: {result}")
            except Exception as e:
                logger.error(f"Failed to update user scrape count: {str(e)}")
        else:
            logger.warning(f"User '{username}' not found in the database.")


# Configuration for Scraping
# =========================

class ScrapingConfig:
    TIMEOUT = 15  # Heroku-friendly timeout
    MAX_CONTENT_LENGTH = 1500  # ~300 words
    MAX_WORKERS = 20  # Conservative for Heroku
    
    # Rate limits (delay between requests)
    RATE_LIMITS = {
        'basic': 0.2,      # 200ms between requests
        'premium': 0.1,    # 100ms between requests
        'enterprise': 0.05 # 50ms between requests
    }
    
    # Worker counts by tier
    WORKER_LIMITS = {
        'basic': 10,       # Conservative
        'premium': 15,     # Moderate
        'enterprise': 20   # Maximum for Heroku
    }

def get_user_tier(user):
    """Determine user's service tier based on their settings."""
    if user.scrape_limit > 50000:
        return 'enterprise'
    elif user.scrape_limit > 20000:
        return 'premium'
    return 'basic'

def optimize_scraping_params(user):
    """Get optimized scraping parameters based on user's tier."""
    tier = get_user_tier(user)
    return {
        'delay': ScrapingConfig.RATE_LIMITS[tier],
        'max_workers': ScrapingConfig.WORKER_LIMITS[tier]
    }

def clean_results(results_list):
    """Clean up results by removing empty columns and normalizing data."""
    # Convert list of dictionaries to DataFrame
    df = pd.DataFrame(results_list)
    
    # Remove completely empty columns
    df = df.dropna(axis=1, how='all')
    
    # Remove columns where all values are empty strings
    df = df.loc[:, (df != '').any()]
    
    # Remove columns that only contain error messages or "No data scraped"
    error_patterns = ['Error:', 'No data scraped']
    for col in df.columns:
        if all(any(pattern in str(val) for pattern in error_patterns) 
               for val in df[col].dropna()):
            df = df.drop(columns=[col])
    
    return df

# =========================
# Routes
# =========================

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('user_dashboard.html')
@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    try:
        logger.info(f"Upload request received from user: {current_user.username if current_user else 'No user'}")
        logger.info(f"User authenticated: {current_user.is_authenticated if current_user else False}")

        if 'file' not in request.files:
            logger.error("No file part in request")
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        if not file or file.filename == '':
            logger.error("No selected file in request")
            return jsonify({"error": "No selected file"}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_suffix = uuid.uuid4().hex
            filename = f"{unique_suffix}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            try:
                file.save(file_path)
                logger.info(f"File saved successfully at: {file_path}")
            except Exception as e:
                logger.error(f"Failed to save file: {str(e)}")
                return jsonify({"error": "Failed to save the file. Please try again."}), 500

            try:
                df = pd.read_csv(file_path, low_memory=False)

                # Clean DataFrame
                df = df.loc[:, ~df.columns.str.contains('^Unnamed:')]
                df = df.dropna(axis=1, how='all')

                # Define acceptable column names
                acceptable_names = [
                    'websites', 'Websites',
                    'sites', 'Sites',
                    'domains', 'Domains',
                    'company_website',
                    'companywebsite'
                ]

                # Check if any acceptable column name exists
                found_column = None
                for name in acceptable_names:
                    if name in df.columns:
                        found_column = name
                        break

                if not found_column:
                    logger.error("No valid website column found")
                    return jsonify({
                        "error": "CSV file must contain a column named one of: 'Websites', 'Sites', 'Domains', 'company_website', or 'companywebsite'"
                    }), 400

                # Rename the found column to 'Websites' for consistency
                if found_column != 'Websites':
                    df = df.rename(columns={found_column: 'Websites'})

                available_columns = list(df.columns)
                logger.info(f"File upload successful. Columns: {available_columns}, Rows: {len(df)}")

                # Save the modified DataFrame back to CSV
                df.to_csv(file_path, index=False)

                return jsonify({
                    "filename": filename,
                    "file_path": file_path,
                    "columns": available_columns,
                    "row_count": len(df)
                }), 200

            except pd.errors.EmptyDataError:
                logger.error("Uploaded file is empty or invalid")
                return jsonify({"error": "Uploaded file is empty or invalid."}), 400

            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                return jsonify({"error": "Error processing the file. Please check the file format and try again."}), 500

        logger.error("Invalid file type uploaded")
        return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400

    except Exception as e:
        logger.error(f"Unexpected error during upload: {str(e)}")
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500
def allowed_file(filename):
    """Check if the file has an allowed extension."""
    ALLOWED_EXTENSIONS = {'csv'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/process', methods=['POST'])
@login_required
def process():
    """Handle processing with optimized multithreading and proper column ordering."""
    try:
        # Get SocketIO instance and incoming request data
        socketio_instance = get_socketio()
        data = request.json

        # Initialize ScrapeOps client and OpenAI API key
        scrapeops_client = get_scrapeops_client()
        openai.api_key = data.get('api_key')

        # Load CSV file and clean unnamed columns
        df = pd.read_csv(data['file_path'])
        df = df.loc[:, ~df.columns.str.contains('^Unnamed:')]

        # Apply row limit
        row_limit = min(
            int(data.get('row_limit', 20000)),
            current_user.scrape_limit - current_user.scrapes_used,
            20000
        )
        df = df.head(row_limit)

        total_rows = len(df)
        results = []
        processed = 0

        # Get optimized parameters for this user
        scraping_params = optimize_scraping_params(current_user)

        # Process rows using ThreadPoolExecutor with user-specific max_workers
        with ThreadPoolExecutor(max_workers=scraping_params['max_workers']) as executor:
            futures = {
                executor.submit(
                    handle_single_row_with_additional_columns,
                    row=row,
                    instructions=data.get('instructions'),
                    additional_columns=data.get('additional_columns', []),
                    gpt_model=data.get('gpt_model', 'gpt-3.5-turbo'),
                    scrapeops_client=scrapeops_client
                ): idx
                for idx, row in df.iterrows()
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    processed += 1

                    # Update progress
                    progress = int((processed / total_rows) * 100)
                    socketio_instance.emit('processing_progress', {
                        'current': processed,
                        'total': total_rows,
                        'progress': progress,
                        'status': 'processing'
                    }, namespace='/')

                except Exception as e:
                    logger.error(f"Error processing row: {str(e)}")
                    results.append({
                        'Websites': df.iloc[futures[future]]['Websites'],
                        'Error': str(e)
                    })

        # Create DataFrame from results
        results_df = pd.DataFrame(results)

        # Define column order
        column_order = ['Websites']

        # Add original columns
        original_cols = [col for col in df.columns if col != 'Websites']
        column_order.extend(original_cols)

        # Add specific columns in the desired order
        if 'Scraped_Content' in results_df.columns:
            column_order.append('Scraped_Content')

        if 'Analysis' in results_df.columns:
            column_order.append('Analysis')

        # Include additional analysis columns
        additional_columns = data.get('additional_columns', [])
        for column in additional_columns:
            if column.get('name') and column['name'] in results_df.columns:
                column_order.append(column['name'])

        if 'Error' in results_df.columns:
            column_order.append('Error')

        # Merge original and results DataFrames
        merged_df = pd.merge(
            df[['Websites'] + original_cols],
            results_df,
            on='Websites',
            how='left'
        )

        # Select only existing columns and drop empty ones
        final_cols = [col for col in column_order if col in merged_df.columns]
        final_df = merged_df[final_cols].dropna(axis=1, how='all')

        # Clean up remaining unnamed columns and replace NaN with empty string in string columns
        final_df = final_df.loc[:, ~final_df.columns.str.contains('^Unnamed:')]
        string_columns = final_df.select_dtypes(include=['object']).columns
        final_df[string_columns] = final_df[string_columns].fillna('')

        # Save DataFrame to CSV
        output = io.StringIO()
        final_df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)

        # Update user's scrape count
        logger.info(f"Updating scrape count for {current_user.username} - Adding {total_rows} scrapes")
        current_user.scrapes_used += total_rows
        db.session.commit()

        # Emit updated scrape count via Socket.IO
        socketio_instance.emit('scrape_count_updated', {
            'scrapes_used': current_user.scrapes_used,
            'scrape_limit': current_user.scrape_limit
        }, namespace='/')

        # Create response with CSV content
        response = make_response(output.getvalue())
        response.headers.update({
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename=analysis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        })

        logger.info(f"Processing complete. Processed {total_rows} rows with columns: {final_df.columns.tolist()}")
        return response

    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        try:
            socketio_instance.emit('processing_error', {'message': str(e)}, namespace='/')
        except Exception as emit_error:
            logger.error(f"Failed to emit error event: {str(emit_error)}")
        return jsonify({'error': str(e)}), 500
# Move this outside and unindent it (should be at the same level as your routes)
if __name__ == '__main__':
    socketio.run(app, debug=True)

