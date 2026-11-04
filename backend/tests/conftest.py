import os
from pathlib import Path

import pytest

test_url = os.environ.get("TEST_DATABASE_URL", "")
if not test_url or not test_url.rsplit("/", 1)[-1].startswith("evidencelens_test_"):
    raise RuntimeError("Set TEST_DATABASE_URL to a dedicated PostgreSQL database named evidencelens_test_*. Tests reset that database's tables.")
os.environ["DATABASE_URL"] = test_url
os.environ["MODEL_MODE"] = "fixture"

from fastapi.testclient import TestClient
from sqlalchemy import delete
from app.config import settings
from app.db import Session
from app.main import app
from app.models import Base


@pytest.fixture(autouse=True)
def clean_database(tmp_path, monkeypatch):
    original_settings = vars(settings).copy()
    object.__setattr__(settings, "storage_dir", tmp_path / "artifacts")
    with Session.begin() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    for key, value in original_settings.items():
        object.__setattr__(settings, key, value)


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
