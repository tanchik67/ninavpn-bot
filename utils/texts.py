from typing import Any, Dict, Optional

from config import PLANS, EXTRA_DEVICE_PRICE, EXTRA_DEVICE_USDT, bot_username_clean, settings


def txt_welcome(name: str, ref_from_link: bool = False) -> str:
    bonus = ""
    if ref_from_link:
        ib = max(0, int(getattr(settings, "REFERRAL_INVITEE_BONUS_DAYS", 0) or 0))
        rb = max(1, int(getattr(settings, "REFERRAL_BONUS_DAYS", 30) or 30))
        if ib > 0:
            bonus = (
                f"\n\n🎁 По реферальной ссылке: к <b>первой оплате</b> подписки добавится "
                f"<b>+{ib}</b> дн. VPN."
            )
        else:
            bonus = (
                f"\n\n🤝 Ты перешёл по ссылке друга. Когда ты <b>первый раз оплатишь</b> подписку, "
                f"он получит <b>+{rb}</b> дн. к своему VPN."
            )
    return (
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"Добро пожаловать в <b>NINAVPN</b> — быстрый VPN на v2ray/XTLS.\n\n"
        f"<b>Что умею:</b>\n"
        f"🛒 Оформить подписку (USDT, TON, рубли — как настроено в боте)\n"
        f"📋 Показать твои активные конфиги\n"
        f"🌍 Статус серверов в реальном времени\n"
        f"🎁 Применить промокод\n"
        f"👥 Реферальная программа — зарабатывай{bonus}"
    )


def txt_plans(
    plans: Optional[Dict[str, Any]] = None,
    *,
    promo_bonus_days: int = 0,
) -> str:
    catalog = plans if plans is not None else PLANS
    bd = max(0, int(promo_bonus_days))
    lines = ["💳 <b>Выбери тариф:</b>\n"]
    if bd:
        lines.append(
            f"🎁 Промокод: <b>+{bd}</b> бесплатных дн. доступа (активация в разделе «Промокод»).\n"
        )
    for key, p in catalog.items():
        popular = " ⭐ <i>Хит продаж</i>" if p.get("popular") else ""
        rub = float(p["price_rub"])
        usdt = float(p["price_usdt"])
        lines.append(
            f"{p['emoji']} <b>{p['name']}</b>{popular}\n"
            f"   {p['description']}\n"
            f"   <b>{rub:g} ₽</b>  /  <b>{usdt:g} USDT</b>\n"
        )
    lines.append("\n🔧 Или собери <b>свой тариф</b> в конструкторе.")
    return "\n".join(lines)


def txt_plan_detail(
    key: str,
    plans: Optional[Dict[str, Any]] = None,
    *,
    promo_bonus_days: int = 0,
) -> str:
    catalog = plans if plans is not None else PLANS
    p = catalog[key]
    bd = max(0, int(promo_bonus_days))
    rub = float(p["price_rub"])
    usdt = float(p["price_usdt"])
    price_line = f"💰 Стоимость: <b>{rub:.0f} ₽</b>  /  <b>{usdt:g} USDT</b>"
    bonus_line = ""
    if bd:
        bonus_line = f"\n🎁 Промокод: <b>+{bd} дн.</b> бесплатного доступа при вводе кода."
    return (
        f"{p['emoji']} <b>{p['name']}</b>\n\n"
        f"📅 Срок: <b>{p['months']} мес.</b>\n"
        f"📱 Устройств: <b>{p['devices']}</b>\n"
        f"🌍 Серверы: все локации включены\n"
        f"⚡ Трафик: безлимит\n\n"
        f"{price_line}{bonus_line}\n\n"
        f"Выбери способ оплаты 👇"
    )


def txt_constructor_period() -> str:
    return (
        "🔧 <b>Конструктор тарифа</b>\n\n"
        "Выбери <b>срок</b> подписки:\n\n"
        "• Чем длиннее срок — тем дешевле каждый месяц\n"
        "• Доп. устройства дешевле на длинном сроке (6 мес ~17%, 12 мес ~30%)"
    )


def txt_constructor_devices(months: int) -> str:
    return (
        f"🔧 <b>Конструктор</b> · {months} мес.\n\n"
        f"Выбери количество <b>устройств</b> (1–10):\n\n"
        f"+ каждое устройство: <b>+{EXTRA_DEVICE_PRICE[months]} ₽</b>"
    )


def txt_constructor_result(
    months: int,
    devices: int,
    price_rub: float,
    price_usdt: float,
    *,
    promo_bonus_days: int = 0,
) -> str:
    bd = max(0, int(promo_bonus_days))
    rub, usd = float(price_rub), float(price_usdt)
    total_line = f"💰 Итого: <b>{rub:.0f} ₽</b>  /  <b>{usd:.2f} USDT</b>"
    bonus_line = ""
    if bd:
        bonus_line = f"\n🎁 Промокод: <b>+{bd} дн.</b> бесплатного доступа при вводе кода."
    return (
        f"🔧 <b>Твой тариф:</b>\n\n"
        f"📅 Срок: <b>{months} мес.</b>\n"
        f"📱 Устройств: <b>{devices}</b>\n"
        f"{total_line}{bonus_line}\n\n"
        f"Выбери способ оплаты 👇"
    )


def _fmt_crypto(amount: float, decimals: int) -> str:
    s = f"{amount:.{decimals}f}"
    return s.rstrip("0").rstrip(".")


def txt_pay_usdt(amount: float, wallet: str, comment: str) -> str:
    amt = _fmt_crypto(amount, 6)
    return (
        f"💎 <b>Оплата USDT TRC-20</b>\n\n"
        f"Отправь ровно <code>{amt}</code> <b>USDT</b>\n"
        f"на кошелёк:\n\n"
        f"<code>{wallet}</code>\n\n"
        f"⚠️ <b>Важно:</b>\n"
        f"• Только сеть <b>TRC-20 (Tron)</b>\n"
        f"• Номер заказа: <code>{comment}</code> (сохрани для обращения в поддержку)\n"
        f"• После отправки нажми «Я оплатил»\n\n"
        f"⏱ Проверка занимает до 2 минут."
    )


def txt_pay_ton(amount: float, wallet: str) -> str:
    amt = _fmt_crypto(amount, 9)
    return (
        f"💎 <b>Оплата TON</b>\n\n"
        f"Отправь ровно <code>{amt}</code> <b>TON</b>\n"
        f"на кошелёк:\n\n"
        f"<code>{wallet}</code>\n\n"
        f"⚠️ <b>Важно:</b>\n"
        f"• Используй TonKeeper, TonHub или любой TON-кошелёк\n"
        f"• Комментарий в TON не обязателен; сумма уникальна для твоего заказа\n"
        f"• После отправки нажми «Я оплатил»\n\n"
        f"⏱ Проверка занимает до 2 минут."
    )


def txt_pay_card(url: str, amount: float) -> str:
    return (
        f"💳 <b>Оплата картой РФ / СБП</b>\n\n"
        f"Сумма к оплате: <b>{amount:.2f} ₽</b>\n\n"
        f"Нажми кнопку ниже — откроется страница оплаты Freekassa.\n"
        f"После успешной оплаты конфиг придёт автоматически."
    )


def txt_pay_sber(url: str, amount: float, payment_id: int) -> str:
    return (
        f"🏦 <b>Оплата переводом (Т-Банк)</b>\n\n"
        f"Сумма к переводу: <b>{amount:.2f} ₽</b>\n"
        f"Номер заказа: <code>{payment_id}</code> (при обращении к админу назови его)\n\n"
        f"Нажми кнопку ниже — откроется страница перевода в Т-Банке.\n"
        f"Укажи ту же сумму в форме, если она не подставилась автоматически.\n\n"
        f"После оплаты нажми <b>«Я оплатил — сообщить админу»</b>.\n"
        f"Подписка активируется после проверки перевода администратором."
    )


def txt_pay_tbank(
    amount: float,
    payment_id: int,
    *,
    webhook_ok: bool = True,
) -> str:
    hook = ""
    if not webhook_ok:
        hook = (
            "⚠️ <i>Не задан <code>PAYMENT_PUBLIC_BASE_URL</code> — укажи в кабинете терминала Т-Банка "
            "URL уведомлений вида <code>https://твой-домен/payment/tbank</code> (через тот же nginx, "
            "что и для Freekassa), иначе после оплаты конфиг не придёт автоматически.</i>\n\n"
        )
    return (
        f"🏦 <b>Оплата через Т-Банк</b>\n\n"
        f"Сумма: <b>{amount:.2f} ₽</b>\n"
        f"Заказ: <code>{payment_id}</code>\n\n"
        f"{hook}"
        f"Нажми кнопку ниже или отсканируй <b>QR</b> в следующем сообщении — откроется форма оплаты "
        f"(карта или СБП).\n\n"
        f"После успешной оплаты конфиг придёт в Telegram автоматически (обычно до минуты)."
    )


def txt_reminder(days_left: int, expires_str: str) -> str:
    return (
        f"⏰ <b>Подписка скоро закончится</b>\n\n"
        f"Осталось дней: <b>{max(0, int(days_left))}</b>\n"
        f"Дата окончания: <b>{expires_str}</b>\n\n"
        f"Продли подписку, чтобы не потерять доступ 👇"
    )


def txt_payment_checking() -> str:
    return "🔍 Проверяю транзакцию... Подожди несколько секунд."


def txt_payment_not_found() -> str:
    return "❌ Платёж не найден или уже обработан."


def txt_config_ready(
    config_link: str,
    expires_str: str,
    devices: int,
    *,
    extra_link: Optional[str] = None,
    partial_nodes: bool = False,
) -> str:
    extra = ""
    if extra_link and extra_link.strip():
        extra = (
            f"\n\n📎 <b>Запасная ссылка</b> (другой узел):\n"
            f"<code>{extra_link}</code>"
        )
    warn = ""
    if partial_nodes:
        warn = (
            "\n\n⚠️ <i>Один из узлов временно недоступен — основная ссылка должна работать. "
            "Если что-то не подключается, напиши в поддержку.</i>"
        )
    main = (config_link or "").strip() or "—"
    return (
        f"✅ <b>Конфиг готов!</b>\n\n"
        f"📅 Активен до: <b>{expires_str}</b>\n"
        f"📱 Устройств по тарифу: <b>{devices}</b>\n\n"
        f"🔗 <b>Ссылка подписки</b> (скопируй в приложение v2ray / Happ / v2rayNG):\n"
        f"<code>{main}</code>"
        f"{extra}"
        f"{warn}\n\n"
        f"<i>Ниже отдельным сообщением — та же ссылка plain-текстом (удобно копировать в Telegram).</i>"
    )


def txt_my_subs_empty() -> str:
    return (
        "📋 <b>Мои подписки</b>\n\n"
        "У тебя пока нет активных подписок.\n"
        "Оформи в разделе «Купить подписку» 👇"
    )


def txt_sub_info(sub, *, telegram_username: Optional[str] = None) -> str:
    from html import escape as html_escape

    st = "✅ активна" if sub.is_active else "⏸ неактивна"
    exp = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "—"
    link = (sub.config_link or "—").strip()
    if len(link) > 120:
        link = link[:117] + "..."
    u = (telegram_username or "").strip().lstrip("@")
    if u:
        who = f"👤 Telegram: <b>@{html_escape(u)}</b>\n"
    else:
        who = "👤 Telegram: <i>username не указан в профиле Telegram</i>\n"
    return (
        f"Статус: <b>{st}</b>\n"
        f"{who}"
        f"Тариф: <code>{html_escape(sub.plan_key or '')}</code>\n"
        f"📱 Устройств: <b>{sub.devices}</b>\n"
        f"📅 До: <b>{exp}</b>\n"
        f"🔗 Ссылка: <code>{html_escape(link)}</code>"
    )


def txt_referral(
    user_id: int,
    *,
    invited_registered: int,
    invited_paid: int,
    earned_days: int,
    referrer_bonus_days: int,
    invitee_bonus_days: int,
) -> str:
    bu = bot_username_clean()
    ref_url = f"https://t.me/{bu}?start=ref{user_id}"
    rb = max(1, int(referrer_bonus_days))
    invitee_line = ""
    if invitee_bonus_days > 0:
        invitee_line = (
            f"Приглашённый при <b>первой оплате</b> получит <b>+{invitee_bonus_days}</b> дн. VPN; "
        )
    else:
        invitee_line = "Приглашённый оформляет подписку как обычно; "
    body = (
        f"👥 <b>Реферальная программа NINAVPN</b>\n\n"
        f"{invitee_line}"
        f"ты получаешь <b>+{rb}</b> дн. к своему VPN за каждого друга после его "
        f"<b>первой успешной оплаты</b>.\n\n"
        f"Перешло по ссылке (регистрации): <b>{invited_registered}</b>\n"
        f"Принесли бонус (оплатили): <b>{invited_paid}</b>\n"
        f"Начислено тебе дней: <b>{earned_days}</b>\n\n"
        f"Твоя ссылка:\n<code>{ref_url}</code>"
    )
    return body


def _txt_geo_routing_lines() -> str:
    """Ссылки на geoip/geosite (runetfreedom/russia-v2ray-rules-dat), при наличии — через наш /geo/."""
    from config import public_web_base_url

    base = public_web_base_url()
    if base:
        g1 = f"{base}/geo/geoip.dat"
        g2 = f"{base}/geo/geosite.dat"
        note = "Файлы на нашем домене (кэш того же набора, что runetfreedom):"
    else:
        g1 = "https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geoip.dat"
        g2 = "https://raw.githubusercontent.com/runetfreedom/russia-v2ray-rules-dat/release/geosite.dat"
        note = "Прямые ссылки на GitHub (runetfreedom/russia-v2ray-rules-dat):"
    return (
        "\n\n<b>Роутинг RU (по желанию)</b>\n"
        "В v2rayN / v2rayNG: параметры Geo-файлов — укажите ссылки на geoip и geosite ниже. "
        "Так в правилах маршрутизации доступны категории вроде geosite:ru-blocked.\n"
        f"{note}\n<code>{g1}</code>\n<code>{g2}</code>"
    )


def txt_howto(platform: str) -> str:
    p = (platform or "").lower().strip()
    tail = (
        "\n\n<i>Не подключается — проверь дату подписки и лимит устройств по тарифу. "
        "«Поддержка» → «Написать в поддержку».</i>"
    )
    geo = _txt_geo_routing_lines()
    if p == "ios":
        return (
            "📱 <b>iPhone / iPad</b>\n\n"
            "1. Установи <b>Streisand</b>, <b>v2Box</b> или <b>Shadowrocket</b> из App Store.\n"
            "2. Скопируй <b>ссылку подписки</b> из бота (или отсканируй QR).\n"
            "3. В приложении: добавить подписку из буфера / по QR.\n"
            "4. Обнови подписку и включи VPN.\n"
            "5. Разреши добавление VPN-профиля в настройках iOS."
        ) + geo + tail
    if p == "android":
        return (
            "🤖 <b>Android</b>\n\n"
            "1. Установи <b>v2rayNG</b> из Google Play или GitHub.\n"
            "2. Скопируй ссылку подписки из бота.\n"
            "3. v2rayNG → <b>+</b> → «Импорт из буфера обмена».\n"
            "4. Нажми на импортированную подписку → обновить → выбери сервер → включи VPN."
        ) + geo + tail
    if p == "windows":
        return (
            "🖥 <b>Windows</b>\n\n"
            "1. Установи <b>v2rayN</b> (релиз с GitHub).\n"
            "2. Скопируй ссылку подписки из бота.\n"
            "3. v2rayN → «Подписки» → добавить из буфера → обновить.\n"
            "4. Выбери сервер в списке и нажми Enter / системный прокси по инструкции клиента."
        ) + geo + tail
    if p == "macos":
        return (
            "🍎 <b>macOS</b>\n\n"
            "1. Установи <b>v2rayN</b> для Mac, <b>Stash</b> или другой клиент с поддержкой VLESS.\n"
            "2. Импортируй подписку по ссылке из бота.\n"
            "3. Обнови список узлов и включи подключение."
        ) + geo + tail
    return (
        "📖 <b>Как подключиться</b>\n\n"
        "1. Скопируй ссылку подписки из бота (или QR).\n"
        "2. Открой её в клиенте v2ray / Happ / v2rayNG.\n"
        "3. Выбери сервер и включи VPN."
    ) + geo + tail


def txt_channel_required(*, channel_html: str) -> str:
    """channel_html — подпись канала в HTML (уже с тегами или экранированный @username)."""
    return (
        f"📢 Чтобы пользоваться ботом, подпишись на {channel_html}.\n\n"
        "После подписки снова нажми /start или кнопку в меню."
    )
