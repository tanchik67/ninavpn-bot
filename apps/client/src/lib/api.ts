import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";
import { formatApiDetail } from "./apiErrors";
import { ninaVpnEnsureNetwork } from "./ninaVpn";

const EXTRA = Constants.expoConfig?.extra as { apiUrl?: string } | undefined;
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  EXTRA?.apiUrl ||
  "https://ninavpn.store";

const ACCESS_KEY = "nv_access";
const REFRESH_KEY = "nv_refresh";

/** Refresh a bit before JWT exp so screens don't start with a guaranteed 401. */
const ACCESS_SKEW_MS = 60_000;

export type Tokens = { access_token: string; refresh_token: string };

/** Single in-flight refresh — concurrent 401s must not rotate/revoke each other. */
let refreshInFlight: Promise<string | null> | null = null;

/**
 * Limit concurrent HTTPS calls. On MIUI, a storm of hung GETs (prefetch/poll)
 * starves POSTs — support messages never leave the device.
 */
const MAX_INFLIGHT = 2; // keep low — hung GETs otherwise block support POSTs
let inflightHttp = 0;
const httpWaiters: Array<{ priority: boolean; wake: () => void }> = [];

function acquireHttp(priority = false): Promise<void> {
  // Priority (support send / login) must NEVER wait behind hung MIUI GETs —
  // oversubscribe briefly so the POST can leave the device.
  if (priority || inflightHttp < MAX_INFLIGHT) {
    inflightHttp += 1;
    return Promise.resolve();
  }
  return new Promise<void>((resolve) => {
    const item = {
      priority,
      wake: () => {
        inflightHttp += 1;
        resolve();
      },
    };
    if (priority) httpWaiters.unshift(item);
    else httpWaiters.push(item);
  });
}

function releaseHttp() {
  const next = httpWaiters.shift();
  if (next) next.wake();
  else inflightHttp = Math.max(0, inflightHttp - 1);
}

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

export async function getRefreshToken() {
  return AsyncStorage.getItem(REFRESH_KEY);
}

export async function hasSessionTokens(): Promise<boolean> {
  const [a, r] = await AsyncStorage.multiGet([ACCESS_KEY, REFRESH_KEY]);
  return !!(a[1] || r[1]);
}

function isTransientNetworkError(msg: string): boolean {
  return /network_timeout|network_error|timeout|failed to fetch|load failed|networkerror/i.test(
    msg
  );
}

function jwtExpMs(token: string): number | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    // atob is available in Hermes / RN
    const json = JSON.parse(globalThis.atob(padded)) as { exp?: number };
    return typeof json.exp === "number" ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

function accessNeedsRefresh(token: string | null): boolean {
  if (!token) return true;
  const exp = jwtExpMs(token);
  if (exp == null) return false; // opaque / unreadable — try as-is
  return Date.now() >= exp - ACCESS_SKEW_MS;
}

async function refreshAccess(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refresh = await AsyncStorage.getItem(REFRESH_KEY);
    if (!refresh) return null;
    try {
      const res = await withTimeout(
        fetch(`${API_URL}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        }),
        12000,
        "network_timeout"
      );
      if (!res.ok) {
        // Only wipe session on definitive auth rejection — not on 5xx/gateway blips
        if (res.status === 401 || res.status === 403) {
          await clearTokens();
        }
        return null;
      }
      const data = (await res.json()) as Tokens;
      if (!data?.access_token || !data?.refresh_token) {
        await clearTokens();
        return null;
      }
      await saveTokens(data);
      return data.access_token;
    } catch {
      // Network/timeout — keep tokens so cold start can retry
      return null;
    }
  })().finally(() => {
    refreshInFlight = null;
  });

  return refreshInFlight;
}

/** Ensure Authorization uses a non-expired access token when possible. */
export async function ensureAccessToken(): Promise<string | null> {
  const access = await getAccessToken();
  if (access && !accessNeedsRefresh(access)) return access;
  const refresh = await getRefreshToken();
  if (!refresh) return access; // may still work if clock skew / opaque
  const next = await refreshAccess();
  return next || (await getAccessToken());
}

/** Always rotate access via refresh endpoint (used after a 401 on send). */
export async function forceRefreshAccess(): Promise<string | null> {
  return refreshAccess();
}

function withTimeout<T>(p: Promise<T>, ms: number, code = "timeout"): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(code)), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      }
    );
  });
}

export async function api<T>(
  path: string,
  opts: RequestInit & {
    auth?: boolean;
    timeoutMs?: number;
    retries?: number;
    /** Jump the HTTP queue (use for support send). */
    priority?: boolean;
  } = {}
): Promise<T> {
  // MIUI: stale bindProcessToNetwork after VPN/Wi‑Fi changes makes fetch hang until timeout.
  await ninaVpnEnsureNetwork();
  await acquireHttp(!!opts.priority);

  try {
    const method = (opts.method || "GET").toUpperCase();
    const headers: Record<string, string> = {
      ...(opts.headers as Record<string, string>),
    };
    // Avoid forcing JSON content-type on GET — some stacks mishandle empty bodies.
    if (method !== "GET" && method !== "HEAD" && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    if (opts.auth !== false) {
      const token = await ensureAccessToken();
      if (!token) {
        const refresh = await getRefreshToken();
        if (!refresh) throw new Error("not_authenticated");
        throw new Error("network_error");
      }
      headers.Authorization = `Bearer ${token}`;
    }

    const timeoutMs = opts.timeoutMs ?? 12000;
    const retries = opts.retries ?? 0;
    const {
      timeoutMs: _t,
      auth: _a,
      retries: _r,
      priority: _p,
      signal: outerSignal,
      ...fetchOpts
    } = opts;

    const doFetch = async (hdrs: Record<string, string>) => {
      const ctrl = new AbortController();
      const onOuterAbort = () => ctrl.abort();
      if (outerSignal) {
        if (outerSignal.aborted) throw new Error("network_timeout");
        outerSignal.addEventListener("abort", onOuterAbort);
      }
      const timer = setTimeout(() => ctrl.abort(), timeoutMs);
      try {
        return await fetch(`${API_URL}${path}`, {
          ...fetchOpts,
          headers: hdrs,
          signal: ctrl.signal,
        });
      } catch (e: any) {
        const msg = String(e?.message || e || "");
        if (/abort/i.test(msg)) throw new Error("network_timeout");
        if (/load failed|failed to fetch|networkerror/i.test(msg)) {
          throw new Error("network_error");
        }
        throw e instanceof Error ? e : new Error(msg || "network_error");
      } finally {
        clearTimeout(timer);
        outerSignal?.removeEventListener("abort", onOuterAbort);
      }
    };

    let attempt = 0;
    let res: Response | null = null;
    let lastErr: Error | null = null;
    while (attempt <= retries) {
      try {
        res = await doFetch(headers);
        lastErr = null;
        break;
      } catch (e: any) {
        lastErr = e instanceof Error ? e : new Error(String(e));
        if (!isTransientNetworkError(lastErr.message) || attempt >= retries)
          throw lastErr;
        attempt += 1;
        await new Promise((r) => setTimeout(r, 300 * attempt));
      }
    }
    if (!res) throw lastErr || new Error("network_error");

    if (res.status === 401 && opts.auth !== false) {
      const next = await refreshAccess();
      if (next) {
        headers.Authorization = `Bearer ${next}`;
        res = await doFetch(headers);
      } else {
        const still = await getRefreshToken();
        if (!still) throw new Error("not_authenticated");
        // Refresh token still stored → transient failure, not a logout
        throw new Error("network_error");
      }
    }
    if (!res.ok) {
      const body = await res.text();
      let detail = body || `HTTP ${res.status}`;
      try {
        const parsed = JSON.parse(body) as { detail?: unknown };
        detail = formatApiDetail(parsed.detail, body, res.status);
      } catch {
        /* keep raw body */
      }
      throw new Error(detail);
    }
    if (res.status === 204) return undefined as T;
    const raw = await res.text();
    // MIUI: HTTP 200 with empty body after the server already saved the row
    if (!raw) {
      if (method === "POST") throw new Error("ack_needed");
      return undefined as T;
    }
    try {
      return JSON.parse(raw) as T;
    } catch {
      if (method === "POST") throw new Error("ack_needed");
      throw new Error("bad_response");
    }
  } finally {
    releaseHttp();
  }
}
