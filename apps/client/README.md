# NinaVPN Client (Expo)

Единый клиент для iOS / Android / Web (Expo Router).

## Setup

```bash
cd apps/client
npm install
EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web
```

Для устройства в LAN укажите IP машины с API:

```bash
EXPO_PUBLIC_API_URL=http://192.168.1.10:8000 npm start
```

## Screens

- Auth: login / register
- Plans → checkout (mock confirm в dev)
- Subscription / Config (QR + deeplinks)
- Support tickets
