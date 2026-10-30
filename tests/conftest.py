"""Shared test setup.

Runs the API against a throwaway SQLite database with dummy secrets,
so the test suite needs no Postgres and makes no real LLM calls.
"""

import os
import tempfile

_db_dir = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_dir}/test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")

import uuid  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _new_user(client):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectHorse9!"
    res = client.post("/auth/signup", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"email": email, "password": password, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def user(client):
    return _new_user(client)


@pytest.fixture
def other_user(client):
    return _new_user(client)
