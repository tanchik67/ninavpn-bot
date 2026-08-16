import { AppState, type AppStateStatus } from "react-native";
import { api } from "./api";
import { ninaVpnEnsureNetwork } from "./ninaVpn";
import {
  clearCachedSupportChat,
  saveCachedSupportChat,
  type CachedSupportChat,
} from "./supportChatCache";

type Chat = CachedSupportChat;

let inflight: Promise<boolean> | null = null;
let lastOkAt = 0;
let loopStarted = false;
let loopTimer: ReturnType<typeof setInterval> | null = null;
let appSub: { remove: () => void } | null = null;
/** While true, prefetch/poll must not compete with message send POSTs. */
let sendPaused = false;
let prefetchAbort: AbortController | null = null;

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export function pauseSupportPrefetch() {
  sendPaused = true;
  prefetchAbort?.abort();
  prefetchAbort = null;
}

export function resumeSupportPrefetch() {
  sendPaused = false;
}

export function isSupportPrefetchPaused() {
  return sendPaused;
}

/**
 * Warm support chat cache in the background so opening Поддержка is instant.
 */
export async function prefetchSupportChat(opts?: {
  force?: boolean;
  attempts?: number;
}): Promise<boolean> {
  if (sendPaused) return false;
  const force = !!opts?.force;
  const attempts = opts?.attempts ?? 3;
  if (!force && Date.now() - lastOkAt < 40_000) return true;
  if (inflight) return inflight;

  inflight = (async () => {
    for (let i = 0; i < attempts; i++) {
      if (sendPaused) return false;
      const ctrl = new AbortController();
      prefetchAbort = ctrl;
      try {
        await ninaVpnEnsureNetwork();
        if (sendPaused) return false;
        const data = await api<Chat>("/api/v1/support/chat", {
          timeoutMs: 8000,
          retries: 0,
          signal: ctrl.signal,
        });
        if (!data?.ticket?.id) continue;
        await saveCachedSupportChat(data);
        lastOkAt = Date.now();
        return true;
      } catch {
        if (sendPaused) return false;
        await sleep(1500 * (i + 1));
      } finally {
        if (prefetchAbort === ctrl) prefetchAbort = null;
      }
    }
    return false;
  })().finally(() => {
    inflight = null;
  });

  return inflight;
}

export function startSupportChatPrefetchLoop() {
  if (loopStarted) {
    void prefetchSupportChat({ force: true, attempts: 4 });
    return;
  }
  loopStarted = true;
  void prefetchSupportChat({ force: true, attempts: 4 });

  loopTimer = setInterval(() => {
    if (!sendPaused) void prefetchSupportChat({ attempts: 2 });
  }, 90_000);

  const onApp = (state: AppStateStatus) => {
    if (state === "active" && !sendPaused) {
      void prefetchSupportChat({ force: true, attempts: 3 });
    }
  };
  appSub = AppState.addEventListener("change", onApp);
}

export function stopSupportChatPrefetchLoop() {
  loopStarted = false;
  if (loopTimer) {
    clearInterval(loopTimer);
    loopTimer = null;
  }
  appSub?.remove();
  appSub = null;
  lastOkAt = 0;
  sendPaused = false;
  prefetchAbort?.abort();
  prefetchAbort = null;
}

export async function resetSupportChatPrefetch() {
  stopSupportChatPrefetchLoop();
  await clearCachedSupportChat();
}
