# Quick Start Guide - Video Conference Application

This guide will help you get the application running locally in just a few minutes.

## Prerequisites
- Python 3.8+
- Git
- A modern web browser (Chrome, Firefox, Safari, Edge)

## Option 1: Local Development (Recommended for Testing)

### Step 1: Clone and Navigate to Project

```bash
cd confrence
```

### Step 2: Setup Django (Terminal 1)

```bash
cd django_app

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python manage.py migrate

# Create admin user
python manage.py createsuperuser
# Follow the prompts, enter username/password/email

# Run Django server
python manage.py runserver 0.0.0.0:8000
```

You should see:
```
Starting development server at http://0.0.0.0:8000/
```

### Step 3: Setup Flask (Terminal 2)

```bash
cd flask_app

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run Flask server
python signaling_server.py
```

You should see:
```
Starting Flask-SocketIO server on port 5000
```

### Step 4: Access the Application

1. **Register a New User**
   - Go to: `http://localhost:8000/video/register/`
   - Fill in the form with:
     - Username: `testuser`
     - Email: `test@example.com`
     - Password: `SecurePass123!`
     - Birth Date: Select a date that makes you 18+
   - Click Register

2. **Join a Video Call**
   - After registration, you're auto-logged in
   - Fill in the room name (e.g., `test-room`)
   - Click "Start Private Call" or "Join Group Call"
   - Allow browser permissions when prompted
   - You'll see your local video!

3. **Test Multi-User (Open Another Browser/Incognito)
   - Register a second user in another browser tab
   - Have both users join the same room
   - You should see both video feeds!

### Step 5: Access Admin Panel

1. Go to: `http://localhost:8000/admin/`
2. Login with superuser credentials
3. You can now:
   - View registered users
   - View active video sessions
   - Ban users
   - View admin monitor for any active session

---

## Option 2: Docker (Recommended for Production)

### Prerequisites
- Docker & Docker Compose installed

### Step 1: Clone Repository

```bash
cd confrence
```

### Step 2: Create Environment File

```bash
cp .env.example .env

# Edit .env with your configuration:
nano .env
```

### Step 3: Build and Run Containers

```bash
# Build all images
docker-compose build

# Start all services
docker-compose up -d

# Check services are running
docker-compose ps
```

### Step 4: Initialize Database

```bash
# Run migrations
docker-compose exec django python manage.py migrate

# Create superuser
docker-compose exec django python manage.py createsuperuser
```

### Step 5: Access Application

- **Application**: `http://localhost/`
- **Admin Panel**: `http://localhost/admin/`
- **Flask Stats**: `http://localhost/stats`
- **Flask Health**: `http://localhost/health`

### Useful Docker Commands

```bash
# View logs
docker-compose logs -f django
docker-compose logs -f flask
docker-compose logs -f nginx

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Restart services
docker-compose restart

# Access shell
docker-compose exec django python manage.py shell
```

---

## Testing Workflow

### Test 1: User Registration & Age Verification ✓
```
1. Go to /video/register/
2. Enter birth date (must result in 18+)
3. Attempt to use birth date that makes you under 18
4. Verify error message
```

### Test 2: 1v1 Video Call ✓
```
1. Register User A
2. Register User B (in incognito/new browser)
3. User A creates room: "1v1-call"
4. User B joins room: "1v1-call"
5. Both should see video feeds
6. User A toggles microphone - verify change
7. User B ends call - both should be redirected
```

### Test 3: Group Video Call ✓
```
1. Have 3+ users registered
2. All join the same room: "group-meeting"
3. Verify mesh connections (everyone sees everyone)
4. One user toggles camera - others should still see audio
5. Admin joins as silent observer
6. Admin ends session - all users disconnected
```

### Test 4: User Banning ✓
```
1. User is in active video call
2. Admin goes to User Profiles in admin panel
3. Selects user and chooses "Ban and Terminate Sessions"
4. User is immediately disconnected
5. User cannot join new sessions
6. User sees ban message
```

### Test 5: Admin Silent Monitoring ✓
```
1. Users A and B are in a video call
2. Admin goes to Video Sessions
3. Clicks "Monitor" on the active session
4. Admin sees both users' video
5. Admin's video/audio is disabled (verified in browser console)
6. Admin can use "End Session" button
```

---

## Troubleshooting

### Issue: "Connection refused" to Flask

**Solution:**
- Ensure Flask is running on port 5000
- Check `DJANGO_BASE_URL` in Django settings
- Verify `SHARED_SECRET` matches between apps

### Issue: No camera/microphone access

**Solution:**
```javascript
// Check in browser console:
navigator.mediaDevices.enumerateDevices().then(devices => {
    console.log(devices);
});
```

### Issue: WebRTC peers not connecting

**Solution:**
- Check browser console for detailed errors
- Verify both users' ICE states: `pc.iceConnectionState`
- Check Flask logs for signal relay

### Issue: Port already in use

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000
kill -9 <PID>

# Or use different port
python manage.py runserver 0.0.0.0:8001
```

---

## Default Test Credentials

After running migrations, use these to login:

```
Admin Panel:
- URL: http://localhost:8000/admin/
- Username: (from createsuperuser command)
- Password: (from createsuperuser command)
```

---

## Key URLs Reference

```
User Registration:    http://localhost:8000/video/register/
Join Room:           http://localhost:8000/video/join/
Video Room:          http://localhost:8000/video/room/<room_id>/
Admin Panel:         http://localhost:8000/admin/
Admin Monitor:       http://localhost:8000/video/admin/monitor/?room_id=<room_id>

Flask Health:        http://localhost:5000/health
Flask Stats:         http://localhost:5000/stats
```

---

## Common Commands

```bash
# Django
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
python manage.py runserver

# Flask
python signaling_server.py

# Database reset (WARNING: Clears all data!)
rm django_app/db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

---

## Next Steps

1. ✅ Get application running locally
2. ✅ Test with multiple users
3. ✅ Try admin features
4. 📝 Configure for your domain/server
5. 🚀 Deploy using Docker/Docker Compose
6. 🔐 Setup SSL certificates (Let's Encrypt)
7. 📊 Monitor with nginx logs

---

## Support

For detailed documentation, see: [README.md](README.md)

For issues, check:
- Browser console (F12 → Console tab)
- Django logs: `tail -f django_app/logs/django.log`
- Flask logs: Terminal where Flask is running
- Network tab in DevTools for API calls

---

**Happy Video Conferencing! 🎥**
