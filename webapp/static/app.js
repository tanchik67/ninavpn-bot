(function () {
  const API = "/miniapp/api";

  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    try {
      tg.setHeaderColor("#0a0a0f");
      tg.setBackgroundColor("#0a0a0f");
    } catch (e) {}
  }

  const elPlans = document.getElementById("plans");
  const elGreeting = document.getElementById("greeting");
  const elBtn = document.getElementById("btn-bot");
  const elHint = document.getElementById("hint-bot");

  const user = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
  if (user && user.first_name) {
    elGreeting.textContent = "Привет, " + user.first_name;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function openBot(url) {
    if (!url) return;
    if (tg && typeof tg.openTelegramLink === "function") {
      tg.openTelegramLink(url);
      return;
    }
    window.open(url, "_blank");
  }

  Promise.all([
    fetch(API + "/config").then(function (r) {
      return r.json();
    }),
    fetch(API + "/plans").then(function (r) {
      return r.json();
    }),
  ])
    .then(function (results) {
      const cfg = results[0] || {};
      const plans = results[1] || {};

      const botUrl = cfg.bot_open_url || "";
      if (elBtn) {
        elBtn.addEventListener("click", function () {
          openBot(botUrl || "https://t.me/");
        });
      }
      if (elHint) {
        elHint.textContent = botUrl
          ? "На карточке тарифа нажми «Оформить» — бот откроется с этим планом и способами оплаты."
          : "Задайте BOT_USERNAME в .env для кнопок «Оформить» и внизу страницы.";
      }

      const keys = Object.keys(plans);
      if (!keys.length) {
        elPlans.innerHTML = '<p class="err">Тарифы не найдены.</p>';
        return;
      }

      function planStartParam(planKey) {
        if (!/^[a-zA-Z0-9_-]+$/.test(planKey)) return null;
        return "plan_" + planKey;
      }

      const frag = document.createDocumentFragment();
      keys.forEach(function (key) {
        const p = plans[key];
        const popular = p.popular;
        const card = document.createElement("article");
        card.className = "card" + (popular ? " popular" : "");
        const rub = Number(p.price_rub);
        const usdt = Number(p.price_usdt);
        card.innerHTML =
          '<div class="card-top">' +
          '<span class="card-title">' +
          esc(p.emoji || "📦") +
          " " +
          esc(p.name || key) +
          "</span>" +
          (popular ? '<span class="badge">Хит</span>' : "") +
          "</div>" +
          '<p class="card-desc">' +
          esc(p.description || "") +
          "</p>" +
          '<div class="card-meta">' +
          "<span>" +
          esc(p.months) +
          " мес.</span>" +
          "<span>" +
          esc(p.devices) +
          " устр.</span>" +
          '<span class="price">' +
          (isFinite(rub) ? rub.toFixed(0) + " ₽" : "—") +
          "</span>" +
          "<span>" +
          (isFinite(usdt) ? usdt + " USDT" : "") +
          "</span>" +
          "</div>" +
          '<div class="card-actions"></div>';
        const actions = card.querySelector(".card-actions");
        const startArg = planStartParam(key);
        if (actions && botUrl && startArg) {
          const cta = document.createElement("button");
          cta.type = "button";
          cta.className = "btn card-cta";
          cta.textContent = "Оформить в Telegram";
          cta.addEventListener("click", function () {
            var sep = botUrl.indexOf("?") >= 0 ? "&" : "?";
            openBot(botUrl + sep + "start=" + startArg);
          });
          actions.appendChild(cta);
        } else if (actions && !botUrl) {
          actions.innerHTML =
            '<p class="card-cta-hint">Укажите BOT_USERNAME в настройках бота.</p>';
        }
        frag.appendChild(card);
      });
      elPlans.innerHTML = "";
      elPlans.appendChild(frag);
    })
    .catch(function () {
      elPlans.innerHTML =
        '<p class="err">Не удалось загрузить данные. Проверьте сеть и URL Mini App.</p>';
    });
})();
