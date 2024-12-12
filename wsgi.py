#/wsgi.py
import eventlet

# Add thread=False to avoid lock issues
eventlet.monkey_patch(thread=False)  

import logging
logging.basicConfig(level=logging.DEBUG)

from app import create_app
app = create_app()

if __name__ == "__main__":
    app.run()