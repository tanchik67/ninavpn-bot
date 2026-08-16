from core.services.inbound_protocols import format_protocol_stack, stack_from_inbound


def test_stack_from_inbound_vless_reality_tcp():
    stack = stack_from_inbound(
        "vless",
        {"network": "tcp", "security": "reality"},
        {"clients": []},
    )
    assert stack == ["VLESS", "Reality", "TCP"]
    assert format_protocol_stack(stack) == "VLESS · Reality · TCP"


def test_stack_from_inbound_mixed_socks():
    stack = stack_from_inbound(
        "mixed",
        None,
        {"auth": "password", "accounts": [{"user": "a", "pass": "b"}]},
    )
    assert "SOCKS" in stack
