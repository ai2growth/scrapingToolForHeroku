import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class BaseConfig:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key')
    SCRAPEOPS_API_KEY = os.getenv('SCRAPEOPS_API_KEY', '0139316f-c2f9-44ad-948c-f7a3439511c2')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(BaseConfig):
    FLASK_ENV = 'development'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///users.db'

class ProductionConfig(BaseConfig):
    FLASK_ENV = 'production'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError("DATABASE_URL is required in production!")

# Determine which config to use
env = os.getenv('FLASK_ENV', 'development').lower()
if env == 'production':
    Config = ProductionConfig
else:
    Config = DevelopmentConfig

# Add warnings for local development
if env != 'production' and not os.path.exists('.env'):
    print("Warning: .env file not found. Ensure environment variables are set.")
if Config.SQLALCHEMY_DATABASE_URI == 'sqlite:///users.db':
    print("Using SQLite fallback. Set DATABASE_URL for production.")
