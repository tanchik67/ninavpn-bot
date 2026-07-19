# 🤖 NINAVPN Bot — Инструкция по установке

**Выкладка на Linux-сервер:** пошаговая инструкция — **[DEPLOY.md](DEPLOY.md)** (rsync, systemd, nginx, 3x-ui/Marzban).

## Структура проекта

```
ninavpn-bot/
├── main.py                  # Telegram bot entry
├── apps/api/                # FastAPI SaaS API
├── apps/worker/             # ARQ provision / reminders
├── apps/client/             # Expo (iOS / Android / Web)
├── core/                    # shared domain + ports
├── adapters/                # vpn / payments / notifications
├── infrastructure/          # Postgres models, Redis
├── docker-compose.yml
├── handlers/                # bot handlers (+ /linkcabinet)
├── services/                # Marzban, 3x-ui, payments…
└── utils/
```

SaaS локально: см. [apps/api/README.md](apps/api/README.md) и [apps/client/README.md](apps/client/README.md).

---

## Шаг 1 — Установка Marzban (если ещё нет)

```bash
# Подключись к серверу
ssh root@твой_ip

# Установка Marzban одной командой
bash <(curl -sL https://github.com/Gozargah/Marzban-scripts/raw/master/marzban.sh) install

# После установки создай первого администратора
marzban cli admin create --sudo

# Панель будет доступна на http://IP:8000
# Настрой SSL через Nginx или встроенный SSL Marzban
```

### Настройка inbound в Marzban:
1. Зайди в панель → Inbounds → добавь `VLESS TCP REALITY`
2. Запомни точное имя inbound — оно идёт в `config.py → PLANS`

---

## Шаг 2 — Подготовка бота

```bash
# Создай директорию
mkdir -p /opt/ninavpn-bot
cd /opt/ninavpn-bot

# Скопируй все файлы проекта
# (загрузи через scp или git clone)

# Создай виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установи зависимости
pip install -r requirements.txt
```

---

## Шаг 3 — Настройка .env

```bash
cp .env.example .env
nano .env
```

Заполни все поля:

| Переменная | Как получить |
|---|---|
| `BOT_TOKEN` | @BotFather → /newbot |
| `ADMIN_ID` | @userinfobot |
| `MARZBAN_URL` | URL твоей панели |
| `MARZBAN_USERNAME` | логин admin в Marzban |
| `MARZBAN_PASSWORD` | пароль admin в Marzban |
| `TON_WALLET` | TonKeeper → скопировать адрес |
| `USDT_TRC20_WALLET` | Биржа/кошелёк TRC-20 адрес |

---

## Шаг 4 — Тестовый запуск

```bash
source venv/bin/activate
python main.py
```

Если в консоли нет ошибок — всё работает.

---

## Шаг 5 — Автозапуск через systemd

```bash
# Скопируй unit файл
cp ninavpn-bot.service /etc/systemd/system/

# Активируй
systemctl daemon-reload
systemctl enable ninavpn-bot
systemctl start ninavpn-bot

# Проверь статус
systemctl status ninavpn-bot

# Логи
journalctl -u ninavpn-bot -f
```

---

## Шаг 6 — Freekassa (опционально, только webhook)

В меню бота оплата через Freekassa **не отображается**. Если нужен IPN для старых магазинов: переменные `FREEKASSA_*` в `.env`, URL уведомлений `https://ваш-домен/payment/freekassa`, nginx → порт **8080** (см. **[DEPLOY.md](DEPLOY.md)**).

---

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Начало работы |
| `/admin` | Панель администратора |
| `/stats` | Статистика (только admin) |
| `/promo_add CODE ДНИ` | Промокод: **ДНИ** календарных дней VPN при вводе (1 раз на пользователя) |
| `/broadcast Текст` | Рассылка всем пользователям |

---

## Логика оплаты USDT/TON

```
Пользователь выбирает тариф
    ↓
Бот показывает адрес кошелька + сумму
    ↓
Пользователь отправляет крипту
    ↓
Нажимает «Я оплатил»
    ↓
Бот проверяет блокчейн (Tronscan / Toncenter API)
    ↓
Нашёл транзакцию → создаёт юзера в Marzban
    ↓
Отправляет конфиг + QR-код
```

---

## Расходы на инфраструктуру

| Статья | Стоимость |
|---|---|
| VPS (Aeza/Hetzner) | ~300–500 ₽/мес |
| Домен ninavpn.store | ~150 ₽/мес |
| Marzban | **бесплатно** |
| Telegram Bot API | **бесплатно** |
| Tronscan / Toncenter | **бесплатно** |
| **Итого** | **~500–650 ₽/мес** |

При 10 клиентах (×100 ₽) = 1000 ₽ → уже в плюсе 🚀
