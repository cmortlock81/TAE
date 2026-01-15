"""
ASGI config for tedious_engine project.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tedious_engine.settings')

application = get_asgi_application()
