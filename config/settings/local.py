from .base import *
import os

DEBUG = True

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-local-dev-key-riwaaya-threads')

ALLOWED_HOSTS = ['*']

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = True  # For local dev ease
CORS_ALLOW_CREDENTIALS = True
