from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import FRONTEND_DIST, QWEN_PRELOAD
from .database import SessionLocal, init_db
from .seed import seed_demo_data
from .services.llm import get_answerer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_demo_data(db)
    logger.info("База готова")
    if QWEN_PRELOAD:
        get_answerer().preload_in_background()
    yield


app = FastAPI(
    title="Where is the milk?",
    description="Визуальный конструктор стеллажей и AI-навигация по магазину",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:

    @app.get("/")
    def root() -> dict:
        return {
            "service": "where-is-the-milk",
            "docs": "/docs",
            "frontend": "соберите frontend: cd frontend && npm install && npm run build",
        }
