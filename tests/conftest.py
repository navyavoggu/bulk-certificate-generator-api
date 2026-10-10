import pytest
from fastapi.testclient import TestClient
from app.main import create_app

@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.db"
    storage = tmp_path / "certificates"
    return create_app(f"sqlite:///{db_path.as_posix()}", storage)

@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def payload():
    return {
        "event_name": "Python Fundamentals",
        "issuer_name": "Example Institute",
        "certificate_date": "2026-10-09",
        "recipients": [
            {"name": "Asha Rao", "email": "asha@example.com"},
            {"name": "Ravi Kumar", "email": "ravi@example.com"}
        ]
    }
