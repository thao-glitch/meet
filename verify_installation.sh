#!/bin/bash
# Installation Verification Script
# Checks that all files and directories are in place

echo "🔍 Video Conference Application - Installation Verification"
echo "=============================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
PASS=0
FAIL=0

# Function to check file
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $1 (MISSING)"
        ((FAIL++))
    fi
}

# Function to check directory
check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $1 (MISSING)"
        ((FAIL++))
    fi
}

echo "📁 Directory Structure:"
echo "----------------------"
check_dir "django_app"
check_dir "django_app/conference_project"
check_dir "django_app/video_chat"
check_dir "django_app/video_chat/templates"
check_dir "django_app/video_chat/templates/video_chat"
check_dir "flask_app"
check_dir "frontend"

echo ""
echo "📄 Configuration Files:"
echo "----------------------"
check_file ".env.example"
check_file ".gitignore"
check_file "README.md"
check_file "QUICK_START.md"
check_file "DELIVERY_SUMMARY.md"
check_file "docker-compose.yml"
check_file "nginx.conf"

echo ""
echo "🐍 Django Files:"
echo "----------------"
check_file "django_app/manage.py"
check_file "django_app/requirements.txt"
check_file "django_app/Dockerfile"
check_file "django_app/conference_project/__init__.py"
check_file "django_app/conference_project/settings.py"
check_file "django_app/conference_project/urls.py"
check_file "django_app/conference_project/wsgi.py"
check_file "django_app/video_chat/__init__.py"
check_file "django_app/video_chat/models.py"
check_file "django_app/video_chat/views.py"
check_file "django_app/video_chat/forms.py"
check_file "django_app/video_chat/admin.py"
check_file "django_app/video_chat/urls.py"
check_file "django_app/video_chat/templates/video_chat/register.html"
check_file "django_app/video_chat/templates/video_chat/join_room.html"
check_file "django_app/video_chat/templates/video_chat/room.html"
check_file "django_app/video_chat/templates/video_chat/admin_monitor.html"

echo ""
echo "🔥 Flask Files:"
echo "---------------"
check_file "flask_app/signaling_server.py"
check_file "flask_app/requirements.txt"
check_file "flask_app/Dockerfile"

echo ""
echo "🌐 Frontend Files:"
echo "------------------"
check_file "frontend/room.html"
check_file "frontend/admin_monitor.html"
check_file "frontend/webrtc.js"

echo ""
echo "======================="
echo -e "✓ Passed: ${GREEN}$PASS${NC}"
echo -e "✗ Failed: ${RED}$FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ All files present! Application is ready.${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Some files are missing. Please review.${NC}"
    exit 1
fi
