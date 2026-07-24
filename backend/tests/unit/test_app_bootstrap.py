from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app import main
from app.core import database


async def test_lifespan_rejects_default_secret_in_non_debug(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main.settings, "DEBUG", False)
    monkeypatch.setattr(main.settings, "SECRET_KEY", "change-me-in-production-use-openssl-rand-hex-32")

    with pytest.raises(RuntimeError):
        async with main.lifespan(FastAPI()):
            pass


async def test_lifespan_calls_init_db_when_secret_is_safe(monkeypatch: pytest.MonkeyPatch):
    called = {"init_db": False}

    async def fake_init_db():
        called["init_db"] = True

    monkeypatch.setattr(main.settings, "DEBUG", False)
    monkeypatch.setattr(main.settings, "SECRET_KEY", "safe-secret")
    monkeypatch.setattr(main, "init_db", fake_init_db)

    async with main.lifespan(FastAPI()):
        assert called["init_db"] is True


async def test_health_check_returns_status_payload():
    assert await main.health_check() == {"status": "ok", "version": "0.9.8"}


async def test_init_db_skips_create_all_when_not_debug(monkeypatch: pytest.MonkeyPatch):
    called = {"begin": False}

    class FakeEngine:
        def begin(self):
            called["begin"] = True
            raise AssertionError("engine.begin should not be called when DEBUG is False")

    monkeypatch.setattr(database.settings, "DEBUG", False)
    monkeypatch.setattr(database, "engine", FakeEngine())

    await database.init_db()
    assert called["begin"] is False


async def test_init_db_runs_create_all_when_debug(monkeypatch: pytest.MonkeyPatch):
    called = {"begin": False, "run_sync": False}

    class FakeConn:
        async def run_sync(self, func):
            called["run_sync"] = True
            assert func == database.Base.metadata.create_all

    class FakeBegin:
        async def __aenter__(self):
            called["begin"] = True
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def begin(self):
            return FakeBegin()

    monkeypatch.setattr(database.settings, "DEBUG", True)
    monkeypatch.setattr(database, "engine", FakeEngine())

    await database.init_db()
    assert called == {"begin": True, "run_sync": True}


async def test_get_db_yields_session_from_factory(monkeypatch: pytest.MonkeyPatch):
    session = SimpleNamespace(name="session")

    class FakeSessionManager:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: FakeSessionManager())

    generator = database.get_db()
    yielded = await anext(generator)
    assert yielded is session

    with pytest.raises(StopAsyncIteration):
        await anext(generator)
