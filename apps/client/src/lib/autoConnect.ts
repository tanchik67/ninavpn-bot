import { AppState, type AppStateStatus } from "react-native";
import { loadCachedServers } from "./serverCache";
import { getSelectedServerId } from "./selectedServer";
import {
  isSubscriptionActive,
  loadCachedSubscription,
} from "./subscriptionCache";
import { loadVpnPrefs, applyTunnelAccess } from "./vpnPrefs";
import {
  ninaVpnConnect,
  ninaVpnGetStatus,
  ninaVpnPrepare,
  ninaVpnSupported,
} from "./ninaVpn";

let inFlight = false;
let seenBackground = true;
let resumeTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleTryAutoConnect() {
  if (resumeTimer) clearTimeout(resumeTimer);
  resumeTimer = setTimeout(() => {
    resumeTimer = null;
    void tryAutoConnect();
  }, 350);
}

export function onAppStateForAutoConnect(state: AppStateStatus) {
  if (state !== "active") {
    seenBackground = true;
    return;
  }
  if (!seenBackground) return;
  seenBackground = false;
  scheduleTryAutoConnect();
}

/**
 * JS backup for auto-connect. Native Activity.onResume is the primary path
 * (MIUI Recents often never delivers AppState background/active).
 */
export async function tryAutoConnect(): Promise<boolean> {
  if (inFlight) return false;
  if (!ninaVpnSupported()) return false;

  inFlight = true;
  try {
    const prefs = await loadVpnPrefs();
    if (!prefs.autoConnect) return false;
    const st = await ninaVpnGetStatus();
    if (st === "connected" || st === "connecting") return false;
    const sub = await loadCachedSubscription();
    if (!sub || !isSubscriptionActive(sub) || !sub.has_config) return false;
    await applyTunnelAccess(true);
    const servers = await loadCachedServers();
    const selectedId = await getSelectedServerId();
    const row =
      servers.find((s) => s.id === selectedId && s.uri) ||
      servers.find((s) => !!s.uri);
    if (!row?.uri) return false;

    const prepared = await ninaVpnPrepare();
    if (!prepared) return false;

    await ninaVpnConnect(row.uri, row.id);
    return true;
  } catch {
    return false;
  } finally {
    inFlight = false;
  }
}

export function attachAutoConnectAppState() {
  const sub = AppState.addEventListener("change", onAppStateForAutoConnect);
  if (AppState.currentState === "active") {
    seenBackground = false;
    void tryAutoConnect();
  }
  return () => {
    sub.remove();
    if (resumeTimer) {
      clearTimeout(resumeTimer);
      resumeTimer = null;
    }
  };
}
