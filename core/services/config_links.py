"""Normalize / persist VPN share links on subscriptions (SaaS + bot)."""
from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy import Text as SAText


def normalize_config_links(*parts: Any) -> list[str]:
    """Flatten links from lists / JSON strings / single URLs; unique, order preserved."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, (list, tuple)):
            for x in item:
                _add(x)
            return
        if isinstance(item, str):
            s = item.strip()
            if not s:
                return
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        _add(parsed)
                        return
                except Exception:
                    pass
            if s not in seen:
                seen.add(s)
                out.append(s)
            return

    for p in parts:
        _add(p)
    return out


def links_to_json(links: Sequence[str]) -> Optional[list[str]]:
    norm = normalize_config_links(list(links))
    return norm or None


def apply_links_to_subscription(
    sub: Any, links: Sequence[str], *, primary: str | None = None
) -> list[str]:
    """
    Write primary + legacy extra + full list onto a subscription row.
    primary defaults to first http(s) subscription URL, else first link.
    """
    norm = normalize_config_links(list(links), primary)
    if primary:
        p = primary.strip()
        if p:
            norm = normalize_config_links([p], [x for x in norm if x != p])

    http_first = next(
        (x for x in norm if x.startswith("http://") or x.startswith("https://")), None
    )
    main = http_first or (norm[0] if norm else "")
    rest = [x for x in norm if x != main]
    extra = rest[0] if rest else None

    sub.config_link = main or None
    sub.config_link_extra = extra
    if hasattr(sub, "config_links"):
        _write_config_links_field(sub, norm)
    return norm


def _write_config_links_field(sub: Any, links: list[str]) -> None:
    payload = links or None
    try:
        col = type(sub).config_links.property.columns[0].type
        if isinstance(col, SAText):
            sub.config_links = json.dumps(payload, ensure_ascii=False) if payload else None
            return
    except Exception:
        pass
    sub.config_links = payload


def read_links_from_subscription(sub: Any) -> list[str]:
    """Read all stored links (config_links preferred, else legacy columns)."""
    raw_json = getattr(sub, "config_links", None)
    return normalize_config_links(
        raw_json,
        getattr(sub, "config_link", None),
        getattr(sub, "config_link_extra", None),
    )
