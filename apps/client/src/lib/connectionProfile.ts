import AsyncStorage from "@react-native-async-storage/async-storage";
import { getSessionUserId } from "./sessionUser";

const LEGACY = "nv_connection_profile";

export type ConnectionProfileId = "low_latency" | "streaming" | "max_stealth";

function key() {
  const uid = getSessionUserId();
  return uid ? `${LEGACY}:${uid}` : LEGACY;
}

export async function loadConnectionProfile(): Promise<ConnectionProfileId> {
  try {
    const uid = getSessionUserId();
    if (!uid) return "low_latency";
    const v = await AsyncStorage.getItem(key());
    if (v === "low_latency" || v === "streaming" || v === "max_stealth") return v;
  } catch {
    /* ignore */
  }
  return "low_latency";
}

export async function saveConnectionProfile(id: ConnectionProfileId): Promise<void> {
  const uid = getSessionUserId();
  if (!uid) return;
  await AsyncStorage.setItem(key(), id);
}
