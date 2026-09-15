"""Environment-backed configuration for the Q&M chatbot API."""

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")


def _database_url():
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured.startswith("postgres://"):
        return configured.replace("postgres://", "postgresql://", 1)
    if configured:
        return configured

    sqlite_path = (BACKEND_DIR / "data" / "qm_chatbot.db").as_posix()
    return f"sqlite:///{sqlite_path}"


class Config:
    """Settings shared by local development and production deployments."""

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "development-only-change-me")
    PORT = int(os.getenv("FLASK_PORT", "5000"))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip()
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CONVERSATION_CONTEXT_MESSAGE_LIMIT = int(
        os.getenv("CONVERSATION_CONTEXT_MESSAGE_LIMIT", "20")
    )
    CORS_ORIGINS = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )
