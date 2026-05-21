"""
Клиент API панели 3x-ui (MHSanaei/3x-ui): сессия по cookie после POST /login.
Пути: {path_prefix}/login и {path_prefix}/panel/api/inbounds/...
Несколько узлов — класс MultiXuiPanel (зеркало клиента).
"""
from __future__ import annotations

import asyncio
import base64
import html
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import unquote, urlparse, urlunparse

import httpx
from sqlalchemy import select

from config import XuiNodeConfig, settings
from database import AsyncSessionLocal, User
from services.vpn_panel import VpnPanel, client_email, legacy_client_email

log = logging.getLogger(__name__)


def _try_b64(blob: str, *, std: bool) -> bytes | None:
    try:
        if std:
            try:
                return base64.b64decode(blob, validate=False)
            except TypeError:
                return base64.b64decode(blob)
        return base64.urlsafe_b64decode(blob)
    except Exception:
        return None


class XuiPanel(VpnPanel):
    def __init__(self, node: XuiNodeConfig) -> None:
        self._node = node
        self._base = node.url.rstrip("/")
        self._prefix = (node.path_prefix or "").strip().rstrip("/")
        self._user = node.username
        self._password = node.password
        self._2fa = (node.two_factor_code or "").strip()
        self._inbound_id = int(node.inbound_id or 1)
        self._sub_base = (node.subscription_base or "").strip().rstrip("/")
        self._sub_port = getattr(node, "sub_port", None)
        _sp = (getattr(node, "sub_path", None) or "").strip().strip("/")
        if not _sp:
            _sp = (getattr(settings, "XUI_SUB_PATH", None) or "sub").strip().strip("/")
        self._sub_path_seg = _sp or "sub"
        self._flow = (node.client_flow or "").strip()
        self._label = (node.label or "").strip() or "3x-ui"
        if node.verify_ssl is not None:
            self._panel_verify_ssl = bool(node.verify_ssl)
        else:
            self._panel_verify_ssl = bool(getattr(settings, "XUI_VERIFY_SSL", True))
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    @property
    def node_label(self) -> str:
        return self._label

    @property
    def node(self) -> XuiNodeConfig:
        return self._node

    def _path(self, tail: str) -> str:
        t = tail if tail.startswith("/") else f"/{tail}"
        if not self._prefix:
            return t
        return f"/{self._prefix}{t}".replace("//", "/")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                follow_redirects=True,
                timeout=httpx.Timeout(30.0),
                verify=self._panel_verify_ssl,
            )
        return self._client

    async def _login(self) -> None:
        c = await self._get_client()
        path = self._path("/login")
        data = {
            "username": self._user,
            "password": self._password,
            "twoFactorCode": self._2fa or "",
        }
        r = await c.post(path, data=data)
        r.raise_for_status()
        try:
            body = r.json()
        except Exception:
            raise RuntimeError("3x-ui: ответ логина не JSON") from None
        if not body.get("success", True):
            raise RuntimeError(body.get("msg") or "3x-ui: вход не выполнен")

    async def _ensure_session(self) -> httpx.AsyncClient:
        async with self._lock:
            c = await self._get_client()
            test = await c.get(self._path("/panel/api/inbounds/list"))
            if test.status_code == 404:
                await self._login()
            return c

    async def _get_inbound_json(self, c: httpx.AsyncClient) -> dict[str, Any]:
        r = await c.get(self._path(f"/panel/api/inbounds/get/{self._inbound_id}"))
        r.raise_for_status()
        data = r.json()
        return data.get("obj") or data

    def _client_dict(
        self,
        tg_id: int,
        email: str,
        devices: int,
        expiry_ms: int,
        client_uuid: str,
        sub_id: str,
        enable: bool = True,
    ) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": client_uuid,
            "email": email,
            "limitIp": max(1, int(devices)),
            "totalGB": 0,
            "expiryTime": expiry_ms,
            "enable": enable,
            "tgId": str(tg_id),
            "subId": sub_id,
            "reset": 0,
        }
        if self._flow:
            d["flow"] = self._flow
        return d

    def _subscription_public_origin(self) -> str:
        """
        scheme://host:port для ссылок sub-сервера 3x-ui.
        В 3x-ui подписка идёт с отдельного процесса на корне /sub/, без webBasePath панели.
        """
        p = urlparse(self._base)
        if self._sub_port is not None:
            host = p.hostname or ""
            if not host:
                netloc = p.netloc
            elif ":" in host:
                netloc = f"[{host}]:{self._sub_port}"
            else:
                netloc = f"{host}:{self._sub_port}"
        else:
            netloc = p.netloc
        return urlunparse((p.scheme, netloc, "", "", "", "")).rstrip("/")

    def _subscription_fetch_urls(self, sub_url: str) -> list[str]:
        """
        URL для скачивания подписки. Если хост совпадает с панелью, перебираем порты sub-сервиса
        (XUI_SUB_PORT узла, XUI_SUB_FALLBACK_PORTS, иначе 2096). Так обрабатываются:
        ссылка только на :443 (XUI_SUBSCRIPTION_BASE без порта), порт панели :2053 и т.д. —
        иначе часто 404/400 на /sub/.
        """
        u = (sub_url or "").strip()
        seen: set[str] = set()
        out: list[str] = []

        def add(x: str) -> None:
            x = x.strip()
            if x and x not in seen:
                seen.add(x)
                out.append(x)

        add(u)
        su, bu = urlparse(u), urlparse(self._base)
        host = su.hostname or ""
        bu_host = bu.hostname or ""
        if not host or host.lower() != bu_host.lower():
            return out

        sch = (su.scheme or "https").lower()
        if sch not in ("http", "https"):
            return out
        eff = su.port
        if eff is None:
            eff = 443 if sch == "https" else 80

        ports_ordered: list[int] = []
        if self._sub_port is not None:
            ports_ordered.append(int(self._sub_port))
        raw = getattr(settings, "XUI_SUB_FALLBACK_PORTS", None)
        if raw and str(raw).strip():
            for part in str(raw).split(","):
                part = part.strip()
                if part.isdigit():
                    ports_ordered.append(int(part))
        else:
            ports_ordered.append(2096)

        seen_p: set[int] = set()
        ports: list[int] = []
        for p in ports_ordered:
            if p not in seen_p:
                seen_p.add(p)
                ports.append(p)

        for alt in ports:
            if alt == eff:
                continue
            netloc = f"[{host}]:{alt}" if ":" in host else f"{host}:{alt}"
            add(
                urlunparse(
                    (
                        su.scheme or sch,
                        netloc,
                        su.path or "",
                        "",
                        su.query or "",
                        su.fragment or "",
                    )
                )
            )
        return out

    def _subscription_link(self, sub_id: str) -> str:
        """Публичная ссылка: XUI_SUBSCRIPTION_BASE или {origin}/{XUI_SUB_PATH}/{subId}."""
        if not sub_id:
            return ""
        sid = str(sub_id).strip()
        if not sid:
            return ""
        if self._sub_base:
            return f"{self._sub_base.rstrip('/')}/{sid}"
        root = self._subscription_public_origin()
        return f"{root}/{self._sub_path_seg}/{sid}"

    @staticmethod
    def _prepare_body_for_link_extract(raw: str) -> str:
        """HTML-субстраница и href с percent-encoding — приводим к тексту для поиска vless://."""
        t = raw or ""
        if not t.strip():
            return t
        t = html.unescape(t)
        for _ in range(4):
            if re.search(r"vless://", t, re.I):
                break
            low = t.lower()
            if "vless%3a" in low or "vless%253a" in low:
                t = unquote(t)
                t = html.unescape(t)
            else:
                break
        return t

    @staticmethod
    def _normalize_subscription_body(raw: str) -> str:
        """Расшифровка base64-целой подписки (std / urlsafe), если vless ещё не виден как текст."""
        t = (raw or "").strip()
        if not t:
            return t
        if re.search(r"vless://", t, re.I) or re.search(r"vmess://", t, re.I):
            return t
        compact = re.sub(r"\s+", "", t)
        for pad in ("", "=", "==", "==="):
            blob = compact + pad
            for dec in (
                _try_b64(blob, std=True),
                _try_b64(blob, std=False),
            ):
                if dec is None:
                    continue
                s = dec.decode("utf-8", errors="replace")
                if re.search(r"vless://|vmess://|trojan://|ss://", s, re.I):
                    return s
        return t

    @staticmethod
    def _extract_share_links(body: str) -> list[str]:
        """vless:// и др. из любого текста (в т.ч. HTML), порядок сохраняется."""
        if not body:
            return []
        seen: set[str] = set()
        out: list[str] = []
        # Разрешаем query/fragment в URI; обрезаем лишние кавычки/скобки в конце
        for m in re.finditer(
            r"vless://[^\s\r\n<>\"'`)]+(?:[?#][^\s\r\n<>\"'`)]*)?",
            body,
            re.IGNORECASE,
        ):
            u = m.group(0).rstrip(".,;)'\"")
            if u not in seen:
                seen.add(u)
                out.append(u)
        if out:
            return out
        for proto in ("vmess://", "trojan://", "ss://"):
            for m in re.finditer(
                re.escape(proto) + r"[^\s\r\n<>\"']+", body, re.IGNORECASE
            ):
                u = m.group(0).rstrip(".,;)")
                if u not in seen:
                    seen.add(u)
                    out.append(u)
        return out

    async def _vless_uris_from_subscription_url(self, sub_url: str) -> tuple[list[str], str]:
        """
        GET подписки. Возвращает (список vless://…, публичный URL подписки для пользователя).
        При 404 на порту панели перебирает XUI_SUB_FALLBACK_PORTS (по умолчанию 2096).
        """
        u = (sub_url or "").strip()
        if not u.lower().startswith(("http://", "https://")):
            return [], ""
        verify = bool(getattr(settings, "XUI_SUBSCRIPTION_FETCH_VERIFY_SSL", False))
        # 3x-ui отдаёт HTML, если в Accept есть text/html; явно просим «не страницу»
        accept_variants = (
            "text/plain, application/octet-stream;q=0.9, */*;q=0.5",
            "application/yaml, text/yaml;q=0.8, */*;q=0.5",
            "*/*",
        )
        ua = "clash-meta/2.10 (Windows; amd64) ninavpn-bot"
        candidates = self._subscription_fetch_urls(u)

        def _parse_response(text: str) -> list[str]:
            raw = self._prepare_body_for_link_extract(text)
            norm = self._normalize_subscription_body(raw)
            return self._extract_share_links(norm)

        try:
            async with httpx.AsyncClient(
                timeout=25.0,
                follow_redirects=True,
                verify=verify,
            ) as ac:
                last_r: httpx.Response | None = None
                last_candidate = ""
                ok_200_url = ""
                last_ok_body = ""
                last_ok_ct = ""
                saw_panel_port_404 = False
                bu = urlparse(self._base)
                for cand in candidates:
                    for accept in accept_variants:
                        last_r = await ac.get(
                            cand,
                            headers={
                                "Accept": accept,
                                "User-Agent": ua,
                            },
                        )
                        last_candidate = cand
                        if last_r.status_code == 404:
                            cu = urlparse(cand)
                            if (
                                self._sub_port is None
                                and not self._sub_base
                                and cu.port == bu.port
                                and (cu.hostname or "").lower()
                                == (bu.hostname or "").lower()
                            ):
                                saw_panel_port_404 = True
                            continue
                        if last_r.status_code != 200:
                            continue
                        body = last_r.content.decode("utf-8", errors="replace")
                        ok_200_url = cand
                        last_ok_body = body
                        last_ok_ct = last_r.headers.get("content-type") or ""
                        found = _parse_response(body)
                        if found:
                            if cand != u:
                                log.info(
                                    "3x-ui [%s]: подписка открылась на %s (не на порту панели). "
                                    "Задайте XUI_SUB_PORT=%s в .env.",
                                    self._label,
                                    cand[:96],
                                    urlparse(cand).port or "?",
                                )
                            return found, cand
                if saw_panel_port_404 and len(candidates) > 1:
                    log.warning(
                        "3x-ui [%s]: /sub/ на порту панели вернул 404 — sub на другом порту. "
                        "Использован fallback; задайте XUI_SUB_PORT в .env.",
                        self._label,
                    )
                if ok_200_url and last_ok_body.strip():
                    log.warning(
                        "3x-ui [%s]: нет vless в ответе подписки (Content-Type=%s), фрагмент: %r",
                        self._label,
                        (last_ok_ct or "")[:80],
                        last_ok_body[:160].replace("\n", " "),
                    )
                    return [], ok_200_url
                if last_r is not None and last_r.status_code != 200:
                    log.warning(
                        "3x-ui: подписка HTTP %s для %s",
                        last_r.status_code,
                        (last_candidate or u)[:120],
                    )
                return [], u
        except Exception as e:
            log.warning("3x-ui: не удалось скачать подписку [%s]: %s", self._label, e)
            return [], u

    async def _links_for_client_async(
        self,
        sub_url: str,
    ) -> tuple[list[str], str]:
        vless, effective = await self._vless_uris_from_subscription_url(sub_url)
        if vless:
            return vless, vless[0]
        if effective:
            return [effective], effective
        if sub_url:
            return [sub_url], sub_url
        return [], ""

    async def refresh_share_links_for_tg(self, tg_id: int) -> tuple[list[str], str]:
        """Актуальные строки vless:// (и др.) с URL подписки — для «Получить конфиг»."""
        try:
            c = await self._ensure_session()
            inbound = await self._get_inbound_json(c)
            existing, _, _ = await self._resolve_panel_client(inbound, tg_id)
            if not existing:
                return [], ""
            sub_id = str(existing.get("subId") or "").strip()
            if not sub_id:
                return [], ""
            sub_url = self._subscription_link(sub_id)
            if not sub_url:
                return [], ""
            links, primary = await self._links_for_client_async(sub_url)
            return links, primary
        except Exception as e:
            log.warning("3x-ui refresh_share_links [%s]: %s", self._label, e)
            return [], ""

    async def _add_client(
        self, c: httpx.AsyncClient, client_obj: dict[str, Any]
    ) -> None:
        payload = {
            "id": self._inbound_id,
            "settings": json.dumps({"clients": [client_obj]}),
        }
        r = await c.post(self._path("/panel/api/inbounds/addClient"), json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"3x-ui addClient: HTTP {r.status_code} {r.text[:200]}")
        try:
            body = r.json()
        except Exception:
            return
        if not body.get("success", True):
            raise RuntimeError(body.get("msg") or "3x-ui addClient failed")

    async def _update_client(
        self, c: httpx.AsyncClient, client_uuid: str, client_obj: dict[str, Any]
    ) -> None:
        payload = {
            "id": self._inbound_id,
            "settings": json.dumps({"clients": [client_obj]}),
        }
        path = self._path(f"/panel/api/inbounds/updateClient/{client_uuid}")
        r = await c.post(path, json=payload)
        if r.status_code != 200:
            raise RuntimeError(f"3x-ui updateClient: HTTP {r.status_code} {r.text[:200]}")
        try:
            body = r.json()
        except Exception:
            return
        if not body.get("success", True):
            raise RuntimeError(body.get("msg") or "3x-ui updateClient failed")

    def _find_client_in_inbound(
        self, inbound: dict[str, Any], email: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        raw = inbound.get("settings") or "{}"
        if isinstance(raw, dict):
            settings_map = raw
        else:
            settings_map = json.loads(raw)
        clients = settings_map.get("clients") or []
        for cl in clients:
            if isinstance(cl, dict) and cl.get("email") == email:
                cid = cl.get("id") or cl.get("password")
                return cl, str(cid) if cid else None
        return None, None

    def _find_client_by_tgid(
        self, inbound: dict[str, Any], tg_id: int
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Клиент в inbound по tgId (3x-ui), если email уже не совпадает с legacy/preferred."""
        want = str(int(tg_id))
        raw = inbound.get("settings") or "{}"
        if isinstance(raw, dict):
            settings_map = raw
        else:
            settings_map = json.loads(raw)
        for cl in settings_map.get("clients") or []:
            if not isinstance(cl, dict):
                continue
            raw_tid = cl.get("tgId", cl.get("tg_id"))
            if raw_tid is None:
                continue
            tid = str(raw_tid).strip()
            if tid != want:
                continue
            cid = cl.get("id") or cl.get("password")
            if cid:
                return cl, str(cid)
        return None, None

    async def _tg_username_from_db(self, tg_id: int) -> str | None:
        async with AsyncSessionLocal() as s:
            u = await s.scalar(select(User).where(User.tg_id == tg_id))
        return (u.username if u else None) or None

    async def _resolve_panel_client(
        self,
        inbound: dict[str, Any],
        tg_id: int,
        *,
        tg_username: str | None = None,
    ) -> tuple[dict[str, Any] | None, str | None, str]:
        """
        Как при оплате: сначала legacy nina_{id}, иначе клиент с username из Telegram (из БД, если не передан).
        Третий элемент — email для нового клиента (preferred), если записи в inbound ещё нет.
        """
        u = tg_username
        if u is None:
            u = await self._tg_username_from_db(tg_id)
        legacy_email = legacy_client_email(tg_id)
        preferred_email = client_email(tg_id, tg_username=u)
        existing, client_uuid = self._find_client_in_inbound(inbound, legacy_email)
        if existing and client_uuid:
            return existing, client_uuid, legacy_email
        existing, client_uuid = self._find_client_in_inbound(inbound, preferred_email)
        if existing and client_uuid:
            return existing, client_uuid, preferred_email
        existing, client_uuid = self._find_client_by_tgid(inbound, tg_id)
        if existing and client_uuid:
            em = (str(existing.get("email") or "").strip() or preferred_email)
            return existing, client_uuid, em
        return None, None, preferred_email

    async def _fallback_subscription_url(self, tg_id: int) -> str:
        """Публичный URL подписки по subId, если вытащить vless из страницы не удалось."""
        try:
            c = await self._ensure_session()
            inbound = await self._get_inbound_json(c)
            existing, _, _ = await self._resolve_panel_client(inbound, tg_id)
            if not existing:
                return ""
            sub_id = str(existing.get("subId") or "").strip()
            if not sub_id:
                return ""
            return (self._subscription_link(sub_id) or "").strip()
        except Exception as e:
            log.debug("3x-ui _fallback_subscription_url [%s]: %s", self._label, e)
            return ""

    async def create_or_extend_subscription(
        self, tg_id: int, months: int, devices: int, *, tg_username: str | None = None
    ) -> dict[str, Any]:
        c = await self._ensure_session()
        inbound = await self._get_inbound_json(c)
        existing, client_uuid, email = await self._resolve_panel_client(
            inbound, tg_id, tg_username=tg_username
        )
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        add_ms = int(months * 30 * 86400 * 1000)

        if existing and client_uuid:
            old_exp = int(existing.get("expiryTime") or 0)
            base = max(old_exp, now_ms)
            new_exp = base + add_ms
            sub_id = str(existing.get("subId") or uuid.uuid4().hex[:16])
            upd = self._client_dict(
                tg_id, email, devices, new_exp, client_uuid, sub_id, enable=True
            )
            await self._update_client(c, client_uuid, upd)
            link = self._subscription_link(sub_id)
            links, primary = await self._links_for_client_async(link)
            return {
                "uuid": client_uuid,
                "links": links,
                "subscription_url": primary,
                "expiry_ms": new_exp,
                "node_label": self._label,
            }

        client_uuid = str(uuid.uuid4())
        sub_id = uuid.uuid4().hex[:16]
        new_exp = now_ms + add_ms
        cl = self._client_dict(tg_id, email, devices, new_exp, client_uuid, sub_id)
        try:
            await self._add_client(c, cl)
        except RuntimeError as e:
            if "Duplicate" in str(e) or "duplicate" in str(e).lower():
                inbound = await self._get_inbound_json(c)
                existing, client_uuid, _ = await self._resolve_panel_client(
                    inbound, tg_id, tg_username=tg_username
                )
                if existing and client_uuid:
                    return await self.create_or_extend_subscription(
                        tg_id, months, devices, tg_username=tg_username
                    )
            raise
        link = self._subscription_link(sub_id)
        links, primary = await self._links_for_client_async(link)
        return {
            "uuid": client_uuid,
            "links": links,
            "subscription_url": primary,
            "expiry_ms": new_exp,
            "node_label": self._label,
        }

    async def extend_by_days(self, tg_id: int, days: int) -> bool:
        try:
            c = await self._ensure_session()
            inbound = await self._get_inbound_json(c)
            existing, client_uuid, email = await self._resolve_panel_client(
                inbound, tg_id
            )
            if not existing or not client_uuid:
                return False
            now_ms = int(datetime.utcnow().timestamp() * 1000)
            add_ms = int(days * 86400 * 1000)
            old_exp = int(existing.get("expiryTime") or 0)
            base = max(old_exp, now_ms)
            new_exp = base + add_ms
            sub_id = str(existing.get("subId") or uuid.uuid4().hex[:16])
            devices = int(existing.get("limitIp") or 1)
            upd = self._client_dict(
                tg_id, email, devices, new_exp, client_uuid, sub_id, enable=True
            )
            await self._update_client(c, client_uuid, upd)
            return True
        except Exception as e:
            log.warning("3x-ui extend_by_days [%s]: %s", self._label, e)
            return False

    async def disable_client(self, tg_id: int) -> bool:
        try:
            c = await self._ensure_session()
            inbound = await self._get_inbound_json(c)
            existing, client_uuid, email = await self._resolve_panel_client(
                inbound, tg_id
            )
            if not existing or not client_uuid:
                return True
            now_ms = int(existing.get("expiryTime") or 0)
            sub_id = str(existing.get("subId") or "")
            devices = int(existing.get("limitIp") or 1)
            upd = self._client_dict(
                tg_id,
                email,
                devices,
                now_ms,
                client_uuid,
                sub_id or uuid.uuid4().hex[:16],
                enable=False,
            )
            await self._update_client(c, client_uuid, upd)
            return True
        except Exception as e:
            log.warning("3x-ui disable_client [%s]: %s", self._label, e)
            return False

    async def delete_client(self, tg_id: int) -> bool:
        try:
            c = await self._ensure_session()
            from urllib.parse import quote

            inbound = await self._get_inbound_json(c)
            existing, _, email = await self._resolve_panel_client(inbound, tg_id)
            if not existing:
                return True
            em = quote(email, safe="")
            path = self._path(
                f"/panel/api/inbounds/{self._inbound_id}/delClientByEmail/{em}"
            )
            r = await c.post(path)
            return r.status_code == 200
        except Exception as e:
            log.warning("3x-ui delete_client [%s]: %s", self._label, e)
            return False

    async def get_usage(self, tg_id: int) -> dict[str, Any]:
        try:
            c = await self._ensure_session()
            inbound = await self._get_inbound_json(c)
            existing, _, em = await self._resolve_panel_client(inbound, tg_id)
            if not existing:
                return {}
            r = await c.get(self._path(f"/panel/api/inbounds/getClientTraffics/{em}"))
            if r.status_code != 200:
                return {}
            data = r.json()
            obj = data.get("obj") or data
            if isinstance(obj, list) and obj:
                obj = obj[0]
            if not isinstance(obj, dict):
                return {}
            up = int(obj.get("upload", 0) or 0)
            down = int(obj.get("download", 0) or 0)
            used_gb = round((up + down) / 1e9, 2)
            return {
                "used_gb": used_gb,
                "expire": None,
                "status": "on" if obj.get("enable", True) else "off",
                "online_at": None,
                "node_label": self._label,
            }
        except Exception as e:
            log.warning("3x-ui get_usage [%s]: %s", self._label, e)
            return {}

    async def get_subscription_expiry(self, tg_id: int) -> datetime | None:
        try:
            c = await self._ensure_session()
            inbound = await self._get_inbound_json(c)
            existing, _, _ = await self._resolve_panel_client(inbound, tg_id)
            if not existing:
                return None
            ms = int(existing.get("expiryTime") or 0)
            if ms <= 0:
                return None
            return datetime.utcfromtimestamp(ms / 1000.0)
        except Exception as e:
            log.warning("3x-ui get_subscription_expiry [%s]: %s", self._label, e)
            return None

    async def sync_device_limit(self, tg_id: int, devices: int) -> bool:
        """Обновляет limitIp клиента без смены срока и subId."""
        try:
            c = await self._ensure_session()
            inbound = await self._get_inbound_json(c)
            existing, client_uuid, email = await self._resolve_panel_client(
                inbound, tg_id
            )
            if not existing or not client_uuid:
                return False
            want = max(1, int(devices))
            if int(existing.get("limitIp") or 0) == want:
                return True
            new_exp = int(existing.get("expiryTime") or 0)
            sub_id = str(existing.get("subId") or uuid.uuid4().hex[:16])
            en = bool(existing.get("enable", True))
            upd = self._client_dict(
                tg_id, email, want, new_exp, client_uuid, sub_id, enable=en
            )
            await self._update_client(c, client_uuid, upd)
            return True
        except Exception as e:
            log.warning("3x-ui sync_device_limit [%s]: %s", self._label, e)
            return False

    async def grant_free_days(
        self, tg_id: int, days: int, devices: int
    ) -> dict[str, Any]:
        dev = max(1, min(10, int(devices)))
        d = max(1, int(days))
        ext = await self.extend_by_days(tg_id, d)
        if not ext:
            try:
                await self.create_or_extend_subscription(tg_id, 0, dev)
            except Exception as e:
                log.exception("3x-ui grant_free_days create: [%s] %s", self._label, e)
                return {
                    "ok": False,
                    "links": [],
                    "subscription_url": "",
                    "expires": None,
                }
            ext = await self.extend_by_days(tg_id, d)
        if not ext:
            return {
                "ok": False,
                "links": [],
                "subscription_url": "",
                "expires": None,
            }
        merged, primary = await self.refresh_share_links_for_tg(tg_id)
        exp = await self.get_subscription_expiry(tg_id)
        url = (primary or "").strip() or (merged[0] if merged else "")
        return {
            "ok": True,
            "links": merged,
            "subscription_url": url,
            "expires": exp,
        }


class MultiXuiPanel(VpnPanel):
    """Зеркало: одни и те же операции на нескольких панелях 3x-ui."""

    def __init__(self, nodes: list[XuiNodeConfig]) -> None:
        if not nodes:
            raise ValueError("MultiXuiPanel: нужен хотя бы один узел")
        self._panels = [XuiPanel(n) for n in nodes]

    async def _sorted_panels(self) -> list[XuiPanel]:
        """Узлы с меньшим HTTP-пингом первыми — их vless попадают в начало списка ссылок."""
        from services.server_status import ping_xui_node_ms

        async def measure(p: XuiPanel) -> tuple[XuiPanel, float | None]:
            ms = await ping_xui_node_ms(p.node)
            return (p, ms)

        pairs = await asyncio.gather(*[measure(p) for p in self._panels])
        ordered = sorted(
            pairs,
            key=lambda x: (x[1] is None, x[1] if x[1] is not None else 1e12),
        )
        return [p for p, _ in ordered]

    async def create_or_extend_subscription(
        self, tg_id: int, months: int, devices: int, *, tg_username: str | None = None
    ) -> dict[str, Any]:
        panels = await self._sorted_panels()
        results = await asyncio.gather(
            *[p.create_or_extend_subscription(tg_id, months, devices, tg_username=tg_username) for p in panels],
            return_exceptions=True,
        )
        ok: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for p, res in zip(panels, results):
            if isinstance(res, Exception):
                log.error(
                    "MultiXui create_or_extend [%s]: %s", p.node_label, res, exc_info=res
                )
                errors.append({"label": p.node_label, "error": str(res)})
            else:
                ok.append(res)
        if not ok:
            raise RuntimeError(
                "Все узлы 3x-ui недоступны: "
                + "; ".join(f"{e['label']}: {e['error']}" for e in errors)
            )
        all_links: list[str] = []
        for r in ok:
            for L in r.get("links") or []:
                if L and L not in all_links:
                    all_links.append(L)
        primary = all_links[0] if all_links else (ok[0].get("subscription_url") or "")
        expiry_ms = max(int(r.get("expiry_ms") or 0) for r in ok)
        return {
            "uuid": ok[0].get("uuid"),
            "links": all_links,
            "subscription_url": primary,
            "expiry_ms": expiry_ms,
            "partial": len(errors) > 0,
            "node_errors": errors,
        }

    async def refresh_share_links_for_tg(self, tg_id: int) -> tuple[list[str], str]:
        merged: list[str] = []
        primary = ""
        for p in await self._sorted_panels():
            links, pr = await p.refresh_share_links_for_tg(tg_id)
            if pr and not primary:
                primary = pr
            for x in links:
                if x and x not in merged:
                    merged.append(x)
        return merged, primary

    async def sync_device_limit(self, tg_id: int, devices: int) -> bool:
        results = await asyncio.gather(
            *[p.sync_device_limit(tg_id, devices) for p in self._panels],
            return_exceptions=True,
        )
        oks = 0
        for p, res in zip(self._panels, results):
            if res is True:
                oks += 1
            elif isinstance(res, Exception):
                log.warning("MultiXui sync_device_limit [%s]: %s", p.node_label, res)
        return oks == len(self._panels)

    async def grant_free_days(
        self, tg_id: int, days: int, devices: int
    ) -> dict[str, Any]:
        dev = max(1, min(10, int(devices)))
        d = max(1, int(days))
        # Сначала проверяем все узлы (TLS/сеть). Иначе при падении второго узла
        # первый уже мог получить +дни, а промокод в боте — «ошибка».
        for p in self._panels:
            try:
                await p._ensure_session()
            except Exception as e:
                log.warning(
                    "MultiXui grant_free_days: узел «%s» недоступен до начисления: %s. "
                    "Обновите сертификат HTTPS на панели или в XUI_NODES для этого узла "
                    'укажите "verify_ssl": false.',
                    p.node_label,
                    e,
                )
                return {
                    "ok": False,
                    "links": [],
                    "subscription_url": "",
                    "expires": None,
                }
        for p in self._panels:
            ext = await p.extend_by_days(tg_id, d)
            if not ext:
                try:
                    await p.create_or_extend_subscription(tg_id, 0, dev)
                except Exception as e:
                    log.warning(
                        "MultiXui grant_free_days create [%s]: %s",
                        p.node_label,
                        e,
                    )
                ext = await p.extend_by_days(tg_id, d)
            if not ext:
                return {
                    "ok": False,
                    "links": [],
                    "subscription_url": "",
                    "expires": None,
                }
        merged, primary = await self.refresh_share_links_for_tg(tg_id)
        exp = await self.get_subscription_expiry(tg_id)
        url = (primary or "").strip() or (merged[0] if merged else "")
        if not url:
            for p in self._panels:
                cand = await p._fallback_subscription_url(tg_id)
                if cand:
                    url = cand.strip()
                    break
        if url and not merged:
            merged = [url]
        elif url and merged and url not in merged and url.lower().startswith("http"):
            merged = [url] + merged
        primary_out = (primary or "").strip() or url
        return {
            "ok": bool(primary_out or url),
            "links": merged,
            "subscription_url": primary_out or url,
            "expires": exp,
        }

    async def extend_by_days(self, tg_id: int, days: int) -> bool:
        results = await asyncio.gather(
            *[p.extend_by_days(tg_id, days) for p in self._panels],
            return_exceptions=True,
        )
        oks = 0
        for p, res in zip(self._panels, results):
            if res is True:
                oks += 1
            elif isinstance(res, Exception):
                log.warning("MultiXui extend_by_days [%s]: %s", p.node_label, res)
        return oks == len(self._panels)

    async def disable_client(self, tg_id: int) -> bool:
        results = await asyncio.gather(
            *[p.disable_client(tg_id) for p in self._panels],
            return_exceptions=True,
        )
        for p, r in zip(self._panels, results):
            if isinstance(r, Exception):
                log.warning("MultiXui disable_client [%s]: %s", p.node_label, r)
                return False
            if r is not True:
                return False
        return True

    async def delete_client(self, tg_id: int) -> bool:
        results = await asyncio.gather(
            *[p.delete_client(tg_id) for p in self._panels],
            return_exceptions=True,
        )
        for p, r in zip(self._panels, results):
            if isinstance(r, Exception):
                log.warning("MultiXui delete_client [%s]: %s", p.node_label, r)
                return False
            if r is not True:
                return False
        return True

    async def get_usage(self, tg_id: int) -> dict[str, Any]:
        parts = await asyncio.gather(
            *[p.get_usage(tg_id) for p in self._panels], return_exceptions=True
        )
        total_gb = 0.0
        labels: list[str] = []
        status = "off"
        for p, u in zip(self._panels, parts):
            if isinstance(u, Exception):
                labels.append(f"{p.node_label}: ?")
                continue
            total_gb += float(u.get("used_gb") or 0)
            if u.get("status") == "on":
                status = "on"
            labels.append(
                f"{u.get('node_label') or p.node_label}: {u.get('used_gb', 0)} ГБ"
            )
        return {
            "used_gb": round(total_gb, 2),
            "expire": None,
            "status": status,
            "online_at": None,
            "per_node": ", ".join(labels),
        }

    async def get_subscription_expiry(self, tg_id: int) -> datetime | None:
        exps = await asyncio.gather(
            *[p.get_subscription_expiry(tg_id) for p in self._panels],
            return_exceptions=True,
        )
        valid: list[datetime] = []
        for p, e in zip(self._panels, exps):
            if isinstance(e, Exception):
                log.warning("MultiXui get_subscription_expiry [%s]: %s", p.node_label, e)
                continue
            if e is not None:
                valid.append(e)
        return max(valid) if valid else None
