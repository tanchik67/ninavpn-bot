# NinaVPN API (FastAPI)

## Local (Docker)

```bash
docker compose up -d postgres redis
pip install -r requirements.txt -r requirements-saas.txt
export SAAS_DATABASE_URL=postgresql+asyncpg://ninavpn:ninavpn@localhost:5432/ninavpn
export REDIS_URL=redis://localhost:6379/0
export JWT_SECRET=dev-secret
export PAYMENT_MOCK_ENABLED=true
uvicorn apps.api.app.main:app --reload --port 8000
```

Worker:

```bash
python -m apps.worker.main
```

Or full stack: `docker compose up`.

## Key routes

- `POST /api/v1/auth/register|login|refresh|logout`
- `POST /api/v1/auth/password/forgot` — email → 6-digit code (SMTP; `dev_code` if SMTP unset)
- `POST /api/v1/auth/password/reset` — email + code + new_password
- `POST /api/v1/auth/password/change` — authenticated; current_password if user already has one
- `POST /api/v1/auth/me/emoji` (also PATCH) — body `{ "emoji": "😎" }` (empty string clears)
- `POST /api/v1/auth/google` — body `{ "id_token": "..." }`
- `POST /api/v1/auth/telegram` — Telegram Login Widget fields (`id`, `first_name`, `auth_date`, `hash`, …)
- `GET /api/v1/plans`
- `GET /api/v1/subscriptions/me` + `/config`
- `POST /api/v1/payments/checkout` — `provider`: `tbank` | `mock` | `stripe`
- `POST /api/v1/payments/webhooks/{provider}`
- `POST /api/v1/payments/mock/confirm/{id}` (dev)
- `GET /api/v1/referrals/me` + `POST /api/v1/referrals/apply` + `GET /api/v1/referrals/affiliate`
- `GET /api/v1/network/locations|status|profiles|fx`
- `POST /api/v1/support/tickets`
- `GET /api/v1/support/chat` + ticket messages
- Staff (`role` admin/support): `GET /api/v1/support/admin/tickets`, `GET …/admin/tickets/{id}`, `POST …/admin/tickets/{id}/messages`
- Promote cabinet admins: `ADMIN_EMAILS=you@example.com` (comma-separated) or `UPDATE saas_users SET role='admin' WHERE email='…'`

## OAuth setup (Expo cabinet)

Быстрый прод-прогон (после Google Client ID и Domain в BotFather):

```bash
GOOGLE_WEB_CLIENT_ID='….apps.googleusercontent.com' ./scripts/configure-oauth.sh
```

Скрипт пишет `GOOGLE_CLIENT_IDS` / `TELEGRAM_BOT_USERNAME` в `/opt/ninavpn-bot/.env`, обновляет `tg-login.html`, собирает и выкладывает `app.ninavpn.store`.

### Google

1. Google Cloud Console → OAuth 2.0 Client ID (Web).
2. Authorized JavaScript origins:
   - `https://app.ninavpn.store`
   - `https://ninavpn.store`
   - `http://localhost:8081`
3. Authorized redirect URIs (required for Android app + web):
   - `https://ninavpn.store/google-login.html` ← native bridge (`site/google-login.html`)
   - `https://app.ninavpn.store`
   - `http://localhost:8081`
4. Set on API: `GOOGLE_CLIENT_IDS=<web-client-id>` (comma-separate iOS/Android IDs later).
5. Set on Expo: `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=<same-web-client-id>` and
   `EXPO_PUBLIC_GOOGLE_LOGIN_URL=https://ninavpn.store/google-login.html`.

Android uses the HTTPS bridge page (not a custom-scheme Web client redirect) to avoid
Google `invalid_request` / OAuth policy errors.

### Telegram Login Widget

1. BotFather → Bot Settings → Domain → `ninavpn.store` (required for widget on that host).
2. Ensure `BOT_TOKEN` is set for the API (HMAC verification).
3. Ship / update `site/tg-login.html` (served at `https://ninavpn.store/tg-login.html`).
4. Expo: `EXPO_PUBLIC_TELEGRAM_BOT_USERNAME=<bot_without_at>` and optional `EXPO_PUBLIC_TG_LOGIN_URL`.

### DB

`password_hash` is nullable; `google_sub` unique nullable. Alembic: `002_saas_oauth`. API `init_db` also best-effort alters existing Postgres/SQLite.
