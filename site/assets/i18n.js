/**
 * Site language: RU | EN (localStorage key nv_site_lang).
 * Usage: elements with data-i18n="key"; optional data-i18n-html for HTML snippets.
 */
(function (global) {
  var KEY = "nv_site_lang";
  var TG = "https://t.me/ninavpn_official";

  var LEGAL = {
    ru: {
      oferta: "/ninavpn-oferta-2.html",
      privacy: "/ninavpn-privacy-2.html",
      terms: "/ninavpn-terms-2.html",
      security: "/security.html",
      home: "/",
    },
    en: {
      oferta: "/en/oferta.html",
      privacy: "/en/privacy.html",
      terms: "/en/terms.html",
      security: "/en/security.html",
      home: "/",
    },
  };

  var I18N = {
    ru: {
      "meta.title": "NINAVPN — VPN для России от 100 ₽/мес | v2ray XTLS",
      "nav.features": "Фичи",
      "nav.pricing": "Цены",
      "nav.constructor": "Конструктор",
      "nav.faq": "FAQ",
      "nav.pay": "Оплатить →",
      "hero.badge": "v2ray protocol · Онлайн",
      "hero.line1": "Интернет без",
      "hero.line2": "цензуры",
      "hero.sub":
        "VPN на базе v2ray/XTLS — самый устойчивый к блокировкам протокол. Instagram, YouTube, Discord, TikTok — всё летит без тормозов.",
      "hero.ctaPay": "Оплатить — от 100 ₽/мес",
      "hero.ctaHow": "Как это работает",
      "stat.users": "Активных юзеров",
      "stat.uptime": "Аптайм",
      "stat.countries": "Стран серверов",
      "stat.logs": "Логов активности",
      "features.tag": "Почему NINAVPN",
      "features.h2": "Не просто VPN.<br>Настоящая свобода.",
      "feat.1.h": "v2ray + XTLS",
      "feat.1.p": "Самый продвинутый протокол. Трафик выглядит как HTTPS — блокировки бессильны.",
      "feat.2.h": "Скорость без лимитов",
      "feat.2.p": "Серверы 10 Гбит/с. YouTube 4K, стриминг без буфера.",
      "feat.3.h": "До 10 устройств",
      "feat.3.p": "Пока официальное приложение — Android. iPhone, Windows и macOS в разработке. Роутер — по конфигу.",
      "feat.4.h": "Абсолютная анонимность",
      "feat.4.p": "No-log политика. Оплата криптой — полная анонимность.",
      "how.tag": "Простое подключение",
      "how.h2": "Работает быстро",
      "how.1.h": "Оплати на сайте",
      "how.1.p": "СБП или карта РФ через Т-Банк",
      "how.2.h": "Получи ссылку VPN",
      "how.2.p": "Сразу после оплаты на сайте",
      "how.3.h": "Включи",
      "how.3.p": "в приложении NinaVPN",
      "how.4.h": "Всё работает",
      "how.4.p": "Instagram, TikTok, YouTube",
      "pricing.tag": "Честные цены",
      "pricing.h2": "Выбери свой план",
      "plan.month": "Месяц",
      "plan.pay": "Оплатить",
      "plan.payArrow": "Оплатить →",
      "plan.f1": "1 устройство",
      "plan.f2": "Все серверы",
      "plan.f3": "Безлимит",
      "plan.hit": "🔥 Хит",
      "plan.6m": "6 месяцев",
      "plan.f4": "до 3 устройств",
      "plan.f5": "Приоритетная поддержка",
      "plan.f6": "Экономия 100 ₽",
      "plan.12m": "12 месяцев",
      "plan.f7": "до 5 устройств",
      "plan.f8": "Реферальная программа",
      "plan.f9": "Экономия 200 ₽",
      "ctor.tag": "Конструктор тарифа",
      "ctor.h2": "Собери свой план",
      "ctor.period": "Период подписки",
      "ctor.m1": "1 мес",
      "ctor.m6": "6 мес",
      "ctor.m12": "12 мес",
      "ctor.devices": "Количество устройств:",
      "ctor.total": "Итого",
      "ctor.buy": "Купить сейчас →",
      "pay.tag": "Оплата из России",
      "pay.h2": "Платишь как удобно, без санкций",
      "pay.sbp": "📱 СБП",
      "pay.cards": "💳 Карты РФ (Visa / МИР)",
      "pay.crypto": "💎 USDT / TON",
      "faq.tag": "FAQ",
      "faq.h2": "Частые вопросы",
      "faq.q1": "Что такое v2ray?",
      "faq.a1": "v2ray — прокси-фреймворк с протоколами VLESS/XTLS, маскирует трафик под HTTPS, обходит DPI.",
      "faq.q2": "Это законно?",
      "faq.a2": "Использование VPN для личных нужд в РФ не преследуется.",
      "faq.q3": "На каких устройствах работает?",
      "faq.a3": "Сейчас — Android. Приложения для iPhone, Windows и macOS в разработке. Роутер можно настроить по конфигу.",
      "faq.q4": "Храните ли логи?",
      "faq.a4": "Нет, строгая no-log политика. Полная анонимность.",
      "cta.h2": "Разблокируй всё прямо сейчас",
      "cta.p": "От 100 рублей в месяц. Меньше чем чашка кофе.",
      "cta.btn": "Оплатить подписку →",
      "foot.oferta": "Публичная оферта",
      "foot.privacy": "Политика конфиденциальности",
      "foot.terms": "Условия использования",
      "foot.tg": "Telegram",
      "foot.copy": "© 2026 NINAVPN · Работает в РФ · ОГРНИП 326565800043202",
      "checkout.title": "Оплата NINAVPN",
      "checkout.pick": "Выберите тариф на странице",
      "checkout.emailLabel": "Email для чека и восстановления доступа",
      "checkout.pay": "💳 Оплатить картой / СБП (Т-Банк)",
      "checkout.note":
        "После оплаты вы попадёте на страницу с VPN-ссылкой. Бот Telegram не нужен.<br>🔒 Без логов · Возврат 24 часа",
      "checkout.tbankLine": "Оплата картой или СБП через Т-Банк",
      "checkout.paying": "Переход к оплате…",
      "checkout.badEmail": "Укажите корректный email",
      "checkout.fail": "Не удалось создать оплату",
      "checkout.net": "Ошибка сети. Попробуйте ещё раз.",
      "ctor.detail": "~{perMonth} ₽/мес · {devices} уст. · {months} мес",
      "ctor.saving": "🎉 Экономия {saved} ₽ по сравнению с помесячной оплатой",
      "planLabel.1m": "1 месяц · 1 устройство · 100 ₽",
      "planLabel.6m": "6 месяцев · до 3 устройств · 500 ₽",
      "planLabel.12m": "12 месяцев · до 5 устройств · 1000 ₽",
      "legal.back": "← На главную",
    },
    en: {
      "meta.title": "NINAVPN — Fast no-log VPN from 100 ₽/mo | v2ray XTLS",
      "nav.features": "Features",
      "nav.pricing": "Pricing",
      "nav.constructor": "Builder",
      "nav.faq": "FAQ",
      "nav.pay": "Pay →",
      "hero.badge": "v2ray protocol · Online",
      "hero.line1": "Internet without",
      "hero.line2": "censorship",
      "hero.sub":
        "VPN on v2ray/XTLS — built for hostile networks. Instagram, YouTube, Discord, TikTok — without the drama.",
      "hero.ctaPay": "Pay — from 100 ₽/mo",
      "hero.ctaHow": "How it works",
      "stat.users": "Active users",
      "stat.uptime": "Uptime",
      "stat.countries": "Server countries",
      "stat.logs": "Activity logs",
      "features.tag": "Why NINAVPN",
      "features.h2": "Not just a VPN.<br>Real freedom.",
      "feat.1.h": "v2ray + XTLS",
      "feat.1.p": "Traffic looks like HTTPS — DPI has nothing to latch onto.",
      "feat.2.h": "Speed without limits",
      "feat.2.p": "10 Gbps servers. YouTube 4K, streaming without buffering.",
      "feat.3.h": "Up to 10 devices",
      "feat.3.p": "Official app is Android for now. iPhone, Windows, and macOS are in development. Router works via config.",
      "feat.4.h": "Absolute anonymity",
      "feat.4.p": "No-log policy. Crypto payments — full anonymity.",
      "how.tag": "Simple setup",
      "how.h2": "Works fast",
      "how.1.h": "Pay on the site",
      "how.1.p": "SBP or RU card via T-Bank",
      "how.2.h": "Get the VPN link",
      "how.2.p": "Right after payment on the site",
      "how.3.h": "Turn it on",
      "how.3.p": "in the NinaVPN app",
      "how.4.h": "Everything works",
      "how.4.p": "Instagram, TikTok, YouTube",
      "pricing.tag": "Fair pricing",
      "pricing.h2": "Pick your plan",
      "plan.month": "Month",
      "plan.pay": "Pay",
      "plan.payArrow": "Pay →",
      "plan.f1": "1 device",
      "plan.f2": "All servers",
      "plan.f3": "Unlimited",
      "plan.hit": "🔥 Hit",
      "plan.6m": "6 months",
      "plan.f4": "up to 3 devices",
      "plan.f5": "Priority support",
      "plan.f6": "Save 100 ₽",
      "plan.12m": "12 months",
      "plan.f7": "up to 5 devices",
      "plan.f8": "Referral program",
      "plan.f9": "Save 200 ₽",
      "ctor.tag": "Plan builder",
      "ctor.h2": "Build your plan",
      "ctor.period": "Subscription period",
      "ctor.m1": "1 mo",
      "ctor.m6": "6 mo",
      "ctor.m12": "12 mo",
      "ctor.devices": "Number of devices:",
      "ctor.total": "Total",
      "ctor.buy": "Buy now →",
      "pay.tag": "Pay from Russia",
      "pay.h2": "Pay your way, no sanctions drama",
      "pay.sbp": "📱 SBP",
      "pay.cards": "💳 RU cards (Visa / MIR)",
      "pay.crypto": "💎 USDT / TON",
      "faq.tag": "FAQ",
      "faq.h2": "Common questions",
      "faq.q1": "What is v2ray?",
      "faq.a1": "v2ray is a proxy framework with VLESS/XTLS — traffic looks like HTTPS and resists DPI.",
      "faq.q2": "Is it legal?",
      "faq.a2": "Personal VPN use is generally fine — follow your local laws.",
      "faq.q3": "Which devices?",
      "faq.a3": "Android today. iPhone, Windows, and macOS apps are in development. Routers can use the config.",
      "faq.q4": "Do you keep logs?",
      "faq.a4": "No. Strict no-log policy. Full anonymity.",
      "cta.h2": "Unlock everything now",
      "cta.p": "From 100 ₽ a month. Less than a coffee.",
      "cta.btn": "Pay for subscription →",
      "foot.oferta": "Public offer",
      "foot.privacy": "Privacy policy",
      "foot.terms": "Terms of use",
      "foot.tg": "Telegram",
      "foot.copy": "© 2026 NINAVPN · OGRNIP 326565800043202",
      "checkout.title": "NINAVPN checkout",
      "checkout.pick": "Pick a plan on the page",
      "checkout.emailLabel": "Email for receipt and access recovery",
      "checkout.pay": "💳 Pay by card / SBP (T-Bank)",
      "checkout.note":
        "After payment you’ll land on a page with your VPN link. Telegram bot not required.<br>🔒 No logs · 24h refund",
      "checkout.tbankLine": "Pay by card or SBP via T-Bank",
      "checkout.paying": "Redirecting to payment…",
      "checkout.badEmail": "Enter a valid email",
      "checkout.fail": "Could not create payment",
      "checkout.net": "Network error. Try again.",
      "ctor.detail": "~{perMonth} ₽/mo · {devices} devices · {months} mo",
      "ctor.saving": "🎉 Save {saved} ₽ vs paying monthly",
      "planLabel.1m": "1 month · 1 device · 100 ₽",
      "planLabel.6m": "6 months · up to 3 devices · 500 ₽",
      "planLabel.12m": "12 months · up to 5 devices · 1000 ₽",
      "legal.back": "← Home",
    },
  };

  function getLang() {
    try {
      var v = localStorage.getItem(KEY);
      if (v === "en" || v === "ru") return v;
    } catch (e) {}
    return "ru";
  }

  function setLang(lang) {
    if (lang !== "en" && lang !== "ru") lang = "ru";
    try {
      localStorage.setItem(KEY, lang);
    } catch (e) {}
    applyLang(lang);
    return lang;
  }

  function t(key, vars) {
    var lang = getLang();
    var dict = I18N[lang] || I18N.ru;
    var raw = dict[key] || (I18N.ru[key] || key);
    if (!vars) return raw;
    return raw.replace(/\{(\w+)\}/g, function (_, k) {
      return vars[k] != null ? String(vars[k]) : "{" + k + "}";
    });
  }

  function applyLang(lang) {
    lang = lang || getLang();
    document.documentElement.lang = lang;
    var dict = I18N[lang] || I18N.ru;
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (!key || dict[key] == null) return;
      if (el.getAttribute("data-i18n-html") === "1") el.innerHTML = dict[key];
      else el.textContent = dict[key];
    });
    if (dict["meta.title"]) document.title = dict["meta.title"];

    document.querySelectorAll(".lang-btn").forEach(function (btn) {
      var l = btn.getAttribute("data-set-lang");
      btn.classList.toggle("active", l === lang);
    });

    var links = LEGAL[lang] || LEGAL.ru;
    document.querySelectorAll("[data-legal]").forEach(function (a) {
      var k = a.getAttribute("data-legal");
      if (links[k]) a.setAttribute("href", links[k]);
    });

    document.querySelectorAll('a[data-tg="channel"]').forEach(function (a) {
      a.setAttribute("href", TG);
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    });

    document.querySelectorAll("[data-i18n-href-ru]").forEach(function (a) {
      var href =
        lang === "en"
          ? a.getAttribute("data-i18n-href-en")
          : a.getAttribute("data-i18n-href-ru");
      if (href) a.setAttribute("href", href);
    });

    if (typeof global.nvOnLangChange === "function") {
      try {
        global.nvOnLangChange(lang);
      } catch (e) {}
    }
  }

  function wireSwitcher(root) {
    (root || document).querySelectorAll("[data-set-lang]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setLang(btn.getAttribute("data-set-lang"));
      });
    });
  }

  global.nvI18n = {
    getLang: getLang,
    setLang: setLang,
    t: t,
    applyLang: applyLang,
    wireSwitcher: wireSwitcher,
    TG: TG,
    LEGAL: LEGAL,
  };

  document.addEventListener("DOMContentLoaded", function () {
    wireSwitcher();
    applyLang(getLang());
  });
})(window);
