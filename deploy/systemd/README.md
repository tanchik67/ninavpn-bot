## systemd: bot + SaaS API + worker

Units:
- `ninavpn-bot.service` (repo root) — Telegram bot + aiohttp :8080
- `deploy/systemd/ninavpn-api.service` — FastAPI :8000
- `deploy/systemd/ninavpn-worker.service` — ARQ provision / reminders

### Install (once, as root)

```bash
cd /opt/ninavpn-bot
cp ninavpn-bot.service /etc/systemd/system/
cp deploy/systemd/ninavpn-api.service /etc/systemd/system/
cp deploy/systemd/ninavpn-worker.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ninavpn-bot ninavpn-api ninavpn-worker
```

`.env` must include SaaS keys, for example:

```
SAAS_DATABASE_URL=sqlite+aiosqlite:////opt/ninavpn-bot/saas_ninavpn.db
# or postgresql+asyncpg://...
REDIS_URL=redis://127.0.0.1:6379/0
JWT_SECRET=<long-random>
PAYMENT_MOCK_ENABLED=false
SAAS_PUBLIC_BASE_URL=https://ninavpn.store
```

Redis: `apt install redis-server` (or Docker).

### Update after git pull / Actions deploy

```bash
bash scripts/update-server.sh
```

### Logs

```bash
journalctl -u ninavpn-bot -f
journalctl -u ninavpn-api -f
journalctl -u ninavpn-worker -f
```

### Smoke

```bash
curl -sS http://127.0.0.1:8080/payment/success -o /dev/null -w "%{http_code}\n"
curl -sS http://127.0.0.1:8000/health
curl -sS https://ninavpn.store/api/v1/plans
```
