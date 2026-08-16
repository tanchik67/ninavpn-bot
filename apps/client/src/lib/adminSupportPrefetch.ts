import { AppState, type AppStateStatus } from "react-native";
import { api } from "./api";
import {
  loadCachedAdminInbox,
  saveCachedAdminInbox,
  saveCachedAdminTicket,
  clearCachedAdminSupport,
  peekCachedAdminTicket,
  purgeLegacyAdminSupportCache,
  type AdminTicketRow,
  type AdminTicketChat,
} from "./adminSupportCache";
import { ninaVpnEnsureNetwork } from "./ninaVpn";

let inflightInbox: Promise<AdminTicketRow[] | null> | null = null;
let lastInboxOkAt = 0;
let loopStarted = false;
let loopTimer: ReturnType<typeof setInterval> | null = null;
let appSub: { remove: () => void } | null = null;
let warmInflight: Promise<void> | null = null;
const ticketInflight = new Map<string, Promise<AdminTicketChat | null>>();
/** While true, inbox warm/poll must not compete with staff reply POSTs. */
let sendPaused = false;

export function pauseAdminSupportPrefetch() {
  sendPaused = true;
}

export function resumeAdminSupportPrefetch() {
  sendPaused = false;
}

function ticketLooksStale(cached: AdminTicketChat, inboxRow?: AdminTicketRow | null) {
  if (!inboxRow?.last_message_at) return false;
  const cachedLast = cached.messages?.[cached.messages.length - 1];
  if (!cachedLast?.created_at) return true;
  const inboxMs = Date.parse(inboxRow.last_message_at);
  const cacheMs = Date.parse(cachedLast.created_at);
  if (!Number.isFinite(inboxMs) || !Number.isFinite(cacheMs)) return false;
  // Inbox preview is newer than last cached bubble → force network refresh
  if (inboxMs > cacheMs + 500) return true;
  // Inbox says last is staff but cache has no staff flags at all
  if (
    inboxRow.last_is_staff &&
    !(cached.messages || []).some((m) => m.is_staff)
  ) {
    return true;
  }
  return false;
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

/** Fetch + cache admin ticket list. Returns rows (or null on failure). */
export async function prefetchAdminInbox(opts?: {
  force?: boolean;
  attempts?: number;
}): Promise<AdminTicketRow[] | null> {
  if (sendPaused) return loadCachedAdminInbox();
  const force = !!opts?.force;
  const attempts = opts?.attempts ?? 3;
  await purgeLegacyAdminSupportCache();
  if (!force && Date.now() - lastInboxOkAt < 25_000) {
    return loadCachedAdminInbox();
  }
  if (inflightInbox) return inflightInbox;

  inflightInbox = (async () => {
    for (let i = 0; i < attempts; i++) {
      try {
        await ninaVpnEnsureNetwork();
        const data = await api<AdminTicketRow[]>(
          "/api/v1/support/admin/tickets",
          { timeoutMs: 12000, retries: 0 }
        );
        if (!Array.isArray(data)) continue;
        await saveCachedAdminInbox(data);
        lastInboxOkAt = Date.now();
        void warmAdminTickets(data);
        return data;
      } catch {
        await sleep(900 * (i + 1));
      }
    }
    return loadCachedAdminInbox();
  })().finally(() => {
    inflightInbox = null;
  });

  return inflightInbox;
}

/** Prefetch one ticket now (call on inbox row press before navigate). */
export async function prefetchAdminTicket(
  ticketId: string,
  opts?: { force?: boolean; inboxRow?: AdminTicketRow | null }
): Promise<AdminTicketChat | null> {
  const id = String(ticketId || "").trim();
  if (!id) return null;
  if (sendPaused) return peekCachedAdminTicket(id);
  await purgeLegacyAdminSupportCache();
  if (!opts?.force) {
    const mem = peekCachedAdminTicket(id);
    if (mem && !ticketLooksStale(mem, opts?.inboxRow)) return mem;
  }
  const existing = ticketInflight.get(id);
  if (existing) return existing;

  const p = (async () => {
    try {
      await ninaVpnEnsureNetwork();
      const chat = await api<AdminTicketChat>(
        `/api/v1/support/admin/tickets/${id}`,
        { timeoutMs: 10000, retries: 0, priority: !!opts?.force }
      );
      if (chat?.ticket?.id) {
        await saveCachedAdminTicket(chat);
        return chat;
      }
    } catch {
      /* ignore */
    }
    return peekCachedAdminTicket(id);
  })().finally(() => {
    ticketInflight.delete(id);
  });

  ticketInflight.set(id, p);
  return p;
}

/** Prefetch full threads for inbox tickets so open is instant. */
export async function warmAdminTickets(rows?: AdminTicketRow[]): Promise<void> {
  if (sendPaused) return;
  if (warmInflight) return warmInflight;
  warmInflight = (async () => {
    try {
      if (sendPaused) return;
      const list = rows || (await loadCachedAdminInbox()) || [];
      // Only warm a few waiting threads — warming every fat ticket starved opens on MIUI.
      const waiting = list.filter((r) => r.status === "open" && !r.last_is_staff);
      const rest = list.filter((r) => !waiting.some((w) => w.id === r.id));
      const targets = [...waiting, ...rest].slice(0, 3);
      for (const row of targets) {
        if (sendPaused) return;
        await prefetchAdminTicket(row.id, { force: false });
        await sleep(200);
      }
    } finally {
      warmInflight = null;
    }
  })();
  return warmInflight;
}

export function startAdminSupportPrefetchLoop() {
  if (loopStarted) {
    void prefetchAdminInbox({ force: true, attempts: 4 });
    return;
  }
  loopStarted = true;
  void prefetchAdminInbox({ force: true, attempts: 4 });

  loopTimer = setInterval(() => {
    void prefetchAdminInbox({ attempts: 2 });
  }, 45_000);

  const onApp = (state: AppStateStatus) => {
    if (state === "active") {
      void prefetchAdminInbox({ force: true, attempts: 3 });
    }
  };
  appSub = AppState.addEventListener("change", onApp);
}

export function stopAdminSupportPrefetchLoop() {
  loopStarted = false;
  if (loopTimer) {
    clearInterval(loopTimer);
    loopTimer = null;
  }
  appSub?.remove();
  appSub = null;
  lastInboxOkAt = 0;
}

export async function resetAdminSupportPrefetch() {
  stopAdminSupportPrefetchLoop();
  await clearCachedAdminSupport();
}
