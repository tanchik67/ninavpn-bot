import AsyncStorage from "@react-native-async-storage/async-storage";
import { getSessionUserId } from "./sessionUser";

const LEGACY_KEY = "nv_subscription_v1";

function subKey() {
  const uid = getSessionUserId();
  return uid ? `${LEGACY_KEY}:${uid}` : LEGACY_KEY;
}

export type CachedSubscription = {
  id?: string;
  status: string;
  devices?: number;
  months?: number;
  plan_key?: string | null;
  plan_name?: string | null;
  expires_at?: string | null;
  has_config?: boolean;
};

/** True when the user can use VPN / should see Active in profile. */
export function isSubscriptionActive(
  sub: { status?: string; expires_at?: string | null } | null | undefined
): boolean {
  if (!sub?.status) return false;
  const st = String(sub.status).toLowerCase();
  if (st !== "active" && st !== "past_due" && st !== "trial") return false;
  if (sub.expires_at) {
    const t = new Date(sub.expires_at).getTime();
    if (!Number.isNaN(t) && t <= Date.now()) return false;
  }
  return true;
}

export async function loadCachedSubscription(): Promise<CachedSubscription | null> {
  try {
    const raw = await AsyncStorage.getItem(subKey());
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedSubscription;
    return parsed?.status ? parsed : null;
  } catch {
    return null;
  }
}

export async function saveCachedSubscription(sub: CachedSubscription | null): Promise<void> {
  try {
    if (!sub) {
      await AsyncStorage.removeItem(subKey());
      return;
    }
    await AsyncStorage.setItem(subKey(), JSON.stringify(sub));
  } catch {
    /* ignore */
  }
}

export async function clearCachedSubscription(): Promise<void> {
  try {
    await AsyncStorage.removeItem(subKey());
    await AsyncStorage.removeItem(LEGACY_KEY);
  } catch {
    /* ignore */
  }
}
