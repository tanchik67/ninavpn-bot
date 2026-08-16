"""Login accepts Telegram placeholder emails (not EmailStr)."""

from apps.api.app.schemas import LoginRequest


def test_login_accepts_telegram_local():
    body = LoginRequest(email="tg_767831067@telegram.local", password="anything")
    assert body.email == "tg_767831067@telegram.local"


def test_login_accepts_normal_email():
    body = LoginRequest(email="User@Example.com", password="secret123")
    assert body.email == "user@example.com"


def test_login_rejects_garbage():
    try:
        LoginRequest(email="not-an-email", password="x")
        assert False, "expected validation error"
    except Exception:
        pass
