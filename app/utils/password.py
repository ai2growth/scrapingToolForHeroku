# app/utils/password.py
from werkzeug.security import generate_password_hash, check_password_hash
import logging

logger = logging.getLogger(__name__)

class PasswordHasher:
    """Utility class for password hashing and verification."""
    
    @staticmethod
    def generate_password_hash(password):
        """Generate a secure hash of the password."""
        try:
            return generate_password_hash(password, method='pbkdf2:sha256')
        except Exception as e:
            logger.error(f"Error generating password hash: {str(e)}")
            raise

    @staticmethod
    def check_password_hash(hash_value, password):
        """Check if the password matches the hash."""
        try:
            return check_password_hash(hash_value, password)
        except Exception as e:
            logger.error(f"Error checking password hash: {str(e)}")
            return False