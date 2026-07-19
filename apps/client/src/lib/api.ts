import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

const EXTRA = Constants.expoConfig?.extra as { apiUrl?: string } | undefined;
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL || EXTRA?.apiUrl || "http://localhost:8000";

const ACCESS_KEY = "nv_access";
const REFRESH_KEY = "nv_refresh";

export type Tokens = { access_token: string; refresh_token: string };

export async function saveTokens(t: Tokens) {
  await AsyncStorage.multiSet([
    [ACCESS_KEY, t.access_token],
    [REFRESH_KEY, t.refresh_token],
  ]);
}

export async function clearTokens() {
  await AsyncStorage.multiRemove([ACCESS_KEY, REFRESH_KEY]);
}

export async function getAccessToken() {
  return AsyncStorage.getItem(ACCESS_KEY);
}

async function refreshAccess(): Promise<string | null> {
  const refresh = await AsyncStorage.getItem(REFRESH_KEY);
  if (!refresh) return null;
  const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) {
    await clearTokens();
    return null;
  }
  const data = (await res.json()) as Tokens;
  await saveTokens(data);
  return data.access_token;
}

export async function api<T>(
  path: string,
  opts: RequestInit & { auth?: boolean } = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  };
  if (opts.auth !== false) {
    let token = await getAccessToken();
    if (!token) throw new Error("not_authenticated");
    headers.Authorization = `Bearer ${token}`;
  }

  let res = await fetch(`${API_URL}${path}`, { ...opts, headers });
  if (res.status === 401 && opts.auth !== false) {
    const next = await refreshAccess();
    if (next) {
      headers.Authorization = `Bearer ${next}`;
      res = await fetch(`${API_URL}${path}`, { ...opts, headers });
    }
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
