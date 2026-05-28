# Video Conference Application with Django and Flask

A production-ready, split-backend video conferencing application with full WebRTC mesh architecture support for 1v1 and group video calls.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Browser                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Frontend (room.html + webrtc.js)                            │   │
│  │  - Local/Remote Video Rendering                             │   │
│  │  - WebRTC Peer Connection Management                        │   │
│  │  - Socket.IO Signal Emission                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │ HTTP                           │ Socket.IO
         │ (REST API)                     │ (WebRTC Signaling)
         ▼                                ▼
┌──────────────────────┐      ┌──────────────────────────────────┐
│   Django App         │      │   Flask + Flask-SocketIO         │
│   (Port 8000)        │      │   (Port 5000)                    │
├──────────────────────┤      ├──────────────────────────────────┤
│ - User Registration  │      │ - WebRTC Signal Relay            │
│ - Age Verification   │      │ - Room State Management          │
│ - User Banning       │      │ - Peer Connection Coordination   │
│ - Admin Dashboard    │      │ - ICE Candidate Forwarding      │
│ - Session Tracking   │      │                                  │
│ - Database (SQLite)  │      │ - Real-time Event Broadcasting   │
└──────────────────────┘      └──────────────────────────────────┘
```

## Features

### Security & Compliance
- ✅ Mandatory 18+ age verification
- ✅ User ban system with immediate session termination
- ✅ HMAC-SHA256 token-based Flask-Django communication
- ✅ Banned user detection at socket connection
- ✅ Session state validation

### Video Conferencing
- ✅ Full mesh WebRTC architecture
- ✅ Support for 1v1 (private) and multi-peer (group) sessions
- ✅ Dynamic peer connection management
- ✅ ICE candidate exchange
- ✅ Automatic video resolution selection
- ✅ Audio/video track toggling

### Admin Features
- ✅ View all active video sessions
- ✅ Silent observer mode (hidden peer joining)
- ✅ Disabled local stream for admins (no audio/video leakage)
- ✅ End session remotely
- ✅ Ban users and terminate their sessions
- ✅ Session duration monitoring

### Technical Features
- ✅ CORS configuration for cross-origin communication
- ✅ Comprehensive error handling
- ✅ Connection state monitoring
- ✅ Logging and debugging support
- ✅ Graceful disconnection handling

## Project Structure

```
confrence/
├── django_app/
│   ├── manage.py                    # Django CLI
│   ├── db.sqlite3                   # SQLite database
│   ├── requirements.txt
│   ├── conference_project/
│   │   ├── __init__.py
│   │   ├── settings.py              # Django configuration
│   │   ├── urls.py                  # URL routing
│   │   └── wsgi.py                  # WSGI application
│   └── video_chat/
│       ├── __init__.py
│       ├── models.py                # UserProfile, VideoSession models
│       ├── views.py                 # Views and API endpoints
│       ├── forms.py                 # Registration forms
│       ├── admin.py                 # Admin customization
│       ├── urls.py                  # App URL routing
│       └── templates/
│           ├── register.html
│           ├── join_room.html
│           ├── room.html            # Video chat room (served by Django)
│           └── admin_monitor.html   # Admin monitoring view
│
├── flask_app/
│   ├── signaling_server.py          # Flask-SocketIO signaling server
│   ├── requirements.txt
│   └── __pycache__/
│
├── frontend/
│   ├── room.html                    # Frontend HTML template
│   ├── admin_monitor.html           # Admin monitor template
│   ├── webrtc.js                    # WebRTC client logic
│   └── static/
│       └── webrtc.js                # Copy of webrtc.js
│
└── README.md                        # This file
```

## Installation & Setup

### Prerequisites
- Python 3.8+
- Node.js (optional, for frontend development)
- Modern browser with WebRTC support (Chrome, Firefox, Edge, Safari)

### 1. Django Setup

```bash
cd django_app

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create migrations
python manage.py makemigrations

# Run migrations
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser

# Run Django development server
python manage.py runserver 0.0.0.0:8000
```

### 2. Flask Setup

```bash
cd flask_app

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DJANGO_BASE_URL=http://localhost:8000
export FLASK_DJANGO_SECRET=your-shared-secret-key-change-in-production
export DEBUG=True

# Run Flask development server
python signaling_server.py
```

### 3. Configuration

#### Django Settings (django_app/conference_project/settings.py)
```python
# Update these values:
FLASK_DJANGO_SECRET = 'your-shared-secret-key-change-in-production'
SOCKET_SERVER_URL = 'http://localhost:5000'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'your-domain.com']
```

#### Flask Configuration (flask_app/signaling_server.py)
```python
DJANGO_BASE_URL = 'http://localhost:8000'
SHARED_SECRET = 'your-shared-secret-key-change-in-production'  # Must match Django
```

## Usage

### User Registration & Login

1. Navigate to `http://localhost:8000/video/register/`
2. Fill in the registration form:
   - Username
   - Email
   - Password (min 8 characters)
   - Date of Birth (must be 18+)
3. Click Register
4. You'll be logged in automatically

### Starting a Video Call

1. After login, navigate to `http://localhost:8000/video/join/`
2. Choose session type:
   - **Private (1v1)**: Enter another user's ID
   - **Group**: Enter a room name
3. Allow browser permissions for camera/microphone
4. The application will:
   - Display your local video
   - Show remote peers' videos as they join
   - Handle WebRTC signaling automatically

### Controls

- **Microphone Toggle**: Enable/disable microphone
- **Camera Toggle**: Enable/disable camera
- **Resolution**: Cycle through video resolutions (720p → 480p → 1080p)
- **End Call**: Leave the room and return to join screen

### Admin Features

#### Accessing Admin Panel
1. Navigate to `http://localhost:8000/admin/`
2. Login with superuser credentials

#### Banning a User
1. Go to Admin → User Profiles
2. Select user(s) to ban
3. Choose "Ban selected users and terminate their active sessions"
4. Enter ban reason
5. The user will be:
   - Marked as banned
   - Disconnected from all active sessions
   - Prevented from joining future sessions

#### Monitoring Active Sessions
1. Go to Admin → Video Sessions
2. Click the "Monitor" button next to any active session
3. You'll join as a hidden observer:
   - Your video/audio completely disabled
   - Other participants can't see/hear you
   - You can silently audit the session
4. Use "End Session" button if needed to terminate the session

#### Session Statistics
- Number of active rooms
- Participant count per room
- Session duration
- User names and join times

## API Endpoints

### Django REST APIs

```
POST /video/api/verify-session/
- Verify user session validity (Flask ↔ Django)
- Payload: {user_id, room_id, token}
- Response: {valid, is_banned, username, age_verified}

POST /video/api/update-session-users/
- Update active users in a session
- Payload: {room_id, user_ids, action, token}
- Actions: "set", "add", "remove"

GET /video/api/get-sessions/
- Get user's active sessions
- Response: {status, sessions}

POST /video/api/end-session/
- End a user's video session
- Payload: {room_id}
```

### Flask REST APIs

```
GET /health
- Server health check
- Response: {status, active_rooms, total_peers}

GET /stats
- Detailed server statistics
- Response: {active_rooms_count, total_peers, rooms}

POST /room/<room_id>/end (requires token)
- Admin endpoint to end a room
```

## WebRTC Signaling Events (Socket.IO)

### Client → Server

```javascript
// Join a room
socket.emit('join_room', {
    user_id: <int>,
    room_id: <string>,
    username: <string>,
    session_type: '1v1' | 'group'
});

// Send WebRTC signal
socket.emit('webrtc_signal', {
    from_user_id: <int>,
    to_user_id: <int>,
    room_id: <string>,
    type: 'offer' | 'answer' | 'candidate',
    payload: <object>
});

// Get room peers
socket.emit('get_room_peers', {
    room_id: <string>
});

// End room
socket.emit('end_room', {
    room_id: <string>,
    initiator_user_id: <int>
});
```

### Server → Client

```javascript
// Room joined successfully
socket.on('room_joined', {
    user_id, room_id, username, existing_peers, room_peer_count
});

// New peer joined
socket.on('peer_joined', {
    user_id, username, room_peer_count
});

// Peer disconnected
socket.on('peer_disconnected', {
    user_id, username
});

// WebRTC signal received
socket.on('webrtc_signal', {
    from_user_id, type, payload
});

// Room ended
socket.on('room_ended', {
    message
});

// Authentication failed
socket.on('auth_failed', {
    message, reason
});
```

## Debugging & Logging

### Enable Detailed Logging

**Django:**
```python
# settings.py
LOGGING['loggers']['video_chat']['level'] = 'DEBUG'
```

**Flask:**
```python
# signaling_server.py
logging.basicConfig(level=logging.DEBUG)
```

### Browser Console
- Open Developer Tools (F12)
- Check Console tab for client-side logs
- Each log entry is timestamped and labeled with level

### Common Issues

#### "Connection timeout to Django"
- Ensure Django is running on port 8000
- Check DJANGO_BASE_URL in Flask configuration
- Verify FLASK_DJANGO_SECRET matches between apps

#### "No video/audio captured"
- Check browser permissions
- Ensure camera/microphone are not in use elsewhere
- Try different camera by cycling through resolution

#### "Peer connection fails"
- Check ICE server connectivity
- Verify firewall allows UDP traffic
- Check peer's browser WebRTC support

#### "Banned user joins room"
- Verify Django /api/verify-session/ endpoint is accessible
- Check user's is_banned flag in database
- Ensure Flask gets correct token

## Production Deployment

### Security Considerations

1. **HTTPS/WSS Required**: Use TLS for all communications
   ```nginx
   # nginx proxy_pass with SSL
   server {
       listen 443 ssl;
       ssl_certificate /path/to/cert;
       ssl_certificate_key /path/to/key;
       
       location / {
           proxy_pass http://localhost:8000;
       }
       
       location /socket.io {
           proxy_pass http://localhost:5000/socket.io;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }
   ```

2. **Environment Variables**: Use .env file
   ```
   DJANGO_SECRET_KEY=production-secret-key
   FLASK_DJANGO_SECRET=shared-secret-key
   DATABASE_URL=postgresql://user:pass@host/db
   DEBUG=False
   ```

3. **Database**: Migrate to PostgreSQL in production
4. **Caching**: Use Redis for session management
5. **SSL Certificates**: Use Let's Encrypt (certbot)

### Deployment Steps

```bash
# 1. Create production directory
mkdir /opt/videoconf

# 2. Clone application
git clone <repo> /opt/videoconf
cd /opt/videoconf

# 3. Setup Django
cd django_app
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic

# 4. Setup Flask
cd ../flask_app
pip install -r requirements.txt

# 5. Use Gunicorn for Django
gunicorn conference_project.wsgi:application --bind 0.0.0.0:8000

# 6. Use Gunicorn for Flask
gunicorn --worker-class eventlet -w 1 signaling_server:app --bind 0.0.0.0:5000
```

### Process Management (systemd)

**Django Service** (`/etc/systemd/system/django-conference.service`):
```ini
[Unit]
Description=Django Conference Service
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/videoconf/django_app
ExecStart=/opt/videoconf/django_app/venv/bin/gunicorn \
          --workers 4 \
          --bind 0.0.0.0:8000 \
          conference_project.wsgi:application

[Install]
WantedBy=multi-user.target
```

**Flask Service** (`/etc/systemd/system/flask-conference.service`):
```ini
[Unit]
Description=Flask Conference Signaling Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/videoconf/flask_app
ExecStart=/opt/videoconf/flask_app/venv/bin/gunicorn \
          --worker-class eventlet \
          --workers 1 \
          --bind 0.0.0.0:5000 \
          signaling_server:app

[Install]
WantedBy=multi-user.target
```

## Testing

### Manual Testing Checklist

- [ ] User registration with age verification
- [ ] Login and session management
- [ ] 1v1 video call creation and connection
- [ ] Group video with 3+ participants
- [ ] Microphone/camera toggle
- [ ] Video resolution cycling
- [ ] End call functionality
- [ ] User banning and session termination
- [ ] Admin silent monitoring
- [ ] Peer disconnection handling
- [ ] Reconnection after network interruption

### Unit Tests

```bash
# Django tests
python manage.py test video_chat

# Flask tests (create tests/test_signaling.py)
pytest flask_app/tests/
```

## Performance Optimization

### Bandwidth Reduction
- Adaptive video bitrate encoding
- VP8/VP9 codec selection
- Resolution downscaling for weaker connections

### Scalability
- Implement Session Traversal Utilities for NAT (STUN) servers
- Use TURN servers for firewall traversal
- Distribute Flask servers with load balancing
- Implement Redis-backed session store

## Support & Troubleshooting

For issues, check:
1. Browser console for client errors
2. Django logs: `tail -f django_app/logs/django.log`
3. Flask logs: Terminal output from `python signaling_server.py`
4. Network tab in Developer Tools for failed requests

## License

MIT License - See LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Author

Built with ❤️ for secure, production-ready video conferencing.

---

**Last Updated**: May 2026
