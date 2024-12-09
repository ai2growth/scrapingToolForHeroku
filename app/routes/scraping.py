def scrape_website(url):
    import requests
    from bs4 import BeautifulSoup

    if not url.startswith('http'):
        url = 'http://' + url

    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text()[:300]  # Limit to 300 characters
    except Exception:
        return None
