import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///users.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCRAPEOPS_API_KEY = os.getenv('SCRAPEOPS_API_KEY', '0139316f-c2f9-44ad-948c-f7a3439511c2')