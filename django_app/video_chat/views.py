from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.conf import settings
import json
import hmac
import hashlib
import uuid
import requests

from .models import UserProfile, VideoSession, RandomMatchQueue
from .forms import RegistrationForm, UserProfileForm


# ============================================================================
# Authentication & Registration Views
# ============================================================================

def login_view(request):
    """Custom user login view (separate from admin login)."""
    if request.user.is_authenticated:
        return redirect('video-chat:join-room')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('video-chat:join-room')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'video_chat/login.html')


@login_required
def logout_view(request):
    """Custom user logout view (separate from admin logout)."""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('video-chat:login')


def register(request):
    """
    User registration view with 18+ age verification.
    """
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        profile_form = UserProfileForm(request.POST)

        if form.is_valid() and profile_form.is_valid():
            # Save user
            user = form.save()

            # Create user profile with birth date
            birth_date = profile_form.cleaned_data['birth_date']
            UserProfile.objects.create(
                user=user,
                birth_date=birth_date
            )

            # Log the user in
            login(request, user)
            messages.success(
                request,
                f"Welcome, {user.username}! Your account has been created successfully."
            )
            return redirect('video-chat:join-room')
        else:
            # Combine form errors
            errors = {**form.errors, **profile_form.errors}
            for field, error_list in errors.items():
                for error in error_list:
                    messages.error(request, f"{field}: {error}")
    else:
        form = RegistrationForm()
        profile_form = UserProfileForm()

    context = {
        'form': form,
        'profile_form': profile_form,
    }
    return render(request, 'video_chat/register.html', context)


@login_required
def join_room(request):
    """
    Room join view - presents UI for selecting 1v1 or group chat.
    """
    # Check if user is banned
    try:
        profile = request.user.profile
        if profile.is_banned:
            messages.error(
                request,
                f"Your account has been banned. Reason: {profile.banned_reason}"
            )
            return redirect('video-chat:logout')
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found. Please contact support.")
        return redirect('video-chat:logout')

    # Check if user is 18+
    if not profile.is_old_enough:
        messages.error(
            request,
            f"You must be 18 years or older to access video chat features. "
            f"Your current age is {profile.age}."
        )
        return redirect('video-chat:logout')

    context = {
        'user': request.user,
        'profile': profile,
    }
    return render(request, 'video_chat/join_room.html', context)


@login_required
def video_room(request, room_id):
    """
    Main video chat room view.
    """
    # Check if user is banned
    try:
        profile = request.user.profile
        if profile.is_banned:
            messages.error(request, "Your account has been banned.")
            return redirect('video-chat:join-room')
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect('video-chat:join-room')

    # Check if user is 18+
    if not profile.is_old_enough:
        messages.error(request, "You must be 18 years or older.")
        return redirect('video-chat:join-room')

    # Get or create the session
    session, created = VideoSession.objects.get_or_create(
        room_id=room_id,
        defaults={'session_type': 'group', 'is_active': True}
    )

    context = {
        'room_id': room_id,
        'user_id': request.user.id,
        'username': request.user.username,
        'session_type': session.session_type,
        'socket_url': getattr(settings, 'SOCKET_SERVER_URL', 'http://localhost:5000'),
    }
    return render(request, 'video_chat/room.html', context)


# ============================================================================
# API Endpoints for Flask-SocketIO Integration
# ============================================================================

@csrf_exempt
@require_http_methods(["POST"])
def verify_session(request):
    """
    API endpoint for Flask signaling server to verify user session validity.

    Expected POST payload:
    {
        "user_id": <int>,
        "room_id": "<string>",
        "token": "<verification_token>"
    }

    Returns:
    {
        "valid": <bool>,
        "user_id": <int>,
        "username": "<string>",
        "is_banned": <bool>,
        "age_verified": <bool>,
        "message": "<string>"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'valid': False,
            'message': 'Invalid JSON payload'
        }, status=400)

    user_id = data.get('user_id')
    room_id = data.get('room_id')
    token = data.get('token')

    # Verify token
    if not _verify_token(token):
        return JsonResponse({
            'valid': False,
            'message': 'Invalid or missing verification token'
        }, status=401)

    # Check if user exists
    try:
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({
            'valid': False,
            'user_id': user_id,
            'message': 'User does not exist'
        })

    # Get user profile
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'valid': False,
            'user_id': user_id,
            'username': user.username,
            'message': 'User profile does not exist'
        })

    # Check if user is banned
    if profile.is_banned:
        return JsonResponse({
            'valid': False,
            'user_id': user_id,
            'username': user.username,
            'is_banned': True,
            'message': f'User is banned. Reason: {profile.banned_reason}'
        })

    # Check if user is 18+
    if not profile.is_old_enough:
        return JsonResponse({
            'valid': False,
            'user_id': user_id,
            'username': user.username,
            'age_verified': False,
            'message': f'User is under 18 years old (age: {profile.age})'
        })

    return JsonResponse({
        'valid': True,
        'user_id': user_id,
        'username': user.username,
        'is_banned': False,
        'age_verified': True,
        'message': 'User session verified successfully'
    })


@login_required
@require_http_methods(["GET"])
def get_user_sessions(request):
    """
    API endpoint to get all active sessions for a user.
    """
    try:
        profile = request.user.profile
        if profile.is_banned:
            return JsonResponse({
                'status': 'error',
                'message': 'User is banned'
            }, status=403)

        sessions = VideoSession.objects.filter(
            active_users=request.user,
            is_active=True
        ).values('room_id', 'session_type', 'created_at')

        return JsonResponse({
            'status': 'success',
            'sessions': list(sessions)
        })
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'User profile not found'
        }, status=404)


@login_required
@require_http_methods(["POST"])
def end_session(request):
    """
    API endpoint to end a video session.
    """
    try:
        data = json.loads(request.body)
        room_id = data.get('room_id')

        session = VideoSession.objects.get(room_id=room_id, is_active=True)
        
        # Verify user is in the session
        if request.user not in session.active_users.all():
            return JsonResponse({
                'status': 'error',
                'message': 'User is not in this session'
            }, status=403)

        session.end_session()

        return JsonResponse({
            'status': 'success',
            'message': 'Session ended successfully'
        })
    except VideoSession.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Session not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON payload'
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def update_session_users(request):
    """
    API endpoint for Flask to update the active users in a session.

    Expected POST payload:
    {
        "room_id": "<string>",
        "user_ids": [<int>, <int>, ...],
        "action": "set" | "add" | "remove",
        "token": "<verification_token>"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON payload'
        }, status=400)

    # Verify token
    if not _verify_token(data.get('token')):
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid verification token'
        }, status=401)

    room_id = data.get('room_id')
    user_ids = data.get('user_ids', [])
    action = data.get('action', 'set')

    try:
        session = VideoSession.objects.get(room_id=room_id)
    except VideoSession.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Session not found'
        }, status=404)

    from django.contrib.auth.models import User

    try:
        if action == 'set':
            session.active_users.clear()
            for user_id in user_ids:
                user = User.objects.get(id=user_id)
                session.add_user(user)
        elif action == 'add':
            for user_id in user_ids:
                user = User.objects.get(id=user_id)
                session.add_user(user)
        elif action == 'remove':
            for user_id in user_ids:
                user = User.objects.get(id=user_id)
                session.remove_user(user)
        else:
            return JsonResponse({
                'status': 'error',
                'message': f'Unknown action: {action}'
            }, status=400)

        session.save()

        return JsonResponse({
            'status': 'success',
            'message': f'Session users updated (action: {action})',
            'active_users': list(session.active_users.values_list('id', flat=True))
        })
    except User.DoesNotExist as e:
        return JsonResponse({
            'status': 'error',
            'message': f'One or more users not found: {str(e)}'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# ============================================================================
# User Listing & Random Match Views
# ============================================================================

@login_required
@require_http_methods(["GET"])
def get_users(request):
    """
    API endpoint returning all registered users with online/offline status.
    """
    try:
        profile = request.user.profile
        if profile.is_banned:
            return JsonResponse({'status': 'error', 'message': 'User is banned'}, status=403)
    except UserProfile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=404)

    from django.contrib.auth.models import User
    users = User.objects.exclude(id=request.user.id).select_related('profile')

    # Get online users from Flask
    online_user_ids = set()
    try:
        flask_url = getattr(settings, 'SOCKET_SERVER_URL', 'http://localhost:5000')
        resp = requests.get(f'{flask_url}/online-users', timeout=3)
        if resp.status_code == 200:
            online_user_ids = set(resp.json().get('online_user_ids', []))
    except requests.RequestException:
        pass

    user_list = []
    for u in users:
        try:
            user_profile = u.profile
            if user_profile.is_banned:
                continue
        except UserProfile.DoesNotExist:
            continue

        user_list.append({
            'id': u.id,
            'username': u.username,
            'first_name': u.first_name,
            'is_online': u.id in online_user_ids,
        })

    return JsonResponse({'status': 'success', 'users': user_list})


@login_required
def random_match_page(request):
    """Page for random video matching with other users."""
    try:
        profile = request.user.profile
        if profile.is_banned:
            messages.error(request, "Your account has been banned.")
            return redirect('video-chat:join-room')
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found.")
        return redirect('video-chat:join-room')

    context = {
        'user': request.user,
        'socket_url': getattr(settings, 'SOCKET_SERVER_URL', 'http://localhost:5000'),
    }
    return render(request, 'video_chat/random_match.html', context)


@login_required
@require_http_methods(["POST"])
def find_random_match(request):
    """
    API endpoint for random match pairing.
    Returns room_id when a match is found.
    """
    import json as _json
    try:
        data = _json.loads(request.body) if request.body else {}
    except _json.JSONDecodeError:
        data = {}

    is_next = data.get('is_next', False)
    prev_room_id = data.get('prev_room_id')

    user = request.user

    # Check if user is banned
    try:
        profile = user.profile
        if profile.is_banned:
            return JsonResponse({'status': 'error', 'message': 'User is banned'}, status=403)
    except UserProfile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=404)

    # End previous room if next was clicked
    if is_next and prev_room_id:
        try:
            session = VideoSession.objects.get(room_id=prev_room_id, is_active=True)
            session.end_session()
        except VideoSession.DoesNotExist:
            pass

    # Remove existing queue entry for this user
    RandomMatchQueue.objects.filter(user=user).delete()

    # Look for another user waiting for a match
    waiting_entry = RandomMatchQueue.objects.filter(is_waiting=True).exclude(user=user).first()

    if waiting_entry:
        # Match found!
        matched_user = waiting_entry.user
        room_id = str(uuid.uuid4())[:8]

        # Create the session
        session = VideoSession.objects.create(
            room_id=room_id,
            session_type='1v1',
            is_active=True
        )
        session.active_users.add(user, matched_user)
        session.save()

        # Mark queue entry as matched
        waiting_entry.is_waiting = False
        waiting_entry.matched_user = user
        waiting_entry.room_id = room_id
        waiting_entry.save()

        # Also create a record for the current user (for history)
        RandomMatchQueue.objects.create(
            user=user,
            is_waiting=False,
            matched_user=matched_user,
            room_id=room_id
        )

        return JsonResponse({
            'status': 'matched',
            'room_id': room_id,
            'matched_user': {
                'id': matched_user.id,
                'username': matched_user.username,
            }
        })
    else:
        # No match available, add to waiting queue
        RandomMatchQueue.objects.create(user=user, is_waiting=True)
        return JsonResponse({
            'status': 'waiting',
            'message': 'Looking for a match...'
        })


@login_required
@require_http_methods(["POST"])
def cancel_random_match(request):
    """Cancel waiting for a random match."""
    RandomMatchQueue.objects.filter(user=request.user, is_waiting=True).delete()
    return JsonResponse({'status': 'cancelled'})


# ============================================================================
# Admin Views
# ============================================================================

@login_required
def admin_monitor(request):
    """
    Admin silent monitor view - allows admins to join rooms as hidden observers.
    """
    if not request.user.is_staff:
        messages.error(request, "Only administrators can access this page.")
        return redirect('video-chat:join-room')

    room_id = request.GET.get('room_id')
    if not room_id:
        messages.error(request, "Room ID is required.")
        return redirect('video-chat:join-room')

    try:
        session = VideoSession.objects.get(room_id=room_id, is_active=True)
    except VideoSession.DoesNotExist:
        messages.error(request, "Session not found or is no longer active.")
        return redirect('admin:index')

    context = {
        'room_id': room_id,
        'user_id': request.user.id,
        'username': f"{request.user.username} (Admin)",
        'is_admin': True,
        'session_type': session.session_type,
        'socket_url': getattr(settings, 'SOCKET_SERVER_URL', 'http://localhost:5000'),
    }
    return render(request, 'video_chat/admin_monitor.html', context)


# ============================================================================
# Helper Functions
# ============================================================================

def _verify_token(token):
    """
    Verify the Flask-Django communication token.
    This uses HMAC-SHA256 with a shared secret.
    """
    if not token:
        return False

    secret = getattr(settings, 'FLASK_DJANGO_SECRET', 'your-secret-key-here')
    expected_token = hashlib.sha256(secret.encode()).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(token, expected_token)
