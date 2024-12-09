from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required
from werkzeug.utils import secure_filename
from flask_socketio import emit
import asyncio
import os
import random
import pandas as pd
from datetime import datetime, timedelta
from functools import wraps
from bs4 import BeautifulSoup
from aiohttp import ClientSession, ClientTimeout
import openai
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bp = Blueprint("api", __name__)

# Constants
UPLOAD_FOLDER = "uploads"
DOWNLOADS_FOLDER = "downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
]

class RateLimiter:
    def __init__(self, calls_per_minute=60):
        self.calls_per_minute = calls_per_minute
        self.calls = []

    def can_call(self):
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        self.calls = [call for call in self.calls if call > minute_ago]
        if len(self.calls) < self.calls_per_minute:
            self.calls.append(now)
            return True
        return False

rate_limiter = RateLimiter()

def rate_limit_scraping(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not rate_limiter.can_call():
            return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
        return await func(*args, **kwargs)
    return wrapper

async def scrape_website(url):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    timeout = ClientTimeout(total=30)
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        async with ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    soup = BeautifulSoup(await response.text(), "html.parser")
                    title = soup.title.string if soup.title else ""
                    meta_desc = soup.find("meta", attrs={"name": "description"})
                    description = meta_desc["content"] if meta_desc else ""
                    content = " ".join([elem.get_text(strip=True) for elem in soup.find_all(["p", "h1", "h2"])])
                    return {"url": url, "title": title, "description": description, "content": content[:5000], "status": "success"}
                else:
                    return {"url": url, "status": "error", "error": f"HTTP {response.status}"}
    except Exception as e:
        return {"url": url, "status": "error", "error": str(e)}

def analyze_with_gpt(data, instructions, model="gpt-3.5-turbo"):
    try:
        prompt = f"""
        Analyze the following:
        URL: {data['url']}
        Title: {data['title']}
        Description: {data['description']}
        Content: {data['content']}
        Instructions: {instructions}
        """
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a web content analysis expert."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        return {"status": "success", "analysis": response.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]
        if not file or file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        if file and file.filename.endswith(".csv"):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            df = pd.read_csv(file_path)
            df = df.dropna(axis=1, how="all")
            df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

            website_columns = ["Website", "website", "Domain", "domain", "URL", "url"]
            found_column = next((col for col in website_columns if col in df.columns), None)

            if not found_column:
                return jsonify({"error": "No website column found"}), 400

            return jsonify({
                "filename": filename,
                "columns": list(df.columns),
                "file_path": file_path,
                "website_column": found_column
            })
        return jsonify({"error": "Invalid file type. Please upload a CSV file."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route("/scrape", methods=["POST"])
@login_required
@rate_limit_scraping
async def scrape():
    try:
        data = request.json
        file_path = data["file_path"]
        instructions = data["instructions"]
        gpt_model = data["gpt_model"]
        api_key = data.get("api_key")
        website_column = data.get("website_column")
        row_limit = data.get("row_limit")

        if not api_key:
            return jsonify({"error": "OpenAI API key is required"}), 400

        if not website_column:
            return jsonify({"error": "Website column not specified"}), 400

        openai.api_key = api_key

        df = pd.read_csv(file_path)
        if website_column not in df.columns:
            return jsonify({"error": f"Column '{website_column}' not found in CSV"}), 400
        if row_limit and row_limit > 0:
            df = df.head(row_limit)

        total_rows = len(df)
        results = []

        for index, row in df.iterrows():
            try:
                url = row[website_column]
                scraped_data = await scrape_website(url)
                if scraped_data["status"] == "success":
                    gpt_result = analyze_with_gpt(scraped_data, instructions, gpt_model)
                    results.append({**scraped_data, **gpt_result})
                else:
                    results.append(scraped_data)

                progress = {
                    "current": index + 1,
                    "total": total_rows,
                    "percentage": round(((index + 1) / total_rows) * 100, 2)
                }
                emit("scraping_progress", progress)

                await asyncio.sleep(1)
            except Exception as e:
                results.append({
                    "url": row[website_column],
                    "status": "error",
                    "error": str(e)
                })

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"results_{timestamp}.csv"
        output_path = os.path.join(DOWNLOADS_FOLDER, output_file)
        pd.DataFrame(results).to_csv(output_path, index=False)

        emit("scraping_complete", {
            "file": output_file,
            "summary": {
                "total": total_rows,
                "successful": len([r for r in results if r["status"] == "success"]),
                "failed": len([r for r in results if r["status"] == "error"])
            }
        })

        return jsonify({"status": "success", "file": output_file})

    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@bp.route("/download/<filename>")
@login_required
def download(filename):
    return send_file(os.path.join(DOWNLOADS_FOLDER, filename), as_attachment=True)

@bp.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "error": "File too large",
        "message": "The uploaded file exceeds the maximum allowed size."
    }), 413

@bp.errorhandler(429)
def too_many_requests(error):
    return jsonify({
        "error": "Too many requests",
        "message": "Please wait before making another request."
    }), 429

@bp.errorhandler(500)
def internal_server_error(error):
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred."
    }), 500
