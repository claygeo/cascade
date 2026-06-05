"""Test bootstrap: provide required settings via env before app modules import."""
import os

from cryptography.fernet import Fernet

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret-please-change-0123456789abcd")
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("OPENROUTER_API_KEY", "test-server-key")
