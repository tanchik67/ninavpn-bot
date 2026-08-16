import AsyncStorage from "@react-native-async-storage/async-storage";

const INBOX_KEY = "nv_admin_inbox_v2";
const TICKET_PREFIX = "nv_admin_ticket_v2:";
/** Drop poisoned v1 caches (is_staff always false / truncated threads). */
const LEGACY_KEYS = ["nv_admin_inbox_v1", "nv_admin_ticket_v1:"];

export type AdminTicketRow = {
  id: string;
  subject: string;
  status: string;
  user_email: string;
  last_message: string | null;
  last_message_at: string | null;
  last_is_staff: boolean;
  created_at: string;
};

export type AdminTicketChat = {
  ticket: { id: string; status: string };
  messages: Array<{
    id: string;
    body: string;
    created_at: string;
    is_staff: boolean;
    image_url?: string | null;
    client_msg_id?: string | null;
  }>;
  user_email?: string;
};

/** Sync memory layer — open chat without waiting on AsyncStorage. */
const memInbox: { rows: AdminTicketRow[] | null } = { rows: null };
const memTickets = new Map<string, AdminTicketChat>();

export function peekCachedAdminInbox(): AdminTicketRow[] | null {
  return memInbox.rows;
}

export function peekCachedAdminTicket(ticketId: string): AdminTicketChat | null {
  return memTickets.get(ticketId) || null;
}

export async function loadCachedAdminInbox(): Promise<AdminTicketRow[] | null> {
  if (memInbox.rows) return memInbox.rows;
  try {
    const raw = await AsyncStorage.getItem(INBOX_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AdminTicketRow[];
    if (!Array.isArray(parsed)) return null;
    memInbox.rows = parsed;
    return parsed;
  } catch {
    return null;
  }
}

export async function saveCachedAdminInbox(rows: AdminTicketRow[]): Promise<void> {
  memInbox.rows = rows || [];
  try {
    await AsyncStorage.setItem(INBOX_KEY, JSON.stringify(rows || []));
  } catch {
    /* ignore */
  }
}

export async function loadCachedAdminTicket(
  ticketId: string
): Promise<AdminTicketChat | null> {
  const id = String(ticketId || "").trim();
  if (!id) return null;
  const hit = memTickets.get(id);
  if (hit) return hit;
  try {
    const raw = await AsyncStorage.getItem(TICKET_PREFIX + id);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AdminTicketChat;
    if (!parsed?.ticket?.id || !Array.isArray(parsed.messages)) return null;
    parsed.messages = parsed.messages.filter(
      (m) => !String(m.id || "").startsWith("local-")
    );
    memTickets.set(id, parsed);
    return parsed;
  } catch {
    return null;
  }
}

export async function saveCachedAdminTicket(chat: AdminTicketChat): Promise<void> {
  const id = String(chat?.ticket?.id || "").trim();
  if (!id) return;
  const safe: AdminTicketChat = {
    ...chat,
    messages: (chat.messages || []).filter(
      (m) => !String(m.id || "").startsWith("local-")
    ),
  };
  memTickets.set(id, safe);
  try {
    await AsyncStorage.setItem(TICKET_PREFIX + id, JSON.stringify(safe));
  } catch {
    /* ignore */
  }
}

export async function clearCachedAdminSupport(): Promise<void> {
  memInbox.rows = null;
  memTickets.clear();
  try {
    const keys = await AsyncStorage.getAllKeys();
    const drop = keys.filter(
      (k) =>
        k === INBOX_KEY ||
        k.startsWith(TICKET_PREFIX) ||
        k === LEGACY_KEYS[0] ||
        k.startsWith(LEGACY_KEYS[1])
    );
    if (drop.length) await AsyncStorage.multiRemove(drop);
  } catch {
    /* ignore */
  }
}

/** One-shot wipe of bad v1 admin chat caches. */
let legacyCleared = false;
export async function purgeLegacyAdminSupportCache(): Promise<void> {
  if (legacyCleared) return;
  legacyCleared = true;
  try {
    const keys = await AsyncStorage.getAllKeys();
    const drop = keys.filter(
      (k) => k === LEGACY_KEYS[0] || k.startsWith(LEGACY_KEYS[1])
    );
    if (drop.length) await AsyncStorage.multiRemove(drop);
  } catch {
    /* ignore */
  }
}
