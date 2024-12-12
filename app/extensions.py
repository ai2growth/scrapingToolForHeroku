# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO  # Add this import
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect() 
mail = Mail()

# Add this PasswordHasher class to replace bcrypt
class PasswordHasher:
    @staticmethod
    def generate_password_hash(password):
        return generate_password_hash(password)
    
    @staticmethod
    def check_password_hash(pw_hash, password):
        return check_password_hash(pw_hash, password)

bcrypt = PasswordHasher()

# Initialize SocketIO with specific configuration
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    always_connect=True,
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=1000,
    reconnection_delay_max=5000
)

# Add error handling for SocketIO
@socketio.on_error_default
def default_error_handler(e):
    print(f'SocketIO Error: {str(e)}')
    socketio.emit('error', {'error': str(e)})

# Add connection handling
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')