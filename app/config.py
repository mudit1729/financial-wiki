import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    raw_database_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'financial_wiki.db'}")
    if raw_database_url.startswith("postgres://"):
        raw_database_url = raw_database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif raw_database_url.startswith("postgresql://"):
        raw_database_url = raw_database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    SQLALCHEMY_DATABASE_URI = raw_database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
    STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", BASE_DIR / "data")).resolve()
    UPLOAD_FOLDER = STORAGE_ROOT / "raw" / "company_documents"
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024))
    STOOQ_BASE_URL = os.environ.get("STOOQ_BASE_URL", "https://stooq.com/q/d/l/")
    STOOQ_API_KEY = os.environ.get("STOOQ_API_KEY")
    RAG_MAX_CHUNKS = int(os.environ.get("RAG_MAX_CHUNKS", 8))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


def get_config(name=None):
    selected = name or os.environ.get("FLASK_ENV", "development")
    if selected == "testing":
        return TestConfig
    return Config
