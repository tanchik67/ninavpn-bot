"""Smoke tests for Telegram Login Widget HMAC (no network)."""
from __future__ import annotations

import hashlib
import hmac
import time

from core.services.oauth_verify import OAuthVerifyError, verify_telegram_login
from core.settings import saas_settings


def test_telegram_login_hash_ok(monkeypatch):
    token = "123456:ABC-DEF"
    monkeypatch.setattr(saas_settings, "BOT_TOKEN", token)
    monkeypatch.setattr(saas_settings, "TELEGRAM_AUTH_MAX_AGE_SEC", 86400)

    auth_date = int(time.time())
    payload = {
        "id": 42,
        "first_name": "Nina",
        "username": "nina",
        "auth_date": auth_date,
    }
    pairs = [f"{k}={payload[k]}" for k in sorted(payload.keys())]
    data_check = "\n".join(pairs)
    secret = hashlib.sha256(token.encode()).digest()
    payload["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

    out = verify_telegram_login(payload)
    assert out["id"] == 42
    assert out["username"] == "nina"


def test_telegram_login_bad_hash(monkeypatch):
    monkeypatch.setattr(saas_settings, "BOT_TOKEN", "123456:ABC")
    monkeypatch.setattr(saas_settings, "TELEGRAM_AUTH_MAX_AGE_SEC", 86400)
    payload = {
        "id": 1,
        "first_name": "X",
        "auth_date": int(time.time()),
        "hash": "0" * 64,
    }
    try:
        verify_telegram_login(payload)
        assert False, "expected OAuthVerifyError"
    except OAuthVerifyError as e:
        assert e.code == "invalid_telegram_auth"
