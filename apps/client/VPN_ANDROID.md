# NinaVPN — Android VPN core

In-app tunnel lives in `modules/nina-vpn`:

- `VpnService.prepare` (+ activity result)
- Foreground `NinaVpnService`
- **Xray-core via AndroidLibXrayLite** (`XrayBridge` + `VlessConfigBuilder`)
- JS: `prepare` / `connect(uri)` / `disconnect` / `getStatus`

## Why Xray (not sing-box)

Panel nodes speak **VLESS + Reality** (Xray 26.x). Official sing-box libbox fails Reality
verification against these servers (`reality verification failed`), so the UI can show
“connected” while apps like Telegram stay on “connecting”. The data plane uses
`libv2ray.aar` instead.

## Dependencies

Place `libv2ray.aar` in `modules/nina-vpn/android/libs/`:

```bash
# from https://github.com/2dust/AndroidLibXrayLite/releases
cp libv2ray.aar apps/client/modules/nina-vpn/android/libs/
```

## Build / run

```bash
cd apps/client
npm install
npx expo prebuild --platform android --clean
npx expo run:android
# or: cd android && ./gradlew assembleRelease
```

Requirements: Android SDK, JDK 17+, device/emulator API 24+.

First Connect: system VPN permission dialog → TUN established → Xray `startLoop` with
VLESS/Reality outbound from the selected node URI.

## Web

`app.ninavpn.store` stays account/billing. Browsers cannot create a device VPN; Connect shows “install Android app”.

## iOS

Phase 2 (Network Extension). Same `apps/client` UI; native module is Android-only for now.
