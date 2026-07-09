"""
NINAVPN Bot — точка входа
Запуск: python main.py
"""
import asyncio
import json
import logging
import time
from html import escape as html_escape
from collections import defaultdict
from pathlib import Path

from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault
from config import settings, bot_username_clean, bot_telegram_https_url, payment_public_base_url
from database import init_db
from handlers.ban_middleware import BanMiddleware
from handlers.channel_subscription_middleware import ChannelSubscriptionMiddleware
from handlers.safe_callback_answer_middleware import SafeCallbackAnswerMiddleware
from handlers.main import (
    router,
    handle_freekassa_webhook,
    handle_tbank_webhook,
)
from utils.scheduler import scheduler_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"

# (ip, path) → метки времени запросов за последнюю минуту
_miniapp_rate_bucket: dict[tuple[str, str], list[float]] = defaultdict(list)


def _request_client_ip(request: web.Request) -> str:
    return (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.remote or "")
    )


@web.middleware
async def security_middleware(request: web.Request, handler):
    path = request.path
    if path.startswith("/miniapp/api/") or path.startswith("/api/checkout/"):
        lim = int(getattr(settings, "MINIAPP_API_RATE_LIMIT_PER_MIN", 0) or 0)
        if lim > 0:
            ip = _request_client_ip(request)
            now = time.monotonic()
            key = (ip, path)
            bucket = _miniapp_rate_bucket[key]
            bucket[:] = [t for t in bucket if now - t < 60.0]
            if len(bucket) >= lim:
                return web.json_response(
                    {"error": "too_many_requests"},
                    status=429,
                    headers={"X-Content-Type-Options": "nosniff"},
                )
            bucket.append(now)

    resp = await handler(request)
    if isinstance(resp, web.StreamResponse):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
    return resp


# ══════════════════════════════════════════════════════════════
#  Webhook-сервер для Freekassa (aiohttp, порт 8080)
#  Nginx проксирует: /payment/* → http://localhost:8080/payment/*
# ══════════════════════════════════════════════════════════════

async def freekassa_notify(request: web.Request) -> web.Response:
    """
    GET/POST /payment/freekassa — IPN от Freekassa.
    Ждёт ответ YES — иначе повторяет запрос.
    IP: 168.119.157.136, 168.119.60.227, 178.154.197.79, 51.250.54.238
    """
    client_ip = (
        request.headers.get("X-Real-IP") or
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
        request.remote or ""
    )
    if request.method == "POST":
        try:
            data = dict(await request.post())
        except Exception:
            data = dict(request.rel_url.query)
    else:
        data = dict(request.rel_url.query)

    from utils.safe_log import freekassa_log_summary

    log.info("Freekassa IPN: %s", freekassa_log_summary(data, client_ip))
    bot: Bot = request.app["bot"]
    result = await handle_freekassa_webhook(data, bot, client_ip)
    response_text = result.get("text", "NO") if result else "NO"
    if response_text == "YES":
        return web.Response(text="YES", content_type="text/plain")
    log.warning(f"Freekassa webhook rejected: {result}")
    return web.Response(text="NO", content_type="text/plain", status=400)


async def tbank_notify(request: web.Request) -> web.Response:
    """POST /payment/tbank — уведомления интернет-эквайринга Т-Банка (JSON)."""
    if request.method == "GET":
        # Проверка URL в браузере / кабинете Т-Бизнес (реальные уведомления — только POST).
        return web.Response(
            status=200,
            text="OK — webhook Т-Банка. Уведомления принимаются методом POST.",
            content_type="text/plain",
        )
    if request.method != "POST":
        return web.Response(status=405, text="Method Not Allowed", headers={"Allow": "GET, POST"})
    bot: Bot = request.app["bot"]
    data: dict
    try:
        raw = await request.json()
        data = raw if isinstance(raw, dict) else {}
    except Exception:
        try:
            data = dict(await request.post())
        except Exception:
            data = {}
    log.info("T-Bank notify: keys=%s", list(data.keys()))
    result = await handle_tbank_webhook(data, bot)
    if result.get("ok"):
        return web.Response(status=200, text="OK", content_type="text/plain")
    code = int(result.get("http_status", 500))
    return web.Response(status=code, text="ERR", content_type="text/plain")


async def payment_success(request: web.Request) -> web.Response:
    """GET /payment/success — после оплаты с сайта (конфиг по checkout token)."""
    token = (request.rel_url.query.get("t") or "").strip()
    site_href = html_escape(payment_public_base_url() or "https://ninavpn.store")
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Оплата прошла — NINAVPN</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0f;color:#F0EEFF;font-family:'Segoe UI',sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px}}
.box{{max-width:520px;width:100%;padding:40px 28px;text-align:center}}
.icon{{font-size:3.5rem;margin-bottom:16px}}
h1{{font-size:1.5rem;font-weight:700;margin-bottom:12px}}
p,li{{color:#6b6b90;font-size:0.95rem;line-height:1.6}}
.muted{{margin:12px 0 20px}}
.link-box{{background:#111120;border:1px solid rgba(123,47,255,0.25);border-radius:14px;
  padding:14px;margin:16px 0;text-align:left;word-break:break-all;font-size:0.85rem;color:#c8c6e8}}
.btn{{display:inline-block;background:linear-gradient(135deg,#7B2FFF,#FF2FA0);
  color:#fff;padding:12px 24px;border-radius:100px;text-decoration:none;font-weight:600;margin:6px}}
.btn-ghost{{background:transparent;border:1.5px solid rgba(123,47,255,0.35)}}
.spinner{{width:36px;height:36px;border:3px solid rgba(123,47,255,0.2);
  border-top-color:#7B2FFF;border-radius:50%;animation:spin 0.8s linear infinite;margin:20px auto}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.hidden{{display:none}}
ol{{text-align:left;padding-left:20px;margin-top:12px}}
</style></head>
<body><div class="box">
<div id="state-wait">
  <div class="spinner"></div>
  <h1>Оплата принята</h1>
  <p class="muted">Создаём VPN-доступ… обычно это занимает до минуты.</p>
</div>
<div id="state-ready" class="hidden">
  <div class="icon">✅</div>
  <h1>Готово!</h1>
  <p class="muted">Скопируй ссылку подписки и вставь в приложение v2rayNG / Streisand / Hiddify.</p>
  <div class="link-box" id="mainLink"></div>
  <div class="link-box hidden" id="extraLink"></div>
  <p class="muted" id="expiresLine"></p>
  <a class="btn" href="#" id="copyBtn">Скопировать ссылку</a>
  <a class="btn btn-ghost" href="{site_href}">На главную</a>
  <ol>
    <li>Установи v2rayNG (Android) или Streisand (iOS)</li>
    <li>Импортируй ссылку подписки</li>
    <li>Включи VPN</li>
  </ol>
</div>
<div id="state-pending" class="hidden">
  <div class="icon">⏳</div>
  <h1>Ожидаем подтверждение</h1>
  <p class="muted">Если оплата прошла, страница обновится автоматически.</p>
</div>
<div id="state-error" class="hidden">
  <div class="icon">⚠️</div>
  <h1>Не удалось получить конфиг</h1>
  <p class="muted" id="errText">Напишите в поддержку с номером заказа.</p>
  <a class="btn" href="{site_href}">На главную</a>
</div>
</div>
<script>
const token = {json.dumps(token)};
const mainEl = document.getElementById('mainLink');
const extraEl = document.getElementById('extraLink');
const copyBtn = document.getElementById('copyBtn');
let configUrl = '';

function show(id) {{
  ['state-wait','state-ready','state-pending','state-error'].forEach(s => {{
    document.getElementById(s).classList.toggle('hidden', s !== id);
  }});
}}

async function poll() {{
  if (!token) {{
    document.getElementById('errText').textContent = 'Нет кода заказа. Вернитесь на сайт и оформите снова.';
    show('state-error');
    return;
  }}
  try {{
    const r = await fetch('/api/checkout/status?t=' + encodeURIComponent(token));
    const data = await r.json();
    if (!data.ok) {{
      document.getElementById('errText').textContent = 'Заказ не найден.';
      show('state-error');
      return;
    }}
    if (data.status === 'confirmed' && data.config_link) {{
      configUrl = data.config_link;
      mainEl.textContent = data.config_link;
      if (data.config_link_extra) {{
        extraEl.textContent = data.config_link_extra;
        extraEl.classList.remove('hidden');
      }}
      if (data.expires_at) {{
        document.getElementById('expiresLine').textContent = 'Действует до ' + data.expires_at;
      }}
      show('state-ready');
      return;
    }}
    if (data.status === 'failed') {{
      document.getElementById('errText').textContent = 'Оплата не завершена. Заказ #' + data.payment_id;
      show('state-error');
      return;
    }}
    show(data.status === 'pending' ? 'state-pending' : 'state-wait');
    setTimeout(poll, 2500);
  }} catch (e) {{
    setTimeout(poll, 3000);
  }}
}}
copyBtn?.addEventListener('click', (e) => {{
  e.preventDefault();
  if (!configUrl) return;
  navigator.clipboard.writeText(configUrl).then(() => {{ copyBtn.textContent = 'Скопировано ✓'; }});
}});
poll();
</script></body></html>"""
    return web.Response(text=html, content_type="text/html")


async def payment_fail(request: web.Request) -> web.Response:
    """GET /payment/fail — отмена оплаты на стороне Т-Банка."""
    site_href = html_escape(payment_public_base_url() or "https://ninavpn.store")
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Оплата отменена — NINAVPN</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0f;color:#F0EEFF;font-family:'Segoe UI',sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center}}
.box{{max-width:420px;padding:48px 32px}}
.icon{{font-size:4rem;margin-bottom:20px}}
h1{{font-size:1.6rem;font-weight:700;margin-bottom:12px}}
p{{color:#6b6b90;font-size:0.95rem;line-height:1.6;margin-bottom:28px}}
a{{display:inline-block;background:linear-gradient(135deg,#7B2FFF,#FF2FA0);
  color:#fff;padding:14px 32px;border-radius:100px;text-decoration:none;font-weight:600}}
</style></head>
<body><div class="box">
<div class="icon">❌</div>
<h1>Оплата отменена</h1>
<p>Деньги не списаны.<br>Можно попробовать снова на сайте.</p>
<a href="{site_href}#pricing">Вернуться к тарифам</a>
</div></body></html>"""
    return web.Response(text=html, content_type="text/html")


async def api_checkout_tbank(request: web.Request) -> web.Response:
    """POST /api/checkout/tbank — создать оплату Т-Банка с сайта (JSON)."""
    if request.method != "POST":
        return web.json_response({"error": "method_not_allowed"}, status=405)
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"success": False, "error": "invalid_json"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"success": False, "error": "invalid_json"}, status=400)

    from services.checkout import create_site_tbank_checkout

    email = str(body.get("email") or "")
    plan_key = body.get("plan_key")
    months = body.get("months")
    devices = body.get("devices")
    try:
        months_i = int(months) if months is not None else None
    except (TypeError, ValueError):
        months_i = None
    try:
        devices_i = int(devices) if devices is not None else None
    except (TypeError, ValueError):
        devices_i = None

    result = await create_site_tbank_checkout(
        email=email,
        plan_key=str(plan_key).strip() if plan_key else None,
        months=months_i,
        devices=devices_i,
    )
    status = 200 if result.get("success") else 400
    return web.json_response(result, status=status)


async def api_checkout_status(request: web.Request) -> web.Response:
    """GET /api/checkout/status?t=... — статус заказа и ссылка подписки."""
    token = (request.rel_url.query.get("t") or request.rel_url.query.get("token") or "").strip()
    from services.checkout import get_checkout_status

    data = await get_checkout_status(token)
    status = 200 if data.get("ok") else 404
    return web.json_response(data, status=status)


async def miniapp_api_plans(request: web.Request) -> web.Response:
    """GET /miniapp/api/plans — каталог тарифов (как в боте, из БД или PLANS)."""
    from services.catalog import get_plans_catalog

    try:
        plans = await get_plans_catalog()
    except Exception:
        log.exception("miniapp_api_plans")
        return web.json_response({"error": "catalog"}, status=500)
    out: dict = {}
    for k, v in plans.items():
        out[str(k)] = {
            "name": v.get("name"),
            "description": v.get("description") or "",
            "months": int(v.get("months") or 0),
            "devices": int(v.get("devices") or 0),
            "price_rub": float(v.get("price_rub") or 0),
            "price_usdt": float(v.get("price_usdt") or 0),
            "emoji": v.get("emoji") or "📦",
            "popular": bool(v.get("popular")),
        }
    resp = web.json_response(out)
    resp.headers["Cache-Control"] = "public, max-age=60"
    return resp


async def miniapp_api_config(request: web.Request) -> web.Response:
    """GET /miniapp/api/config — ссылка на бота для кнопки внутри Mini App."""
    u = bot_username_clean()
    return web.json_response(
        {
            "bot_username": u or None,
            "bot_open_url": f"https://t.me/{u}" if u else None,
        }
    )


async def miniapp_index(request: web.Request) -> web.Response:
    """GET /miniapp/ — точка входа Telegram Mini App."""
    index = WEBAPP_DIR / "index.html"
    if not index.is_file():
        return web.Response(status=404, text="Mini App: index.html not found")
    return web.FileResponse(index)


async def v2ray_geo_geoip(request: web.Request) -> web.Response:
    """GET /geo/geoip.dat — кэш runetfreedom/russia-v2ray-rules-dat (для v2rayN и др.)."""
    from services.v2ray_geo import get_bytes

    if not settings.V2RAY_GEO_ENABLED:
        return web.Response(status=404, text="disabled")
    try:
        data = await get_bytes("geoip")
    except Exception:
        log.exception("geo/geoip.dat")
        return web.Response(status=502, text="upstream error")
    resp = web.Response(body=data, content_type="application/octet-stream")
    ttl = max(60, int(getattr(settings, "V2RAY_GEO_CACHE_TTL_SEC", 21600) or 21600))
    resp.headers["Cache-Control"] = f"public, max-age={ttl}"
    return resp


async def v2ray_geo_geosite(request: web.Request) -> web.Response:
    """GET /geo/geosite.dat — кэш runetfreedom/russia-v2ray-rules-dat."""
    from services.v2ray_geo import get_bytes

    if not settings.V2RAY_GEO_ENABLED:
        return web.Response(status=404, text="disabled")
    try:
        data = await get_bytes("geosite")
    except Exception:
        log.exception("geo/geosite.dat")
        return web.Response(status=502, text="upstream error")
    resp = web.Response(body=data, content_type="application/octet-stream")
    ttl = max(60, int(getattr(settings, "V2RAY_GEO_CACHE_TTL_SEC", 21600) or 21600))
    resp.headers["Cache-Control"] = f"public, max-age={ttl}"
    return resp


async def setup_bot_commands(bot: Bot) -> None:
    """Меню команд на русском (перекрывает список из BotFather для всех пользователей)."""
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Меню, подписка и оплата"),
        ],
        BotCommandScopeDefault(),
    )


async def start_webhook_server(bot: Bot):
    """Запускает aiohttp-сервер на порту 8080."""
    app = web.Application(middlewares=[security_middleware])
    app["bot"] = bot
    app.router.add_get("/payment/freekassa", freekassa_notify)
    app.router.add_post("/payment/freekassa", freekassa_notify)  # Freekassa может слать и POST
    app.router.add_get("/payment/tbank", tbank_notify)
    app.router.add_post("/payment/tbank", tbank_notify)
    app.router.add_get("/payment/success",   payment_success)
    app.router.add_get("/payment/fail",      payment_fail)

    app.router.add_post("/api/checkout/tbank", api_checkout_tbank)
    app.router.add_get("/api/checkout/status", api_checkout_status)

    app.router.add_get("/miniapp/api/plans", miniapp_api_plans)
    app.router.add_get("/miniapp/api/config", miniapp_api_config)
    app.router.add_get("/miniapp", miniapp_index)
    app.router.add_get("/miniapp/", miniapp_index)
    app.router.add_static("/miniapp/static", WEBAPP_DIR / "static")

    if settings.V2RAY_GEO_ENABLED:
        app.router.add_get("/geo/geoip.dat", v2ray_geo_geoip)
        app.router.add_get("/geo/geosite.dat", v2ray_geo_geosite)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8080)
    await site.start()
    log.info(
        "HTTP-сервер на http://127.0.0.1:8080 — payment/*, api/checkout/*, miniapp/*"
        + (" и /geo/*.dat" if settings.V2RAY_GEO_ENABLED else "")
        + " (проксируйте /payment/, /miniapp/"
        + (", /geo/" if settings.V2RAY_GEO_ENABLED else "")
        + " в nginx)"
    )
    if settings.V2RAY_GEO_ENABLED:
        from services.v2ray_geo import prefetch_both

        asyncio.create_task(prefetch_both())

async def main():
    # ── БД ──────────────────────────────────────────────────
    await init_db()
    log.info("База данных инициализирована")

    # ── Бот ─────────────────────────────────────────────────
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(BanMiddleware())
    dp.callback_query.middleware(BanMiddleware())
    dp.message.middleware(ChannelSubscriptionMiddleware())
    dp.callback_query.middleware(ChannelSubscriptionMiddleware())
    dp.callback_query.middleware(SafeCallbackAnswerMiddleware())
    dp.include_router(router)

    try:
        await setup_bot_commands(bot)
    except Exception as e:
        log.warning("Не удалось установить меню команд: %s", e)

    # ── Планировщик (в фоне) ────────────────────────────────
    asyncio.create_task(scheduler_loop(bot))
    asyncio.create_task(start_webhook_server(bot))

    # ── Уведомление админа о старте ─────────────────────────
    try:
        await bot.send_message(
            settings.ADMIN_ID,
            "🚀 <b>NINAVPN Bot запущен!</b>\n\n"
            f"📅 {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            "Используй /admin для управления.",
        )
    except Exception:
        pass

    log.info("Бот запущен, начинаю polling...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
