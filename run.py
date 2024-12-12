import logging
from flask import Flask
from app import create_app
from app.extensions import socketio

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Starting application initialization")
app = create_app()
logger.debug("Application initialized successfully")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.debug(f"Starting server on port {port}")
    socketio.run(app,
                host='0.0.0.0',
                port=port,
                debug=True,
                allow_unsafe_werkzeug=True)