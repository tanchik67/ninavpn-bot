import AsyncStorage from "@react-native-async-storage/async-storage";
import { ninaVpnSetOptions } from "./ninaVpn";
import { getSessionUserId } from "./sessionUser";

const LEGACY_KEY = "nv_vpn_prefs_v1";

export type VpnPrefs = {
  autoConnect: boolean;
  killSwitch: boolean;
  lanAccess: boolean;
};

export const VPN_PREF_DEFAULTS: VpnPrefs = {
  autoConnect: false,
  killSwitch: true,
  lanAccess: false,
};

let owner: string | null | undefined = undefined;
let memory: VpnPrefs | null = null;

function keyFor(userId: string) {
  return `nv_vpn_prefs_v2:${userId}`;
}

function syncNative(prefs: VpnPrefs, tunnelAllowed: boolean) {
  void ninaVpnSetOptions(
    prefs.killSwitch,
    prefs.lanAccess,
    !!(prefs.autoConnect && tunnelAllowed),
    tunnelAllowed
  );
}

export async function bindVpnPrefsUser(userId: string | null): Promise<VpnPrefs> {
  owner = userId;
  memory = null;
  if (!userId) {
    memory = { ...VPN_PREF_DEFAULTS };
    syncNative(memory, false);
    return { ...memory };
  }
  return loadVpnPrefs();
}

export async function loadVpnPrefs(): Promise<VpnPrefs> {
  const uid = owner !== undefined ? owner : getSessionUserId();
  if (memory && owner === uid) return { ...memory };
  if (!uid) {
    memory = { ...VPN_PREF_DEFAULTS };
    owner = null;
    return { ...memory };
  }
  try {
    const raw = await AsyncStorage.getItem(keyFor(uid));
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<VpnPrefs>;
      memory = { ...VPN_PREF_DEFAULTS, ...parsed };
      owner = uid;
      return { ...memory };
    }
  } catch {
    /* defaults */
  }
  memory = { ...VPN_PREF_DEFAULTS };
  owner = uid;
  return { ...memory };
}

export async function saveVpnPrefs(partial: Partial<VpnPrefs>): Promise<VpnPrefs> {
  const cur = await loadVpnPrefs();
  const next: VpnPrefs = { ...cur, ...partial };
  memory = next;
  const uid = owner ?? getSessionUserId();
  if (uid) {
    try {
      await AsyncStorage.setItem(keyFor(uid), JSON.stringify(next));
      await AsyncStorage.removeItem(LEGACY_KEY);
    } catch {
      /* ignore */
    }
  }
  try {
    const { isSubscriptionActive, loadCachedSubscription } = await import(
      "./subscriptionCache"
    );
    const sub = await loadCachedSubscription();
    const allowed = !!sub && isSubscriptionActive(sub) && !!sub.has_config;
    syncNative(next, allowed);
  } catch {
    syncNative(next, false);
  }
  return { ...next };
}

/** Enable native auto-connect / tunnel only when this account has an active sub. */
export async function applyTunnelAccess(allowed: boolean): Promise<void> {
  const prefs = memory || VPN_PREF_DEFAULTS;
  syncNative(prefs, allowed);
}

export function getVpnPrefsSync(): VpnPrefs {
  return memory ? { ...memory } : { ...VPN_PREF_DEFAULTS };
}
