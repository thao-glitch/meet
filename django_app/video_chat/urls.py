from django.urls import path
from . import views

app_name = 'video-chat'

urlpatterns = [
    # Authentication and joining
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('join/', views.join_room, name='join-room'),
    path('room/<str:room_id>/', views.video_room, name='room'),

    # Random matching
    path('random-match/', views.random_match_page, name='random-match'),

    # API endpoints
    path('api/users/', views.get_users, name='get-users'),
    path('api/verify-session/', views.verify_session, name='verify-session'),
    path('api/get-sessions/', views.get_user_sessions, name='get-sessions'),
    path('api/end-session/', views.end_session, name='end-session'),
    path('api/update-session-users/', views.update_session_users, name='update-session-users'),
    path('api/random-match/', views.find_random_match, name='find-random-match'),
    path('api/random-match/cancel/', views.cancel_random_match, name='cancel-random-match'),

    # Admin monitoring
    path('admin/monitor/', views.admin_monitor, name='admin-monitor'),
]
