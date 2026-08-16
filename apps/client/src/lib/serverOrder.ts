import AsyncStorage from "@react-native-async-storage/async-storage";
import { getSessionUserId } from "./sessionUser";

const LEGACY = "nv_server_order_v1";

function key() {
  const uid = getSessionUserId();
  return uid ? `${LEGACY}:${uid}` : LEGACY;
}

export async function loadServerOrder(): Promise<string[]> {
  try {
    const raw = await AsyncStorage.getItem(key());
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((id) => typeof id === "string")
      : [];
  } catch {
    return [];
  }
}

export async function saveServerOrder(ids: string[]): Promise<void> {
  try {
    await AsyncStorage.setItem(key(), JSON.stringify(ids));
  } catch {
    /* ignore */
  }
}

export function applyIdOrder<T extends { id: string }>(
  rows: T[],
  order: string[]
): T[] {
  if (!rows.length || !order.length) return rows;
  const map = new Map(rows.map((r) => [r.id, r]));
  const out: T[] = [];
  for (const id of order) {
    const row = map.get(id);
    if (row) {
      out.push(row);
      map.delete(id);
    }
  }
  for (const row of rows) {
    if (map.has(row.id)) out.push(row);
  }
  return out;
}
