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
    reconnection_delay_max=5000,
    manage_session=False  # Add this
)

# Modify the connect handler to be more informative
@socketio.on('connect')
def handle_connect():
    print('Client connected - Session ID:', request.sid)
    # Send immediate acknowledgment to client
    socketio.emit('connection_confirmed', {'status': 'connected'}, room=request.sid)