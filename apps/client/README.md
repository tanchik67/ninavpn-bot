# NinaVPN Client (Expo)

Единый клиент для iOS / Android / Web (Expo Router).

## Setup

```bash
cd apps/client
cp .env.example .env
npm install
npx expo install
npm run web
```

Откроется браузер: **http://localhost:8081**

Важно: в команде `cp` не копируйте комментарии после `#` — только:

```bash
cp .env.example .env
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
