"""
Flask + Flask-SocketIO Signaling Server for WebRTC

This server handles real-time WebRTC signaling:
- User verification against Django backend
- WebRTC offer/answer exchange
- ICE candidate forwarding
- Room state management
- Silent admin monitoring
"""
import eventlet
eventlet.monkey_patch()

import os
import logging
from datetime import datetime
import hashlib
import requests
from functools import wraps

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from flask_cors import CORS

# ============================================================================
# Configuration
# ============================================================================

DJANGO_BASE_URL = os.environ.get('DJANGO_BASE_URL', 'http://localhost:8000')
DJANGO_VERIFY_ENDPOINT = f'{DJANGO_BASE_URL}/video/api/verify-session/'
DJANGO_UPDATE_ENDPOINT = f'{DJANGO_BASE_URL}/video/api/update-session-users/'
SHARED_SECRET = os.environ.get('FLASK_DJANGO_SECRET', 'your-shared-secret-key-change-in-production')

# ============================================================================
# Setup Flask and SocketIO
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'flask-insecure-secret-key-change-in-production')

# Enable CORS for Flask
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize SocketIO with eventlet
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25,
    logger=True,
    engineio_logger=True,
)

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# State Management
# ============================================================================

# Global state for tracking active rooms and users
# Structure: {room_id: {user_id: {'sid': socket_id, 'username': username, ...}}}
active_rooms = {}


class Room:
    """
    Represents an active video conference room.
    """
    def __init__(self, room_id, session_type='group'):
        self.room_id = room_id
        self.session_type = session_type
        self.peers = {}  # {user_id: {'sid': sid, 'username': username, ...}}
        self.created_at = datetime.utcnow()

    def add_peer(self, user_id, sid, username):
        """Add a peer to the room."""
        self.peers[user_id] = {
            'sid': sid,
            'username': username,
            'joined_at': datetime.utcnow()
        }
        logger.info(f"Peer {username} (ID: {user_id}) added to room {self.room_id}")

    def remove_peer(self, user_id):
        """Remove a peer from the room."""
        if user_id in self.peers:
            username = self.peers[user_id]['username']
            del self.peers[user_id]
            logger.info(f"Peer {username} (ID: {user_id}) removed from room {self.room_id}")

    def get_peers(self):
        """Get list of all peers in the room."""
        return list(self.peers.keys())

    def is_empty(self):
        """Check if room has no peers."""
        return len(self.peers) == 0

    def get_peer_count(self):
        """Get number of peers in the room."""
        return len(self.peers)


# ============================================================================
# Token Generation and Verification
# ============================================================================

def generate_verification_token():
    """Generate a verification token for Django communication."""
    token = hashlib.sha256(SHARED_SECRET.encode()).hexdigest()
    return token


def verify_token(token):
    """Verify the token from request."""
    expected_token = generate_verification_token()
    import hmac
    return hmac.compare_digest(token, expected_token)


# ============================================================================
# Decorators
# ============================================================================

def token_required(f):
    """Decorator to verify token in requests."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        data = request.get_json()
        token = data.get('token') if data else None

        if not token or not verify_token(token):
            return jsonify({'error': 'Invalid or missing token'}), 401

        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Helper Functions
# ============================================================================

def verify_user_with_django(user_id, room_id):
    """
    Verify user session with Django backend.

    Returns: (is_valid, is_banned, username)
    """
    try:
        token = generate_verification_token()
        payload = {
            'user_id': user_id,
            'room_id': room_id,
            'token': token
        }

        response = requests.post(
            DJANGO_VERIFY_ENDPOINT,
            json=payload,
            timeout=5
        )

        if response.status_code != 200:
            logger.warning(f"Django verification failed: {response.status_code}")
            return False, False, None

        data = response.json()
        is_valid = data.get('valid', False)
        is_banned = data.get('is_banned', False)
        username = data.get('username', 'Unknown')

        logger.info(
            f"User verification - ID: {user_id}, Valid: {is_valid}, "
            f"Banned: {is_banned}, Username: {username}"
        )

        return is_valid, is_banned, username

    except requests.RequestException as e:
        logger.error(f"Error verifying user with Django: {str(e)}")
        return False, False, None


def update_room_users_in_django(room_id, user_ids, action='set'):
    """
    Update the active users in a session on Django backend.
    """
    try:
        token = generate_verification_token()
        payload = {
            'room_id': room_id,
            'user_ids': user_ids,
            'action': action,
            'token': token
        }

        response = requests.post(
            DJANGO_UPDATE_ENDPOINT,
            json=payload,
            timeout=5
        )

        if response.status_code == 200:
            logger.info(f"Room users updated in Django: {room_id}")
            return True
        else:
            logger.warning(f"Django update failed: {response.status_code}")
            return False

    except requests.RequestException as e:
        logger.error(f"Error updating room users in Django: {str(e)}")
        return False


# ============================================================================
# SocketIO Event Handlers
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    sid = request.sid
    logger.info(f"Client connected: {sid}")
    emit('connection_response', {'data': 'Connected to signaling server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    sid = request.sid
    logger.info(f"Client disconnected: {sid}")

    # Remove user from all rooms and notify others
    for room_id, room in list(active_rooms.items()):
        for user_id, peer_info in list(room.peers.items()):
            if peer_info['sid'] == sid:
                room.remove_peer(user_id)

                # Notify other peers
                emit_to_room(
                    room_id,
                    'peer_disconnected',
                    {'user_id': user_id, 'username': peer_info['username']},
                    skip_sid=sid
                )

                # Update Django
                update_room_users_in_django(
                    room_id,
                    room.get_peers()
                )

                # Clean up empty rooms
                if room.is_empty():
                    del active_rooms[room_id]
                    logger.info(f"Room {room_id} deleted (empty)")

                break


@socketio.on('join_room')
def handle_join_room(data):
    """
    Handle peer joining a video room.

    Expected data:
    {
        'user_id': <int>,
        'room_id': <string>,
        'username': <string>
    }
    """
    user_id = data.get('user_id')
    room_id = data.get('room_id')
    username = data.get('username', f'User_{user_id}')
    sid = request.sid

    logger.info(f"Join room request - User: {username} (ID: {user_id}), Room: {room_id}")

    # Verify user with Django
    is_valid, is_banned, django_username = verify_user_with_django(user_id, room_id)

    if is_banned:
        logger.warning(f"Banned user {username} (ID: {user_id}) attempted to join")
        emit('auth_failed', {
            'message': 'Your account has been banned',
            'reason': 'Banned by administrator'
        })
        return

    if not is_valid:
        logger.warning(f"Invalid user verification - Username: {username} (ID: {user_id})")
        emit('auth_failed', {
            'message': 'User verification failed',
            'reason': 'You do not meet the requirements to join this session'
        })
        return

    # Get or create room
    if room_id not in active_rooms:
        active_rooms[room_id] = Room(room_id, session_type=data.get('session_type', 'group'))

    room = active_rooms[room_id]

    # Add peer to room
    room.add_peer(user_id, sid, django_username)
    join_room(room_id)

    # Get list of existing peers
    existing_peers = [
        peer_id for peer_id in room.get_peers()
        if peer_id != user_id
    ]

    logger.info(f"User {django_username} joined room {room_id}. Existing peers: {existing_peers}")

    # Notify the joining user about existing peers
    emit('room_joined', {
        'user_id': user_id,
        'room_id': room_id,
        'username': django_username,
        'existing_peers': [
            {
                'user_id': peer_id,
                'username': room.peers[peer_id]['username']
            }
            for peer_id in existing_peers
        ],
        'room_peer_count': room.get_peer_count()
    })

    # Notify existing peers about the new user (for mesh setup)
    emit_to_room(
        room_id,
        'peer_joined',
        {
            'user_id': user_id,
            'username': django_username,
            'room_peer_count': room.get_peer_count()
        },
        skip_sid=sid
    )

    # Update Django backend
    update_room_users_in_django(room_id, room.get_peers())

    logger.info(f"Room {room_id} now has {room.get_peer_count()} peer(s)")


@socketio.on('webrtc_signal')
def handle_webrtc_signal(data):
    """
    Handle WebRTC signaling messages (offer, answer, candidate).

    Expected data:
    {
        'from_user_id': <int>,
        'to_user_id': <int>,
        'room_id': <string>,
        'type': 'offer' | 'answer' | 'candidate',
        'payload': {...}
    }
    """
    from_user_id = data.get('from_user_id')
    to_user_id = data.get('to_user_id')
    room_id = data.get('room_id')
    signal_type = data.get('type')
    payload = data.get('payload')

    logger.debug(
        f"WebRTC signal - Type: {signal_type}, From: {from_user_id}, "
        f"To: {to_user_id}, Room: {room_id}"
    )

    if room_id not in active_rooms:
        logger.warning(f"Room {room_id} not found")
        emit('signal_error', {'message': 'Room not found'})
        return

    room = active_rooms[room_id]

    if to_user_id not in room.peers:
        logger.warning(f"Target user {to_user_id} not in room {room_id}")
        emit('signal_error', {'message': f'Target user {to_user_id} not in room'})
        return

    # Get target peer's socket ID
    target_sid = room.peers[to_user_id]['sid']

    # Forward the signal to the target peer
    socketio.emit(
        'webrtc_signal',
        {
            'from_user_id': from_user_id,
            'type': signal_type,
            'payload': payload
        },
        room=target_sid
    )

    logger.debug(f"Signal forwarded to user {to_user_id} (SID: {target_sid})")


@socketio.on('get_room_peers')
def handle_get_room_peers(data):
    """
    Get list of all peers currently in a room.

    Expected data:
    {
        'room_id': <string>
    }
    """
    room_id = data.get('room_id')

    if room_id not in active_rooms:
        emit('room_peers', {'peers': []})
        return

    room = active_rooms[room_id]
    peers = [
        {
            'user_id': peer_id,
            'username': room.peers[peer_id]['username']
        }
        for peer_id in room.get_peers()
    ]

    emit('room_peers', {'peers': peers, 'room_id': room_id})


@socketio.on('end_room')
def handle_end_room(data):
    """
    End a video session and disconnect all peers.

    Expected data:
    {
        'room_id': <string>,
        'initiator_user_id': <int>
    }
    """
    room_id = data.get('room_id')
    logger.info(f"End room request - Room: {room_id}")

    if room_id in active_rooms:
        room = active_rooms[room_id]

        # Notify all peers about room ending
        emit_to_room(
            room_id,
            'room_ended',
            {'message': 'The room host has ended the session'}
        )

        # Delete the room
        del active_rooms[room_id]
        logger.info(f"Room {room_id} ended")

        # Update Django
        update_room_users_in_django(room_id, [], action='set')


# ============================================================================
# Helper Emission Functions
# ============================================================================

def emit_to_room(room_id, event, data, skip_sid=None):
    """
    Emit an event to all clients in a room.

    Args:
        room_id: The room to emit to
        event: Event name
        data: Data to emit
        skip_sid: Optional socket ID to skip
    """
    if skip_sid:
        socketio.emit(event, data, room=room_id, skip_sid=skip_sid)
    else:
        socketio.emit(event, data, room=room_id)


# ============================================================================
# REST API Endpoints
# ============================================================================

@app.route('/online-users', methods=['GET'])
def online_users():
    """Return list of currently online (in-room) user IDs."""
    online_ids = []
    online_details = []
    for room_id, room in active_rooms.items():
        for user_id, peer_info in room.peers.items():
            online_ids.append(user_id)
            online_details.append({
                'user_id': user_id,
                'username': peer_info['username'],
                'room_id': room_id,
                'joined_at': peer_info['joined_at'].isoformat() if hasattr(peer_info['joined_at'], 'isoformat') else str(peer_info['joined_at'])
            })

    return jsonify({
        'status': 'success',
        'online_count': len(online_ids),
        'online_user_ids': online_ids,
        'online_users': online_details
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'active_rooms': len(active_rooms),
        'total_peers': sum(room.get_peer_count() for room in active_rooms.values())
    })


@app.route('/stats', methods=['GET'])
def stats():
    """Get server statistics."""
    room_stats = []
    for room_id, room in active_rooms.items():
        room_stats.append({
            'room_id': room_id,
            'session_type': room.session_type,
            'peer_count': room.get_peer_count(),
            'peers': [
                {'user_id': uid, 'username': peer['username']}
                for uid, peer in room.peers.items()
            ],
            'duration_seconds': (datetime.utcnow() - room.created_at).total_seconds()
        })

    return jsonify({
        'status': 'success',
        'timestamp': datetime.utcnow().isoformat(),
        'active_rooms_count': len(active_rooms),
        'total_peers': sum(room.get_peer_count() for room in active_rooms.values()),
        'rooms': room_stats
    })


@app.route('/room/<room_id>/end', methods=['POST'])
@token_required
def admin_end_room(room_id):
    """
    Admin endpoint to end a room (requires token verification).
    """
    logger.info(f"Admin end room request - Room: {room_id}")

    if room_id in active_rooms:
        room = active_rooms[room_id]

        # Notify all peers
        emit_to_room(
            room_id,
            'room_ended',
            {'message': 'An administrator has ended this session'}
        )

        # Delete the room
        del active_rooms[room_id]

        return jsonify({
            'status': 'success',
            'message': f'Room {room_id} ended by administrator'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Room not found'
        }), 404


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'

    logger.info(f"Starting Flask-SocketIO server on port {port}")
    logger.info(f"Django base URL: {DJANGO_BASE_URL}")
    logger.info(f"Debug mode: {debug}")

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=debug,
        log_output=True
    )
