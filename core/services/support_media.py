"""Save/serve support chat image attachments."""
from __future__ import annotations

import base64
import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from core.settings import saas_settings

log = logging.getLogger(__name__)

_ALLOWED = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_MAX_BYTES = 6 * 1024 * 1024  # 6 MB


def media_root() -> Path:
    raw = getattr(saas_settings, "SUPPORT_MEDIA_DIR", None) or ""
    if raw.strip():
        root = Path(raw.strip())
    else:
        root = Path(__file__).resolve().parents[2] / "data" / "support_media"
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_image_bytes(data: bytes, image_mime: str = "image/jpeg") -> str:
    mime = (image_mime or "image/jpeg").split(";")[0].strip().lower()
    ext = _ALLOWED.get(mime)
    if not ext:
        raise ValueError("unsupported_image_type")
    if not data or len(data) > _MAX_BYTES:
        raise ValueError("image_too_large" if data else "invalid_image")
    name = f"{uuid.uuid4().hex}{ext}"
    path = media_root() / name
    path.write_bytes(data)
    return name


def save_image_base64(image_base64: str, image_mime: str = "image/jpeg") -> str:
    """
    Persist a base64 image; returns relative path like '{uuid}.jpg'
    stored under media_root().
    """
    mime = (image_mime or "image/jpeg").split(";")[0].strip().lower()
    ext = _ALLOWED.get(mime)
    if not ext:
        raise ValueError("unsupported_image_type")

    raw = (image_base64 or "").strip()
    if raw.startswith("data:"):
        # data:image/jpeg;base64,....
        try:
            header, raw = raw.split(",", 1)
            m = re.search(r"data:([^;]+)", header)
            if m:
                mime = m.group(1).strip().lower()
                ext = _ALLOWED.get(mime) or ext
        except ValueError as e:
            raise ValueError("invalid_image") from e

    try:
        data = base64.b64decode(raw, validate=False)
    except Exception as e:
        raise ValueError("invalid_image") from e

    return save_image_bytes(data, mime)


def resolve_media_file(relative: str) -> Optional[Path]:
    name = (relative or "").strip().lstrip("/")
    if not name or "/" in name or ".." in name:
        return None
    path = media_root() / name
    if not path.is_file():
        return None
    return path
