# backend/wsgi.py
"""
WSGI - UNIQUEMENT API (pas de bot)
"""

import os
import sys

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
