"""Public network catalog + status for cabinet / marketing."""
from __future__ import annotations

from typing import Any

# Marketing locations (not necessarily 1:1 with panel nodes).
LOCATIONS: list[dict[str, Any]] = [
    {"id": "de-fra-1", "flag": "🇩🇪", "city": "Frankfurt", "country": "Germany", "region": "EU", "protocol": "VLESS+XTLS"},
    {"id": "fi-hel-1", "flag": "🇫🇮", "city": "Helsinki", "country": "Finland", "region": "EU", "protocol": "VLESS+XTLS"},
    {"id": "nl-ams-1", "flag": "🇳🇱", "city": "Amsterdam", "country": "Netherlands", "region": "EU", "protocol": "VLESS+XTLS"},
    {"id": "us-nyc-1", "flag": "🇺🇸", "city": "New York", "country": "USA", "region": "NA", "protocol": "VLESS+XTLS"},
    {"id": "us-lax-1", "flag": "🇺🇸", "city": "Los Angeles", "country": "USA", "region": "NA", "protocol": "VLESS+XTLS"},
    {"id": "jp-tyo-1", "flag": "🇯🇵", "city": "Tokyo", "country": "Japan", "region": "ASIA", "protocol": "VLESS+XTLS"},
    {"id": "sg-sin-1", "flag": "🇸🇬", "city": "Singapore", "country": "Singapore", "region": "ASIA", "protocol": "VLESS+XTLS"},
    {"id": "tr-ist-1", "flag": "🇹🇷", "city": "Istanbul", "country": "Turkey", "region": "MENA", "protocol": "VLESS+XTLS"},
    {"id": "ae-dxb-1", "flag": "🇦🇪", "city": "Dubai", "country": "UAE", "region": "MENA", "protocol": "VLESS+XTLS"},
    {"id": "fr-par-1", "flag": "🇫🇷", "city": "Paris", "country": "France", "region": "EU", "protocol": "VLESS+XTLS"},
]

CONNECTION_PROFILES: list[dict[str, Any]] = [
    {
        "id": "low_latency",
        "name_en": "Low latency",
        "name_ru": "Низкая задержка",
        "description_en": "Prefer nearest / fastest nodes for calls and gaming.",
        "description_ru": "Ближайшие быстрые узлы для звонков и игр.",
    },
    {
        "id": "streaming",
        "name_en": "Streaming",
        "name_ru": "Стриминг",
        "description_en": "Stable high-bandwidth path for YouTube / Twitch.",
        "description_ru": "Стабильный канал для YouTube / Twitch.",
    },
    {
        "id": "max_stealth",
        "name_en": "Max stealth",
        "name_ru": "Макс. скрытность",
        "description_en": "XTLS-Reality anti-DPI profile for restrictive networks.",
        "description_ru": "Анти-DPI профиль XTLS-Reality для жёстких сетей.",
    },
]


def list_locations() -> list[dict[str, Any]]:
    return list(LOCATIONS)


def list_profiles() -> list[dict[str, Any]]:
    return list(CONNECTION_PROFILES)
