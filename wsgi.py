#/wsgi.py
import eventlet
eventlet.monkey_patch()

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()