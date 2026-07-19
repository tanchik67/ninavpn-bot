from __future__ import annotations

import base64
import io


def make_qr_base64(link: str) -> str:
    import qrcode

    img = qrcode.make(link)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def build_deeplinks(subscription_url: str) -> dict[str, str]:
    """Common VPN client deeplinks for subscription URL."""
    from urllib.parse import quote

    enc = quote(subscription_url, safe="")
    return {
        "happ": f"happ://import/{subscription_url}",
        "streisand": f"streisand://import/{enc}",
        "v2raytun": f"v2raytun://import/{enc}",
        "raw": subscription_url,
    }
