/**
 * NinaVPN in-app tunnel bridge.
 * Uses Expo native module `NinaVpn` (not React Native NativeModules).
 */
import { EventEmitter, requireNativeModule } from "expo-modules-core";
import { Platform } from "react-native";

export type NinaVpnStatus = "disconnected" | "connecting" | "connected" | "unavailable";

type NinaVpnNative = {
  isSupported: () => Promise<boolean>;
  prepare: () => Promise<boolean>;
  connect: (uri: string, nodeId?: string) => Promise<void>;
  disconnect: () => Promise<void>;
  getStatus: () => Promise<NinaVpnStatus>;
  ensureNetwork?: () => Promise<void>;
  tcpPingMs?: (host: string, port: number, timeoutMs: number) => Promise<number>;
  setOptions?: (
    killSwitch: boolean,
    lanAccess: boolean,
    autoConnect: boolean,
    tunnelAllowed: boolean
  ) => Promise<void>;
  reconnect?: () => Promise<boolean>;
  clearSession?: () => Promise<void>;
  requestQuickTile?: () => Promise<boolean>;
};

let cached: NinaVpnNative | null | undefined;

function getNative(): NinaVpnNative | null {
  if (cached !== undefined) return cached;
  if (Platform.OS !== "android") {
    cached = null;
    return null;
  }
  try {
    cached = requireNativeModule<NinaVpnNative>("NinaVpn");
  } catch {
    cached = null;
  }
  return cached;
}

export function ninaVpnSupported(): boolean {
  return Platform.OS === "android" && !!getNative();
}

export async function ninaVpnIsSupported(): Promise<boolean> {
  const Native = getNative();
  if (!Native) return false;
  try {
    return await Native.isSupported();
  } catch {
    return false;
  }
}

/** System VPN permission dialog on Android. Returns false if user denies / needs retry. */
export async function ninaVpnPrepare(): Promise<boolean> {
  const Native = getNative();
  if (!Native) return false;
  return Promise.race([
    Native.prepare(),
    new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 45000)),
  ]);
}

export async function ninaVpnConnect(uri: string, nodeId?: string): Promise<void> {
  const Native = getNative();
  if (!Native) throw new Error("vpn_unavailable");
  try {
    const { getVpnPrefsSync } = await import("./vpnPrefs");
    const p = getVpnPrefsSync();
    await Native.setOptions?.(p.killSwitch, p.lanAccess, p.autoConnect, true);
  } catch {
    /* prefs optional */
  }
  await Native.connect(uri, nodeId || "");
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 150));
    const st = await Native.getStatus();
    if (st === "connected") return;
    if (st === "disconnected" && i > 8) throw new Error("vpn_core_missing");
  }
  const st = await Native.getStatus();
  if (st !== "connected") throw new Error("vpn_core_missing");
}

export async function ninaVpnDisconnect(): Promise<void> {
  const Native = getNative();
  if (!Native) return;
  try {
    // MIUI: native disconnect can hang and block login for tens of seconds
    await Promise.race([
      Native.disconnect(),
      new Promise<void>((resolve) => setTimeout(resolve, 2000)),
    ]);
  } catch {
    /* ignore */
  }
  // Always clear process network bind after tunnel teardown.
  try {
    await Promise.race([
      Native.ensureNetwork?.() ?? Promise.resolve(),
      new Promise<void>((resolve) => setTimeout(resolve, 1200)),
    ]);
  } catch {
    /* ignore */
  }
}

export async function ninaVpnGetStatus(): Promise<NinaVpnStatus> {
  const Native = getNative();
  if (!Native) return "unavailable";
  try {
    return await Native.getStatus();
  } catch {
    return "unavailable";
  }
}

/** Skip repeated ensureNetwork within this window — login/chat were paying 1.5s per call. */
const ENSURE_COOLDOWN_MS = 4000;
let lastEnsureAt = 0;
let ensureInFlight: Promise<void> | null = null;

/** Clear stale process→network bind. Never hang JS — native calls can stall on MIUI. */
export async function ninaVpnEnsureNetwork(opts?: {
  force?: boolean;
}): Promise<void> {
  const Native = getNative();
  if (!Native?.ensureNetwork) return;
  const now = Date.now();
  if (!opts?.force && now - lastEnsureAt < ENSURE_COOLDOWN_MS) return;
  if (ensureInFlight) {
    await ensureInFlight;
    return;
  }
  ensureInFlight = (async () => {
    try {
      await Promise.race([
        Native.ensureNetwork!(),
        new Promise<void>((resolve) => setTimeout(resolve, 800)),
      ]);
      lastEnsureAt = Date.now();
    } catch {
      /* ignore */
    } finally {
      ensureInFlight = null;
    }
  })();
  await ensureInFlight;
}

export async function ninaVpnSetOptions(
  killSwitch: boolean,
  lanAccess: boolean,
  autoConnect = false,
  tunnelAllowed = false
): Promise<void> {
  const Native = getNative();
  if (!Native?.setOptions) return;
  try {
    await Native.setOptions(!!killSwitch, !!lanAccess, !!autoConnect, !!tunnelAllowed);
  } catch {
    /* ignore */
  }
}

/** Drop last node, auto-connect flags and stop the tunnel — used on logout / account switch. */
export async function ninaVpnClearSession(): Promise<void> {
  const Native = getNative();
  if (!Native) return;
  try {
    if (Native.clearSession) {
      await Promise.race([
        Native.clearSession(),
        new Promise<void>((resolve) => setTimeout(resolve, 2500)),
      ]);
      try {
        await ninaVpnEnsureNetwork({ force: true });
      } catch {
        /* ignore */
      }
      return;
    }
  } catch {
    /* fall through */
  }
  await ninaVpnDisconnect();
  try {
    await Native.setOptions?.(true, false, false, false);
  } catch {
    /* ignore */
  }
}

/** Android 13+: prompt once to pin the NinaVPN Quick Settings tile. */
export async function ninaVpnRequestQuickTile(): Promise<void> {
  if (Platform.OS !== "android") return;
  const Native = getNative();
  if (!Native?.requestQuickTile) return;
  try {
    await Native.requestQuickTile();
  } catch {
    /* OEM / already asked */
  }
}

export async function ninaVpnReconnect(): Promise<boolean> {
  const Native = getNative();
  if (!Native?.reconnect) return false;
  try {
    return !!(await Native.reconnect());
  } catch {
    return false;
  }
}

/** TCP connect RTT in ms, or null if unsupported / unreachable. */
export async function ninaVpnTcpPingMs(
  host: string,
  port: number,
  timeoutMs = 2500
): Promise<number | null> {
  const Native = getNative();
  if (!Native?.tcpPingMs || !host || !port) return null;
  try {
    const ms = await Promise.race([
      Native.tcpPingMs(host, port, timeoutMs),
      new Promise<number>((resolve) => setTimeout(() => resolve(-1), timeoutMs + 400)),
    ]);
    return typeof ms === "number" && ms > 0 ? Math.round(ms) : null;
  } catch {
    return null;
  }
}

export function ninaVpnAddStatusListener(cb: (status: NinaVpnStatus) => void): () => void {
  const Native = getNative();
  if (!Native) return () => undefined;
  try {
    const emitter = new EventEmitter(Native as any);
    const sub = emitter.addListener("NinaVpnStatus", (e: { status?: string }) => {
      cb((e?.status || "disconnected") as NinaVpnStatus);
    });
    return () => sub.remove();
  } catch {
    return () => undefined;
  }
}
