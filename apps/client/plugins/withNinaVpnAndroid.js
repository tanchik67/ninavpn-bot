const {
  withAndroidManifest,
  AndroidConfig,
  ConfigPlugin,
} = require("@expo/config-plugins");

/**
 * Ensure VPN service + permissions survive Expo prebuild.
 * @type {ConfigPlugin}
 */
function withNinaVpnAndroid(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    if (!manifest["uses-permission"]) manifest["uses-permission"] = [];
    const perms = [
      "android.permission.INTERNET",
      "android.permission.FOREGROUND_SERVICE",
      "android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
      "android.permission.POST_NOTIFICATIONS",
    ];
    for (const name of perms) {
      if (!manifest["uses-permission"].some((p) => p.$?.["android:name"] === name)) {
        manifest["uses-permission"].push({ $: { "android:name": name } });
      }
    }

    const app = manifest.application?.[0];
    if (app) {
      if (!app.service) app.service = [];
      const exists = app.service.some(
        (s) => s.$?.["android:name"] === "store.ninavpn.vpn.NinaVpnService"
      );
      if (!exists) {
        app.service.push({
          $: {
            "android:name": "store.ninavpn.vpn.NinaVpnService",
            "android:exported": "false",
            "android:foregroundServiceType": "specialUse",
            "android:permission": "android.permission.BIND_VPN_SERVICE",
          },
          "intent-filter": [
            {
              action: [{ $: { "android:name": "android.net.VpnService" } }],
            },
          ],
          property: [
            {
              $: {
                "android:name": "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE",
                "android:value": "vpn",
              },
            },
          ],
        });
      }
      const tileExists = app.service.some(
        (s) => s.$?.["android:name"] === "store.ninavpn.vpn.NinaVpnTileService"
      );
      if (!tileExists) {
        app.service.push({
          $: {
            "android:name": "store.ninavpn.vpn.NinaVpnTileService",
            "android:exported": "true",
            "android:icon": "@drawable/ic_qs_nv",
            "android:label": "@string/qs_tile_label",
            "android:permission": "android.permission.BIND_QUICK_SETTINGS_TILE",
          },
          "intent-filter": [
            {
              action: [
                { $: { "android:name": "android.service.quicksettings.action.QS_TILE" } },
              ],
            },
          ],
          "meta-data": [
            {
              $: {
                "android:name": "android.service.quicksettings.ACTIVE_TILE",
                "android:value": "true",
              },
            },
          ],
        });
      }
    }
    return config;
  });
}

module.exports = withNinaVpnAndroid;
