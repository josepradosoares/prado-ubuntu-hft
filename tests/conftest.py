"""Pytest configuration ensuring tests never accidentally read production .env Supabase credentials."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_from_production_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prado_linux.supabase_store._read_dotenv_fallback", lambda: {})
    for key in (
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
