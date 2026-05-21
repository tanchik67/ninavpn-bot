"""
Сервис оплаты:
  - USDT TRC-20: проверка через Tronscan API (бесплатно)
  - TON:         проверка через toncenter.com (бесплатно)
  - Freekassa:   webhook-подтверждение (карты РФ + СБП)
"""
import hashlib
import hmac
import httpx
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from config import settings

log = logging.getLogger(__name__)

# Мин. суммы для подтверждения (защита от пыли)
MIN_USDT = 0.5
MIN_TON  = 0.01


def unique_usdt_amount(base: float, payment_id: int) -> float:
    """Уникальная сумма USDT для привязки платежа к заказу (микро-хвост по id)."""
    return round(float(base) + int(payment_id) * 1e-6, 6)


def unique_ton_amount(base: float, payment_id: int) -> float:
    """Уникальная сумма TON для привязки к заказу."""
    return round(float(base) + int(payment_id) * 1e-9, 9)


# ═══════════════════════════════════════════════════════════
#  USDT TRC-20  (Tronscan API — без ключа, rate limit 5 rps)
# ═══════════════════════════════════════════════════════════
USDT_CONTRACT_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

async def check_usdt_payment(
    wallet: str,
    expected_usdt: float,
    absolute_tolerance: float = 2e-6,
    minutes_back: int = 180,
) -> Optional[Dict[str, Any]]:
    """
    Ищет входящий перевод USDT TRC-20 на wallet за последние minutes_back минут.
    Сумма должна совпадать с ожидаемой (уникальной для payment_id) с допуском absolute_tolerance.
    Возвращает {"tx_hash": str, "amount": float} или None.
    """
    url = "https://apilist.tronscanapi.com/api/token_trc20/transfers"
    params = {
        "toAddress": wallet,
        "tokens": USDT_CONTRACT_TRC20,
        "limit": 20,
        "start": 0,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        cutoff = datetime.utcnow() - timedelta(minutes=minutes_back)
        for tx in data.get("token_transfers", []):
            ts = datetime.utcfromtimestamp(tx["block_ts"] / 1000)
            if ts < cutoff:
                continue
            amount = float(tx["quant"]) / 1e6   # USDT имеет 6 decimals
            if abs(amount - expected_usdt) <= absolute_tolerance:
                log.info(f"USDT TX найден: {tx['transaction_id']} / {amount} USDT")
                return {"tx_hash": tx["transaction_id"], "amount": amount}
    except Exception as e:
        log.error(f"USDT check error: {e}")
    return None


# ═══════════════════════════════════════════════════════════
#  TON  (toncenter.com — бесплатный API)
# ═══════════════════════════════════════════════════════════
def _ton_wallet_looks_like_placeholder(addr: str) -> bool:
    a = (addr or "").strip()
    if not a:
        return True
    # как в .env.example — toncenter вернёт 422 «failed to parse address»
    if "xxxxxxxx" in a.lower():
        return True
    return False


def _ton_tx_hash(tx: dict) -> str:
    tid = tx.get("transaction_id")
    if isinstance(tid, dict):
        return str(tid.get("hash") or tid.get("lt") or tid)
    return str(tid) if tid is not None else ""


async def check_ton_payment(
    wallet: str,
    expected_ton: float,
    absolute_tolerance: float = 1e-7,
    minutes_back: int = 180,
) -> Optional[Dict[str, Any]]:
    """
    Ищет входящий TON-перевод на wallet (сумма с уникальным хвостом по заказу).
    """
    wallet = (wallet or "").strip()
    if _ton_wallet_looks_like_placeholder(wallet):
        log.warning(
            "TON: в .env указан нереальный TON_WALLET (заглушка или пусто). "
            "Укажите адрес из TonKeeper / TonHub (UQ… или EQ…). Проверка TON пропущена."
        )
        return None

    url = "https://toncenter.com/api/v2/getTransactions"
    params: dict = {"address": wallet, "limit": 20}
    key = (getattr(settings, "TONCENTER_API_KEY", None) or "").strip()
    if key:
        params["api_key"] = key

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, params=params)

        if r.status_code != 200:
            try:
                err_body = r.json()
                detail = err_body.get("error", r.text[:300])
            except Exception:
                detail = r.text[:300]
            if r.status_code == 422:
                log.error(
                    "TON: toncenter отклонил адрес (%s). Проверьте TON_WALLET в .env.",
                    detail,
                )
            else:
                log.error("TON check HTTP %s: %s", r.status_code, detail)
            return None

        data = r.json()
        if not data.get("ok"):
            log.error("TON: toncenter ok=false: %s", data.get("error", data))
            return None

        cutoff = datetime.utcnow() - timedelta(minutes=minutes_back)
        for tx in data.get("result", []):
            msg = tx.get("in_msg") or {}
            val = msg.get("value")
            if val is None or val == "" or val == "0":
                continue
            ts = datetime.utcfromtimestamp(int(tx["utime"]))
            if ts < cutoff:
                continue
            amount_ton = int(val) / 1e9
            if abs(amount_ton - expected_ton) <= absolute_tolerance:
                th = _ton_tx_hash(tx)
                log.info("TON TX найден: %s / %s TON", th, amount_ton)
                return {"tx_hash": th, "amount": amount_ton}
    except Exception as e:
        log.error(f"TON check error: {e}")
    return None


# ═══════════════════════════════════════════════════════════
#  Freekassa — генерация ссылки и проверка подписи webhook
# ═══════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════
#  Freekassa SCI  (docs.freekassa.net)
#  Форма оплаты:  https://pay.fk.money/
#  API:           https://api.fk.life/v1/
# ═══════════════════════════════════════════════════════════

FREEKASSA_PAY_URL = "https://pay.fk.money/"
FREEKASSA_API_URL = "https://api.fk.life/v1/"

# IP-адреса Freekassa для проверки webhook (из документации)
FREEKASSA_IPS = {
    "168.119.157.136",
    "168.119.60.227",
    "178.154.197.79",
    "51.250.54.238",
}


def freekassa_payment_url(
    order_id: str,
    amount_rub: float,
    description: str = "NINAVPN подписка",
    currency_id: int = 42,   # 42 = СБП, 36 = Card RUB API, 4 = VISA RUB
) -> str:
    """
    Генерирует ссылку на форму оплаты Freekassa (SCI).

    Подпись: MD5(shopId:amount:secret1:currency:orderId)
    Документация: https://docs.freekassa.net/#section/1.-Vvedenie/1.5.
    """
    m        = settings.FREEKASSA_MERCHANT_ID
    s1       = settings.FREEKASSA_SECRET1
    currency = "RUB"

    # Формат суммы строго с двумя знаками после запятой
    amount_str = f"{amount_rub:.2f}"

    # Подпись: shopId:amount:secret1:currency:orderId
    sign_str = f"{m}:{amount_str}:{s1}:{currency}:{order_id}"
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    params = (
        f"?m={m}"
        f"&oa={amount_str}"
        f"&currency={currency}"
        f"&o={order_id}"
        f"&s={sign}"
        f"&i={currency_id}"       # предпочтительный способ оплаты
        f"&lang=ru"
        f"&us_order={order_id}"   # доп. параметр — вернётся в webhook
    )
    return FREEKASSA_PAY_URL + params


def verify_freekassa_webhook(data: dict, client_ip: str = "") -> bool:
    """
    Проверяет подпись IPN-уведомления от Freekassa.

    Freekassa шлёт GET с параметрами на URL оповещения.
    Подпись: MD5(shopId:amount:secret2:orderId)
    Документация: https://docs.freekassa.net/#section/1.-Vvedenie/1.7.

    Также проверяем IP отправителя (опционально).
    """
    # Проверка IP (рекомендуется документацией; строгий режим — в .env)
    if client_ip and client_ip not in FREEKASSA_IPS:
        log.warning("Freekassa webhook с неизвестного IP: %s", client_ip)
        strict = bool(getattr(settings, "FREEKASSA_WEBHOOK_STRICT_IP", False))
        if strict:
            log.error("Freekassa IPN отклонён (FREEKASSA_WEBHOOK_STRICT_IP=1)")
            return False

    s2     = settings.FREEKASSA_SECRET2
    m      = data.get("MERCHANT_ID", "")
    amount = data.get("AMOUNT", "")
    order  = data.get("MERCHANT_ORDER_ID", "")
    sign   = data.get("SIGN", "")

    if not all([m, amount, order, sign]):
        log.error("Freekassa webhook: отсутствуют обязательные параметры")
        return False

    # Подпись: shopId:amount:secret2:orderId
    expected = hashlib.md5(
        f"{m}:{amount}:{s2}:{order}".encode("utf-8")
    ).hexdigest()

    ok = hmac.compare_digest(expected.lower(), str(sign).lower())
    if not ok:
        log.error("Freekassa: неверная подпись IPN (order=%s)", order)
    return ok


async def freekassa_check_order(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Проверяет статус заказа через Freekassa API.
    Возвращает данные заказа или None при ошибке.
    Статусы: 0=новый, 1=оплачен, 6=возврат, 8=ошибка, 9=отмена
    """
    import time
    api_key = getattr(settings, 'FREEKASSA_API_KEY', None)
    if not api_key:
        log.warning("FREEKASSA_API_KEY не задан — проверка статуса недоступна")
        return None

    shop_id = int(settings.FREEKASSA_MERCHANT_ID)
    nonce   = int(time.time())

    # Подпись API: HMAC-SHA256 от отсортированных значений через |
    data_to_sign = {"shopId": shop_id, "nonce": nonce, "paymentId": order_id}
    sorted_vals  = "|".join(str(v) for k, v in sorted(data_to_sign.items()))
    signature    = hmac.new(
        api_key.encode(), sorted_vals.encode(), "sha256"
    ).hexdigest()

    payload = {**data_to_sign, "signature": signature}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{FREEKASSA_API_URL}orders", json=payload)
            r.raise_for_status()
            data = r.json()
            if data.get("type") == "success" and data.get("orders"):
                return data["orders"][0]
    except Exception as e:
        log.error(f"Freekassa API error: {e}")
    return None


# ═══════════════════════════════════════════════════════════
#  Курс TON к рублю (CoinGecko — бесплатно)
# ═══════════════════════════════════════════════════════════
async def get_ton_price_rub() -> float:
    """Возвращает текущий курс 1 TON в рублях."""
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "the-open-network", "vs_currencies": "rub"},
            )
            r.raise_for_status()
            return float(r.json()["the-open-network"]["rub"])
    except Exception as e:
        log.warning(f"Курс TON недоступен: {e}")
        return 600.0   # fallback


async def rub_to_ton(rub: float) -> float:
    price = await get_ton_price_rub()
    return round(rub / price, 3)
