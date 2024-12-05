from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging

class ScraperService:
    def __init__(self, api_key):
        self.scrapeops_logger = ScrapeOpsRequests(scrapeops_api_key=api_key)
        self.requests_wrapper = self.scrapeops_logger.RequestsWrapper()

    def scrape_url(self, url):
        try:
            url = f"https://{url}" if not urlparse(url).scheme else url
            response = self.requests_wrapper.get(url)
            
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.string if soup.title else "No Title"
                description = soup.find("meta", {"name": "description"})
                description = description["content"] if description else "No Description"
                
                return {
                    "URL": url,
                    "Title": title,
                    "Description": description
                }
            return {
                "URL": url,
                "Error": "Failed to fetch"
            }
        except Exception as e:
            logging.error(f"Error scraping {url}: {str(e)}")
            return {
                "URL": url,
                "Error": str(e)
            }