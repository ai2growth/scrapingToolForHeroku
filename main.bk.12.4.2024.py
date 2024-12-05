from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import os
import threading
import uuid
import time
from datetime import datetime
from werkzeug.utils import secure_filename
import openai
from flask_socketio import SocketIO
from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import random
import aiohttp
import asyncio
from aiohttp import ClientTimeout
from concurrent.futures import ThreadPoolExecutor
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler("app_debug.log", mode="w"),  # Log to a file
    ],
)


# Flask app setup
app = Flask(__name__)
app.secret_key = "your_secret_key_here"
socketio = SocketIO(app, cors_allowed_origins="*")

# Folder configurations
UPLOAD_FOLDER = "uploads"
DOWNLOADS_FOLDER = "downloads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["DOWNLOADS_FOLDER"] = DOWNLOADS_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

# ScrapeOps setup
SCRAPEOPS_API_KEY = "0139316f-c2f9-44ad-948c-f7a3439511c2"
scrapeops_logger = ScrapeOpsRequests(scrapeops_api_key=SCRAPEOPS_API_KEY)
requests_wrapper = scrapeops_logger.RequestsWrapper()
# User agents
USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0",
    ]

    # Cleanup old files
def cleanup_old_files():
    """Remove files older than 24 hours from configured folders."""
    current_time = time.time()
    for folder in [UPLOAD_FOLDER, DOWNLOADS_FOLDER]:
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath) and current_time - os.path.getmtime(filepath) > 86400:  # 24 hours in seconds
                try:
                    os.remove(filepath)
                    print(f"Deleted old file: {filepath}")
                except OSError as e:
                    print(f"Error removing {filepath}: {e}")


@app.before_first_request
def initialize():
        """Initialize app and clean up old files."""
        cleanup_old_files()

    # Routes
@app.route("/")
def index():
        return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    """Upload CSV file."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]
        if not file or file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        if file and file.filename.endswith(".csv"):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            df = pd.read_csv(file_path)
            df = df.dropna(axis=1, how="all")
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

            # Check for website column
            website_columns = ['Website', 'Websites', 'website', 'websites', 'Domain', 'Domains', 'domain', 'domains']
            found_website_column = next((col for col in website_columns if col in df.columns), None)

            if found_website_column is None:
                return jsonify({
                    "error": "No website column found. Please ensure your CSV has a column named Website, Websites, Domain, or Domains."
                }), 400

            df.to_csv(file_path, index=False)

            return jsonify({
                "filename": filename,
                "columns": list(df.columns),
                "file_path": file_path,
                "website_column": found_website_column
            })

        return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400
    except Exception as e:
        print("Error during upload:", str(e))
        return jsonify({"error": str(e)}), 500



@app.route("/process", methods=["POST"])
def process():
    try:
        data = request.json
        print("Received process request:", data)  # Debug print
        
        file_path = data.get("file_path")
        row_limit = data.get("row_limit", "all")
        selected_columns = data.get("selected_columns", [])
        num_output_columns = int(data.get("num_output_columns", 1))
        read_instructions = data.get("read_instructions", "")
        output_instructions = data.get("output_instructions", "")
        gpt_model = data.get("gpt_model", "gpt-3.5-turbo")
        openai.api_key = data.get("api_key")

        # Debug file_path and ensure it exists
        print("file_path:", file_path)
        if not file_path or not os.path.exists(file_path):
            print("Invalid file path:", file_path)
            return jsonify({"error": "File path is invalid or missing"}), 400

        # Debugging selected_columns
        print("Selected columns:", selected_columns)
        if not selected_columns:
            print("No columns selected for analysis")
            return jsonify({"error": "No columns selected for analysis"}), 400

        # Debugging thread execution
        task_id = str(uuid.uuid4())
        print("Starting task:", task_id)
        thread = threading.Thread(
            target=scrape_and_analyze,
            args=(file_path, row_limit, selected_columns, num_output_columns, read_instructions, output_instructions, gpt_model, task_id)
        )
        thread.start()

        return jsonify({"task_id": task_id})
    except Exception as e:
        print("Error in process endpoint:", str(e))
        return jsonify({"error": str(e)}), 500

def process_row_with_gpt(row_data, read_instructions, output_instructions, gpt_model, task_id, row_index, total_rows):
    """Process a single row with OpenAI GPT."""
    try:
        if not row_data or not isinstance(row_data, dict):
            print(f"Row data is invalid or empty for row {row_index}")
            return f"Error: Invalid row data at row {row_index}"

        print(f"Processing row {row_index + 1}/{total_rows}: {row_data}")
        formatted_data = "\n".join([f"{key}: {value}" for key, value in row_data.items()])
        prompt = f"""
        Instructions for reading the data:
        {read_instructions}

        Data to analyze:
        {formatted_data}

        Instructions for output:
        {output_instructions}
        """

        response = openai.ChatCompletion.create(
            model=gpt_model,
            messages=[
                {"role": "system", "content": "You are a data analysis assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        print(f"Response for row {row_index}: {response}")
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error processing row {row_index + 1}: {e}")
        return f"Error processing with GPT: {str(e)}"

def get_headers():
        """Get random headers to mimic different browsers."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com",
            "DNT": "1",
            "Connection": "keep-alive"
        }

def is_valid_url(url):
    """Check if a URL is valid."""
    try:
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except ValueError:
        return False

def preprocess_urls(df, website_col):
    """Preprocess and validate website URLs."""
    if website_col not in df.columns or df[website_col].empty:
        print(f"Website column {website_col} is either missing or empty.")
        return []

    print("Processing URLs from column:", website_col)
    urls = df[website_col].dropna()  # Drop NaN values
    print("Raw URLs:", urls.head())  # Debug print for inspection

    # Normalize and validate URLs
    valid_urls = []
    for url in urls:
        normalized_url = f"https://{url}" if not is_valid_url(url) else url
        if is_valid_url(normalized_url):
            valid_urls.append(normalized_url)

    print("Valid URLs:", valid_urls[:5])  # Debug print for inspection
    return valid_urls


def get_headers():
    """Get random headers to mimic different browsers."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com",
        "DNT": "1",
        "Connection": "keep-alive",
    }

def get_random_delay():
        """Get a random delay between requests to mimic human behavior."""
        return random.uniform(1, 3)

def safe_request(url, headers=None, timeout=10):
    """Make a safe HTTP request with error handling."""
    headers = headers or get_headers()  # Default to generated headers
    try:
        response = requests_wrapper.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Request failed for URL {url}: {e}")
        return None

@app.route("/download/<filename>", methods=["GET"])
def download(filename):
        """Download processed file."""
        try:
            file_path = os.path.join(app.config["DOWNLOADS_FOLDER"], filename)
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True, download_name=filename)
            return jsonify({"error": "File not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

async def async_scrape_website(session, url):
    """Asynchronously scrape a single website."""
    url = f"https://{url}" if not is_valid_url(url) else url

    try:
        headers = get_headers()
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status != 200:
                return json.dumps({
                    "url": url,
                    "status": "error",
                    "error_type": "http_error",
                    "message": f"HTTP {response.status}"
                })

            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            return json.dumps({
                "url": url,
                "title": soup.title.string.strip() if soup.title else "No title found",
                "description": soup.find("meta", {"name": "description"}).get("content", "No description found"),
                "main_content ": " ".join(soup.stripped_strings)[:1000],
                "status": "success"
            })
    except aiohttp.ClientError as e:
        return json.dumps({
            "url": url,
            "status": "error",
            "error_type": "client_error",
            "message": str(e)
        })
    except Exception as e:
        return json.dumps({
            "url": url,
            "status": "error",
            "error_type": "request_error",
            "message": str(e)
        })

class RateLimiter:
    """Rate limiter to control the frequency of requests."""

    def __init__(self, requests_per_second=2):
        self.requests_per_second = requests_per_second
        self.last_request_time = 0
        self.lock = threading.Lock()

    async def wait(self):
        """Wait for the appropriate interval between requests."""
        with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            min_interval = 1 / self.requests_per_second
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self.last_request_time = time.time()

async def scrape_batch(urls, batch_size=10, requests_per_second=2):
    """Scrape a batch of URLs concurrently with rate limiting."""
    timeout = ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(limit=batch_size, ssl=False)
    rate_limiter = RateLimiter(requests_per_second=requests_per_second)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for url in urls:
            await rate_limiter.wait()  # Enforce rate limiting
            tasks.append(async_scrape_website(session, url))  # Scraping task

        # Gather results from all tasks
        return await asyncio.gather(*tasks, return_exceptions=True)


async def async_scrape_website(session, url):
    """Asynchronously scrape a single website."""
    if not is_valid_url(url):
        url = "https://" + url  # Ensure URL is properly formatted

    try:
        headers = get_headers()
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                # Extract metadata
                title = soup.title.string if soup.title else "No title found"
                description = soup.find("meta", {"name": "description"})
                description = description["content"] if description and "content" in description.attrs else "No description found"

                # Return structured content
                return json.dumps({
                    "url": url,
                    "title": title,
                    "description": description,
                    "main_content": " ".join(soup.stripped_strings)[:1000],  # First 1000 characters
                    "status": "success"
                })
            else:
                return json.dumps({
                    "url": url,
                    "status": "error",
                    "error_type": "http_error",
                    "message": f"HTTP {response.status}"
                })
    except Exception as e:
        return json.dumps({
            "url": url,
            "status": "error",
            "error_type": "request_error",
            "message": str(e)
        })

def safe_concatenate(original_df, scraped_df):
    """Ensure the scraped dataframe aligns with the original dataframe before concatenation."""
    # Define required columns from the scraped data
    required_columns = ["URL", "Title", "Description", "Main Content", "Error"]

    # Add missing columns to scraped_df with empty values
    for col in required_columns:
        if col not in scraped_df.columns:
            scraped_df[col] = ""  # Fill missing columns with empty strings

    # Align column order to match the original_df if necessary
    for col in original_df.columns:
        if col not in scraped_df.columns:
            scraped_df[col] = ""  # Add columns missing in scraped_df with empty values

    # Concatenate the original and scraped dataframes
    combined_df = pd.concat([original_df, scraped_df[required_columns]], axis=1)

    return combined_df

def scrape_websites_concurrent(df, website_col, task_id, batch_size=5, max_retries=2):
    """Scrape websites concurrently with retries and structured results."""
    if website_col not in df.columns or df[website_col].empty:
        print(f"Website column {website_col} is missing or empty.")
        return pd.DataFrame()

    urls = preprocess_urls(df, website_col)
    if not urls:
        print("No valid URLs to scrape.")
        return pd.DataFrame()

    processed_urls = set()
    raw_results = []

    try:
        for i in range(0, len(urls), batch_size):
            batch_urls = urls[i:i + batch_size]
            print(f"Scraping batch {i // batch_size + 1}/{len(urls) // batch_size + 1}: {batch_urls}")

            retry_count = 0
            while retry_count <= max_retries and batch_urls:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Scrape the current batch
                    batch_results = loop.run_until_complete(scrape_batch(batch_urls, batch_size))
                    for url, result in zip(batch_urls, batch_results):
                        try:
                            data = json.loads(result)
                            if data.get("status") == "success":
                                processed_urls.add(url)
                            raw_results.append(result)
                        except Exception as e:
                            print(f"Error processing result for {url}: {e}")
                            raw_results.append({
                                "url": url,
                                "status": "error",
                                "message": str(e)
                            })

                    # Remove successfully processed URLs
                    batch_urls = [url for url in batch_urls if url not in processed_urls]
                except Exception as e:
                    print(f"Batch error (retry {retry_count}): {e}")
                finally:
                    loop.close()
                retry_count += 1
    except Exception as e:
        print(f"Error during concurrent scraping: {e}")
        raise

    # Process results into a DataFrame
    return process_scraping_results(raw_results)

def scrape_and_analyze(file_path, row_limit, selected_columns, num_output_columns, 
                       read_instructions, output_instructions, gpt_model, task_id):
    """Process the file with scraping and GPT analysis."""
    try:
        # Load the CSV and apply row limits
        df = pd.read_csv(file_path)
        if row_limit != "all":
            try:
                row_limit_int = int(row_limit)
                df = df.head(row_limit_int)
            except ValueError:
                pass

        # Find website column
        website_columns = ['Website', 'Websites', 'website', 'websites',
                           'Domain', 'Domains', 'domain', 'domains']
        website_col = next((col for col in website_columns if col in df.columns), None)

        if not website_col:
            raise ValueError("No website column found in the CSV")

        # Use concurrent scraping
        scraped_df = scrape_websites_concurrent(
            df=df,
            website_col=website_col,
            task_id=task_id,
            batch_size=5
        )

        # Merge scraped results with original dataframe
        df = pd.concat([df, scraped_df], axis=1)

        # Analyze with GPT
        for i in range(num_output_columns):
            column_name = f"GPT_Analysis_{i + 1}"
            results = []

            for index, row in df.iterrows():
                row_data = {
                    col: str(row[col]) for col in selected_columns
                    if col in df.columns and pd.notna(row[col])
                }
                # Add scraped content to the analysis
                row_data['Title'] = row.get('Title', '')
                row_data['Description'] = row.get('Description', '')
                row_data['Main Content'] = row.get('Main Content', '')

                if row_data:
                    try:
                        result = process_row_with_gpt(
                            row_data=row_data,
                            read_instructions=read_instructions,
                            output_instructions=output_instructions,
                            gpt_model=gpt_model,
                            task_id=task_id,
                            row_index=index,
                            total_rows=len(df)
                        )
                        results.append(result)
                    except Exception as e:
                        results.append(f"Error processing row: {str(e)}")
                else:
                    results.append("")

                # Update GPT analysis progress
                progress = 50 + int((index + 1) / len(df) * 50)
                socketio.emit("analysis_progress", {
                    "task_id": task_id,
                    "progress": progress
                })

            df[column_name] = results

        # **Drop the Error column if it exists**
        if "Error" in df.columns:
            df = df.drop(columns=["Error"])

        # Save the updated CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"processed_file_{timestamp}.csv"
        output_path = os.path.join(app.config["DOWNLOADS_FOLDER"], output_filename)
        df.to_csv(output_path, index=False)

        # Emit completion
        socketio.emit('process_complete', {
            'task_id': task_id,
            'download_path': output_filename
        })

    except Exception as e:
        socketio.emit('process_error', {
            'task_id': task_id,
            'error': str(e)
        })


def process_scraping_results(results):
    """Process and structure scraping results into a DataFrame."""
    processed_results = []

    for result in results:
        if not isinstance(result, str):
            processed_results.append({
                "URL": "Unknown",
                "Title": "",
                "Description": "",
                "Main Content": "",
                "Error": "Invalid result format"
            })
            continue

        try:
            data = json.loads(result)
            status = data.get("status", "error")
            processed_results.append({
                "URL": data.get("url", ""),
                "Title": data.get("title", ""),
                "Description": data.get("description", ""),
                "Main Content": data.get("main_content", "") if status == "success" else "",
                "Error": "" if status == "success" else f"{data.get('error_type', '')}: {data.get('message', '')}"
            })
        except json.JSONDecodeError as e:
            processed_results.append({
                "URL": "Unknown",
                "Title": "",
                "Description": "",
                "Main Content": "",
                "Error": f"JSON decoding error: {str(e)}"
            })

    return pd.DataFrame(processed_results)


if __name__ == "__main__":
        socketio.run(app, debug=True, host="0.0.0.0", port=5000)
