"""
Marzban API — создание/удаление пользователей, получение конфигов.
Документация: https://github.com/Gozargah/Marzban
Адаптер панели: MarzbanPanelAdapter в конце файла (см. services.vpn_panel).
"""
import httpx
import qrcode
import io
import base64
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select
from config import settings
import logging

from database import AsyncSessionLocal, User
from services.vpn_panel import VpnPanel, client_email, legacy_client_email

log = logging.getLogger(__name__)

# API Marzban — unix-время в секундах; при ошибочной записи в мс (~1.7e12) срок в панели «раздувается».
_MARZBAN_EXPIRE_MS_THRESHOLD = 11_000_000_000


def marzban_expire_unix_seconds(raw) -> Optional[int]:
    """Приводит поле expire от API к секундам (мс → деление на 1000)."""
    if raw is None:
        return None
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return v
    if v > _MARZBAN_EXPIRE_MS_THRESHOLD:
        return v // 1000
    return v


def marzban_effective_expire_base(raw, now_ts: int) -> int:
    """База для продления: валидный unix sec в будущем или now_ts."""
    v = marzban_expire_unix_seconds(raw)
    if v is None or v <= 0:
        return now_ts
    return max(v, now_ts)


def _marzban_http_error_body(r: httpx.Response) -> str:
    """Текст ответа Marzban (FastAPI) для логов и алертов админу."""
    try:
        j = r.json()
        if isinstance(j, dict):
            d = j.get("detail")
            if isinstance(d, list):
                parts = []
                for x in d:
                    if isinstance(x, dict):
                        loc = x.get("loc")
                        msg = x.get("msg", x)
                        parts.append(f"{loc}: {msg}" if loc else str(msg))
                    else:
                        parts.append(str(x))
                return "; ".join(parts) if parts else str(j)
            if d is not None:
                return str(d)
    except Exception:
        pass
    return (r.text or "").strip()[:500] or r.reason_phrase


def _marzban_raise(r: httpx.Response) -> None:
    if r.is_success:
        return
    detail = _marzban_http_error_body(r)
    path = r.request.url.path if r.request else ""
    raise RuntimeError(f"Marzban {r.status_code} {r.request.method if r.request else '?'} {path}: {detail}")


class MarzbanAPI:
    def __init__(self):
        raw = (settings.MARZBAN_API_URL or settings.MARZBAN_URL or "").strip().rstrip("/")
        self.api_base = raw
        self._token: Optional[str] = None
        self._token_expires: datetime = datetime.min

    def _verify_ssl(self) -> bool:
        return bool(getattr(settings, "MARZBAN_VERIFY_SSL", True))

    # ─── Auth ───────────────────────────────────────────────
    async def _get_token(self) -> str:
        if self._token and datetime.utcnow() < self._token_expires:
            return self._token
        url = f"{self.api_base}/api/admin/token"
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.post(
                url,
                data={
                    "username": settings.MARZBAN_USERNAME,
                    "password": settings.MARZBAN_PASSWORD,
                    "grant_type": "password",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            if r.status_code == 405:
                hint = (
                    "POST /api/admin/token вернул 405: домен, скорее всего, отдаёт статический сайт "
                    "(Cloudflare/Pages), а не API Marzban. "
                    "Укажите MARZBAN_API_URL — базовый URL FastAPI (где открывается /docs), "
                    "часто порт из docker-compose (например :8000, :62050) или отдельный поддомен."
                )
                log.error("Marzban auth: %s base=%s", hint, self.api_base)
                raise RuntimeError(hint)
            _marzban_raise(r)
            data = r.json()
            self._token = data["access_token"]
            self._token_expires = datetime.utcnow() + timedelta(hours=23)
            return self._token

    async def _headers(self) -> dict:
        return {"Authorization": f"Bearer {await self._get_token()}"}

    def _vless_proxies(self) -> dict:
        flow = (settings.MARZBAN_VLESS_FLOW or "").strip()
        if flow:
            return {"vless": {"flow": flow}}
        return {"vless": {}}

    def _vless_inbounds(self) -> dict:
        name = (settings.MARZBAN_VLESS_INBOUND or "VLESS TCP REALITY").strip()
        return {"vless": [name]}

    def _max_ips_field(self, devices: int) -> dict:
        """Часть JSON для панелей с лимитом IP (официальный Marzban может игнорировать поле)."""
        if not bool(getattr(settings, "MARZBAN_SEND_MAX_IPS", True)):
            return {}
        return {"max_ips": max(1, int(devices))}

    # ─── Создать пользователя ───────────────────────────────
    async def create_user(
        self,
        username: str,
        months: int,
        devices: int,
    ) -> dict:
        """
        Возвращает: {"uuid": str, "links": [str, ...], "subscription_url": str}
        """
        expire_ts = int(
            (datetime.utcnow() + timedelta(days=30 * months)).timestamp()
        )
        payload = {
            "username": username,
            "proxies": self._vless_proxies(),
            "inbounds": self._vless_inbounds(),
            "expire": expire_ts,
            "data_limit": 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "note": f"tg_user | devices={devices} | created_by_bot",
            **self._max_ips_field(devices),
        }
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.post(
                f"{self.api_base}/api/user",
                json=payload,
                headers=await self._headers(),
                timeout=15,
            )
            _marzban_raise(r)
            data = r.json()
            log.info(f"Marzban: создан пользователь {username}")
            exp = data.get("expire")
            exp_norm = marzban_expire_unix_seconds(exp)
            return {
                "uuid":             data["uuid"],
                "links":            data.get("links", []),
                "subscription_url": data.get("subscription_url", ""),
                "expire_ts":        exp_norm,
            }

    async def create_or_extend_user(
        self, tg_id: int, months: int, devices: int, *, tg_username: Optional[str] = None
    ) -> dict:
        """Создать/продлить. Для совместимости сначала пробуем legacy nina_{tg_id}."""
        if tg_username is None:
            tg_username = await self._tg_username_from_db(tg_id)
        preferred = client_email(tg_id, tg_username=tg_username)
        legacy = legacy_client_email(tg_id)
        username = await self._resolve_existing_username(preferred=preferred, legacy=legacy)
        now_ts = int(datetime.utcnow().timestamp())
        add_s = months * 30 * 86400
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.get(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            if r.status_code == 404:
                return await self.create_user(username, months, devices)
            _marzban_raise(r)
            user = r.json()
            base = marzban_effective_expire_base(user.get("expire"), now_ts)
            new_exp = base + add_s
            r2 = await c.put(
                f"{self.api_base}/api/user/{username}",
                json={
                    "expire": new_exp,
                    "note": f"tg_user={preferred} | devices={devices} | renewed_by_bot",
                    **self._max_ips_field(devices),
                },
                headers=await self._headers(),
                timeout=10,
            )
            _marzban_raise(r2)
            r3 = await c.get(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            _marzban_raise(r3)
            u2 = r3.json()
            exp2 = u2.get("expire")
            exp2n = marzban_expire_unix_seconds(exp2)
            return {
                "uuid": u2["uuid"],
                "links": u2.get("links", []),
                "subscription_url": u2.get("subscription_url", ""),
                "expire_ts": exp2n,
            }

    async def _tg_username_from_db(self, tg_id: int) -> Optional[str]:
        async with AsyncSessionLocal() as s:
            u = await s.scalar(select(User).where(User.tg_id == tg_id))
        return (u.username if u else None)

    async def _user_exists(self, username: str) -> bool:
        if not username:
            return False
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.get(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            if r.status_code == 404:
                return False
            _marzban_raise(r)
            return True

    async def _resolve_existing_username(self, *, preferred: str, legacy: str) -> str:
        # Если legacy уже существует в панели — продолжаем использовать его, чтобы не плодить дубли.
        if legacy and legacy != preferred:
            try:
                if await self._user_exists(legacy):
                    return legacy
            except Exception:
                # не блокируем выдачу, если check упал; пойдём по preferred
                pass
        return preferred or legacy

    async def sync_user_device_limit(self, tg_id: int, devices: int) -> bool:
        """PUT max_ips и текущий expire — выровнять лимит с подпиской в БД."""
        extra = self._max_ips_field(devices)
        if not extra:
            return True
        preferred = client_email(tg_id, tg_username=await self._tg_username_from_db(tg_id))
        legacy = legacy_client_email(tg_id)
        username = await self._resolve_existing_username(preferred=preferred, legacy=legacy)
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            if r.status_code == 404:
                return False
            _marzban_raise(r)
            user = r.json()
            exp = marzban_expire_unix_seconds(user.get("expire"))
            if exp is None or exp <= 0:
                return False
            r2 = await c.put(
                f"{self.api_base}/api/user/{username}",
                json={"expire": exp, **extra},
                headers=await self._headers(),
                timeout=10,
            )
            _marzban_raise(r2)
        return True

    async def create_user_days_only(
        self, username: str, days: int, devices: int
    ) -> dict:
        """Новый пользователь сразу с сроком days (промо)."""
        expire_ts = int(
            (datetime.utcnow() + timedelta(days=max(1, int(days)))).timestamp()
        )
        payload = {
            "username": username,
            "proxies": self._vless_proxies(),
            "inbounds": self._vless_inbounds(),
            "expire": expire_ts,
            "data_limit": 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "note": f"tg_user | devices={devices} | promo_trial",
            **self._max_ips_field(devices),
        }
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.post(
                f"{self.api_base}/api/user",
                json=payload,
                headers=await self._headers(),
                timeout=15,
            )
            _marzban_raise(r)
            data = r.json()
            exp = data.get("expire")
            expn = marzban_expire_unix_seconds(exp)
            return {
                "uuid": data["uuid"],
                "links": data.get("links", []),
                "subscription_url": data.get("subscription_url", ""),
                "expire_ts": expn,
            }

    async def grant_free_days(self, tg_id: int, days: int, devices: int) -> dict:
        preferred = client_email(tg_id, tg_username=await self._tg_username_from_db(tg_id))
        legacy = legacy_client_email(tg_id)
        username = await self._resolve_existing_username(preferred=preferred, legacy=legacy)
        d = max(1, int(days))
        dev = max(1, min(10, int(devices)))
        ok = await self.extend_user_by_days(tg_id, d)
        created: dict | None = None
        if not ok:
            try:
                created = await self.create_user_days_only(username, d, dev)
                ok = True
            except Exception as e:
                log.warning("Marzban grant_free_days create: %s", e)
                ok = False
        links: list = []
        primary = ""
        exp_dt: Optional[datetime] = None
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.get(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            if r.status_code == 200:
                u = r.json()
                links = list(u.get("links") or [])
                primary = (u.get("subscription_url") or "").strip() or (
                    links[0] if links else ""
                )
                ex = marzban_expire_unix_seconds(u.get("expire"))
                if ex is not None and ex > 0:
                    exp_dt = datetime.utcfromtimestamp(ex)
        if ok and not primary and created:
            links = list(created.get("links") or [])
            primary = (created.get("subscription_url") or "").strip() or (
                links[0] if links else ""
            )
            ex = created.get("expire_ts")
            if exp_dt is None and ex is not None:
                try:
                    exi = int(ex)
                    if exi > 0:
                        exp_dt = datetime.utcfromtimestamp(exi)
                except (TypeError, ValueError):
                    pass
        return {
            "ok": ok and bool(primary),
            "links": links,
            "subscription_url": primary,
            "expires": exp_dt,
        }

    async def extend_user_by_days(self, tg_id: int, days: int) -> bool:
        preferred = client_email(tg_id, tg_username=await self._tg_username_from_db(tg_id))
        legacy = legacy_client_email(tg_id)
        username = await self._resolve_existing_username(preferred=preferred, legacy=legacy)
        now_ts = int(datetime.utcnow().timestamp())
        add_s = days * 86400
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.get(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            if r.status_code == 404:
                return False
            _marzban_raise(r)
            user = r.json()
            base = marzban_effective_expire_base(user.get("expire"), now_ts)
            new_exp = base + add_s
            payload: dict = {"expire": new_exp}
            if bool(getattr(settings, "MARZBAN_SEND_MAX_IPS", True)):
                mi = user.get("max_ips")
                if mi is not None:
                    payload["max_ips"] = mi
            r2 = await c.put(
                f"{self.api_base}/api/user/{username}",
                json=payload,
                headers=await self._headers(),
                timeout=10,
            )
            return r2.status_code == 200

    # ─── Продлить подписку ──────────────────────────────────
    async def extend_user(self, username: str, extra_months: int) -> bool:
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.get(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            if r.status_code == 404:
                return False
            _marzban_raise(r)
            user = r.json()
            now_ts = int(datetime.utcnow().timestamp())
            base = marzban_effective_expire_base(user.get("expire"), now_ts)
            new_expire = base + extra_months * 30 * 86400

            r2 = await c.put(
                f"{self.api_base}/api/user/{username}",
                json={"expire": new_expire},
                headers=await self._headers(),
                timeout=10,
            )
            _marzban_raise(r2)
            log.info(f"Marzban: продлён {username} на {extra_months} мес.")
            return True

    # ─── Заблокировать / удалить ────────────────────────────
    async def disable_user(self, username: str) -> bool:
        async with httpx.AsyncClient() as c:
            r = await c.put(
                f"{self.api_base}/api/user/{username}",
                json={"status": "disabled"},
                headers=await self._headers(),
                timeout=10,
            )
            return r.status_code == 200

    async def delete_user(self, username: str) -> bool:
        async with httpx.AsyncClient() as c:
            r = await c.delete(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            return r.status_code == 200

    # ─── Статистика ─────────────────────────────────────────
    async def get_user_expire(self, username: str) -> Optional[datetime]:
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.get(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            if r.status_code == 404:
                return None
            _marzban_raise(r)
            user = r.json()
            ts = marzban_expire_unix_seconds(user.get("expire"))
            if ts is None or ts <= 0:
                return None
            return datetime.utcfromtimestamp(ts)

    async def get_user_usage(self, username: str) -> dict:
        async with httpx.AsyncClient(verify=self._verify_ssl()) as c:
            r = await c.get(
                f"{self.api_base}/api/user/{username}",
                headers=await self._headers(),
                timeout=10,
            )
            if r.status_code == 404:
                return {}
            _marzban_raise(r)
            d = r.json()
            exp_u = marzban_expire_unix_seconds(d.get("expire"))
            return {
                "used_gb":    round((d.get("used_traffic") or 0) / 1e9, 2),
                "expire":     exp_u,
                "status":     d.get("status"),
                "online_at":  d.get("online_at"),
            }

    # ─── QR-код для конфига ─────────────────────────────────
    @staticmethod
    def make_qr_base64(link: str) -> str:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(link)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#7B2FFF", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    @staticmethod
    def gen_username(tg_id: int, plan_key: Optional[str] = None) -> str:
        """Стабильный логин в панели (plan_key игнорируется)."""
        return client_email(tg_id)


marzban = MarzbanAPI()


class MarzbanPanelAdapter(VpnPanel):
    """Обертка MarzbanAPI под общий интерфейс VpnPanel."""

    def __init__(self) -> None:
        self._api = marzban

    async def create_or_extend_subscription(
        self, tg_id: int, months: int, devices: int, *, tg_username: Optional[str] = None
    ) -> dict:
        return await self._api.create_or_extend_user(tg_id, months, devices, tg_username=tg_username)

    async def extend_by_days(self, tg_id: int, days: int) -> bool:
        return await self._api.extend_user_by_days(tg_id, days)

    async def disable_client(self, tg_id: int) -> bool:
        return await self._api.disable_user(client_email(tg_id))

    async def delete_client(self, tg_id: int) -> bool:
        return await self._api.delete_user(client_email(tg_id))

    async def get_usage(self, tg_id: int) -> dict:
        return await self._api.get_user_usage(client_email(tg_id))

    async def get_subscription_expiry(self, tg_id: int) -> Optional[datetime]:
        return await self._api.get_user_expire(client_email(tg_id))

    async def sync_device_limit(self, tg_id: int, devices: int) -> bool:
        return await self._api.sync_user_device_limit(tg_id, devices)

    async def grant_free_days(self, tg_id: int, days: int, devices: int) -> dict:
        return await self._api.grant_free_days(tg_id, days, devices)
