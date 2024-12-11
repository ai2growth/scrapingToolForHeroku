# Imports
from flask import Blueprint, render_template, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db, socketio
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import os
import uuid
import threading
import openai
from datetime import datetime, timedelta
import logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
import time
from app.models import User
import random
from functools import lru_cache
import requests.adapters
from urllib3.util.retry import Retry

# Configuration Constants
# **Security Note:** It's highly recommended to store API keys securely using environment variables.
SCRAPEOPS_API_KEY = "0139316f-c2f9-44ad-948c-f7a3439511c2"  # Your API key (Consider storing securely)
MAX_WORKERS = 10  # Increased from 5 for better performance
BATCH_SIZE = 10   # Number of rows to process in each batch
RATE_LIMIT_DELAY = 0.5  # Reduced from 1 second if API limits allow
# Rate limiters will be defined later

# Blueprint Definition
bp = Blueprint('main', __name__)

# Helper Functions

def allowed_file(filename):
    """Check if the uploaded file is a valid CSV file."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

def create_folders():
    """Ensure required folders exist."""
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(current_app.config['DOWNLOADS_FOLDER'], exist_ok=True)

def clean_content(content):
    """Clean and normalize scraped content."""
    if not content:
        return ""
    content = ' '.join(content.split())  # Remove extra whitespace
    content = ''.join(char for char in content if char.isprintable())  # Remove non-printable chars
    words = content.split()[:300]  # Limit length
    return ' '.join(words)

def setup_requests_session():
    """Set up a requests session with connection pooling and retries."""
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
    adapter = requests.adapters.HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_scrapeops_client():
    """Initialize and return the ScrapeOps client with optimized settings."""
    from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
    try:
        # Create ScrapeOps client without custom session
        scrapeops_logger = ScrapeOpsRequests(
            scrapeops_api_key=SCRAPEOPS_API_KEY
        )
        
        # Get the requests wrapper
        wrapper = scrapeops_logger.RequestsWrapper()
        
        # Set up the session with our optimized settings
        session = setup_requests_session()
        
        # Attach our optimized session to the wrapper
        wrapper.session = session
        
        return wrapper
    except Exception as e:
        current_app.logger.error(f"Error initializing ScrapeOps client: {str(e)}")
        raise


def scrape_single_site(url, scrapeops_client, app):
    """Optimized version of scrape_single_site."""
    with app.app_context():
        try:
            if not url or pd.isna(url):
                return {"error": "No URL provided"}

            # Ensure URL has scheme
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'

            headers = {
                "User-Agent": random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15"
                ]),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive"
            }

            # Reduced timeout for faster processing
            response = scrapeops_client.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Optimize content extraction
                content_elements = []

                # Get title
                title = soup.title.string if soup.title else ""
                if title:
                    content_elements.append(f"Title: {title}")

                # Get meta description efficiently
                meta_desc = soup.find('meta', {'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    content_elements.append(f"Description: {meta_desc['content']}")

                # Priority content selectors (ordered by importance)
                priority_selectors = [
                    'main article',  # Main content
                    '.about-section, .about-us',  # About sections
                    'h1, h2',  # Headers
                    '.main-content p, article p'  # Paragraphs in main content
                ]

                # Extract content efficiently
                for selector in priority_selectors:
                    elements = soup.select(selector, limit=5)  # Limit elements per selector
                    for elem in elements:
                        text = elem.get_text(strip=True)
                        if text and len(text) > 20:  # Only include substantial content
                            content_elements.append(text)
                            if len(content_elements) >= 10:  # Limit total elements
                                break
                    if len(content_elements) >= 10:
                        break

                main_content = ' '.join(content_elements)
                # Limit content length while preserving meaningful information
                if len(main_content) > 1000:
                    main_content = main_content[:997] + "..."

                return {
                    "success": True,
                    "scraped_content": main_content
                }
            else:
                return {"error": f"HTTP Status: {response.status_code}"}

        except Exception as e:
            return {"error": str(e)}

def safe_scrape_site(url, scrapeops_client, app, max_retries=3):
    """Wrapper for scrape_single_site with retries."""
    for attempt in range(max_retries):
        try:
            result = scrape_single_site(url, scrapeops_client, app)
            if result.get("success"):
                return result
            if attempt < max_retries - 1:
                time.sleep(RATE_LIMIT_DELAY * (attempt + 1))
                continue
        except Exception as e:
            if attempt == max_retries - 1:
                return {"error": str(e)}
            time.sleep(RATE_LIMIT_DELAY * (attempt + 1))
    return {"error": "Max retries exceeded"}

# Rate Limiter Class
class RateLimiter:
    def __init__(self, calls_per_second=2):
        self.calls_per_second = calls_per_second
        self.last_call = time.time()
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            time_since_last_call = now - self.last_call
            if time_since_last_call < 1.0 / self.calls_per_second:
                time.sleep(1.0 / self.calls_per_second - time_since_last_call)
            self.last_call = time.time()

# Create rate limiters
scraping_limiter = RateLimiter(calls_per_second=5)  # 5 requests per second
gpt_limiter = RateLimiter(calls_per_second=3)       # 3 requests per second

@lru_cache(maxsize=1000)
def get_cached_domain_info(domain):
    """Cache domain information to avoid repeated lookups."""
    return urlparse(domain).netloc

def get_openai_response(prompt, model="gpt-3.5-turbo", max_retries=3, retry_delay=1):
    """Optimized version of get_openai_response with better error handling and retry logic."""
    for attempt in range(max_retries):
        try:
            # Optimize prompt to reduce token usage
            cleaned_prompt = prompt.strip()
            if len(cleaned_prompt) > 2000:  # Arbitrary length limit
                cleaned_prompt = cleaned_prompt[:1997] + "..."

            gpt_limiter.wait()  # Apply rate limiting

            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a concise data analysis assistant."},
                    {"role": "user", "content": cleaned_prompt}
                ],
                max_tokens=300,  # Reduced for faster response
                temperature=0.7,
                request_timeout=30  # Add timeout
            )
            return response.choices[0].message.content

        except openai.error.RateLimitError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return "Error: Rate limit exceeded"
            
        except openai.error.APIError as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return f"API Error: {str(e)}"
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return f"Error: {str(e)}"

def cleanup_old_files(days=7):
    """Remove files older than specified days."""
    cutoff = datetime.now() - timedelta(days=days)
    for folder in [current_app.config['UPLOAD_FOLDER'], current_app.config['DOWNLOADS_FOLDER']]:
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath) and os.path.getctime(filepath) < cutoff.timestamp():
                try:
                    os.remove(filepath)
                    current_app.logger.info(f"Removed old file: {filepath}")
                except Exception as e:
                    current_app.logger.error(f"Error removing {filepath}: {e}")

def process_large_file(file_path, chunk_size=1000):
    """Process large CSV files in chunks."""
    for chunk in pd.read_csv(file_path, chunksize=chunk_size, low_memory=False):
        yield chunk

def handle_single_row(row, app, abort_flag, scrapeops_client, gpt_model, instructions):
    """Process a single row with its own application context."""
    with app.app_context():
        try:
            if app.config.get(abort_flag, False):
                app.logger.info(f"Abort signal detected. Skipping row processing.")
                return None

            url = row.get('Websites', '')
            if not url or pd.isna(url):
                return {
                    **row.to_dict(),
                    "Scraped_Content": "No URL provided",
                    "Analysis": "No URL to analyze"
                }

            # Use cached domain info
            domain = get_cached_domain_info(url if url.startswith(('http://', 'https://')) else f'https://{url}')

            # Scrape website with rate limiting
            scraping_limiter.wait()
            scrape_result = safe_scrape_site(url, scrapeops_client, app)

            if scrape_result.get('success'):
                website_data = scrape_result['scraped_content']
                
                # Prepare concise data for analysis
                analysis_data = {
                    'url': url,
                    'domain': domain,
                    'content_summary': website_data[:500] if website_data else ""  # Limit content for analysis
                }

                # Prepare prompt
                prompt = f"""
                Analyze this website concisely:
                URL: {analysis_data['url']}
                Content: {analysis_data['content_summary']}
                
                Instructions: {instructions}
                """

                # Get analysis with rate limiting
                gpt_limiter.wait()
                analysis = get_openai_response(prompt, gpt_model)
            else:
                analysis = f"Could not analyze: {scrape_result.get('error', 'Unknown error')}"

            # Return only essential data
            return {
                'First Name': row.get('First Name', ''),
                'Websites': url,
                'Scraped_Content': scrape_result.get('scraped_content', ''),
                'Analysis': analysis
            }

        except Exception as e:
            app.logger.error(f"Error processing row: {str(e)}")
            return {
                'First Name': row.get('First Name', ''),
                'Websites': url,
                'Scraped_Content': "Error during scraping",
                'Analysis': f"Error: {str(e)}"
            }

def update_usage_metrics(user_id, rows_processed, success_count, error_count):
    """Track detailed usage metrics on the user."""
    try:
        user = User.query.get(user_id)
        if user:
            user.scrapes_used += rows_processed
            user.successful_scrapes = (getattr(user, 'successful_scrapes', 0) or 0) + success_count
            user.failed_scrapes = (getattr(user, 'failed_scrapes', 0) or 0) + error_count
            db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error updating usage metrics: {str(e)}")

def handle_processing_error(task_id, error_message):
    """Emit an error event to the frontend."""
    socketio.emit('error', {
        'task_id': task_id,
        'error': error_message,
        'status': 'error'
    }, namespace='/')

# Main Processing Function

def process_file(app, task_id, file_path, selected_columns, row_limit, api_key, instructions, gpt_model, user_id):
    """Process the uploaded file and generate analysis."""
    with app.app_context():
        try:
            # Initialize abort flag
            abort_flag = f'abort_task_{task_id}'
            app.config[abort_flag] = False

            # Configure OpenAI API
            openai.api_key = api_key
            app.logger.info(f"Starting processing with GPT model: {gpt_model}")

            # Initialize ScrapeOps client
            scrapeops_client = get_scrapeops_client()
            app.logger.info("ScrapeOps client initialized")

            # Read CSV file and keep all original columns
            df = pd.read_csv(file_path, low_memory=False)
            original_columns = list(df.columns)
            app.logger.info(f"CSV file loaded with columns: {original_columns}")

            # Apply row limit if specified
            if row_limit and str(row_limit).strip():
                try:
                    row_limit = int(row_limit)
                    if row_limit > 0:
                        df = df.head(row_limit)
                        app.logger.info(f"Row limit applied: processing first {row_limit} rows")
                except ValueError:
                    app.logger.warning(f"Invalid row limit value: {row_limit}. Processing all rows.")

            # Ensure we have the Websites column
            if 'Websites' not in df.columns:
                raise ValueError("CSV must contain a 'Websites' column for scraping")

            total_rows = len(df)
            results = []
            success_count = 0
            error_count = 0

            app.logger.info(f"Processing {total_rows} rows")

            # Create batches
            batches = [df[i:i + BATCH_SIZE] for i in range(0, len(df), BATCH_SIZE)]

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for batch_idx, batch in enumerate(batches):
                    if app.config.get(abort_flag, False):
                        break
                    
                    # Submit batch of rows
                    futures = []
                    for _, row in batch.iterrows():
                        future = executor.submit(
                            handle_single_row,
                            row=row,
                            app=app,
                            abort_flag=abort_flag,
                            scrapeops_client=scrapeops_client,
                            gpt_model=gpt_model,
                            instructions=instructions
                        )
                        futures.append((future, row))
                    
                    # Process batch results
                    for future, row in futures:
                        try:
                            result = future.result()
                            if result is None:
                                # Processing was aborted
                                app.logger.info(f"Processing aborted. Finalizing task {task_id}.")
                                break  # Exit the loop

                            results.append(result)

                            # Update success and error counts
                            if "Error:" not in result.get("Analysis", "") and result.get("Analysis") != "No data available for analysis":
                                success_count += 1
                            else:
                                error_count += 1

                            # Emit progress update
                            progress = int((len(results) / total_rows) * 100)
                            socketio.emit('progress', {
                                'task_id': task_id,
                                'progress': progress,
                                'current': len(results),
                                'total': total_rows,
                                'status': 'processing',
                                'success_count': success_count,
                                'error_count': error_count
                            }, namespace='/')

                            # Check for abort signal
                            if app.config.get(abort_flag, False):
                                app.logger.info(f"Abort signal detected during processing. Finalizing task {task_id}.")
                                break  # Exit the loop

                        except Exception as e:
                            app.logger.error(f"Error processing row: {str(e)}")
                            # Add error result to results
                            row_dict = row.to_dict()
                            results.append({
                                **row_dict,
                                "Scraped_Content": "Couldn't scrape data",
                                "Analysis": f"Error: {str(e)}"
                            })
                            error_count += 1

            # After processing all batches, clean and save results
            results_df = pd.DataFrame(results)

            # Efficient column cleanup
            # 1. Remove system columns and empty columns
            results_df = results_df.loc[:, ~results_df.columns.str.contains('^Unnamed:')]  # Remove unnamed columns

            # 2. Identify non-empty columns efficiently
            non_empty_cols = []
            for col in results_df.columns:
                # Check if column has any non-empty, non-null values
                if results_df[col].notna().any() and (results_df[col].astype(str).str.strip() != '').any():
                    non_empty_cols.append(col)

            # 3. Keep only essential columns
            essential_cols = ['First Name', 'Websites', 'Scraped_Content', 'Analysis']
            cols_to_keep = list(set(essential_cols + non_empty_cols))
            results_df = results_df[cols_to_keep]

            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"analysis_{timestamp}.csv"
            output_path = os.path.join(app.config['DOWNLOADS_FOLDER'], filename)

            # Save results efficiently
            try:
                results_df.to_csv(output_path, index=False, compression=None)  # No compression for faster saving
                app.logger.info(f"Results saved to {output_path}")
            except Exception as e:
                app.logger.error(f"Error saving results to CSV: {str(e)}")
                raise

            # Update user metrics in background
            def update_metrics_background():
                with app.app_context():
                    try:
                        update_usage_metrics(user_id, len(results), success_count, error_count)
                        app.logger.info(f"User metrics updated for user_id {user_id}")
                    except Exception as e:
                        app.logger.error(f"Error updating user metrics: {str(e)}")

            threading.Thread(target=update_metrics_background).start()

            # Emit completion with optimized data
            try:
                socketio.emit('complete', {
                    'task_id': task_id,
                    'status': 'complete',
                    'filename': filename,
                    'total_rows': total_rows,
                    'processed_rows': success_count,
                    'error_rows': error_count,
                    'success_rate': f"{(success_count / total_rows) * 100:.2f}%" if total_rows > 0 else "0.00%",
                    'completion_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }, namespace='/')

                app.logger.info(
                    f"Processing complete for task {task_id}. "
                    f"Success: {success_count}, Errors: {error_count}, "
                    f"Total: {total_rows}"
                )

            except Exception as e:
                app.logger.error(f"Error emitting completion event: {str(e)}")
                socketio.emit('error', {
                    'task_id': task_id,
                    'error': f"Error completing process: {str(e)}",
                    'status': 'error'
                }, namespace='/')

        except Exception as e:
            # Handle any exceptions that occur during processing
            error_msg = f"Error in process_file: {str(e)}"
            app.logger.error(error_msg)
            handle_processing_error(task_id, error_msg)
            raise

        finally:
            # Cleanup
            try:
                # Remove abort flag from config
                if abort_flag in app.config:
                    del app.config[abort_flag]
                
                # Optional: Cleanup temporary files
                cleanup_old_files()
            except Exception as e:
                app.logger.error(f"Error in cleanup: {str(e)}")

# Route Definitions

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('user_dashboard.html', user=current_user)

@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    try:
        current_app.logger.info("Upload request received")

        if 'file' not in request.files:
            current_app.logger.error("No file part in request")
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        current_app.logger.info(f"Received file: {file.filename}")

        if not file or file.filename == '':
            current_app.logger.error("No selected file")
            return jsonify({"error": "No selected file"}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            
            create_folders()  # Ensure folders exist
            
            file.save(file_path)
            current_app.logger.info("File saved successfully")

            try:
                # Process the CSV file
                df = pd.read_csv(file_path, low_memory=False)
                
                # Remove unnamed and empty columns
                df = df.loc[:, ~df.columns.str.contains('^Unnamed:')]
                df = df.dropna(axis=1, how='all')
                df = df.loc[:, (df != '').any()]
                
                # Get available columns
                available_columns = list(df.columns)
                
                return jsonify({
                    "filename": filename,
                    "file_path": file_path,
                    "columns": available_columns
                })

            except Exception as e:
                current_app.logger.error(f"Error processing CSV: {str(e)}")
                return jsonify({"error": f"Error processing CSV: {str(e)}"}), 500

        current_app.logger.error("Invalid file type")
        return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400

    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/download/<filename>')
@login_required
def download(filename):
    try:
        return send_file(
            os.path.join(current_app.config['DOWNLOADS_FOLDER'], filename),
            as_attachment=True
        )
    except Exception as e:
        current_app.logger.error(f"Download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/process', methods=['POST'])
@login_required
def process():
    try:
        data = request.json
        app = current_app._get_current_object()

        # Log received data (excluding API key for security)
        current_app.logger.info("Received process request with data: %s", 
                                 {k: v for k, v in data.items() if k != 'api_key'})

        # Validate API key
        api_key = data.get('api_key')
        if not api_key:
            current_app.logger.error("No API key provided in request")
            return jsonify({"error": "OpenAI API key is required"}), 400
        
        current_app.logger.info(f"API key received (length: {len(api_key)})")

        # Extract required parameters
        file_path = data.get('file_path')
        if not file_path:
            current_app.logger.error("No file path provided in request")
            return jsonify({"error": "File path is required"}), 400

        selected_columns = data.get('selected_columns', [])
        instructions = data.get('instructions', '')
        gpt_model = data.get('gpt_model', 'gpt-3.5-turbo')
        row_limit = data.get('row_limit')
        
        current_app.logger.info(f"Processing with GPT model: {gpt_model}")

        # Validate file existence
        if not os.path.exists(file_path):
            current_app.logger.error(f"File does not exist at path: {file_path}")
            return jsonify({"error": "File not found"}), 404

        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        current_app.logger.info(f"Generated task ID: {task_id}")

        # Start processing in a background thread
        thread = threading.Thread(
            target=process_file,
            args=(
                app,
                task_id,
                file_path,
                selected_columns,
                row_limit,
                api_key,
                instructions,
                gpt_model,
                current_user.id
            )
        )
        thread.daemon = True
        thread.start()

        # Return success response with task ID
        return jsonify({"task_id": task_id, "status": "processing"}), 200

    except Exception as e:
        current_app.logger.error(f"Process error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/download-csv/<task_id>')
@login_required
def download_csv(task_id):
    try:
        # In a production environment, you would fetch CSV data from a database or cache
        return jsonify({
            "error": "Direct downloads are not supported. Please wait for the automatic download."
        }), 400
    except Exception as e:
        current_app.logger.error(f"Download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/admin/update_user_limit', methods=['POST'])
@login_required
def update_user_limit():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    user_id = data.get('user_id')
    new_limit = data.get('new_limit')

    if not user_id or new_limit is None:
        return jsonify({"error": "Missing user_id or new_limit"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        user.scrape_limit = int(new_limit)
        db.session.commit()
        return jsonify({"message": "User limit updated successfully!"})
    except Exception as e:
        current_app.logger.error(f"Error updating user limit: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/status/<task_id>')
@login_required
def check_status(task_id):
    # TODO: Implement real task status tracking. For now, returning a placeholder.
    return jsonify({"task_id": task_id, "status": "processing"})
