from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"

load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(BASE_DIR / ".env", override=False)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{(DATA_DIR / 'store.db').as_posix()}"
DATABASE_ECHO = os.getenv("DATABASE_ECHO", "0") == "1"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# LLM provider: openai (OpenAI-compatible API), qwen (local model), auto, disabled.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL", "https://api.timeweb.ai/v1"
).strip().rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "dashscope/qwen3.5-flash").strip()
LLM_ENABLE_THINKING = {
    "true": True,
    "false": False,
}.get(os.getenv("LLM_ENABLE_THINKING", "").strip().lower())
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "20"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "160"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_FAILURE_COOLDOWN = float(os.getenv("LLM_FAILURE_COOLDOWN", "30"))
LLM_SITE_URL = os.getenv("LLM_SITE_URL", "").strip()
LLM_APP_NAME = os.getenv("LLM_APP_NAME", "where-is-the-milk").strip()

# Local Qwen is an optional alternative to the API provider.
QWEN_MODEL_ID = os.getenv("QWEN_MODEL_ID", "Qwen/Qwen3-0.6B")
QWEN_ENABLED = os.getenv("QWEN_ENABLED", "auto").strip().lower()
QWEN_PRELOAD = os.getenv("QWEN_PRELOAD", "1").strip().lower() in {"1", "true", "yes", "on"}
QWEN_MAX_NEW_TOKENS = int(os.getenv("QWEN_MAX_NEW_TOKENS", "96"))
QWEN_DEVICE = os.getenv("QWEN_DEVICE", "auto").strip().lower()
QWEN_CACHE_DIR = os.getenv("QWEN_CACHE_DIR") or None

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
