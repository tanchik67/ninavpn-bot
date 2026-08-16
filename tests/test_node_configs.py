"""Tests for subscription URI → cabinet node mapping."""

from __future__ import annotations

from config import XuiNodeConfig
from core.services.network_locations import (
    _normalize_location_token,
    build_node_configs,
    match_uri_to_node,
)


def _node(**kwargs) -> XuiNodeConfig:
    base = dict(
        url="https://31.76.224.213:2035",
        username="u",
        password="p",
        path_prefix="",
        inbound_id=1,
        subscription_base="",
        sub_port=2096,
        sub_path="",
        client_flow="",
        two_factor_code="",
        label="Node",
        id="n",
        flag="🌐",
        city="City",
        country="",
        region="",
        verify_ssl=None,
    )
    base.update(kwargs)
    return XuiNodeConfig(**base)


SHARED_PANEL = [
    _node(id="us-1", flag="🇺🇸", city="USA", label="🇺🇸 USA"),
    _node(id="ge-1", flag="🇬🇪", city="Georgia", label="🇬🇪 Georgia"),
    _node(id="de-1", flag="🇩🇪", city="Germany", label="🇩🇪 Germany"),
    _node(id="fi-1", flag="🇫🇮", city="Finland", label="🇫🇮 Finland"),
    _node(id="tr-1", flag="🇹🇷", city="Turkey", label="🇹🇷 Turkey"),
    _node(id="ru-1", flag="🇷🇺", city="Russia", label="🇷🇺 Russia"),
]

SAMPLE_URIS = [
    "vless://u@31.76.224.213:29393?security=reality#🇺🇸%20USA-sigma2008_8197588898478%7C%E2%8F%B329D",
    "vless://u@31.76.224.213:50135?security=reality#%F0%9F%87%AC%F0%9F%87%AA%20Georgia",
    "vless://u@2.26.117.89:19649?security=reality#%F0%9F%87%A9%F0%9F%87%AA%20Germany",
    "vless://u@2.27.122.201:13611?security=reality#%F0%9F%87%AB%F0%9F%87%AE%20Finland",
    "vless://u@77.83.245.211:34281?security=reality#%F0%9F%87%B9%F0%9F%87%B7%20Turkish",
]


def test_normalize_strips_flag_and_suffix():
    assert _normalize_location_token("🇺🇸 USA-sigma2008_8197588898478|⏳28D") == "usa"
    assert _normalize_location_token("🇹🇷 Turkish") == "turkish"
    assert _normalize_location_token("🇬🇪 Georgia") == "georgia"


def test_match_prefers_remark_over_shared_panel_host():
    usa = SAMPLE_URIS[0]
    geo = SAMPLE_URIS[1]
    assert match_uri_to_node(usa, SHARED_PANEL).id == "us-1"
    assert match_uri_to_node(geo, SHARED_PANEL).id == "ge-1"
    # second match must not reuse USA when used_ids set
    assert match_uri_to_node(geo, SHARED_PANEL, used_ids={"us-1"}).id == "ge-1"


def test_match_turkish_alias_to_turkey():
    tr = SAMPLE_URIS[4]
    assert match_uri_to_node(tr, SHARED_PANEL).id == "tr-1"


def test_build_node_configs_includes_georgia_and_turkey(monkeypatch):
    import core.services.network_locations as nl

    async def _expand(links):
        return list(SAMPLE_URIS)

    async def _protos(nodes):
        return {n.id: ["VLESS", "Reality", "TCP"] for n in nodes}

    monkeypatch.setattr(nl, "xui_nodes_from_settings", lambda _s: SHARED_PANEL)
    monkeypatch.setattr(nl, "expand_share_links", _expand)
    monkeypatch.setattr(nl, "fetch_protocols_for_nodes", _protos)

    import asyncio

    rows = asyncio.get_event_loop().run_until_complete(build_node_configs(["https://example/sub"]))
    ids = [r["id"] for r in rows]
    assert ids == ["us-1", "ge-1", "de-1", "fi-1", "tr-1"]
    by_id = {r["id"]: r for r in rows}
    assert by_id["ge-1"]["flag"] == "🇬🇪"
    assert by_id["ge-1"]["city"] == "Georgia"
    assert by_id["tr-1"]["flag"] == "🇹🇷"
    assert by_id["tr-1"]["city"] == "Turkey"
    assert "🌐" not in by_id["tr-1"]["flag"]
    assert "🇹🇷" not in by_id["tr-1"]["city"]
    assert "Reality" in by_id["us-1"]["protocol"]
    assert "VLESS" in by_id["us-1"]["protocol"]


def test_welcome_location_filter():
    from core.services.network_locations import (
        WELCOME_LOCATION_KEYS,
        filter_config_nodes,
        filter_nodes_by_locations,
        node_in_locations,
    )

    nl = _node(id="nl-1", flag="🇳🇱", city="Amsterdam", country="Netherlands", label="🇳🇱 Netherlands")
    kept = filter_nodes_by_locations(SHARED_PANEL + [nl], WELCOME_LOCATION_KEYS)
    assert {n.id for n in kept} == {"us-1", "ge-1", "de-1", "fi-1", "tr-1", "ru-1"}
    assert node_in_locations(nl, WELCOME_LOCATION_KEYS) is False
    rows = [
        {"id": "de-1", "city": "Germany", "flag": "🇩🇪"},
        {"id": "nl-1", "city": "Amsterdam", "flag": "🇳🇱"},
        {"id": "tr-1", "city": "Turkey", "flag": "🇹🇷"},
    ]
    filtered = filter_config_nodes(rows, WELCOME_LOCATION_KEYS)
    assert [r["id"] for r in filtered] == ["de-1", "tr-1"]


def test_stack_from_share_uri_reality_grpc():
    from core.services.inbound_protocols import format_protocol_stack, stack_from_share_uri

    uri = "vless://u@1.2.3.4:443?type=grpc&security=reality#RU"
    stack = stack_from_share_uri(uri)
    assert stack == ["VLESS", "Reality", "gRPC"]
    assert format_protocol_stack(stack) == "VLESS · Reality · gRPC"
