from .base import *
import os

DEBUG = True

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-local-dev-key-riwaaya-threads')

ALLOWED_HOSTS = [
	'localhost',
	'127.0.0.1',
	'[::1]',
	'app.riwaayathreads.com',
]

CSRF_TRUSTED_ORIGINS = [
	'http://localhost:3000',
	'http://localhost:3001',
	'http://localhost:3002',
	'http://127.0.0.1:3000',
	'http://127.0.0.1:3001',
	'http://127.0.0.1:3002',
	'https://app.riwaayathreads.com',
]

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = True  # For local dev ease
CORS_ALLOW_CREDENTIALS = True
