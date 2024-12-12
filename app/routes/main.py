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

# Constants and Configuration
DEFAULT_NAMESPACE = '/'
SCRAPEOPS_API_KEY = '0139316f-c2f9-44ad-948c-f7a3439511c2'
MAX_WORKERS = 10
MEMORY_THRESHOLD = 500
CHUNK_SIZE = 100

# Initialize Blueprint
bp = Blueprint('main', __name__)

@socketio.on('connect')
def handle_connect():
    logger.info(f'Client connected: {request.sid}')
    emit('connection_confirmed', {'status': 'connected'})  # Use emit instead of socketio.emit

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f'Client disconnected: {request.sid}')

@socketio.on('start_processing', namespace='/')
def handle_start_processing(data):
    logger.info(f'Processing started for client: {request.sid}')
    logger.debug(f'Received data: {data}')
    
    try:
        # Validate the data
        if not data.get('file_path') or not data.get('api_key') or not data.get('instructions'):
            raise ValueError("Missing required fields")

        # Initialize OpenAI
        openai.api_key = data['api_key']
        
        # Read and process the CSV
        original_df = pd.read_csv(data['file_path'])
        
        # Remove completely empty columns
        df = original_df.dropna(axis=1, how='all')
        
        # Apply row limit if specified
        if data.get('row_limit'):
            df = df.head(int(data['row_limit']))
            
        total_rows = len(df)
        
        # Update scrape count
        try:
            result = update_user_scrape_count(current_user, total_rows)
            emit('scrape_count_updated', {
                'scrapes_used': result['scrapes_used'],
                'scrape_limit': result['scrape_limit']
            }, namespace='/')
            logger.info(f"Scrape count updated: {result}")
        except Exception as e:
            logger.error(f"Failed to update scrape count: {str(e)}")
            raise

        # Process the data
        results = []
        
        # Emit initial progress
        emit('processing_progress', {
            'current': 0,
            'total': total_rows,
            'status': 'processing'
        }, namespace='/')

        # Process each row
        for index, row in df.iterrows():
            try:
                # Get the analysis result
                analysis_result = handle_single_row_with_additional_columns(
                    row=row,
                    instructions=data['instructions'],
                    additional_columns=data.get('additional_columns', []),
                    gpt_model=data.get('gpt_model', 'gpt-3.5-turbo')
                )
                
                # Combine original row data with analysis results
                combined_result = {col: row[col] for col in df.columns}
                combined_result.update(analysis_result)
                
                results.append(combined_result)
                
                # Emit progress
                emit('processing_progress', {
                    'current': index + 1,
                    'total': total_rows,
                    'status': 'processing'
                }, namespace='/')
                
            except Exception as row_error:
                logger.error(f'Error processing row {index}: {str(row_error)}')
                # Include original row data even if analysis fails
                error_result = {col: row[col] for col in df.columns}
                error_result['Error'] = str(row_error)
                results.append(error_result)

        # Create final DataFrame
        results_df = pd.DataFrame(results)
        
        # Ensure consistent column order
        # Start with original columns
        column_order = [col for col in df.columns if col in results_df.columns]
        
        # Add analysis columns
        analysis_columns = ['Scraped_Content', 'Analysis']
        column_order.extend([col for col in analysis_columns if col in results_df.columns])
        
        # Add additional analysis columns
        if data.get('additional_columns'):
            for col in data['additional_columns']:
                if col.get('name') and col['name'] in results_df.columns:
                    column_order.append(col['name'])
        
        # Add error column if it exists
        if 'Error' in results_df.columns:
            column_order.append('Error')
            
        # Reorder columns
        results_df = results_df[column_order]
        
        # Clean up the DataFrame
        # Replace NaN with empty string for string columns
        string_columns = results_df.select_dtypes(include=['object']).columns
        results_df[string_columns] = results_df[string_columns].fillna('')
        
        # Convert to CSV string
        output = io.StringIO()
        results_df.to_csv(output, index=False)
        csv_data = output.getvalue()
        
        logger.info(f"Processing complete. Final columns: {results_df.columns.tolist()}")
        
        # Emit completion with CSV data
        emit('processing_complete', {
            'status': 'complete',
            'message': 'Processing completed successfully',
            'csv_data': csv_data
        }, namespace='/')
        
        return True
        
    except Exception as e:
        logger.error(f'Processing error: {str(e)}')
        emit('processing_error', {
            'error': str(e),
            'message': 'An error occurred during processing'
        }, namespace='/')
        return False

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

# Constants
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
@bp.route('/health')
def health_check():
    """Health check endpoint for Render."""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        db.session.commit()
        
        return jsonify({
            'status': 'healthy',
            'message': 'Application is running',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500



@bp.route('/process', methods=['POST'])
@login_required
def process():
    """Handle processing with real-time updates via Socket.IO."""
    try:
        # Log memory usage at the start
        log_memory_usage("before processing")

        # Get SocketIO instance and incoming request data
        socketio_instance = get_socketio()
        data = request.json

        # Emit start event
        socketio_instance.emit('processing_progress', {
            'current': 0,
            'total': 100,
            'status': 'starting'
        })

        # Memory check and optimization
        if not check_memory_threshold(threshold_mb=500):
            optimize_memory()
            log_memory_usage("after memory optimization")

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

        # Log memory after loading the data
        log_memory_usage("after loading CSV")

        # Get optimized parameters for this user
        scraping_params = optimize_scraping_params(current_user)

        # Process in chunks to manage memory
        chunk_size = 50
        for i in range(0, total_rows, chunk_size):
            chunk = df[i:i + chunk_size]

            # Emit progress before processing chunk
            current_progress = int((i / total_rows) * 100)
            socketio_instance.emit('processing_progress', {
                'current': i,
                'total': total_rows,
                'progress': current_progress,
                'status': 'processing'
            })

            # Process chunk with ThreadPoolExecutor
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
                    for idx, row in chunk.iterrows()
                }

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                        processed += 1

                        # Update progress more frequently
                        if processed % 5 == 0:  # Update every 5 rows
                            progress = int((processed / total_rows) * 100)
                            socketio_instance.emit('processing_progress', {
                                'current': processed,
                                'total': total_rows,
                                'progress': progress,
                                'status': 'processing'
                            })

                    except Exception as e:
                        logger.error(f"Error processing row: {str(e)}")
                        results.append({
                            'Websites': df.iloc[futures[future]]['Websites'],
                            'Error': str(e)
                        })

            # Optimize memory after each chunk
            if i % (chunk_size * 5) == 0:
                optimize_memory()

        # Create DataFrame from results
        results_df = pd.DataFrame(results)

        # Define column order
        column_order = ['Websites']

        # Add original columns (excluding completely empty ones)
        df_no_empty = df.dropna(axis=1, how='all')  # Remove completely empty columns
        original_cols = [col for col in df_no_empty.columns if col != 'Websites']
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

        # Emit progress update before merging
        socketio_instance.emit('processing_progress', {
            'current': total_rows,
            'total': total_rows,
            'progress': 90,
            'status': 'finalizing'
        })

        # Merge original and results DataFrames
        merged_df = pd.merge(
            df[['Websites'] + original_cols],
            results_df,
            on='Websites',
            how='left'
        )

        # Select only existing columns and drop empty ones
        final_cols = [col for col in column_order if col in merged_df.columns]
        final_df = merged_df[final_cols]

        # Clean up remaining unnamed columns and replace NaN with empty string
        final_df = final_df.loc[:, ~final_df.columns.str.contains('^Unnamed:')]
        string_columns = final_df.select_dtypes(include=['object']).columns
        final_df[string_columns] = final_df[string_columns].fillna('')

        # Update scrape count
        try:
            result = update_user_scrape_count(current_user, total_rows)
            
            # Emit updated scrape count
            socketio_instance.emit('scrape_count_updated', {
                'scrapes_used': result['scrapes_used'],
                'scrape_limit': result['scrape_limit']
            })
            
            logger.info("Scrape count updated successfully")
        except Exception as e:
            logger.error(f"Failed to update scrape count: {str(e)}")

        # Create CSV response
        output = io.StringIO()
        final_df.to_csv(output, index=False)
        output.seek(0)

        # Emit completion status
        socketio_instance.emit('processing_complete', {
            'status': 'complete',
            'message': 'Processing completed successfully',
            'rows_processed': total_rows
        })

        # Prepare and return response
        response = make_response(output.getvalue())
        response.headers.update({
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename=analysis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        })

        logger.info(f"Processing complete. Processed {total_rows} rows with columns: {final_df.columns.tolist()}")
        return response

    except Exception as e:
        # Log error and memory usage
        logger.error(f"Processing error: {str(e)}")
        log_memory_usage("on error")

        # Emit error to client
        socketio_instance.emit('processing_error', {
            'error': str(e),
            'message': 'An error occurred during processing'
        })

        # Attempt memory optimization
        try:
            optimize_memory()
        except:
            pass
        return jsonify({
            'error': str(e),
            'message': 'An error occurred during processing. Please try again.',
            'details': {
                'type': type(e).__name__,
                'location': 'process route',
                'timestamp': datetime.now().isoformat()
            }
        }), 500

    finally:
        # Final cleanup and progress update
        try:
            # Final memory optimization
            optimize_memory()
            log_memory_usage("after final cleanup")

            # Final status update
            socketio_instance.emit('processing_status', {
                'status': 'completed',
                'timestamp': datetime.now().isoformat()
            })

            logger.info("Process route completed execution")

        except Exception as cleanup_error:
            logger.error(f"Error in final cleanup: {str(cleanup_error)}")




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


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Generate password reset token
            token = user.get_reset_token()
            # Send email with reset link
            flash('Password reset instructions have been sent to your email.', 'info')
            return redirect(url_for('auth.login'))
        flash('Email address not found.', 'error')
    return render_template('auth/forgot_password.html', form=form)

if __name__ == '__main__':
    from app import create_app
    app = create_app()
    socketio.run(app, debug=True)

