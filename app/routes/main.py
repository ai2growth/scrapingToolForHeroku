# main.py
# Python Standard Library
import os
import re
import io
import json
import uuid
import logging
import threading
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import text
from contextlib import contextmanager
# Flask and Extensions
from flask import (
    Flask,
    Blueprint,
    render_template,
    request,
    jsonify,
    current_app,
    make_response,
    redirect,
    url_for,
    flash
)
from flask_login import login_required, current_user, login_user, logout_user
from flask_mail import Message
from flask_socketio import emit, send
from werkzeug.utils import secure_filename

# Database and Models
from app.extensions import db, mail, socketio
from app.models import User
from app.forms import ForgotPasswordForm

# Third-Party Libraries
import pandas as pd
import requests
import openai
from bs4 import BeautifulSoup
import urllib3.util.retry
from requests.adapters import HTTPAdapter

# Local Application Imports
from app.utils.memory import (
    optimize_memory,
    check_memory_threshold,
    get_memory_usage
)

# Constants and Configuration
DEFAULT_NAMESPACE = '/'
SCRAPEOPS_API_KEY = '0139316f-c2f9-44ad-948c-f7a3439511c2'
MAX_WORKERS = 10
MEMORY_THRESHOLD = 500
CHUNK_SIZE = 100

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



# Initialize Blueprint
bp = Blueprint('main', __name__)

@socketio.on('connect')
def handle_connect():
    logger.info(f'Client connected: {request.sid}')
    emit('connection_confirmed', {'status': 'connected'})  # Use emit instead of socketio.emit

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f'Client disconnected: {request.sid}')


@socketio.on('start_processing')
def handle_start_processing(data):
    logger.info(f'Processing started for client: {request.sid}')
    logger.debug(f'Received data: {data}')

    try:
        # Log validation steps
        logger.debug("Validating input data...")
        if not data:
            logger.error("No data received")
            return {'status': 'error', 'error': 'No data received'}

        # Log required fields
        required_fields = ['file_path', 'api_key', 'instructions', 'gpt_model']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return {'status': 'error', 'error': f'Missing fields: {", ".join(missing_fields)}'}

        # Log file check
        logger.debug(f"Checking file path: {data['file_path']}")
        if not os.path.exists(data['file_path']):
            logger.error(f"File not found: {data['file_path']}")
            return {'status': 'error', 'error': 'File not found'}

        # Log processing start
        logger.info("Starting processing with parameters:")
        logger.info(f"Model: {data.get('gpt_model')}")
        logger.info(f"Row limit: {data.get('row_limit')}")
        logger.info(f"Additional columns: {len(data.get('additional_columns', []))}")

        # Your existing processing code...

    except Exception as e:
        logger.exception("Error in handle_start_processing")
        return {'status': 'error', 'error': str(e)}
@bp.route('/test-socket')
def test_socket():
    """Test Socket.IO connection."""
    try:
        socketio.emit('test', {'data': 'Test message'}, namespace='/')
        return jsonify({
            'status': 'success',
            'message': 'Socket.IO test message sent'
        })
    except Exception as e:
        logger.error(f"Socket.IO test failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Add a helper function to validate the process request
def validate_process_request(data):
    """Validate the incoming process request data."""
    errors = []
    
    if not data.get('file_path'):
        errors.append('No file path provided')
    elif not os.path.exists(data['file_path']):
        errors.append('File does not exist')
        
    if not data.get('api_key'):
        errors.append('No API key provided')
        
    if not data.get('instructions'):
        errors.append('No instructions provided')
        
    return errors



@socketio.on_error_default
def default_error_handler(e):
    logger.error(f'Socket.IO error: {str(e)}')
    emit('error', {'error': str(e)})

# Then your error handlers
@bp.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# Attempt to import ScrapeOps client
try:
    from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
    SCRAPEOPS_ENABLED = True
except ImportError:
    SCRAPEOPS_ENABLED = False
    logging.warning("ScrapeOps not available. Using fallback scraping method.")

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

@bp.route('/test-scrape')
@login_required
def test_scrape():
    """Test endpoint to verify scraping functionality."""
    try:
        # Test URL
        test_url = "https://example.com"
        
        # Test ScrapeOps
        scrapeops_client = get_scrapeops_client()
        scrapeops_result = None
        if scrapeops_client:
            try:
                scrapeops_result = scrape_single_site(test_url, scrapeops_client)
            except Exception as e:
                scrapeops_result = f"ScrapeOps Error: {str(e)}"

        # Test direct request
        direct_result = scrape_single_site(test_url)

        return jsonify({
            'status': 'test complete',
            'scrapeops_enabled': SCRAPEOPS_ENABLED,
            'scrapeops_result': scrapeops_result,
            'direct_result': direct_result,
            'memory_usage': get_memory_usage()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        })
    
@bp.route('/get_scrape_count')
@login_required  # Make sure this decorator is here
def get_scrape_count():
    """Get current scrape count for user."""
    try:
        if not current_user.is_authenticated:
            return jsonify({'error': 'Not authenticated'}), 401
            
        return jsonify({
            'scrapes_used': current_user.scrapes_used,
            'scrape_limit': current_user.scrape_limit
        })
    except Exception as e:
        logger.error(f"Error fetching scrape count: {str(e)}")
        return jsonify({'error': 'Failed to fetch scrape count'}), 500
    

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    ALLOWED_EXTENSIONS = {'csv'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



def log_memory_usage(message=""):
    """Log current memory usage with optional message."""
    try:
        memory_usage = get_memory_usage()
        logger.info(f"Memory usage {message}: {memory_usage:.2f}MB")
    except Exception as e:
        logger.error(f"Failed to log memory usage: {str(e)}")

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

def handle_single_row_with_additional_columns(row, instructions, additional_columns, gpt_model):
    """Process a single row with any additional column analyses."""
    result = {}
    
    try:
        # Scrape the website
        scrape_result = scrape_single_site(row.get('Websites', ''))
        
        if scrape_result.get('success'):
            # Store the scraped content
            result['Scraped_Content'] = scrape_result['scraped_content']
            
            # Perform main analysis
            if instructions:
                analysis_prompt = f"Analyze this company based on the following instructions:\n{instructions}\n\nContent: {scrape_result['scraped_content']}"
                result['Analysis'] = get_openai_response(analysis_prompt, gpt_model)
            
            # Process additional columns - Add logging to debug
            logger.info(f"Processing additional columns: {additional_columns}")
            for col in additional_columns:
                if col.get('name') and col.get('instructions'):
                    logger.info(f"Processing additional column: {col['name']}")
                    col_prompt = f"Analyze this company based on the following instructions:\n{col['instructions']}\n\nContent: {scrape_result['scraped_content']}"
                    result[col['name']] = get_openai_response(col_prompt, gpt_model)
                    logger.info(f"Added analysis for column {col['name']}")
        else:
            result['Scraped_Content'] = ''
            result['Analysis'] = f"Scraping failed: {scrape_result.get('error', 'Unknown error')}"
            
    except Exception as e:
        logger.error(f"Error processing row: {str(e)}")
        result['Error'] = str(e)
    
    logger.info(f"Final result keys: {result.keys()}")
    return result


def scrape_single_site(url, scrapeops_client=None):
    """Optimized scraping function with better error handling."""
    try:
        if not url or pd.isna(url):
            logger.debug(f"Invalid URL provided: {url}")
            return {"success": False, "error": "No URL provided"}

        # Clean and validate URL
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        logger.debug(f"Attempting to scrape: {url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Use ScrapeOps if available
        if scrapeops_client and SCRAPEOPS_ENABLED:
            logger.debug("Using ScrapeOps client")
            response = scrapeops_client.get(url, headers=headers, timeout=10)
        else:
            logger.debug("Using direct requests")
            response = requests.get(url, headers=headers, timeout=10)

        logger.debug(f"Response status code: {response.status_code}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for tag in soup(['script', 'style', 'meta', 'noscript', 'header', 'footer', 'nav']):
                tag.decompose()

            # Get text with minimal processing
            text = ' '.join(soup.stripped_strings)
            text = text[:1500]  # Limit to 1500 characters
            
            logger.debug(f"Successfully scraped {len(text)} characters")
            
            return {
                "success": True,
                "scraped_content": text.strip(),
                "status_code": response.status_code
            }
            
        logger.warning(f"Failed to scrape {url} - Status code: {response.status_code}")
        return {
            "success": False,
            "error": f"HTTP Status: {response.status_code}",
            "status_code": response.status_code
        }

    except requests.Timeout:
        logger.error(f"Timeout while scraping {url}")
        return {"success": False, "error": "Request timed out"}
    except requests.RequestException as e:
        logger.error(f"Request error while scraping {url}: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error while scraping {url}: {str(e)}")
        return {"success": False, "error": str(e)}

def update_user_scrape_count(current_user, total_rows):
    """Updates the scrape count for the given user."""
    try:
        # Log the state before the update
        logger.info(f"Before update: User {current_user.username} has {current_user.scrapes_used} scrapes")

        # Update the user's scrape count
        current_user.scrapes_used += total_rows

        # Use the existing db instance from extensions
        from app.extensions import db
        
        # Commit the changes
        db.session.commit()

        logger.info(f"After update: User {current_user.username} now has {current_user.scrapes_used} scrapes")

        return {
            'scrapes_used': current_user.scrapes_used,
            'scrape_limit': current_user.scrape_limit
        }

    except Exception as e:
        logger.error(f"Error updating scrape count: {str(e)}")
        from app.extensions import db
        db.session.rollback()
        raise

def process_chunk(chunk, data, socket_id):
    """Process a chunk of data with progress updates."""
    try:
        total_rows = len(chunk)
        chunk_results = []
        
        for index, row in chunk.iterrows():
            # Emit progress for this chunk
            progress = int((index / total_rows) * 100)
            socketio.emit('processing_progress', {
                'current': index,
                'total': total_rows,
                'progress': progress,
                'status': 'processing chunk'
            }, room=socket_id)
            
            result = handle_single_row_with_additional_columns(
                row=row,
                instructions=data.get('instructions'),
                additional_columns=data.get('additional_columns', []),
                gpt_model=data.get('gpt_model', 'gpt-3.5-turbo')
            )
            chunk_results.append(result)
            
        return chunk_results
    except Exception as e:
        logger.error(f"Chunk processing error: {str(e)}")
        return []

# Configuration for Scraping
# =========================

class ScrapingConfig:
    TIMEOUT = 15  # Heroku-friendly timeout
    MAX_CONTENT_LENGTH = 1500  # ~300 words
    MAX_WORKERS = min(32, (os.cpu_count() or 1) * 4)  # Conservative for Heroku
    
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

@bp.route('/test-db')
def test_db():
    """Test database connection directly."""
    logger.info("Testing database connection")
    try:
        engine = db.get_engine()
        with engine.connect() as conn:
            result = conn.execute(text('SELECT 1')).scalar()
            logger.info(f"Database test successful: {result}")
            return jsonify({
                'status': 'success',
                'connection': 'valid',
                'result': result
            })
    except Exception as e:
        logger.error(f"Database test failed: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_type': type(e).__name__
        }), 500

@bp.route('/env-check')
def env_check():
    """Check environment variables."""
    logger.info("Checking environment variables")
    return jsonify({
        'database_url': bool(current_app.config.get('SQLALCHEMY_DATABASE_URI')),
        'debug': current_app.config.get('DEBUG'),
        'testing': current_app.config.get('TESTING'),
        'env': current_app.config.get('ENV')
    })

# =========================
# Database Utilities
# =========================

@contextmanager
def get_db_session():
    """Provide a transactional scope around a series of operations."""
    session = db.session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


@bp.route('/health')
def health_check():
    """Health check endpoint for Render."""
    logger.info("Starting health check")
    try:
        # Test database
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        
        # Get registered routes
        routes = []
        for rule in current_app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'path': rule.rule
            })
        
        # Get environment info
        env_info = {
            'database_url': bool(current_app.config.get('SQLALCHEMY_DATABASE_URI')),
            'debug': current_app.config.get('DEBUG'),
            'testing': current_app.config.get('TESTING'),
            'env': current_app.config.get('ENV')
        }
        
        response = {
            'status': 'healthy',
            'message': 'Application is running',
            'database': 'connected',
            'timestamp': datetime.now().isoformat(),
            'routes': routes,
            'environment': env_info,
            'blueprint_routes': [r.endpoint for r in current_app.url_map.iter_rules() if r.endpoint.startswith('main')]
        }
        
        logger.info("Health check successful")
        return jsonify(response), 200
            
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'unhealthy',
            'message': str(e),
            'error_type': type(e).__name__,
            'timestamp': datetime.now().isoformat()
        }), 500


@bp.route('/routes')
def list_routes():
    """List all registered routes."""
    routes = []
    for rule in current_app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': rule.rule
        })
    return jsonify(routes)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('user_dashboard.html')


@bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

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
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
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

if __name__ == '__main__':
    try:
        from app import create_app
        app = create_app()
        logger.info("Starting application with SocketIO")
        socketio.init_app(app)
        socketio.run(app, 
                    debug=True,
                    host='0.0.0.0',
                    port=int(os.environ.get('PORT', 5000)),
                    use_reloader=True)
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise
