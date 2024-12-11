import os
import uuid
import json  # Added import for JSON handling
import logging
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, current_app, Blueprint
from flask_login import LoginManager, login_required, current_user
from flask_socketio import SocketIO, emit as socketio_emit
import pandas as pd
import openai
from concurrent.futures import ThreadPoolExecutor, as_completed
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
import time  # Added import for sleep in retry mechanism
import threading
import io
import pandas as pd
from datetime import datetime
from flask import make_response, send_file

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

# Create Flask app
app = Flask(__name__)
app.config.update(
    SECRET_KEY='your_secret_key_here',
    UPLOAD_FOLDER=os.path.abspath(os.path.join(os.getcwd(), 'uploads')),
    DOWNLOADS_FOLDER=os.path.abspath(os.path.join(os.getcwd(), 'downloads')),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max file size
)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['DOWNLOADS_FOLDER'], exist_ok=True)

# Create SocketIO instance (without app initially)
socketio = SocketIO()

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

# Define Blueprint
bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('user_dashboard.html')

# Add error handling for missing dependencies
try:
    from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
    SCRAPEOPS_ENABLED = True
except ImportError:
    SCRAPEOPS_ENABLED = False
    logger.warning("ScrapeOps not available. Using fallback scraping method.")

# Helper Functions (Implement these according to your application logic)
def get_scrapeops_client():
    """Initialize and return the ScrapeOps client."""
    if SCRAPEOPS_ENABLED:
        try:
            from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
            scrapeops_logger = ScrapeOpsRequests(
                scrapeops_api_key=os.getenv('SCRAPEOPS_API_KEY', 'your_scrapeops_api_key_here')  # Replace with your ScrapeOps API key or set as environment variable
            )
            return scrapeops_logger.RequestsWrapper()
        except Exception as e:
            logger.error(f"Error initializing ScrapeOps client: {str(e)}")
            return None
    return None

def scrape_single_site(url, scrapeops_client, app):
    """Scrape a single website and return the scraped content."""
    try:
        socketio.emit('scraping_status', {
            'url': url,
            'status': 'starting'
        })

        if not url or pd.isna(url):
            return {"error": "No URL provided"}

        # Ensure URL has scheme
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            content = soup.get_text(separator=' ', strip=True)
            
            socketio.emit('scraping_status', {
                'url': url,
                'status': 'complete'
            })
            
            return {
                "success": True,
                "scraped_content": content[:1000]  # Limit content length
            }
        else:
            socketio.emit('scraping_status', {
                'url': url,
                'status': 'error',
                'error': f"HTTP Status: {response.status_code}"
            })
            return {"error": f"HTTP Status: {response.status_code}"}

    except Exception as e:
        socketio.emit('scraping_status', {
            'url': url,
            'status': 'error',
            'error': str(e)
        })
        logger.error(f"Error scraping site {url}: {str(e)}")
        return {"error": str(e)}
    
def get_openai_response(prompt, model="gpt-3.5-turbo", max_retries=3, retry_delay=1):
    """Call OpenAI ChatCompletion API and return the response text."""
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(  # Changed from Completion to ChatCompletion
                model=model,
                messages=[
                    {"role": "system", "content": "You are a data analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message['content']  # Updated to get message content
        except Exception as e:
            logger.error(f"OpenAI API error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying after {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                return f"Error: {str(e)}"

def update_usage_metrics(user_id, total, success, errors):
    """Update user metrics in the database."""
    # Implement your own logic to update user metrics
    pass

def handle_processing_error(task_id, error_message):
    """Handle errors during processing by emitting an error event."""
    socketio.emit('error', {
        'task_id': task_id,
        'error': error_message,
        'status': 'error'
    }, namespace='/')

def cleanup_old_files(days=7):
    """Remove files older than specified days."""
    try:
        cutoff = datetime.now() - timedelta(days=days)
        for folder in [current_app.config['UPLOAD_FOLDER'], current_app.config['DOWNLOADS_FOLDER']]:
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.isfile(filepath):
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff:
                        try:
                            os.remove(filepath)
                            logger.info(f"Removed old file: {filepath}")
                        except Exception as e:
                            logger.error(f"Error removing file {filepath}: {e}")
    except Exception as e:
        logger.error(f"Error in cleanup_old_files: {e}")

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    ALLOWED_EXTENSIONS = {'csv'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_folders():
    """Ensure upload and download folders exist."""
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DOWNLOADS_FOLDER'], exist_ok=True)

def validate_config():
    """Validate required configuration."""
    required_config = ['UPLOAD_FOLDER', 'DOWNLOADS_FOLDER']
    for key in required_config:
        if key not in current_app.config:
            raise ValueError(f"Missing required configuration: {key}")
        if not os.path.exists(current_app.config[key]):
            try:
                os.makedirs(current_app.config[key])
                logger.info(f"Created directory: {current_app.config[key]}")
            except Exception as e:
                logger.error(f"Could not create {key} directory: {str(e)}")
                raise ValueError(f"Could not create {key} directory: {str(e)}")

def emit(event, data, namespace='/'):
    """Wrapper for socketio.emit."""
    try:
        socketio.emit(event, data, namespace=namespace)  # Changed from socketio_emit to socketio.emit
    except Exception as e:
        logger.error(f"Error emitting {event}: {str(e)}")

def cleanup_temp_files(file_path):
    """Clean up temporary files."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Could not clean up file {file_path}: {str(e)}")

@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    """Handle file upload and return column information."""
    try:
        logger.info("Upload request received")

        # Ensure directories exist
        for folder in ['UPLOAD_FOLDER', 'DOWNLOADS_FOLDER']:
            folder_path = current_app.config.get(folder)
            if folder_path:
                os.makedirs(folder_path, exist_ok=True)
                logger.info(f"Ensured existence of directory: {folder_path}")
            else:
                logger.error(f"Configuration missing: {folder}")
                return jsonify({"error": f"Server configuration error: {folder} not set"}), 500

        if 'file' not in request.files:
            logger.error("No file part in request")
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        logger.info(f"Received file: {file.filename}")

        if not file or file.filename == '':
            logger.error("No selected file")
            return jsonify({"error": "No selected file"}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_suffix = uuid.uuid4().hex
            filename = f"{unique_suffix}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            try:
                file.save(file_path)
                logger.info(f"File saved to: {file_path}")
            except Exception as e:
                logger.error(f"Error saving file: {str(e)}")
                return jsonify({"error": f"Error saving file: {str(e)}"}), 500

            try:
                # Process the CSV file
                df = pd.read_csv(file_path, low_memory=False)
                logger.info(f"CSV loaded with shape: {df.shape}")
                
                # Remove unnamed and empty columns
                df = df.loc[:, ~df.columns.str.contains('^Unnamed:')]
                df = df.dropna(axis=1, how='all')
                df = df.loc[:, (df != '').any()]
                
                # Get available columns
                available_columns = list(df.columns)
                logger.info(f"Available columns: {available_columns}")
                
                # Verify 'Websites' column exists
                if 'Websites' not in available_columns:
                    logger.error("Required 'Websites' column not found")
                    return jsonify({
                        "error": "CSV file must contain a 'Websites' column"
                    }), 400

                response_data = {
                    "filename": filename,
                    "file_path": file_path,
                    "columns": available_columns,
                    "row_count": len(df)
                }
                logger.info(f"Sending response: {response_data}")
                return jsonify(response_data), 200

            except pd.errors.EmptyDataError:
                logger.error("CSV file is empty")
                return jsonify({"error": "The uploaded CSV file is empty"}), 400
            except pd.errors.ParserError as e:
                logger.error(f"CSV parsing error: {str(e)}")
                return jsonify({"error": "Error parsing CSV file. Please ensure it's a valid CSV."}), 400
            except Exception as e:
                logger.error(f"Error processing CSV: {str(e)}")
                return jsonify({"error": f"Error processing CSV: {str(e)}"}), 500

        logger.error("Invalid file type")
        return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({"error": str(e)}), 500


# Route: Abort Processing
@bp.route('/abort', methods=['POST'])
@login_required
def abort_processing():
    try:
        data = request.json
        task_id = data.get('task_id')

        if not task_id:
            logger.error("No Task ID provided for aborting.")
            return jsonify({'status': 'error', 'message': 'Task ID is required.'}), 400

        abort_flag = f'abort_task_{task_id}'
        current_app.config[abort_flag] = True
        logger.info(f"Abort signal received for task {task_id}")

        return jsonify({'status': 'success', 'message': 'Processing aborted.'}), 200

    except Exception as e:
        logger.error(f"Abort processing error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Route: Receive Error Logs from Frontend
@bp.route('/log-error', methods=['POST'])
@login_required
def log_error():
    try:
        data = request.json
        error_message = data.get('error_message', '')
        error_details = data.get('error_details', '')
        context = data.get('context', 'No context provided')

        if not error_message:
            logger.error("Error message is missing in log request.")
            return jsonify({'status': 'error', 'message': 'Error message is required.'}), 400

        # Log the error with context
        logger.error(f"Frontend Error - Context: {context}, Message: {error_message}, Details: {error_details}")

        return jsonify({'status': 'success', 'message': 'Error logged successfully.'}), 200

    except Exception as e:
        logger.error(f"Error logging frontend error: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Failed to log error.'}), 500

def handle_single_row_with_additional_columns(row, instructions, additional_columns, gpt_model, scrapeops_client):
    """Process a single row with additional columns."""
    # Start with the original row data
    result = row.to_dict()
    
    try:
        # Scrape content
        scrape_result = scrape_single_site(row.get('Websites', ''), scrapeops_client, current_app)
        scraped_content = scrape_result.get('scraped_content', '') if scrape_result.get('success') else "No data scraped"
        
        # Store scraped content
        result['Scraped_Content'] = scraped_content

        # Process main analysis if instructions provided
        if instructions:
            primary_prompt = f"""
            Analyze the following content based on the instructions:
            {instructions}
            Content: {scraped_content}
            """
            result['Analysis'] = get_openai_response(primary_prompt, gpt_model)

        # Process additional columns
        if additional_columns:
            for column in additional_columns:
                column_name = column.get('name')
                column_instructions = column.get('instructions')
                
                if column_name and column_instructions:
                    prompt = f"""
                    Based on the following instructions:
                    {column_instructions}
                    Content: {scraped_content}
                    """
                    try:
                        result[column_name] = get_openai_response(prompt, gpt_model)
                    except Exception as e:
                        result[column_name] = f"Error: {str(e)}"
                        logger.error(f"Error processing additional column {column_name}: {str(e)}")

    except Exception as e:
        logger.error(f"Error processing row: {str(e)}")
        result['Scraped_Content'] = "Error scraping content"
        result['Analysis'] = f"Error: {str(e)}"

    return result

def process_file(app, task_id, file_path, selected_columns, row_limit, api_key, instructions, gpt_model, user_id, additional_columns):
    """Process the uploaded file and generate analysis."""
    with app.app_context():
        try:
            # Initialize abort flag
            abort_flag = f'abort_task_{task_id}'
            app.config[abort_flag] = False

            # Configure OpenAI API
            openai.api_key = api_key
            logger.info(f"Starting processing with GPT model: {gpt_model}")

            # Read CSV file
            try:
                df = pd.read_csv(file_path, low_memory=False)
                logger.info(f"CSV loaded with shape: {df.shape}")
            except Exception as e:
                logger.error(f"Error reading CSV file: {str(e)}")
                handle_processing_error(task_id, 'Failed to read CSV file.')
                return

            # Apply row limit if specified
            if row_limit and str(row_limit).strip():
                try:
                    row_limit = int(row_limit)
                    if row_limit > 0:
                        df = df.head(row_limit)
                        logger.info(f"Row limit applied: processing first {row_limit} rows")
                except ValueError:
                    logger.warning(f"Invalid row limit value: {row_limit}. Processing all rows.")
            
            total_rows = len(df)
            logger.info(f"Starting to process {total_rows} rows")
            
            if 'Websites' not in df.columns:
                logger.error("CSV must contain a 'Websites' column for scraping")
                handle_processing_error(task_id, "CSV must contain a 'Websites' column for scraping.")
                return

            results = []
            success_count = 0
            error_count = 0

            # Process each row
            for idx, row in df.iterrows():
                if app.config.get(abort_flag, False):
                    logger.info(f"Abort signal detected. Finalizing task {task_id}.")
                    break

                try:
                    result = handle_single_row_with_additional_columns(
                        row=row,
                        instructions=instructions,
                        additional_columns=additional_columns,
                        gpt_model=gpt_model,
                        scrapeops_client=None
                    )
                    results.append(result)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error processing row {idx}: {str(e)}")
                    results.append({
                        'Websites': row.get('Websites', ''),
                        'Error': str(e)
                    })
                    error_count += 1

            # Convert results to DataFrame
            try:
                results_df = pd.DataFrame(results)
            except Exception as e:
                logger.error(f"Error creating results DataFrame: {str(e)}")
                handle_processing_error(task_id, 'Failed to create results DataFrame.')
                return

            # Save results to file
            output_path = os.path.join(app.config['DOWNLOADS_FOLDER'], f"results_{task_id}.csv")
            try:
                results_df.to_csv(output_path, index=False, encoding='utf-8-sig')
                logger.info(f"Results saved to {output_path}")
            except Exception as e:
                logger.error(f"Error saving results to CSV: {str(e)}")
                handle_processing_error(task_id, 'Failed to save results to file.')
                return

            # Emit completion event
            socketio.emit('complete', {
                'task_id': task_id,
                'status': 'complete',
                'total_rows': total_rows,
                'processed_rows': len(results),
                'success_rows': success_count,
                'error_rows': error_count,
                'file_path': output_path
            })
            logger.info(f"Processing completed for task {task_id}. Success: {success_count}, Errors: {error_count}")

        except Exception as e:
            logger.error(f"Error in process_file: {str(e)}")
            handle_processing_error(task_id, str(e))
        finally:
            app.config.pop(abort_flag, None)

@bp.route('/process', methods=['POST'])
@login_required
def process():
    try:
        data = request.json
        logger.info(f"Processing started with data: {data}")
        
        # Set OpenAI API key
        openai.api_key = data.get('api_key')
        
        # Load and validate CSV
        df = pd.read_csv(data['file_path'])
        total_rows = len(df)
        processed = 0
        results = []

        # Process each row
        for index, row in df.iterrows():
            try:
                # First emit progress for scraping
                socketio.emit('scraping_progress', {
                    'current': processed,
                    'total': total_rows,
                    'progress': int((processed / total_rows) * 100)
                })

                # Process the row
                result = handle_single_row_with_additional_columns(
                    row=row,
                    instructions=data.get('instructions'),
                    additional_columns=data.get('additional_columns', []),
                    gpt_model=data.get('gpt_model', 'gpt-3.5-turbo'),
                    scrapeops_client=None
                )
                results.append(result)
                processed += 1

            except Exception as e:
                logger.error(f"Error processing row {index}: {str(e)}")
                results.append({
                    'Websites': row.get('Websites', ''),
                    'Error': str(e)
                })

        # Create results DataFrame
        results_df = pd.DataFrame(results)

        # Save to CSV
        output = io.StringIO()
        results_df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)

        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=analysis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response

    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_results(results_df, original_df, additional_columns):
    """
    Process and organize the results DataFrame to include all necessary columns.
    """
    try:
        # Get original columns
        original_columns = list(original_df.columns)

        # Define new columns
        new_columns = ['Scraped_Content', 'Analysis']

        # Add additional column names from the request
        if additional_columns:
            new_columns.extend([col['name'] for col in additional_columns])

        # Ensure all original columns are present in the results
        for col in original_columns:
            if col not in results_df.columns:
                results_df[col] = original_df[col]

        # Ensure all new columns exist (fill missing ones with empty strings)
        for col in new_columns:
            if col not in results_df.columns:
                results_df[col] = ''

        # Arrange columns: original columns first, then new columns
        final_columns = original_columns + [col for col in new_columns if col not in original_columns]

        return results_df[final_columns]

    except Exception as e:
        logger.error(f"Error processing results DataFrame: {str(e)}")
        raise

def validate_row_limit(row_limit):
    """Validate and parse row limit."""
    if row_limit is None:
        return None
    try:
        row_limit = int(row_limit)
        if row_limit <= 0:
            raise ValueError('Row limit must be a positive number.')
        return row_limit
    except ValueError:
        raise ValueError('Invalid row limit value. Must be a positive integer.')

def handle_single_row_with_additional_columns(row, instructions, additional_columns, gpt_model, scrapeops_client):
    """Process a single row with additional columns."""
    result = row.to_dict()  # Include all original columns
    
    try:
        # Scrape content
        scrape_result = scrape_single_site(row.get('Websites', ''), scrapeops_client, current_app)
        scraped_content = scrape_result.get('scraped_content', '') if scrape_result.get('success') else "No data scraped"
        result['Scraped_Content'] = scraped_content

        # Main analysis
        if instructions:
            primary_prompt = f"""
            Analyze the following content based on the instructions:
            {instructions}
            Content: {scraped_content}
            """
            result['Analysis'] = get_openai_response(primary_prompt, gpt_model)

        # Process additional columns
        if additional_columns:
            for column in additional_columns:
                column_name = column.get('name')
                column_instructions = column.get('instructions')

                if column_name and column_instructions:
                    prompt = f"""
                    Based on the following instructions:
                    {column_instructions}
                    Content: {scraped_content}
                    """
                    try:
                        result[column_name] = get_openai_response(prompt, gpt_model)
                    except Exception as e:
                        result[column_name] = f"Error: {str(e)}"
                        logger.error(f"Error processing additional column {column_name}: {str(e)}")

    except Exception as e:
        logger.error(f"Error processing row: {str(e)}")
        result['Scraped_Content'] = "Error scraping content"
        result['Analysis'] = f"Error: {str(e)}"

    return result


# Error Handling Middleware
@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Unhandled error: {str(error)}")
    return jsonify({
        "error": "An unexpected error occurred",
        "details": str(error)
    }), 500

# Configuration Check at Startup
def check_configuration():
    """Check all required configurations are present."""
    required_config = {
        'SECRET_KEY': 'Application secret key',
        'UPLOAD_FOLDER': 'Path for uploaded files',
        'DOWNLOADS_FOLDER': 'Path for downloaded files',
        'MAX_WORKERS': 'Maximum number of worker threads',
        'MAX_CONTENT_LENGTH': 'Maximum allowed payload to be uploaded'
    }

    missing = []
    for key, description in required_config.items():
        if key not in app.config:
            missing.append(f"{key} ({description})")

    if missing:
        raise ValueError(f"Missing required configurations: {', '.join(missing)}")
    else:
        logger.info("All required configurations are present.")

# Call configuration check after app initialization
check_configuration()

# Register Blueprint
app.register_blueprint(bp)

# Run the Flask app
if __name__ == '__main__':
    socketio.run(app, debug=True)
