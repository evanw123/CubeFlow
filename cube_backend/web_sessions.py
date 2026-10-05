from __future__ import annotations

import re
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator


SESSION_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
DEFAULT_SESSION_TTL_SECONDS = 2 * 60 * 60


@dataclass
class WebSession:
    session_id: str
    state: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    commands: list[dict[str, Any]] = field(default_factory=list)
    runtime: dict[str, Any] = field(default_factory=dict)
    last_access_monotonic: float = field(default_factory=time.monotonic)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def touch(self) -> None:
        self.last_access_monotonic = time.monotonic()


_ACTIVE_WEB_SESSION: ContextVar[WebSession | None] = ContextVar(
    "cubeflow_active_web_session",
    default=None,
)


def validate_session_id(session_id: str) -> str:
    normalized = str(session_id or "").strip().lower()
    if not SESSION_ID_PATTERN.fullmatch(normalized):
        raise ValueError("Invalid CubeFlow session identifier.")
    return normalized


def get_active_web_session() -> WebSession | None:
    return _ACTIVE_WEB_SESSION.get()


class WebSessionStore:
    def __init__(self, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS) -> None:
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._sessions: dict[str, WebSession] = {}
        self._lock = threading.RLock()

    def get_or_create(self, session_id: str) -> WebSession:
        normalized = validate_session_id(session_id)
        with self._lock:
            self._expire_locked()
            session = self._sessions.get(normalized)
            if session is None:
                session = WebSession(session_id=normalized)
                self._sessions[normalized] = session
            session.touch()
            return session

    def remove(self, session_id: str) -> None:
        normalized = validate_session_id(session_id)
        with self._lock:
            self._sessions.pop(normalized, None)

    def count(self) -> int:
        with self._lock:
            self._expire_locked()
            return len(self._sessions)

    @contextmanager
    def activate(self, session_id: str) -> Iterator[WebSession]:
        session = self.get_or_create(session_id)
        token = _ACTIVE_WEB_SESSION.set(session)
        try:
            yield session
        finally:
            _ACTIVE_WEB_SESSION.reset(token)

    def _expire_locked(self) -> None:
        cutoff = time.monotonic() - self.ttl_seconds
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.last_access_monotonic < cutoff
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)


WEB_SESSION_STORE = WebSessionStore()
