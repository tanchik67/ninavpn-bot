# Развёртывание NINAVPN Bot на сервере (macOS → Linux)

Инструкция для загрузки проекта с **Mac** на сервер и запуска бота. В примере ниже IP сервера: **`2.27.122.201`**. Замените `USER` на ваш логин SSH (часто `root` или `ubuntu`).

**Сначала протестировать на Mac:** см. **[LOCAL.md](LOCAL.md)** (venv, `.env`, `python3 main.py`, туннель для webhook при необходимости).

---

## Чек-лист перед выкладкой

- [ ] На сервере **Python 3.10+** (рекомендуется 3.11; зависимости в `requirements.txt` рассчитаны на современный Python).
- [ ] Скопирован `.env.example` → `.env`, заполнены **BOT_TOKEN**, **ADMIN_ID**, кошельки **TON** / **USDT**, **VPN_BACKEND** и блок Marzban или 3x-ui.
- [ ] **3x-ui:** задан порт подписки — в `.env` **`XUI_SUB_PORT=2096`** (или в каждом узле **`sub_port`** в `XUI_NODES`). Если используете **`XUI_SUBSCRIPTION_BASE`** / **`subscription_base`**, лучше сразу указывать порт в URL, например `https://IP:2096/sub`, иначе бот всё равно переберёт запасные порты, но лишние запросы попадут в логи.
- [ ] **Marzban:** `MARZBAN_URL` / при необходимости **`MARZBAN_API_URL`** ведут на **FastAPI** (не на статический фронт с 405 на `/api/admin/token`).
- [ ] Для **webhook** Т-Банка и (опционально) Freekassa: nginx проксирует **`/payment/`** на `127.0.0.1:8080`, внешний **HTTPS** доступен.
- [ ] После первого запуска проверены: **/start**, оплата тестовым способом, **«Получить конфиг»**, при необходимости **промокод** и **Mini App**.

---

## Что понадобится

- Mac с установленным **Terminal** (встроен).
- Доступ по **SSH** к серверу (пароль или SSH-ключ).
- На сервере: **Ubuntu/Debian** (или совместимый Linux) с **Python 3.10+** (желательно 3.11).
- Файлы проекта на Mac, например в `~/Downloads/ninavpn-bot`.

---

## 1. Устойчивое SSH-соединение с Mac (чтобы сессия не рвалась)

На Mac откройте или создайте файл:

```bash
nano ~/.ssh/config
```

Добавьте (подставьте свой логин вместо `USER`):

```sshconfig
Host ninavpn
  HostName 2.27.122.201
  User USER
  ServerAliveInterval 30
  ServerAliveCountMax 6
```

Сохраните (Ctrl+O, Enter) и выйдите (Ctrl+X). Подключение:

```bash
ssh ninavpn
```

Для долгих операций на сервере используйте **tmux** (сессия не пропадёт при обрыве сети):

```bash
ssh ninavpn
sudo apt update && sudo apt install -y tmux
tmux new -s deploy
```

Отключиться от tmux без остановки команд: **Ctrl+b**, затем **d**. Вернуться: `tmux attach -t deploy`.

---

## 2. Копирование файлов с Mac на сервер

На **Mac** (не на сервере), в папке, где лежит проект:

```bash
cd ~/Downloads
```

### Вариант A: `rsync` (удобно при повторных обновлениях)

```bash
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '*.db' --exclude '.env' --exclude '.git' \
  ninavpn-bot/ USER@2.27.122.201:/opt/ninavpn-bot/
```

- Папка `venv` и локальная база не копируются — их создаёте на сервере.
- Файл `.env` не перезаписывается с Mac (секреты только на сервере).

Если каталога `/opt/ninavpn-bot` ещё нет, на сервере один раз выполните:

```bash
ssh USER@2.27.122.201 'sudo mkdir -p /opt/ninavpn-bot && sudo chown -R $USER:$USER /opt/ninavpn-bot'
```

### Вариант B: `scp`

Подставьте **`USER`** (логин SSH) и при необходимости **IP** вместо `2.27.122.201`.

**Один раз на сервере** — каталог и права:

```bash
ssh USER@2.27.122.201 'sudo mkdir -p /opt/ninavpn-bot && sudo chown -R $USER:$USER /opt/ninavpn-bot'
```

**С Mac — залить содержимое проекта в `/opt/ninavpn-bot`** (удобно из корня репозитория):

```bash
cd ~/Downloads/ninavpn-bot
scp -r . USER@2.27.122.201:/opt/ninavpn-bot/
```

Команда копирует **все** файлы из текущей папки, включая скрытые (например `.env.example`). Если на Mac есть локальный **`.env`** или папка **`venv`**, они тоже уедут на сервер:

- **`venv` с Mac на Linux не запускать** — на сервере удалите и создайте заново:  
  `bash scripts/ninavpn-heal.sh --recreate-venv`  
  или вручную: `rm -rf /opt/ninavpn-bot/venv && cd /opt/ninavpn-bot && python3 -m venv venv && …`
- Секретный **`.env`** лучше один раз создать **только на сервере** (`cp .env.example .env` и правка). Если случайно перезаписали с Mac — восстановите бэкап с сервера.

**Альтернатива — архив по SSH** (без `venv` и `.git`; при необходимости добавьте `--exclude='./.env'`):

```bash
cd ~/Downloads/ninavpn-bot
tar -czf - \
  --exclude='./venv' \
  --exclude='./__pycache__' \
  --exclude='.git' \
  --exclude='*.db' \
  . | ssh USER@2.27.122.201 'tar -xzf - -C /opt/ninavpn-bot'
```

Каталог **`/opt/ninavpn-bot`** на сервере должен уже существовать (см. команду `mkdir` выше). Такой способ перезаписывает одноимённые файлы; **удалённые** у вас в репозитории файлы на сервере **не исчезнут** — для полного зеркала лучше **rsync** (вариант A).

**Папка целиком в `/opt`** (получится путь `/opt/ninavpn-bot/`, как у systemd):

```bash
cd ~/Downloads
scp -r ninavpn-bot USER@2.27.122.201:/opt/
```

---

## 3. Настройка на сервере

Подключитесь:

```bash
ssh ninavpn
# или: ssh USER@2.27.122.201
```

Перейдите в каталог бота:

```bash
cd /opt/ninavpn-bot
```

### Пакеты и виртуальное окружение

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Не копируйте папку `venv` с Mac на сервер** — внутри лежит бинарник Python под macOS; systemd выдаст **`Exec format error`**. Всегда исключайте `venv` в `rsync` и создавайте окружение на Linux командой `python3 -m venv venv` (см. таблицу «Типичные проблемы»).

Если `pip install` ругается на **aiohttp** и **aiogram**, в `requirements.txt` уже должна быть строка `aiohttp==3.10.11` (совместимо с aiogram 3.13.x). Не ставьте `aiohttp 3.11+` вручную.

### Переменные окружения

```bash
cp .env.example .env
nano .env
```

Заполните обязательные поля:

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | от @BotFather |
| `ADMIN_ID` | числовой ID из @userinfobot |
| `TON_WALLET`, `USDT_TRC20_WALLET` | кошельки |
| `VPN_BACKEND` | `marzban` или `xui` |
| `DATABASE_URL` | по умолчанию SQLite в каталоге бота; для продакшена можно PostgreSQL (см. ниже) |
| `CHANNEL_USERNAME` / `CHANNEL_ID` | опционально: при заполнении хотя бы одного — только подписчики канала; для публичного канала достаточно **username**; бот должен быть **админом** канала (см. `.env.example`) |

**Если VPN на 3x-ui (одна панель):** `VPN_BACKEND=xui` и задайте `XUI_URL`, `XUI_USERNAME`, `XUI_PASSWORD`, `XUI_INBOUND_ID`. Обязательно укажите **`XUI_SUB_PORT=2096`** (или другой порт sub в панели). При необходимости: `XUI_SUBSCRIPTION_BASE` (полный публичный префикс до `subId`, лучше **с портом**), `XUI_CLIENT_FLOW`, `XUI_PATH_PREFIX`, `XUI_SUB_FALLBACK_PORTS`.

**Если VPN на 3x-ui (зеркало, несколько серверов):** `VPN_BACKEND=xui` и переменная **`XUI_NODES`** — одна строка с JSON-массивом объектов. Поля каждого объекта:

| Поле | Обязательно | Описание |
|------|-------------|----------|
| `url` | да | URL панели без `/` в конце, например `https://2.27.122.201:2053` |
| `username`, `password` | да | вход в панель |
| `inbound_id` | да | ID inbound в 3x-ui |
| `path_prefix` | нет | если панель в подпапке (webBasePath) |
| `subscription_base` | нет* | публичный базовый URL **с путём к подписке** без финального `subId`, напр. `https://IP:2096/sub` или свой домен; если не задан — собирается из хоста панели + **`sub_port`** |
| `sub_port` | рекомендуется | порт sub-сервиса 3x-ui, чаще всего **`2096`** |
| `client_flow` | нет | например `xtls-rprx-vision` для VLESS |
| `two_factor_code` | нет | код 2FA панели |
| `label` | нет | подпись для логов, «Серверы / статус» и сортировки |
| `verify_ssl` | нет | `false` — не проверять TLS к API этой панели |

\*Без `subscription_base` ссылка подписки строится из URL панели и **`sub_port`** (или глобального `XUI_SUB_PORT`). Для красивого домена или нестандартного пути задайте `subscription_base` **с нужным портом** (иначе на HTTPS по умолчанию часто **400/404** на `/sub/`).

Для **одной** панели без `XUI_NODES` при ошибке `CERTIFICATE_VERIFY_FAILED` задайте в `.env` **`XUI_VERIFY_SSL=false`** (менее безопасно, зато работает до обновления сертификата на сервере).

Пример для двух нод с **webBasePath** и sub на **2096**:

```bash
XUI_NODES='[{"url":"https://2.27.122.201:2053","username":"USER1","password":"PASS1","path_prefix":"ВАШ_PREFIX_1","inbound_id":1,"subscription_base":"https://2.27.122.201:2096/sub","label":"🇫🇮 Узел 1","sub_port":2096},{"url":"https://45.136.149.58:2053","username":"USER2","password":"PASS2","path_prefix":"ВАШ_PREFIX_2","inbound_id":1,"subscription_base":"https://45.136.149.58:2096/sub","label":"🇳🇱 Узел 2","sub_port":2096}]'
```

Бот создаёт и продлевает одного и того же клиента (`nina_<telegram_id>`) на **каждой** панели. Пользователь получает две (или больше) ссылок **vless**; **порядок ссылок** при нескольких узлах выбирается по **реальному HTTP-пингу** до страницы входа панели — сначала узел с меньшей задержкой. Кнопка **«Серверы / статус»** показывает те же измерения (кэш `SERVER_STATUS_CACHE_SEC`, по умолчанию 90 с). Если один узел временно недоступен при операции, админу уходит предупреждение, пользователю — подсказка в сообщении.

**Лимит устройств (3x-ui):** бот передаёт в API клиента поле **`limitIp`** = число устройств из тарифа и при «Получить конфиг» синхронизирует его с записью подписки в БД. В панели 3x-ui на **inbound** должно быть включено ограничение по IP/устройствам, иначе лимит может не применяться к трафику.

**Если Marzban:** `VPN_BACKEND=marzban` и `MARZBAN_URL`, `MARZBAN_USERNAME`, `MARZBAN_PASSWORD`. Лимит одновременных IP — **`max_ips`** в API (включается **`MARZBAN_SEND_MAX_IPS=true`**). Поле **`expire`** в API — **unix-секунды**; бот нормализует ошибочные значения в миллисекундах, чтобы срок подписки не «раздувался».

### Промокоды и база данных

При старте вызывается **`init_db()`**: создаются таблицы, в том числе **`promo_codes`** и **`promo_redemptions`** (один пользователь — не больше одного использования каждого кода; плюс общий лимит **`max_uses`** у кода).

- Создание кода: **`/promo_add CODE ДНИ`** — **ДНИ** = целые **календарные дни** бесплатного доступа при вводе кода (не часы). Пример: один день — `/promo_add TRIAL1 1`.
- Промо выдаёт доступ в панели сразу (в т.ч. без оплаченной подписки), не «бонус к следующей оплате».

Для **PostgreSQL** после смены `DATABASE_URL` выполните миграции (раздел ниже). Для **SQLite** новые таблицы подтянутся при **`create_all`** при следующем запуске.

### Реферальная программа и тарифы

- **`REFERRAL_BONUS_DAYS`** — сколько дней VPN начисляется **рефереру** после **первой успешной оплаты** каждого приглашённого (продление в панели).
- **`REFERRAL_INVITEE_BONUS_DAYS`** — опционально: доп. дни **приглашённому** при первой оплате, если он зашёл по `/start ref<ID>`. **`0`** — выключено.
- **Каталог цен:** если в БД есть активные записи **`plan_tariffs`**, бот показывает только их; иначе используются встроенные **`PLANS`** и **`EXTRA_DEVICE_*`** в `config.py` (подправьте под свой бизнес или импортируйте тарифы в БД).

### Способы оплаты в боте

В меню оплаты сейчас: **USDT**, **TON**, перевод по ссылке (**SBER_PBPN_URL**), **Т-Банк** (при настроенных ключах). **Freekassa в интерфейсе бота отключена** (кнопки «карта РФ» нет). Эндпоинт **`/payment/freekassa`** в приложении остаётся для совместимости со старыми настройками мерчанта; переменные `FREEKASSA_*` можно не задавать, если не используете IPN.

Рекомендуется запускать процесс бота на отдельном VPS или на одной из нод; токен бота и `.env` не светить публично.

Сохраните файл и выйдите из редактора.

### Пробный запуск

```bash
cd /opt/ninavpn-bot
source venv/bin/activate
python3 main.py
```

Если ошибок нет и бот отвечает в Telegram — остановите: **Ctrl+C**.

---

## 4. Автозапуск через systemd

Юнит **`ninavpn-bot.service`** по умолчанию ожидает каталог **`/opt/ninavpn-bot`** и пользователя **`root`**. При необходимости отредактируйте `User=` и пути перед установкой.

```bash
sudo cp /opt/ninavpn-bot/ninavpn-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ninavpn-bot
sudo systemctl start ninavpn-bot
sudo systemctl status ninavpn-bot
```

Логи в реальном времени:

```bash
sudo journalctl -u ninavpn-bot -f
```

Перезапуск после правок кода или `.env`:

```bash
sudo systemctl restart ninavpn-bot
```

### Скрипт «лечение» на сервере

В репозитории есть **`scripts/ninavpn-heal.sh`**: пересоздаёт **`venv`** (по желанию), ставит зависимости; на **Linux** ещё перезапускает **systemd**. На **macOS** тот же скрипт можно запускать локально — проверка «venv не с Mac» выполняется **только на Linux** (на Mac интерпретатор и должен быть Mach-O).

```bash
cd /opt/ninavpn-bot
bash scripts/ninavpn-heal.sh
```

Если в логах был **`Exec format error`** (на сервер попал `venv` с Mac):

```bash
cd /opt/ninavpn-bot
bash scripts/ninavpn-heal.sh --recreate-venv
```

Без прав root скрипт вызовет **`sudo`** для `systemctl`. Только обновить зависимости без systemd: `SKIP_SYSTEMD=1 bash scripts/ninavpn-heal.sh`.

---

## 5. HTTP-сервис бота (порт 8080): оплата, Mini App и Geo v2ray

Бот поднимает **aiohttp** на `127.0.0.1:8080` для:

- **`POST /payment/tbank`** — уведомления интернет-эквайринга Т-Банка (JSON, ответ тела **`OK`** и код 200);
- **`GET`/`POST /payment/freekassa`** — IPN Freekassa (если мерчант ещё настроен; в меню бота способ не показывается);
- страницы успеха/ошибки оплаты;
- **Telegram Mini App**: `GET /miniapp/`, `GET /miniapp/api/plans`, `GET /miniapp/api/config`, статика `/miniapp/static/`;
- **Geo для клиентов v2ray** (кэш [runetfreedom/russia-v2ray-rules-dat](https://github.com/runetfreedom/russia-v2ray-rules-dat)): `GET /geo/geoip.dat`, `GET /geo/geosite.dat` (если `V2RAY_GEO_ENABLED=1` в `.env`).

В **Nginx** проксируйте префиксы:

- `location /payment/` → `proxy_pass http://127.0.0.1:8080/payment/;`
- `location /miniapp/` → `proxy_pass http://127.0.0.1:8080/miniapp/;` (если используете Mini App)
- `location /geo/` → `proxy_pass http://127.0.0.1:8080/geo/;` (чтобы пользователи открывали те же файлы по вашему домену; в боте в «Как подключиться» ссылки строятся из `PAYMENT_PUBLIC_BASE_URL` или `PUBLIC_WEB_BASE_URL`)

Для **`FREEKASSA_WEBHOOK_STRICT_IP=1`** nginx должен передавать реальный IP клиента в **`X-Real-IP`** (или корректный первый hop в `X-Forwarded-For`), иначе легитимный IPN может отклоняться. См. **[SECURITY.md](SECURITY.md)**.

В `.env` на сервере: **`MINI_APP_URL`** — полный публичный URL точки входа (например `https://ваш-домен/miniapp/`), **`BOT_USERNAME`** — юзернейм бота без `@`. В **BotFather** при необходимости привяжите домен Mini App к этому URL.

Deep link из Mini App: `https://t.me/<BOT_USERNAME>?start=plan_<plan_key>`.

В **Т-Бизнес → интернет-эквайринг** укажите уведомления на `https://ваш-домен/payment/tbank`, либо задайте **`PAYMENT_PUBLIC_BASE_URL`** в `.env`.

Переменные `.env` для Т-Банка: `TBANK_TERMINAL_KEY`, `TBANK_PASSWORD`, опционально `TBANK_TEST_MODE`, `PAYMENT_PUBLIC_BASE_URL` (см. `.env.example`). Проверка готовности: `./scripts/tbank-setup-check.sh` (на сервере из `/opt/ninavpn-bot`).

Убедитесь, что файрвол не блокирует внешний HTTPS; локальный **8080** может оставаться только на localhost.

### PostgreSQL и Alembic (опционально)

Для продакшена можно использовать `DATABASE_URL=postgresql+asyncpg://...`. Миграции:

```bash
export ALEMBIC_SYNC_DATABASE_URL=postgresql+psycopg2://USER:PASS@localhost/DBNAME
cd /opt/ninavpn-bot && source venv/bin/activate
alembic upgrade head
```

Первая ревизия создаёт таблицы через `create_all(checkfirst=True)`. Для **downgrade** таблицы удаляются — используйте осознанно.

---

## 6. Обновление бота с Mac после правок

На Mac:

```bash
cd ~/Downloads
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '*.db' --exclude '.env' --exclude '.git' \
  ninavpn-bot/ USER@2.27.122.201:/opt/ninavpn-bot/
```

На сервере:

```bash
sudo systemctl restart ninavpn-bot
```

После обновления схемы БД (редко) при PostgreSQL снова выполните **`alembic upgrade head`**. При SQLite новые таблицы создаст **`init_db`** при старте.

---

## 7. Резервная копия

Периодически копируйте с сервера:

- файл базы (путь из `DATABASE_URL`, по умолчанию `ninavpn.db` в каталоге бота);
- `.env` (храните в безопасном месте, не в публичных репозиториях).

---

## 8. Типичные проблемы

| Симптом | Что проверить |
|---------|----------------|
| SSH отваливается | `ServerAliveInterval` в `~/.ssh/config`, работа через `tmux` |
| `pip` конфликт aiohttp | `aiohttp==3.10.11` в `requirements.txt` |
| Бот не стартует | `journalctl -u ninavpn-bot -n 50` |
| **`Exec format error`** / `status=203/EXEC` для `venv/bin/python` | Часто скопирован **`venv` с Mac**. Удалите `rm -rf /opt/ninavpn-bot/venv`, на сервере заново: `python3 -m venv venv` → `pip install -r requirements.txt`. Проверка: `file venv/bin/python` → должен быть **ELF** (Linux), не **Mach-O** |
| `/admin` молчит или «доступ запрещён» | `ADMIN_ID` (и при необходимости `ADMIN_IDS`) в `.env` = ваши Telegram ID |
| Т-Банк не выдаёт конфиг | URL `https://.../payment/tbank` в терминале или `PAYMENT_PUBLIC_BASE_URL`; ответ сервера строго `OK` (200); в логах смотрите `T-Bank notify`; выдача только при статусе **CONFIRMED** |
| Mini App не открывается / пустой экран | `MINI_APP_URL` совпадает с URL в кнопке; **HTTPS**; nginx проксирует `/miniapp/`; в BotFather привязан домен; `curl https://домен/miniapp/api/plans` возвращает JSON |
| 3x-ui: в логах **HTTP 400/404** на `https://IP/sub/...` без порта | Sub обычно на **2096**: задайте **`XUI_SUB_PORT`** / **`sub_port`** в ноде или **`subscription_base`** с `:2096` |
| 3x-ui не создаёт клиента | `XUI_URL`, `XUI_INBOUND_ID`, логин/пароль, при 2FA — `XUI_2FA_CODE`; `path_prefix` совпадает с webBasePath |
| Marzban: срок подписки «не тот» после промо | В панели поле expire в **секундах**; пересоздайте пользователя или продлите из бота после обновления кода |
| Marzban 405 на `/api/admin/token` | Укажите **`MARZBAN_API_URL`** на реальный порт API, не на статический сайт |

---

Документ актуален для репозитория **ninavpn-bot** и сервера с IP **2.27.122.201** при развёртывании с **macOS**.
