"""Live VPN node locations for the NinaVPN cabinet (from 3x-ui XUI_NODES)."""
from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any, Optional, Sequence
from urllib.parse import unquote, urlparse

import httpx

from config import XuiNodeConfig, settings, xui_nodes_from_settings
from core.services.inbound_protocols import (
    fetch_protocols_for_nodes,
    format_protocol_stack,
    stack_from_share_uri,
)
from core.services.network_catalog import list_locations as list_catalog_locations
from services.server_status import ping_xui_node_ms

log = logging.getLogger(__name__)

_cache_at: float = 0.0
_cache_rows: list[dict[str, Any]] = []
# Sticky protocol stacks — survive short panel blips; refreshed with a hard timeout
_proto_cache: dict[str, list[str]] = {}
_proto_cache_at: float = 0.0
_PROTO_CACHE_TTL = 600.0  # 10 min
_PROTO_FETCH_BUDGET = 2.8  # never block /locations longer than this


def _cache_ttl() -> float:
    try:
        return float(getattr(settings, "SERVER_STATUS_CACHE_SEC", 90) or 90)
    except Exception:
        return 90.0


def _split_flag_city(label: str, flag: str, city: str) -> tuple[str, str]:
    """Prefer explicit flag/city; else peel leading emoji from label like '🇫🇮 Helsinki'."""
    import re

    f = (flag or "").strip()
    c = (city or "").strip()
    lab = (label or "").strip()
    m = re.match(
        r"^("
        r"[\U0001F1E0-\U0001F1FF]{2}"  # regional flags
        r"|[\U0001F300-\U0001FAFF]"  # misc symbols / new emoji
        r"|🌐"
        r")\s*(.+)$",
        lab,
    )
    if m:
        emoji, rest = m.group(1), m.group(2).strip()
        if not f or f == "🌐":
            f = emoji
        if not c or c == lab:
            c = rest or lab
    if not f:
        f = "🌐"
    if not c:
        c = lab or "Node"
    return f, c


def node_to_location_base(node: XuiNodeConfig) -> dict[str, Any]:
    flag, city = _split_flag_city(node.label or "", node.flag or "", node.city or "")
    return {
        "id": node.id or node.label,
        "flag": flag,
        "city": city,
        "country": node.country or "",
        "region": node.region or "",
        "protocol": "VLESS",
        "protocols": ["VLESS"],
        "label": node.label,
    }


async def list_live_locations(*, hide_offline: bool = True) -> list[dict[str, Any]]:
    """
    Locations for GET /network/locations.
    Prefer live XUI_NODES + HTTP ping to panel; fall back to marketing catalog.
    """
    global _cache_at, _cache_rows
    now = time.monotonic()
    if _cache_rows and (now - _cache_at) < _cache_ttl():
        rows = list(_cache_rows)
        if hide_offline:
            rows = [r for r in rows if r.get("status") == "online"]
        return rows

    nodes = xui_nodes_from_settings(settings)
    if not nodes:
        # Marketing fallback — always "online", no latency
        out = []
        for loc in list_catalog_locations():
            out.append(
                {
                    **loc,
                    "status": "online",
                    "latency_ms": None,
                }
            )
        _cache_rows = out
        _cache_at = now
        return list(out)

    async def _one(node: XuiNodeConfig) -> dict[str, Any]:
        base = node_to_location_base(node)
        ms: Optional[float] = None
        try:
            # Cap per-node probe so one dead panel cannot stall the whole list
            ms = await asyncio.wait_for(ping_xui_node_ms(node), timeout=3.2)
        except Exception as e:
            log.debug("ping node %s: %s", node.id, e)
        if ms is None:
            return {**base, "status": "offline", "latency_ms": None}
        return {**base, "status": "online", "latency_ms": int(round(ms))}

    rows = list(await asyncio.gather(*[_one(n) for n in nodes]))

    global _proto_cache, _proto_cache_at
    proto_map: dict[str, list[str]] = dict(_proto_cache)
    now_mono = time.monotonic()
    need_proto = (now_mono - _proto_cache_at) > _PROTO_CACHE_TTL or not _proto_cache
    if need_proto:
        try:
            fresh = await asyncio.wait_for(
                fetch_protocols_for_nodes(nodes),
                timeout=_PROTO_FETCH_BUDGET,
            )
            if fresh:
                _proto_cache = {**_proto_cache, **fresh}
                _proto_cache_at = now_mono
                proto_map = dict(_proto_cache)
        except Exception as e:
            log.warning("protocol enrich skipped: %s", e)

    for row in rows:
        stack = list(proto_map.get(str(row.get("id")) or "", []) or [])
        if not stack:
            stack = ["VLESS"]
        row["protocols"] = stack
        row["protocol"] = format_protocol_stack(stack)
    # Fastest first
    rows.sort(
        key=lambda r: (
            0 if r.get("status") == "online" else 1,
            r.get("latency_ms") is None,
            r.get("latency_ms") or 10_000,
        )
    )
    _cache_rows = rows
    _cache_at = now
    if hide_offline:
        return [r for r in rows if r.get("status") == "online"]
    return list(rows)


def _decode_subscription_body(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="ignore").strip()
    if "vless://" in text or "vmess://" in text or "trojan://" in text:
        return text
    try:
        pad = "=" * (-len(text) % 4)
        decoded = base64.b64decode(text + pad)
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return text


def sanitize_share_uri(uri: str) -> str:
    """
    Drop ML-KEM / pqv blobs that inflate Reality links to ~3KB.
    Android Uri.parse + in-app VPN choke on those query values.
    """
    u = (uri or "").strip()
    if not u or "://" not in u or "?" not in u:
        return u
    try:
        head, rest = u.split("?", 1)
        query, frag = (rest.split("#", 1) + [""])[:2]
        kept: list[str] = []
        for part in query.split("&"):
            if not part:
                continue
            key = part.split("=", 1)[0].lower()
            # pqv / pqc / mlkem — post-quantum extras unused by our sing-box bridge
            if key in {"pqv", "pqc", "mlkem", "pq"}:
                continue
            if len(part) > 800:
                continue
            kept.append(part)
        out = head
        if kept:
            out += "?" + "&".join(kept)
        if frag:
            out += "#" + frag
        return out
    except Exception:
        return u


async def expand_share_links(links: list[str]) -> list[str]:
    """Turn http(s) subscription URLs into vless:// lines; keep direct URIs."""
    out: list[str] = []
    verify = bool(getattr(settings, "XUI_SUBSCRIPTION_FETCH_VERIFY_SSL", False))
    http_links: list[str] = []
    for link in links:
        L = (link or "").strip()
        if not L:
            continue
        if L.startswith(("vless://", "vmess://", "trojan://", "ss://")):
            out.append(sanitize_share_uri(L))
        elif L.startswith("http://") or L.startswith("https://"):
            http_links.append(L)
        else:
            out.append(L)

    if http_links:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(4.0, connect=2.0),
            follow_redirects=True,
            verify=verify,
        ) as client:

            async def _fetch(url: str) -> list[str]:
                try:
                    res = await client.get(url)
                    res.raise_for_status()
                    body = _decode_subscription_body(res.content)
                    found: list[str] = []
                    for line in body.splitlines():
                        line = line.strip()
                        if line.startswith(("vless://", "vmess://", "trojan://", "ss://")):
                            found.append(sanitize_share_uri(line))
                    return found
                except Exception as e:
                    log.warning("expand_share_links fetch failed: %s", e)
                    return []

            nested = await asyncio.gather(*[_fetch(u) for u in http_links])
            for batch in nested:
                out.extend(batch)
    # unique preserve order (prefer shorter / sanitized form)
    seen_hosts: set[str] = set()
    uniq: list[str] = []
    for u in out:
        key = _uri_host(u) + "|" + _uri_remark(u)
        if key in seen_hosts:
            continue
        seen_hosts.add(key)
        uniq.append(u)
    return uniq


def _uri_remark(uri: str) -> str:
    if "#" in uri:
        return unquote(uri.split("#", 1)[1]).strip()
    return ""


def _uri_host(uri: str) -> str:
    try:
        # vless://uuid@host:port?...
        rest = uri.split("://", 1)[1]
        authority = rest.split("?", 1)[0].split("#", 1)[0]
        if "@" in authority:
            authority = authority.split("@", 1)[1]
        host = authority.rsplit(":", 1)[0]
        return host.strip("[]").lower()
    except Exception:
        return ""


def _uri_host_port(uri: str) -> str:
    """host:port identity so USA+Georgia on the same IP stay distinct."""
    try:
        rest = uri.split("://", 1)[1]
        authority = rest.split("?", 1)[0].split("#", 1)[0]
        if "@" in authority:
            authority = authority.split("@", 1)[1]
        return authority.strip().lower()
    except Exception:
        return _uri_host(uri)


_LOCATION_ALIASES: dict[str, set[str]] = {
    "turkey": {"turkey", "turkish", "tr", "istanbul"},
    "turkish": {"turkey", "turkish", "tr", "istanbul"},
    "usa": {
        "usa",
        "us",
        "america",
        "united-states",
        "unitedstates",
        "nyc",
        "new-york",
        "newyork",
        "los-angeles",
        "losangeles",
    },
    "us": {"usa", "us", "america", "nyc", "new-york"},
    "georgia": {"georgia", "ge", "tbilisi"},
    "germany": {"germany", "de", "frankfurt", "berlin"},
    "finland": {"finland", "fi", "helsinki"},
    "russia": {"russia", "ru", "moscow"},
}

# Launch / unpaid access: Germany, Finland, Turkey, Russia, USA, Georgia
WELCOME_LOCATION_KEYS: tuple[str, ...] = (
    "germany",
    "finland",
    "turkey",
    "russia",
    "usa",
    "georgia",
)


def _normalize_location_token(raw: str) -> str:
    """Strip flag emoji / subscription suffixes → comparable token (e.g. 'turkish')."""
    import re

    s = (raw or "").strip()
    # peel leading regional-indicator / emoji flag
    s = re.sub(
        r"^("
        r"[\U0001F1E0-\U0001F1FF]{2}"
        r"|[\U0001F300-\U0001FAFF]"
        r"|🌐"
        r")\s*",
        "",
        s,
    )
    # drop panel email / expiry tails: USA-sigma…|⏳28D
    s = s.split("|", 1)[0].strip()
    s = re.split(r"[-_]\s*sigma", s, maxsplit=1, flags=re.I)[0].strip()
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s).strip().lower()
    return s.replace(" ", "-") if s else ""


def _tokens_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    aa = _LOCATION_ALIASES.get(a, {a})
    bb = _LOCATION_ALIASES.get(b, {b})
    return bool(aa & bb)


def _node_name_tokens(node: XuiNodeConfig) -> list[str]:
    out: list[str] = []
    for raw in (node.city, node.label, node.id, node.country):
        tok = _normalize_location_token(raw or "")
        if tok:
            out.append(tok)
    return out


def node_in_locations(node: XuiNodeConfig, location_keys: Sequence[str]) -> bool:
    keys = {str(k).strip().lower() for k in location_keys if k}
    if not keys:
        return False
    for tok in _node_name_tokens(node):
        for key in keys:
            if _tokens_match(tok, key):
                return True
    return False


def filter_nodes_by_locations(
    nodes: list[XuiNodeConfig], location_keys: Sequence[str]
) -> list[XuiNodeConfig]:
    return [n for n in nodes if node_in_locations(n, location_keys)]


def config_row_in_locations(row: dict[str, Any], location_keys: Sequence[str]) -> bool:
    keys = {str(k).strip().lower() for k in location_keys if k}
    if not keys:
        return False
    for raw in (row.get("city"), row.get("id"), row.get("country"), row.get("label")):
        tok = _normalize_location_token(str(raw or ""))
        if not tok:
            continue
        for key in keys:
            if _tokens_match(tok, key):
                return True
    return False


def filter_config_nodes(
    rows: list[dict[str, Any]], location_keys: Sequence[str]
) -> list[dict[str, Any]]:
    return [r for r in rows if config_row_in_locations(r, location_keys)]


def match_uri_to_node(
    uri: str, nodes: list[XuiNodeConfig], *, used_ids: Optional[set[str]] = None
) -> Optional[XuiNodeConfig]:
    """
    Map a vless URI to an XUI_NODES entry.

    Prefer remark/city matching. Panel-host matching is only used when that host
    is unique among nodes — shared central panels (USA+Georgia on one IP) must
    not collapse to the first node.
    """
    used_ids = used_ids or set()
    remark_tok = _normalize_location_token(_uri_remark(uri))
    host = _uri_host(uri)

    # 1) Name / alias match (skip already-used nodes)
    if remark_tok:
        for node in nodes:
            if node.id in used_ids:
                continue
            if any(_tokens_match(remark_tok, t) for t in _node_name_tokens(node)):
                return node

    # 2) Panel host — only if exactly one unused node owns that host
    host_owners: list[XuiNodeConfig] = []
    for node in nodes:
        if node.id in used_ids:
            continue
        try:
            panel_host = (urlparse(node.url).hostname or "").lower()
        except Exception:
            panel_host = ""
        if host and panel_host and host == panel_host:
            host_owners.append(node)
    if len(host_owners) == 1:
        return host_owners[0]
    return None


def _display_from_uri(uri: str) -> tuple[str, str]:
    remark = _uri_remark(uri) or "Server"
    flag, city = _split_flag_city(remark, "", "")
    city = _normalize_location_token(city).replace("-", " ").title() or city
    # Prefer friendly aliases for UI
    low = city.lower()
    if low in {"turkish", "tr"}:
        city = "Turkey"
    elif low in {"usa", "us"}:
        city = "USA"
    return flag, city


def _prefer_connect_uri(uris: list[str]) -> str:
    """Native tunnel prefers VLESS; keep first VLESS, else first URI."""
    for u in uris:
        if u.lower().startswith("vless://"):
            return u
    return uris[0] if uris else ""


def _attach_protocol_fields(row: dict[str, Any], uris: list[str], panel_stack: Optional[list[str]] = None) -> None:
    stack: list[str] = list(panel_stack or [])
    for u in uris:
        stack.extend(stack_from_share_uri(u))
    if not stack:
        stack = ["VLESS"]
    label = format_protocol_stack(stack)
    row["protocol"] = label
    row["protocols"] = [p.strip() for p in label.split("·") if p.strip()]


async def build_node_configs(stored_links: list[str]) -> list[dict[str, Any]]:
    """
    Map subscription/share links to cabinet nodes for the native VPN app.
    Returns [{id, flag, city, uri, protocol, protocols}, ...]
    """
    nodes = xui_nodes_from_settings(settings)
    uris = await expand_share_links(stored_links)
    if not uris:
        return []

    proto_map: dict[str, list[str]] = {}
    if nodes:
        try:
            proto_map = await fetch_protocols_for_nodes(nodes)
        except Exception as e:
            log.warning("build_node_configs protocols: %s", e)

    # Collect all URIs per location (multi-protocol inbounds share one city)
    by_node: dict[str, dict[str, Any]] = {}
    used_endpoints: set[str] = set()
    orphan_uris: list[str] = []

    if nodes:
        claimed: set[str] = set()
        for uri in uris:
            node = match_uri_to_node(uri, nodes, used_ids=set())
            if not node:
                orphan_uris.append(uri)
                continue
            # Allow many URIs per node id (different schemes / sibling inbounds)
            bucket = by_node.get(node.id)
            if not bucket:
                flag, city = _split_flag_city(node.label or "", node.flag or "", node.city or "")
                bucket = {
                    "id": node.id,
                    "flag": flag,
                    "city": city,
                    "uris": [],
                }
                by_node[node.id] = bucket
            if uri not in bucket["uris"]:
                bucket["uris"].append(uri)
            claimed.add(uri)
            used_endpoints.add(_uri_host_port(uri))

        result: list[dict[str, Any]] = []
        # Stable order = XUI_NODES order
        for node in nodes:
            bucket = by_node.get(node.id)
            if not bucket:
                continue
            node_uris: list[str] = bucket["uris"]
            row = {
                "id": bucket["id"],
                "flag": bucket["flag"],
                "city": bucket["city"],
                "uri": _prefer_connect_uri(node_uris),
            }
            _attach_protocol_fields(row, node_uris, proto_map.get(node.id))
            result.append(row)

        for i, uri in enumerate(orphan_uris):
            if uri in claimed:
                continue
            ep = _uri_host_port(uri)
            if ep and ep in used_endpoints:
                # Same host:port already represented — merge scheme into matching row if any
                continue
            flag, city = _display_from_uri(uri)
            row = {
                "id": f"link-{i + 1}",
                "flag": flag,
                "city": city,
                "uri": uri,
            }
            _attach_protocol_fields(row, [uri], None)
            used_endpoints.add(ep)
            result.append(row)
        return result

    result = []
    for i, uri in enumerate(uris):
        flag, city = _display_from_uri(uri)
        row = {"id": f"link-{i + 1}", "flag": flag, "city": city, "uri": uri}
        _attach_protocol_fields(row, [uri], None)
        result.append(row)
    return result
