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
- `GET /api/v1/plans`
- `GET /api/v1/subscriptions/me` + `/config`
- `POST /api/v1/payments/checkout`
- `POST /api/v1/payments/webhooks/{provider}`
- `POST /api/v1/payments/mock/confirm/{id}` (dev)
- `POST /api/v1/support/tickets`
