"""
URL configuration for Conference Project
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

# A clean, simple view to catch the root URL and push users to registration
def root_redirect(request):
    return redirect('video-chat:register')

urlpatterns = [
    path('', root_redirect, name='root-home'),
    path('admin/', admin.site.urls),
    path('video/', include('video_chat.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
