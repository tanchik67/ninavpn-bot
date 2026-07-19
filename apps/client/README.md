# NinaVPN Client (Expo)

Единый клиент для iOS / Android / Web (Expo Router).

## Setup

```bash
cd apps/client
cp .env.example .env   # EXPO_PUBLIC_API_URL=https://ninavpn.store
npm install
npm run web            # или npm start
```

Локальный API:

```bash
EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web
```

Прод по умолчанию: `https://ninavpn.store` (см. `app.json` → `extra.apiUrl`).

## Привязка Telegram

1. В боте: `/linkcabinet` → получите код  
2. В приложении: **Аккаунт** → вставьте код → «Привязать Telegram»  
3. Бот пришлёт подтверждение; дальше туда же уходят уведомления о доступе и окончании подписки

## Screens

- Auth, Plans, Pay (poll provision), Subscription, Config/QR, Support, Account
