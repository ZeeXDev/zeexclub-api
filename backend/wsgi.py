# backend/wsgi.py
"""
WSGI config for ZeeXClub project.
"""

import os
import sys

# Ajouter le backend au path
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
