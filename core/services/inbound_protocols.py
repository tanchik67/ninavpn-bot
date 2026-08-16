"""Derive display protocol stacks from 3x-ui inbounds / share URIs."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

from config import XuiNodeConfig

log = logging.getLogger(__name__)

_PROTOCOL_LABELS = {
    "vless": "VLESS",
    "vmess": "VMess",
    "trojan": "Trojan",
    "shadowsocks": "Shadowsocks",
    "ss": "Shadowsocks",
    "wireguard": "WireGuard",
    "hysteria": "Hysteria",
    "hysteria2": "Hysteria2",
    "tuic": "TUIC",
    "http": "HTTP",
    "socks": "SOCKS",
    "mixed": "Mixed",
    "dokodemo-door": "Dokodemo",
}

_NETWORK_LABELS = {
    "tcp": "TCP",
    "raw": "TCP",
    "ws": "WebSocket",
    "websocket": "WebSocket",
    "grpc": "gRPC",
    "gun": "gRPC",
    "h2": "HTTP/2",
    "http": "HTTP/2",
    "httpupgrade": "HTTPUpgrade",
    "xhttp": "xHTTP",
    "splithttp": "SplitHTTP",
    "kcp": "mKCP",
    "quic": "QUIC",
}

# Prefer this order in the UI subtitle
_ORDER = [
    "VLESS",
    "VMess",
    "Trojan",
    "Shadowsocks",
    "SOCKS",
    "Mixed",
    "Hysteria2",
    "Hysteria",
    "TUIC",
    "WireGuard",
    "Reality",
    "TLS",
    "XTLS-Vision",
    "gRPC",
    "WebSocket",
    "xHTTP",
    "HTTPUpgrade",
    "HTTP/2",
    "TCP",
    "QUIC",
    "mKCP",
]


def protocol_label(raw: str) -> str:
    key = (raw or "").strip().lower()
    return _PROTOCOL_LABELS.get(key) or (raw.strip().upper() if raw else "")


def network_label(raw: str) -> str:
    key = (raw or "").strip().lower()
    return _NETWORK_LABELS.get(key) or (raw.strip().upper() if raw else "")


def _uniq(parts: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
    rank = {name: i for i, name in enumerate(_ORDER)}
    out.sort(key=lambda x: (rank.get(x, 500), x.lower()))
    return out


def format_protocol_stack(parts: list[str]) -> str:
    return " · ".join(_uniq(parts))


def _parse_jsonish(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def stack_from_inbound(
    protocol: str,
    stream_settings: Any = None,
    settings: Any = None,
) -> list[str]:
    """Build labels from a 3x-ui inbound row."""
    parts: list[str] = []
    proto = (protocol or "").strip().lower()
    st = _parse_jsonish(settings)
    ss = _parse_jsonish(stream_settings)

    if proto == "mixed":
        # 3x-ui "mixed" is often a local SOCKS helper
        if isinstance(st.get("accounts"), list):
            parts.append("SOCKS")
        else:
            parts.append("Mixed")
    elif proto:
        parts.append(protocol_label(proto))

    security = str(ss.get("security") or "").strip().lower()
    if security == "reality":
        parts.append("Reality")
    elif security in {"tls", "xtls"}:
        parts.append("TLS")

    net = str(ss.get("network") or ss.get("type") or "").strip().lower()
    if net:
        parts.append(network_label(net))

    # Client flow (xtls-rprx-vision) if present on inbound defaults / clients
    flows: set[str] = set()
    for cl in st.get("clients") or []:
        if isinstance(cl, dict) and cl.get("flow"):
            flows.add(str(cl["flow"]).lower())
    if any("vision" in f for f in flows):
        parts.append("XTLS-Vision")

    return _uniq(parts)


def stack_from_share_uri(uri: str) -> list[str]:
    """Infer stack from vless:// / vmess:// / trojan:// / ss:// share link."""
    u = (uri or "").strip()
    if "://" not in u:
        return []
    scheme = u.split("://", 1)[0].lower()
    parts = [protocol_label(scheme)] if scheme else []
    try:
        # vless://uuid@host:port?type=tcp&security=reality#remark
        q = ""
        if "?" in u:
            q = u.split("?", 1)[1].split("#", 1)[0]
        params = {k.lower(): (v[0] if v else "") for k, v in parse_qs(q, keep_blank_values=True).items()}
        sec = (params.get("security") or "").lower()
        if sec == "reality":
            parts.append("Reality")
        elif sec in {"tls", "xtls"}:
            parts.append("TLS")
        net = (params.get("type") or params.get("network") or "").lower()
        if net:
            parts.append(network_label(net))
        flow = (params.get("flow") or "").lower()
        if "vision" in flow:
            parts.append("XTLS-Vision")
    except Exception:
        pass
    return _uniq(parts)


def _inbound_matches_node(remark: str, node: XuiNodeConfig) -> bool:
    from core.services.network_locations import (
        _node_name_tokens,
        _normalize_location_token,
        _tokens_match,
    )

    remark_tok = _normalize_location_token(remark or "")
    if not remark_tok:
        return False
    return any(_tokens_match(remark_tok, t) for t in _node_name_tokens(node))


async def fetch_protocols_for_nodes(nodes: list[XuiNodeConfig]) -> dict[str, list[str]]:
    """
    node.id → protocol stack labels from 3x-ui.
    Groups by panel URL (one login + inbounds/list per host).
    """
    if not nodes:
        return {}

    from services.xui_panel import XuiPanel

    by_host: dict[str, list[XuiNodeConfig]] = {}
    for n in nodes:
        by_host.setdefault(n.url.rstrip("/"), []).append(n)

    out: dict[str, list[str]] = {}

    async def _one_panel(host: str, host_nodes: list[XuiNodeConfig]) -> None:
        panel = XuiPanel(host_nodes[0])
        try:
            c = await panel._ensure_session()
            r = await c.get(
                panel._path("/panel/api/inbounds/list"),
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            if r.status_code != 200:
                log.warning("inbounds/list %s → HTTP %s", host, r.status_code)
                return
            data = r.json()
            inbounds = data.get("obj") if isinstance(data, dict) else None
            if not isinstance(inbounds, list):
                return

            by_id: dict[int, dict[str, Any]] = {}
            for ib in inbounds:
                if not isinstance(ib, dict):
                    continue
                try:
                    by_id[int(ib.get("id"))] = ib
                except Exception:
                    continue

            for node in host_nodes:
                stacks: list[str] = []
                # Primary inbound for this location
                primary = by_id.get(int(node.inbound_id or 0))
                if primary:
                    stacks.extend(
                        stack_from_inbound(
                            str(primary.get("protocol") or ""),
                            primary.get("streamSettings"),
                            primary.get("settings"),
                        )
                    )
                # Extra inbounds on the same panel that belong to this location
                for ib in inbounds:
                    if not isinstance(ib, dict):
                        continue
                    try:
                        iid = int(ib.get("id"))
                    except Exception:
                        continue
                    if iid == int(node.inbound_id or 0):
                        continue
                    if not _inbound_matches_node(str(ib.get("remark") or ""), node):
                        continue
                    stacks.extend(
                        stack_from_inbound(
                            str(ib.get("protocol") or ""),
                            ib.get("streamSettings"),
                            ib.get("settings"),
                        )
                    )
                if stacks:
                    out[node.id] = _uniq(stacks)
                else:
                    out[node.id] = ["VLESS"]
        except Exception as e:
            log.warning("fetch protocols [%s]: %s", host, e)
            for node in host_nodes:
                out.setdefault(node.id, ["VLESS"])
        finally:
            client = getattr(panel, "_client", None)
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    pass
                panel._client = None

    await asyncio.gather(*[_one_panel(h, ns) for h, ns in by_host.items()])
    return out
