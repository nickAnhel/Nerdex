import sys
import os
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]

if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


TEST_ENV_DEFAULTS = {
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "test",
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "CORS_ALLOWED_HOSTS": '["*"]',
    "PROJECT_TITLE": "Nerdex API Tests",
    "PROJECT_DESCRIPTION": "Test configuration",
    "PROJECT_VERSION": "0.1.0",
    "PROJECT_DEBUG": "true",
    "LOG_LEVEL": "DEBUG",
    "LOG_FORMAT": "plain",
    "SLOW_REQUEST_THRESHOLD_MS": "1000",
    "SLOW_RECOMMENDATION_THRESHOLD_MS": "1000",
    "ADMIN_SECRET_KEY": "test-secret",
    "ADMIN_SESSION_EXPIRE_MINUTES": "15",
    "WS_ALLOWED_HOSTS": '["*"]',
    "STORAGE_ENDPOINT_URL": "http://localhost:9000",
    "STORAGE_REGION": "test",
    "STORAGE_ACCESS_KEY": "test",
    "STORAGE_SECRET_KEY": "test",
    "STORAGE_PRIVATE_BUCKET": "test-private",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_DB": "0",
    "REDIS_SOCKETIO_URL": "redis://localhost:6379/2",
    "CELERY_BROKER_URL": "redis://localhost:6379/0",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/1",
    "CELERY_MEDIA_QUEUE_NAME": "media",
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "password",
    "NEO4J_DATABASE": "neo4j",
}


for name, value in TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(name, value)
