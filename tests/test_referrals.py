from types import SimpleNamespace

from core.services.referrals import (
    INVITEE_BONUS_DAYS,
    REFERRAL_BONUS_DAYS,
    parse_referral_key,
    referral_code_for,
)


def test_referral_code_for():
    assert referral_code_for(SimpleNamespace(panel_user_key=42)) == "nv42"


def test_parse_referral_key_variants():
    assert parse_referral_key("nv42") == "42"
    assert parse_referral_key("42") == "42"
    assert parse_referral_key("NV99") == "99"
    assert parse_referral_key("https://ninavpn.store/?ref=nv7") == "7"
    assert parse_referral_key("https://ninavpn.store/?ref=nv7&x=1") == "7"
    assert parse_referral_key("  nv12  ") == "12"
    assert parse_referral_key("") == ""


def test_bonus_days():
    assert REFERRAL_BONUS_DAYS == 7
    assert INVITEE_BONUS_DAYS == 7
