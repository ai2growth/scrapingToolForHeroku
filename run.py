from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == '__main__':
    if os.environ.get('FLASK_ENV') == 'production':
        app.run()
    else:
        socketio.run(app, debug=True)