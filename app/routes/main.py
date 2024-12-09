from flask import Blueprint, render_template, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db, socketio
import pandas as pd
import os
import uuid
import threading
import openai
from datetime import datetime, timedelta
import logging
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
from bs4 import BeautifulSoup
import requests
import time
from app.models import User  # Ensure User model is imported
import random

SCRAPEOPS_API_KEY = "0139316f-c2f9-44ad-948c-f7a3439511c2"  # Your API key
MAX_WORKERS = 5
RATE_LIMIT_DELAY = 1

bp = Blueprint('main', __name__)

def clean_content(content):
    """Clean and normalize scraped content."""
    if not content:
        return ""
    content = ' '.join(content.split())  # Remove extra whitespace
    content = ''.join(char for char in content if char.isprintable())  # Remove non-printable chars
    words = content.split()[:300]  # Limit length
    return ' '.join(words)

def get_scrapeops_client():
    try:
        scrapeops_logger = ScrapeOpsRequests(scrapeops_api_key=SCRAPEOPS_API_KEY)
        return scrapeops_logger.RequestsWrapper()
    except Exception as e:
        current_app.logger.error(f"Error initializing ScrapeOps client: {str(e)}")
        raise

def scrape_single_site(url, scrapeops_client, app):
    with app.app_context():
        try:
            if not url or pd.isna(url):
                return {"error": "No URL provided"}

            # Rate limiting delay
            time.sleep(RATE_LIMIT_DELAY)

            # Define user agents here
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
                "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/89.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
            ]

            # Ensure URL has scheme
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'

            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.google.com",
                "DNT": "1",
                "Connection": "keep-alive"
            }

            app.logger.info(f"Scraping URL: {url}")
            response = scrapeops_client.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title = clean_content(soup.title.string if soup.title else "")

                content_elements = []
                
                # Meta description
                meta_desc = soup.find('meta', {'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    content_elements.append(meta_desc['content'])

                # Main content selectors
                selectors = [
                    'main', 'article',
                    '.about-section', '.about-us',
                    '.company-description', '#company-info',
                    '.product-description', '.products',
                    'h1', 'h2',
                    '.main-content', '.content',
                    'p'
                ]

                for selector in selectors:
                    elements = soup.select(selector)
                    for elem in elements:
                        text = elem.get_text(strip=True)
                        if text:
                            content_elements.append(text)

                main_content = clean_content(' '.join(content_elements))
                app.logger.info(f"Successfully scraped content from {url}")

                return {
                    "success": True,
                    "scraped_content": f"Website Title: {title}\n\nMain Content: {main_content}"
                }
            else:
                app.logger.error(f"Failed to scrape {url}: HTTP {response.status_code}")
                return {"error": f"HTTP Status: {response.status_code}"}

        except Exception as e:
            app.logger.error(f"Error scraping {url}: {str(e)}")
            return {"error": str(e)}
def safe_scrape_site(url, scrapeops_client, app, max_retries=3):  # Add app parameter
    """Wrapper for scrape_single_site with retries"""
    for attempt in range(max_retries):
        try:
            result = scrape_single_site(url, scrapeops_client, app)  # Pass app to scrape_single_site
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
def get_openai_response(prompt, model, max_retries=3, retry_delay=1):
    """Handle OpenAI API calls with rate limiting and retries"""
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a data analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content
        except openai.error.RateLimitError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise
def update_usage_metrics(user_id, rows_processed, success_count, error_count):
    """Track detailed usage metrics on the user."""
    try:
        user = User.query.get(user_id)
        if user:
            user.scrapes_used += rows_processed
            # Make sure your User model has these fields (successful_scrapes, failed_scrapes)
            user.successful_scrapes = (getattr(user, 'successful_scrapes', 0) or 0) + success_count
            user.failed_scrapes = (getattr(user, 'failed_scrapes', 0) or 0) + error_count
            db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error updating usage metrics: {str(e)}")

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

        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

            current_app.logger.info(f"Saving file to: {file_path}")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            file.save(file_path)
            current_app.logger.info("File saved successfully")

            try:
                df = pd.read_csv(file_path)
                column_groups = {
                    'Contact Information': [
                        'First Name', 'Last Name', 'Full Name', 'Title',
                        'Email', 'Email Status'
                    ],
                    'Company Information': [
                        'Company Name', 'Websites', 'Company Phone Number',
                        'Company Founded Year'
                    ],
                    'Location': [
                        'Lead City', 'Lead State', 'Lead Country'
                    ],
                    'Social Media': [
                        'LinkedIn Link', 'Company LinkedIn Link',
                        'Company Twitter Link', 'Company Facebook Link'
                    ],
                    'Other': [
                        'Headline', 'Seniority', 'Is Likely To Engage'
                    ]
                }

                available_columns = list(df.columns)
                organized_columns = {
                    group: [col for col in cols if col in available_columns]
                    for group, cols in column_groups.items()
                }

                return jsonify({
                    "filename": filename,
                    "file_path": file_path,
                    "columns": available_columns,
                    "organized_columns": organized_columns
                })

            except Exception as e:
                current_app.logger.error(f"Error reading CSV: {str(e)}")
                return jsonify({"error": f"Error reading CSV: {str(e)}"}), 500

        current_app.logger.error("Invalid file type")
        return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400

    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

def create_folders():
    """Ensure required folders exist"""
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(current_app.config['DOWNLOADS_FOLDER'], exist_ok=True)

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

        # Calculate number of rows to be processed
        df = pd.read_csv(data['file_path'])
        row_count = len(df) if not data.get('row_limit') else min(int(data.get('row_limit')), len(df))

        # Check user's scraping limit
        if not current_user.check_scrape_limit(row_count):
            remaining_rows = current_user.scrape_limit - current_user.scrapes_used
            return jsonify({
                "error": f"Scraping limit exceeded. You can only scrape {remaining_rows} more rows this month. "
                         f"Your limit resets on {(current_user.last_reset_date + timedelta(days=30)).strftime('%Y-%m-%d')}"
            }), 429

        instructions = data.get('instructions', '')
        gpt_model = data.get('gpt_model', 'gpt-3.5-turbo')
        row_limit = data.get('row_limit')
        selected_columns = data.get('selected_columns', [])
        output_columns = data.get('output_columns', [])

        # Generate task ID
        task_id = str(uuid.uuid4())
        current_app.logger.info(f"Generated task ID: {task_id}")

        # Start processing in background
        thread = threading.Thread(
            target=process_file,
            args=(
                current_app._get_current_object(),
                task_id,
                data['file_path'],
                selected_columns,
                output_columns,
                row_limit,
                data['api_key'],
                instructions,
                gpt_model,
                current_user.id
            )
        )
        thread.daemon = True
        thread.start()

        return jsonify({"task_id": task_id, "status": "processing"})

    except Exception as e:
        current_app.logger.error(f"Process error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def process_file(task_id, file_path, selected_columns, row_limit, api_key, instructions, gpt_model):
    try:
        # Configure OpenAI
        openai.api_key = api_key

        # Read CSV with low_memory=False to handle mixed types
        df = pd.read_csv(file_path, low_memory=False)
        if row_limit and str(row_limit).isdigit() and int(row_limit) > 0:
            df = df.head(int(row_limit))

        # Filter selected columns if specified
        if selected_columns:
            df = df[selected_columns]

        total_rows = len(df)
        results = []

        for index, row in df.iterrows():
            try:
                # Prepare data for GPT
                row_data = row.to_dict()
                prompt = f"""
                Instructions: {instructions}

                Data to analyze:
                {row_data}

                Please provide analysis based on the instructions.
                """

                # Call GPT API
                response = openai.ChatCompletion.create(
                    model=gpt_model,
                    messages=[
                        {"role": "system", "content": "You are a data analysis assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.7
                )

                analysis = response.choices[0].message.content
                results.append({**row_data, "Analysis": analysis})

                # Calculate and emit progress
                progress = int((index + 1) / total_rows * 100)
                socketio.emit('progress', {
                    'task_id': task_id,
                    'progress': progress,
                    'current': index + 1,
                    'total': total_rows
                })

            except Exception as e:
                current_app.logger.error(f"Error processing row {index}: {str(e)}")
                results.append({**row_data, "Analysis": f"Error: {str(e)}"})

        # Convert results to CSV string
        results_df = pd.DataFrame(results)
        csv_data = results_df.to_csv(index=False)

        # Emit completion event with CSV data
        socketio.emit('complete', {
            'task_id': task_id,
            'csv_data': csv_data,
            'filename': f'analysis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        })

    except Exception as e:
        current_app.logger.error(f"Error in process_file: {str(e)}")
        socketio.emit('error', {
            'task_id': task_id,
            'error': str(e)
        })

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
