from __future__ import annotations

import os
import tempfile
from pathlib import Path

TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="where-is-the-milk-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_DB_DIR / 'test.db').as_posix()}"
os.environ["LLM_PROVIDER"] = "disabled"
os.environ["QWEN_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
