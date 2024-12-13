# wsgi.py
import eventlet
eventlet.monkey_patch(thread=False)

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    socketio.run(app)