"""Shared backend test fixtures with isolated runtime storage."""

import os
import shutil
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

TEST_RUNTIME_DIR = Path(__file__).resolve().parent / "_tmp"
TEST_DB_PATH = TEST_RUNTIME_DIR / "educreate_test.db"
TEST_UPLOAD_DIR = TEST_RUNTIME_DIR / "uploads"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["UPLOAD_DIR"] = str(TEST_UPLOAD_DIR)
os.environ["DATABASE_AUTO_CREATE"] = "true"

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_storage() -> Generator[None, None, None]:
    """Give each test a clean database and upload directory."""
    TEST_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if TEST_UPLOAD_DIR.exists():
        shutil.rmtree(TEST_UPLOAD_DIR)
    TEST_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if TEST_UPLOAD_DIR.exists():
        shutil.rmtree(TEST_UPLOAD_DIR)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """FastAPI test client that runs lifespan hooks."""
    with TestClient(app) as test_client:
        yield test_client
