import logging
import eventlet
from app import create_app, socketio

# Monkey patch for eventlet
eventlet.monkey_patch()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Starting application initialization")
app = create_app()
logger.debug("Application initialized successfully")

if __name__ == '__main__':
    logger.debug("Starting server with eventlet")
    socketio.run(app,
                debug=True,
                host='127.0.0.1',
                port=5000,
                use_reloader=True)