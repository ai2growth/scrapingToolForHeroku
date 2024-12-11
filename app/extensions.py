# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO

# Initialize database
db = SQLAlchemy()

# Initialize login manager
login_manager = LoginManager()

# Initialize bcrypt
bcrypt = Bcrypt()

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

# Add error handling for socketio
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