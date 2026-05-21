from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

# Абсолютный путь к .env — не зависит от текущего каталога при запуске (systemd, cron)
_CONFIG_DIR = Path(__file__).resolve().parent
_ENV_FILE = _CONFIG_DIR / ".env"


def _optional_bool_json(v: Any) -> Optional[bool]:
    """Для полей узла: true/false в JSON; иначе None (наследовать глобальную настройку)."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("", "inherit"):
        return None
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return None


@dataclass(frozen=True)
class XuiNodeConfig:
    """Один узел 3x-ui (зеркало)."""

    url: str
    username: str
    password: str
    path_prefix: str = ""
    inbound_id: int = 1
    subscription_base: str = ""
    # Порт sub-сервера 3x-ui (часто ≠ панели); None — как у XUI_URL
    sub_port: Optional[int] = None
    # Сегмент пути до subId (в панели: Subscription → URI Path), по умолчанию sub
    sub_path: str = ""
    client_flow: str = ""
    two_factor_code: str = ""
    label: str = ""
    # None — использовать settings.XUI_VERIFY_SSL; False — TLS без проверки (истёкший/самоподписанный сертификат панели)
    verify_ssl: Optional[bool] = None


def parse_xui_nodes_json(raw: Optional[str]) -> list[XuiNodeConfig]:
    """Парсит XUI_NODES (JSON-массив объектов). Пустая строка → []."""
    if not raw or not str(raw).strip():
        return []
    s = str(raw).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        s = s[1:-1].strip()
    data = json.loads(s)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("XUI_NODES должен быть JSON-массивом объектов или одним объектом {...}")
    out: list[XuiNodeConfig] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"XUI_NODES[{i}]: ожидается объект")
        url = (item.get("url") or "").strip()
        user = (item.get("username") or "").strip()
        pw = (item.get("password") or "").strip()
        if not url or not user or not pw:
            raise ValueError(f"XUI_NODES[{i}]: нужны url, username, password")
        raw_sp = item.get("sub_port")
        sub_port: Optional[int] = None
        if raw_sp is not None and str(raw_sp).strip() != "":
            sub_port = int(raw_sp)
        out.append(
            XuiNodeConfig(
                url=url.rstrip("/"),
                username=user,
                password=pw,
                path_prefix=str(item.get("path_prefix") or "")
                .strip()
                .strip("/")
                .rstrip("/"),
                inbound_id=int(item.get("inbound_id") or 1),
                subscription_base=str(item.get("subscription_base") or "").strip().rstrip("/"),
                sub_port=sub_port,
                sub_path=str(item.get("sub_path") or "").strip().strip("/"),
                client_flow=str(item.get("client_flow") or "").strip(),
                two_factor_code=str(item.get("two_factor_code") or "").strip(),
                label=str(item.get("label") or f"Узел {i + 1}").strip(),
                verify_ssl=_optional_bool_json(item.get("verify_ssl")),
            )
        )
    return out


def xui_nodes_from_settings(s: "Settings") -> list[XuiNodeConfig]:
    """Список узлов: из XUI_NODES или один «легаси» из XUI_URL / XUI_USERNAME / …"""
    nodes = parse_xui_nodes_json(getattr(s, "XUI_NODES", None))
    if nodes:
        return nodes
    if s.XUI_URL and s.XUI_USERNAME and s.XUI_PASSWORD:
        return [
            XuiNodeConfig(
                url=s.XUI_URL.rstrip("/"),
                username=s.XUI_USERNAME,
                password=s.XUI_PASSWORD,
                path_prefix=(s.XUI_PATH_PREFIX or "").strip().rstrip("/"),
                inbound_id=int(s.XUI_INBOUND_ID or 1),
                subscription_base=(s.XUI_SUBSCRIPTION_BASE or "").strip().rstrip("/"),
                sub_port=s.XUI_SUB_PORT,
                sub_path=(s.XUI_SUB_PATH or "").strip().strip("/"),
                client_flow=(s.XUI_CLIENT_FLOW or "").strip(),
                two_factor_code=(s.XUI_2FA_CODE or "").strip(),
                label="Узел 1",
                verify_ssl=None,
            )
        ]
    return []


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8-sig",  # UTF-8 с BOM (часто после сохранения в редакторе на Windows/Mac)
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        По умолчанию pydantic-settings: переменные окружения (systemd, export) перекрывают .env.
        Для бота на сервере важен актуальный BOT_TOKEN в /opt/ninavpn-bot/.env — ставим dotenv раньше env.
        """
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    # Telegram
    BOT_TOKEN: str
    ADMIN_ID: int
    # Доп. админы через запятую (опционально)
    ADMIN_IDS: Optional[str] = None
    CHANNEL_ID: Optional[int] = None
    CHANNEL_USERNAME: Optional[str] = None
    # Telegram Mini App: полный HTTPS-URL страницы (например https://домен/miniapp/)
    MINI_APP_URL: Optional[str] = None
    # Юзернейм бота без @ — ссылки «открыть бота» из Mini App (t.me/username)
    BOT_USERNAME: Optional[str] = None
    # PNG баннер тарифов при /start (путь от корня проекта). Пустая строка — не отправлять картинку
    WELCOME_BANNER_FILE: Optional[str] = "assets/welcome_tariffs.png"
    # Ссылки для меню (опционально)
    TERMS_URL: Optional[str] = None
    SUPPORT_URL: Optional[str] = None

    # VPN backend: marzban | xui
    VPN_BACKEND: str = "marzban"

    # Marzban (если VPN_BACKEND=marzban)
    MARZBAN_URL: Optional[str] = None
    # Если MARZBAN_URL ведёт на статический фронт (Cloudflare) — URL FastAPI Marzban (порт контейнера / поддомен)
    MARZBAN_API_URL: Optional[str] = None
    MARZBAN_USERNAME: Optional[str] = None
    MARZBAN_PASSWORD: Optional[str] = None
    MARZBAN_VLESS_INBOUND: str = "VLESS TCP REALITY"
    MARZBAN_VLESS_FLOW: str = "xtls-rprx-vision"
    # Проверка TLS-сертификата для Marzban API. Отключайте только если ходите на IP/самоподписанный cert.
    MARZBAN_VERIFY_SSL: bool = True
    # Лимит одновременных IP в API Marzban (max_ips). У стокового Marzban поле может игнорироваться;
    # на части сборок включено. При 422 на POST/PUT пользователя выключите (false).
    MARZBAN_SEND_MAX_IPS: bool = True

    # 3x-ui (если VPN_BACKEND=xui)
    XUI_URL: Optional[str] = None
    XUI_PATH_PREFIX: str = ""
    XUI_USERNAME: Optional[str] = None
    XUI_PASSWORD: Optional[str] = None
    XUI_2FA_CODE: Optional[str] = None
    XUI_INBOUND_ID: int = 1
    XUI_SUBSCRIPTION_BASE: Optional[str] = None
    # Порт sub-сервера 3x-ui (в панели: настройки подписки). Пусто = сначала порт XUI_URL, при 404 — fallback
    XUI_SUB_PORT: Optional[int] = None
    # Доп. порты для GET /sub/… через запятую, если не задан XUI_SUB_PORT (типично 2096)
    XUI_SUB_FALLBACK_PORTS: Optional[str] = None
    # URI Path подписки в панели (без слэшей), обычно sub; если изменяли в 3x-ui — укажите здесь
    XUI_SUB_PATH: str = "sub"
    # GET /sub/… для разбора vless: false = не проверять TLS (типично для панели по IP)
    XUI_SUBSCRIPTION_FETCH_VERIFY_SSL: bool = False
    # Проверка TLS при запросах к веб-API панели (логин, inbounds). false — если сертификат истёк или самоподписанный
    XUI_VERIFY_SSL: bool = True
    XUI_CLIENT_FLOW: str = ""
    # JSON-массив узлов 3x-ui для зеркала; если пусто — используются поля XUI_* выше
    XUI_NODES: Optional[str] = None

    # Crypto wallets
    TON_WALLET: str
    USDT_TRC20_WALLET: str
    # Toncenter API v2: без ключа ~1 rps; ключ — https://toncenter.com/api/v2/getApiKey
    TONCENTER_API_KEY: Optional[str] = None

    # Freekassa
    FREEKASSA_MERCHANT_ID: Optional[str] = None
    FREEKASSA_SECRET1: Optional[str] = None
    FREEKASSA_SECRET2: Optional[str] = None

    # Перевод по внешней ссылке (часто Т-Банк t.me/... или tinkoff.ru/rm/...; в коде ключ sber_pbpn)
    SBER_PBPN_URL: Optional[str] = None
    # Дописать сумму в query к URL (для pbpn Сбера; для tinkoff.ru обычно false)
    SBER_PBPN_APPEND_AMOUNT: bool = False

    # Т-Банк интернет-эквайринг (TerminalKey + пароль из кабинета Т-Бизнес)
    TBANK_TERMINAL_KEY: Optional[str] = None
    TBANK_PASSWORD: Optional[str] = None
    # True — тестовый контур rest-api-test.tinkoff.ru
    TBANK_TEST_MODE: bool = False
    # Необязательно: свой базовый URL API (без /Init), иначе prod/test по TBANK_TEST_MODE
    TBANK_API_BASE: Optional[str] = None
    # Публичный https://ваш-домен (без слэша) — SuccessURL, FailURL, NotificationURL в Init
    PAYMENT_PUBLIC_BASE_URL: Optional[str] = None
    # Опционально: публичный базовый URL для ссылок в помощи (geo и т.д.). Если пусто — как PAYMENT_PUBLIC_BASE_URL
    PUBLIC_WEB_BASE_URL: Optional[str] = None

    # Geo-файлы v2ray (runetfreedom/russia-v2ray-rules-dat): GET /geo/geoip.dat и /geo/geosite.dat
    V2RAY_GEO_ENABLED: bool = True
    V2RAY_GEO_GEOIP_URL: str = (
        "https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geoip.dat"
    )
    V2RAY_GEO_GEOSITE_URL: str = (
        "https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geosite.dat"
    )
    V2RAY_GEO_CACHE_TTL_SEC: int = 21600

    # DB
    DATABASE_URL: str = "sqlite+aiosqlite:///ninavpn.db"

    # Reminders
    REMIND_DAYS_BEFORE: int = 3

    # Реферал: дней к VPN рефереру после первой успешной оплаты приглашённого
    REFERRAL_BONUS_DAYS: int = 30
    # 0 = выкл. Дни к VPN приглашённому при первой оплате (если зашёл по /start ref…)
    REFERRAL_INVITEE_BONUS_DAYS: int = 0

    # Пинг «Серверы / статус» и порядок узлов 3x-ui (быстрый первым в конфиге)
    SERVER_STATUS_CACHE_SEC: int = 90
    SERVER_PING_TIMEOUT_SEC: float = 4.0
    SERVER_PING_VERIFY_SSL: bool = False

    # Безопасность: Freekassa IPN только с официальных IP (нужен доверенный X-Real-IP от nginx)
    FREEKASSA_WEBHOOK_STRICT_IP: bool = False
    # Лимит запросов к GET /miniapp/api/* с одного IP в минуту (0 = выкл.)
    MINIAPP_API_RATE_LIMIT_PER_MIN: int = 60

    @field_validator("BOT_TOKEN", mode="before")
    @classmethod
    def normalize_bot_token(cls, v: Any) -> str:
        """Убираем пробелы и обрамляющие кавычки — иначе Telegram отвечает Unauthorized."""
        if v is None or (isinstance(v, str) and not str(v).strip()):
            raise ValueError("BOT_TOKEN не задан")
        s = str(v).strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
            s = s[1:-1].strip()
        return s

    @field_validator("CHANNEL_ID", mode="before")
    @classmethod
    def channel_id_empty_is_none(cls, v: Any) -> Any:
        if v is None or v == "":
            return None
        return v

    @model_validator(mode="after")
    def validate_vpn_backend(self):
        b = (self.VPN_BACKEND or "marzban").lower().strip()
        if b == "marzban":
            if not self.MARZBAN_URL or not self.MARZBAN_USERNAME or not self.MARZBAN_PASSWORD:
                raise ValueError(
                    "Для VPN_BACKEND=marzban задайте MARZBAN_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD"
                )
        elif b == "xui":
            if not xui_nodes_from_settings(self):
                raise ValueError(
                    "Для VPN_BACKEND=xui задайте XUI_NODES (JSON) или XUI_URL, XUI_USERNAME, XUI_PASSWORD"
                )
        else:
            raise ValueError("VPN_BACKEND должен быть marzban или xui")
        return self


settings = Settings()

# ─── Тарифные планы ────────────────────────────────────────
# Базовые планы совпадают с витриной https://ninavpn.store (100 / 500 / 1000 ₽).
PLANS = {
    "1m_1d": {
        "name": "⚡ Старт",
        "months": 1,
        "devices": 1,
        "price_rub": 100,
        "price_usdt": 1.1,
        "description": "1 месяц · 1 устройство",
        "emoji": "⚡",
    },
    "6m_3d": {
        "name": "🔥 Хит",
        "months": 6,
        "devices": 3,
        "price_rub": 500,
        "price_usdt": 5.5,
        "description": "6 месяцев · 3 устройства · экономия 100 ₽",
        "emoji": "🔥",
        "popular": True,
    },
    "12m_5d": {
        "name": "💎 Год",
        "months": 12,
        "devices": 5,
        "price_rub": 1000,
        "price_usdt": 11.1,
        "description": "12 месяцев · 5 устройств · экономия 200 ₽",
        "emoji": "💎",
    },
}

# Доплата за каждое устройство сверх базового в плане — как в конструкторе на сайте https://ninavpn.store.
# 1 мес: +70 ₽, 6 мес: +280 ₽, 12 мес: +490 ₽
EXTRA_DEVICE_PRICE = {1: 70, 6: 280, 12: 490}
# USDT — ориентировочно по курсу ~90 ₽/USDT (для крипто-методов оплаты).
EXTRA_DEVICE_USDT = {1: 0.78, 6: 3.11, 12: 5.44}

PAYMENT_METHODS = {
    "usdt_trc20": {"name": "💎 USDT TRC-20", "currency": "USDT"},
    "ton":        {"name": "💎 TON",          "currency": "TON"},
    "card_ru":    {"name": "💳 Карта РФ (Freekassa)", "currency": "RUB"},
    "tbank":      {"name": "💳 Карта / СБП (Т-Банк)", "currency": "RUB"},
    "sber_pbpn":  {"name": "💳 Перевод (Т-Банк)", "currency": "RUB"},
}


def admin_id_set() -> set[int]:
    ids: set[int] = {settings.ADMIN_ID}
    raw = (settings.ADMIN_IDS or "").strip()
    if raw:
        for part in raw.split(","):
            p = part.strip()
            if p.isdigit():
                ids.add(int(p))
    return ids


def channel_subscription_target() -> int | str | None:
    """
    Идентификатор чата для getChatMember.
    Сначала @CHANNEL_USERNAME (если задан) — так публичный канал работает даже при
    неверном/плейсхолдерном CHANNEL_ID из .env.example. Иначе CHANNEL_ID.
    None — проверка отключена (оба не заданы).
    """
    u = (settings.CHANNEL_USERNAME or "").strip().lstrip("@")
    if u:
        return f"@{u}"
    cid = settings.CHANNEL_ID
    if cid is not None:
        return cid
    return None


def channel_subscribe_url() -> Optional[str]:
    """HTTPS-ссылка для кнопки «Подписаться»; None — только текст (редкий случай)."""
    u = (settings.CHANNEL_USERNAME or "").strip().lstrip("@")
    if u:
        return f"https://t.me/{u}"
    cid = settings.CHANNEL_ID
    if cid is None:
        return None
    s = str(abs(int(cid)))
    if s.startswith("100") and len(s) > 3:
        inner = s[3:]
    else:
        inner = s
    return f"https://t.me/c/{inner}"


def freekassa_configured() -> bool:
    m = (settings.FREEKASSA_MERCHANT_ID or "").strip()
    s1 = (settings.FREEKASSA_SECRET1 or "").strip()
    s2 = (settings.FREEKASSA_SECRET2 or "").strip()
    return bool(m and s1 and s2)


def sber_pbpn_configured() -> bool:
    return bool((settings.SBER_PBPN_URL or "").strip())


def tbank_configured() -> bool:
    tk = (settings.TBANK_TERMINAL_KEY or "").strip()
    pw = (settings.TBANK_PASSWORD or "").strip()
    return bool(tk and pw)


def payment_public_base_url() -> str:
    return (settings.PAYMENT_PUBLIC_BASE_URL or "").strip().rstrip("/")


def public_web_base_url() -> str:
    """Публичный https://домен без хвостового слэша — для ссылок на /geo/ и подобного."""
    p = (settings.PUBLIC_WEB_BASE_URL or "").strip().rstrip("/")
    if p:
        return p
    return payment_public_base_url()


def welcome_banner_path() -> Optional[Path]:
    """Файл PNG для приветствия /start или None, если отключено или файла нет."""
    root = Path(__file__).resolve().parent
    raw = (settings.WELCOME_BANNER_FILE or "").strip()
    # Явное отключение (в .env часто пишут WELCOME_BANNER_FILE= пустым — тогда всё равно покажем файл, если он есть)
    if raw.lower() in ("0", "false", "no", "-", "none", "off"):
        return None
    candidates: list[Path] = []
    if raw:
        p = Path(raw)
        candidates.append(p if p.is_absolute() else root / p)
    # Пустая строка в .env перекрывает дефолт Settings — пробуем стандартный путь
    candidates.append(root / "assets" / "welcome_tariffs.png")
    seen: set[str] = set()
    for p in candidates:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        if p.is_file():
            return p
    return None


def mini_app_url() -> str:
    return (settings.MINI_APP_URL or "").strip()


def mini_app_configured() -> bool:
    return bool(mini_app_url())


def bot_username_clean() -> str:
    return (settings.BOT_USERNAME or "").strip().lstrip("@")


def bot_telegram_https_url() -> str:
    u = bot_username_clean()
    return f"https://t.me/{u}" if u else "https://t.me/"


def sber_pay_url(amount_rub: float) -> str:
    """Базовый URL из .env; опционально добавляет query-параметр amount (неофициально)."""
    base = (settings.SBER_PBPN_URL or "").strip()
    if not base:
        return ""
    if not settings.SBER_PBPN_APPEND_AMOUNT:
        return base
    parsed = urlparse(base)
    q = list(parse_qsl(parsed.query, keep_blank_values=True))
    q.append(("amount", f"{amount_rub:.2f}"))
    new_query = urlencode(q)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


def normalize_support_url(raw: Optional[str], admin_id: int) -> str:
    """Для InlineKeyboard url: http(s), @user, t.me; без SUPPORT_URL — личка с ADMIN_ID."""
    u = (raw or "").strip()
    if not u:
        return f"tg://user?id={int(admin_id)}"
    if u.startswith("@"):
        return "https://t.me/" + u[1:].split("/")[0].split("?")[0]
    if u.startswith("t.me/"):
        return "https://" + u
    if not u.startswith(("http://", "https://")):
        return "https://t.me/" + u.lstrip("/").split("/")[0].split("?")[0]
    return u


def payment_method_entries() -> list[tuple[str, dict]]:
    """Пары (key, meta) для клавиатуры: крипта, перевод по ссылке (если URL), эквайринг Т-Банка."""
    items: list[tuple[str, dict]] = []
    for k in ("usdt_trc20", "ton"):
        items.append((k, PAYMENT_METHODS[k]))
    if sber_pbpn_configured():
        items.append(("sber_pbpn", PAYMENT_METHODS["sber_pbpn"]))
    if tbank_configured():
        items.append(("tbank", PAYMENT_METHODS["tbank"]))
    return items


def payment_methods_visible() -> list[tuple[str, dict]]:
    """Синхронный fallback без async каталога."""
    return payment_method_entries()

# Легаси-витрина (если панель не xui/marzban); основной экран статуса — реальный HTTP-пинг в server_status
SERVERS = [
    {"flag": "🇫🇮", "name": "Финляндия", "ping": "~32 мс"},
    {"flag": "🇬🇧", "name": "Великобритания", "ping": "~68 мс"},
    {"flag": "🇲🇾", "name": "Малайзия", "ping": "~124 мс"},
    {"flag": "🇹🇭", "name": "Таиланд", "ping": "~138 мс"},
    {"flag": "🇯🇵", "name": "Япония", "ping": "~160 мс"},
]
