from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta


class UserProfile(models.Model):
    """
    Extended user profile with age verification and ban status.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    birth_date = models.DateField(
        help_text="User's date of birth (DD/MM/YYYY format)"
    )
    is_banned = models.BooleanField(
        default=False,
        help_text="If True, user cannot access video chat features"
    )
    banned_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for banning the user"
    )
    banned_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when user was banned"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} - {self.birth_date}"

    @property
    def age(self):
        """Calculate current age based on birth_date."""
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    @property
    def is_old_enough(self):
        """Check if user is 18 years or older."""
        return self.age >= 18

    def clean(self):
        """Validate that birth_date results in user being 18+ years old."""
        if self.birth_date:
            today = date.today()
            age = today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
            if age < 18:
                raise ValidationError(
                    f"User must be at least 18 years old. Current age: {age}"
                )
            # Prevent future dates
            if self.birth_date > today:
                raise ValidationError("Birth date cannot be in the future.")

    def save(self, *args, **kwargs):
        """Validate before saving."""
        self.clean()
        super().save(*args, **kwargs)


class VideoSession(models.Model):
    """
    Tracks active video conference sessions.
    """
    SESSION_TYPE_CHOICES = (
        ('1v1', 'One-on-One (Private)'),
        ('group', 'Multi-peer (Group)'),
    )

    room_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique identifier for the video session"
    )
    session_type = models.CharField(
        max_length=10,
        choices=SESSION_TYPE_CHOICES,
        default='group',
        help_text="Type of video session"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the session is currently active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ManyToMany relationship to track active participants
    active_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='active_video_sessions',
        help_text="Users currently in this session"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Video Session"
        verbose_name_plural = "Video Sessions"
        indexes = [
            models.Index(fields=['room_id', 'is_active']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"Session {self.room_id} ({self.session_type}) - {self.get_user_count()} users"

    def get_user_count(self):
        """Get the number of active users in this session."""
        return self.active_users.count()

    def end_session(self):
        """End the session and clean up."""
        self.is_active = False
        self.active_users.clear()
        self.save()

    def add_user(self, user):
        """Add a user to the session if not banned."""
        if hasattr(user, 'profile') and user.profile.is_banned:
            raise ValidationError(f"User {user.username} is banned and cannot join sessions.")
        if not self.active_users.filter(pk=user.pk).exists():
            self.active_users.add(user)

    def remove_user(self, user):
        """Remove a user from the session."""
        self.active_users.remove(user)

    def get_session_duration(self):
        """Get session duration in minutes."""
        if not self.updated_at:
            return 0
        duration = self.updated_at - self.created_at
        return duration.total_seconds() / 60


class RandomMatchQueue(models.Model):
    """
    Queue model for random matching between users.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='random_match_queue')
    created_at = models.DateTimeField(auto_now_add=True)
    is_waiting = models.BooleanField(default=True, help_text="User is waiting for a match")
    matched_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='matched_with'
    )
    room_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} waiting for match"
