from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from .models import UserProfile, VideoSession


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Custom admin interface for UserProfile model.
    """
    list_display = (
        'user_link',
        'age_display',
        'is_old_enough_display',
        'ban_status_display',
        'created_at',
        'updated_at'
    )
    list_filter = ('is_banned', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'age_display', 'ban_info')
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Age Verification', {
            'fields': ('birth_date', 'age_display')
        }),
        ('Ban Status', {
            'fields': ('is_banned', 'banned_reason', 'banned_at', 'ban_info'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    actions = ['ban_and_terminate_sessions']

    def user_link(self, obj):
        """Display clickable user link."""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user.id,
            obj.user.username
        )
    user_link.short_description = 'User'

    def age_display(self, obj):
        """Display user's current age."""
        age = obj.age
        color = 'green' if age >= 18 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} years old</span>',
            color,
            age
        )
    age_display.short_description = 'Age'

    def is_old_enough_display(self, obj):
        """Display age verification status."""
        if obj.is_old_enough:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Verified 18+</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Under 18</span>'
            )
    is_old_enough_display.short_description = 'Age Verification'

    def ban_status_display(self, obj):
        """Display ban status with color."""
        if obj.is_banned:
            return format_html(
                '<span style="color: red; font-weight: bold;">🚫 BANNED</span>'
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
    ban_status_display.short_description = 'Ban Status'

    def ban_info(self, obj):
        """Display detailed ban information."""
        if obj.is_banned:
            info = f"<strong>Banned At:</strong> {obj.banned_at}<br>"
            if obj.banned_reason:
                info += f"<strong>Reason:</strong> {obj.banned_reason}"
            return format_html(info)
        return "User is not banned"
    ban_info.short_description = 'Ban Information'

    @admin.action(
        description='Ban selected users and terminate their active sessions'
    )
    def ban_and_terminate_sessions(self, request, queryset):
        """
        Custom action to ban users and terminate all their active sessions.
        """
        from django.contrib import messages
        
        if 'apply' in request.POST:
            # Get the ban reason from POST
            ban_reason = request.POST.get('ban_reason', '')
            banned_count = 0
            sessions_terminated = 0

            for profile in queryset:
                if not profile.is_banned:
                    # Ban the user
                    profile.is_banned = True
                    profile.banned_at = timezone.now()
                    profile.banned_reason = ban_reason or 'Banned by administrator'
                    profile.save()
                    banned_count += 1

                    # Terminate all active sessions for this user
                    active_sessions = VideoSession.objects.filter(
                        active_users=profile.user,
                        is_active=True
                    )
                    for session in active_sessions:
                        session.end_session()
                        sessions_terminated += 1

            messages.success(
                request,
                f'Successfully banned {banned_count} user(s) and terminated {sessions_terminated} session(s).'
            )
            return redirect(request.path_info)

        # Show confirmation form with reason input
        context = {
            'queryset': queryset,
            'action_name': 'ban_and_terminate_sessions',
            'title': 'Ban Users and Terminate Sessions',
        }
        return render(request, 'admin/ban_confirmation.html', context)


@admin.register(VideoSession)
class VideoSessionAdmin(admin.ModelAdmin):
    """
    Custom admin interface for VideoSession model with live monitoring.
    """
    list_display = (
        'room_id_link',
        'session_type_display',
        'user_count_display',
        'is_active_display',
        'duration_display',
        'created_at',
        'monitor_link'
    )
    list_filter = ('session_type', 'is_active', 'created_at')
    search_fields = ('room_id', 'active_users__username')
    readonly_fields = (
        'room_id',
        'created_at',
        'updated_at',
        'active_users_display',
        'duration_display'
    )
    filter_horizontal = ('active_users',)
    fieldsets = (
        ('Session Information', {
            'fields': ('room_id', 'session_type', 'is_active')
        }),
        ('Participants', {
            'fields': ('active_users', 'active_users_display')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'duration_display'),
            'classes': ('collapse',)
        })
    )
    actions = ['end_selected_sessions']
    change_list_template = 'admin/videosession_changelist.html'

    def has_add_permission(self, request):
        """Prevent manual creation of sessions from admin."""
        return False

    def room_id_link(self, obj):
        """Display clickable room ID."""
        return format_html(
            '<strong>{}</strong>',
            obj.room_id
        )
    room_id_link.short_description = 'Room ID'

    def session_type_display(self, obj):
        """Display session type with styling."""
        color = 'blue' if obj.session_type == '1v1' else 'purple'
        label = '👤 Private' if obj.session_type == '1v1' else '👥 Group'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            label
        )
    session_type_display.short_description = 'Type'

    def user_count_display(self, obj):
        """Display number of active users."""
        count = obj.get_user_count()
        color = 'green' if count > 0 else 'gray'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} user(s)</span>',
            color,
            count
        )
    user_count_display.short_description = 'Participants'

    def is_active_display(self, obj):
        """Display active status."""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">🔴 LIVE</span>'
            )
        else:
            return format_html(
                '<span style="color: gray; font-weight: bold;">⚪ Ended</span>'
            )
    is_active_display.short_description = 'Status'

    def duration_display(self, obj):
        """Display session duration."""
        duration = obj.get_session_duration()
        hours = int(duration // 60)
        minutes = int(duration % 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    duration_display.short_description = 'Duration'

    def active_users_display(self, obj):
        """Display list of active users."""
        users = obj.active_users.all()
        if not users:
            return "No active users"
        user_list = '<ul style="margin: 10px 0;">'
        for user in users:
            user_list += f'<li>{user.username} ({user.email})</li>'
        user_list += '</ul>'
        return format_html(user_list)
    active_users_display.short_description = 'Active Users'

    def monitor_link(self, obj):
        """Display link to live monitoring view."""
        if obj.is_active:
            return format_html(
                '<a class="button" href="/admin/video-monitor/?room_id={}">Monitor</a>',
                obj.room_id
            )
        return '—'
    monitor_link.short_description = 'Actions'

    @admin.action(description='End selected sessions immediately')
    def end_selected_sessions(self, request, queryset):
        """End selected sessions."""
        from django.contrib import messages
        
        count = 0
        for session in queryset:
            if session.is_active:
                session.end_session()
                count += 1

        messages.success(request, f'Successfully ended {count} session(s).')
    end_selected_sessions.short_description = 'End Sessions'

    def get_urls(self):
        """Add custom admin URLs."""
        urls = super().get_urls()
        custom_urls = [
            path('live-monitoring/', self.admin_site.admin_view(self.live_monitoring_view),
                 name='videosession_monitoring'),
        ]
        return custom_urls + urls

    def live_monitoring_view(self, request):
        """View for live monitoring of active sessions."""
        active_sessions = VideoSession.objects.filter(is_active=True).prefetch_related(
            'active_users'
        ).order_by('-created_at')

        context = {
            'title': 'Live Video Session Monitoring',
            'sessions': active_sessions,
            'total_sessions': active_sessions.count(),
            'total_users': sum(s.get_user_count() for s in active_sessions),
        }
        return render(request, 'admin/videosession_monitoring.html', context)
