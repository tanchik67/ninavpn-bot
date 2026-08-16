import AsyncStorage from "@react-native-async-storage/async-storage";
import { getSessionUserId } from "./sessionUser";

const SERVERS_LEGACY = "nv_home_servers_v1";
const CONFIG_LEGACY = "nv_home_config_v1";

function serversKey() {
  const uid = getSessionUserId();
  return uid ? `${SERVERS_LEGACY}:${uid}` : SERVERS_LEGACY;
}

function configKey() {
  const uid = getSessionUserId();
  return uid ? `${CONFIG_LEGACY}:${uid}` : CONFIG_LEGACY;
}

export type CachedServerRow = {
  id: string;
  flag: string;
  name: string;
  protocol: string;
  ping: number | null;
  uri?: string;
};

export type CachedConfigPayload = {
  subscription_url?: string;
  links: string[];
  nodes: {
    id: string;
    flag: string;
    city: string;
    uri: string;
    protocol?: string;
    protocols?: string[];
  }[];
  status: string;
  expires_at?: string | null;
};

export async function loadCachedServers(): Promise<CachedServerRow[]> {
  try {
    const raw = await AsyncStorage.getItem(serversKey());
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function saveCachedServers(rows: CachedServerRow[]): Promise<void> {
  if (!rows.length) return;
  try {
    await AsyncStorage.setItem(serversKey(), JSON.stringify(rows));
  } catch {
    /* ignore */
  }
}

export async function loadCachedConfig(): Promise<CachedConfigPayload | null> {
  try {
    const raw = await AsyncStorage.getItem(configKey());
    if (!raw) return null;
    return JSON.parse(raw) as CachedConfigPayload;
  } catch {
    return null;
  }
}

export async function saveCachedConfig(cfg: CachedConfigPayload): Promise<void> {
  try {
    await AsyncStorage.setItem(configKey(), JSON.stringify(cfg));
  } catch {
    /* ignore */
  }
}

export async function clearHomeCaches(): Promise<void> {
  try {
    await AsyncStorage.multiRemove([
      serversKey(),
      configKey(),
      SERVERS_LEGACY,
      CONFIG_LEGACY,
    ]);
  } catch {
    /* ignore */
  }
}
