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
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # Convert postgres:// to postgresql:// in database URL
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        raise RuntimeError("DATABASE_URL is required in production!")

# Determine which config to use
env = os.getenv('FLASK_ENV', 'development').lower()
if env == 'production':
    Config = ProductionConfig
else:
    Config = DevelopmentConfig