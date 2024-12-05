from setuptools import setup, find_packages

setup(
    name="smartscrape",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'flask',
        'flask-sqlalchemy',
        'flask-login',
        'flask-bcrypt',
        'flask-socketio',
        'gunicorn',
        'psycopg2-binary',
        'scrapeops-python-requests',
        'beautifulsoup4',
        'pandas',
    ]
)