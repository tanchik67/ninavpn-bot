"""Tests for multi-link config persistence helpers."""
from __future__ import annotations

from types import SimpleNamespace

from core.services.config_links import (
    apply_links_to_subscription,
    normalize_config_links,
    read_links_from_subscription,
)


def test_normalize_unique_order():
    assert normalize_config_links(
        ["https://a/sub/1", "vless://x", "https://a/sub/1"],
        "vless://y",
    ) == ["https://a/sub/1", "vless://x", "vless://y"]


def test_apply_and_read_roundtrip():
    sub = SimpleNamespace(config_link=None, config_link_extra=None, config_links=None)
    # duck-type without SQLAlchemy column → list assignment
    links = apply_links_to_subscription(
        sub,
        [
            "vless://us",
            "vless://de",
            "vless://fi",
            "https://panel/sub/abc",
        ],
        primary="https://panel/sub/abc",
    )
    assert sub.config_link == "https://panel/sub/abc"
    assert sub.config_link_extra == "vless://us"
    assert len(links) == 4
    assert read_links_from_subscription(sub)[0] == "https://panel/sub/abc"
    assert "vless://fi" in read_links_from_subscription(sub)
