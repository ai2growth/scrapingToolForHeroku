from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO
import pandas as pd
import os
import time
from datetime import datetime
from werkzeug.utils import secure_filename
import openai
from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.secret_key = 'your_secret_key_here'
UPLOAD_FOLDER = "uploads"
DOWNLOADS_FOLDER = "downloads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["DOWNLOADS_FOLDER"] = DOWNLOADS_FOLDER

# Initialize SocketIO
socketio = SocketIO(app)

# Ensure upload and download folders exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(DOWNLOADS_FOLDER):
    os.makedirs(DOWNLOADS_FOLDER)

# Initialize ScrapeOps
SCRAPEOPS_API_KEY = "ad063779-b85c-4ed8-b3b5-ad06653958a4"  # Replace with your ScrapeOps API Key
scrapeops_logger = ScrapeOpsRequests(scrapeops_api_key=SCRAPEOPS_API_KEY)
requests_wrapper = scrapeops_logger.RequestsWrapper()

# Helper Function: Cleanup Old Files
def cleanup_old_files(folder, max_age_hours=24):
    current_time = time.time()
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            file_age = current_time - os.path.getmtime(filepath)
            if file_age > (max_age_hours * 3600):  # Convert hours to seconds
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Error removing file {filepath}: {e}")

@app.before_first_request
def initialize():
    """
    Initialize the application and clean up old files.
    """
    cleanup_old_files(app.config["UPLOAD_FOLDER"])
    cleanup_old_files(app.config["DOWNLOADS_FOLDER"])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            # Read and clean the CSV file
            df = pd.read_csv(file_path)
            df = df.dropna(axis=1, how='all')  # Drop completely empty columns
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]  # Drop unnamed columns

            # Save the cleaned version of the file
            df.to_csv(file_path, index=False)
            
            columns = list(df.columns)

            return jsonify({
                "filename": filename,
                "columns": columns,
                "file_path": file_path
            })
        else:
            return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400

    except Exception as e:
        print(f"Error in upload: {str(e)}")
        return jsonify({"error": str(e)}), 500
@app.route('/process', methods=['POST'])
def process():
    try:
        data = request.json
        required_fields = [
            'selected_columns', 'api_key', 'gpt_model', 
            'read_instructions', 'output_instructions', 
            'num_output_columns', 'file_path'
        ]
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Set OpenAI API key
        openai.api_key = data['api_key']

        # Load and clean the CSV
        df = pd.read_csv(data['file_path'])
        df = df.dropna(axis=1, how='all')  # Drop completely empty columns
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]  # Drop unnamed columns
        
        # Remove rows with empty 'Websites'
        if 'Websites' not in df.columns:
            return jsonify({"error": "'Websites' column not found in the file."}), 400

        df = df.dropna(subset=['Websites'], how='all')
        websites = df['Websites'].tolist()
        print(f"Scraping {len(websites)} non-empty websites...")

        # Scrape websites
        scraped_contents = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for url in websites:
                if isinstance(url, str) and url.strip():
                    result = scrape_website_content(url)
                    scraped_contents.append(result)
                else:
                    scraped_contents.append('')

        # Add scraped content as a new column
        df['Scraped_Content'] = scraped_contents

        # Process with GPT
        num_output_columns = int(data['num_output_columns'])
        selected_columns = data['selected_columns']

        for i in range(num_output_columns):
            column_name = f"GPT_Analysis_{i+1}"
            results = []

            for _, row in df.iterrows():
                try:
                    # Convert row to dictionary for selected columns only
                    row_data = {col: row[col] for col in selected_columns if pd.notna(row[col])}
                    if row_data:  # Only process if we have data
                        gpt_response = process_row_with_gpt(
                            row_data,
                            data['read_instructions'],
                            data['output_instructions'],
                            data['gpt_model']
                        )
                        results.append(gpt_response)
                    else:
                        results.append('')
                except Exception as e:
                    print(f"Error processing row: {e}")
                    results.append('Error in processing')

            df[column_name] = results

        # Save the processed file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"processed_file_{timestamp}.csv"
        output_path = os.path.join(app.config["DOWNLOADS_FOLDER"], output_filename)
        df.to_csv(output_path, index=False)

        return jsonify({
            "message": "Processing complete!",
            "download_path": output_filename,
            "total_rows_processed": len(df)
        })

    except Exception as e:
        print(f"Processing error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

def scrape_website_content(url):
    """
    Scrape website content from a single URL.
    """
    try:
        if not url or not isinstance(url, str):
            return ""
            
        # Add http:// if no scheme is provided
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        response = requests_wrapper.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = ' '.join(soup.stripped_strings)
        return text[:500]  # Limit to 500 characters
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return f"Error scraping content: {str(e)}"
def process_row_with_gpt(row_data, read_instructions, output_instructions, gpt_model):
    """
    Processes a single row using GPT and instructions provided.
    """
    try:
        # Format the data as key-value pairs
        formatted_data = "\n".join([f"{key}: {value}" for key, value in row_data.items()])
        
        # Construct the prompt with the provided instructions
        prompt = f"""
        Instructions for reading the data:
        {read_instructions}

        Data to analyze:
        {formatted_data}

        Instructions for output:
        {output_instructions}
        """

        # Call OpenAI's API to get the response
        response = openai.ChatCompletion.create(
            model=gpt_model,
            messages=[
                {"role": "system", "content": "You are a data analysis assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,  # Limit the token usage for efficiency
            temperature=0.7   # Control randomness
        )

        # Extract the content from the GPT response
        gpt_output = response['choices'][0]['message']['content'].strip()
        return gpt_output

    except Exception as e:
        print(f"Error processing row with GPT: {e}")
        import traceback
        print(traceback.format_exc())
        return f"Error processing with GPT: {str(e)}"
@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    """
    Provides a route to download the processed file.
    """
    file_path = os.path.join(app.config["DOWNLOADS_FOLDER"], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
