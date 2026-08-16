import {
  loadOutbox,
  markOutboxAttempt,
  removeOutbox,
  type SupportOutboxItem,
} from "./supportOutbox";
import {
  isSupportSendInFlight,
  sendSupportMessage,
  waitForSupportMessage,
} from "./supportSend";

/**
 * Push stuck outbox rows to the server. Staff replies were dying because
 * retries only ran inside an open staff chat and waited on long backoffs.
 */
export async function flushSupportOutbox(opts?: {
  staffOnly?: boolean;
  ticketId?: string;
  ignoreSchedule?: boolean;
}): Promise<number> {
  if (isSupportSendInFlight()) return 0;
  const staffOnly = !!opts?.staffOnly;
  const ticketId = opts?.ticketId ? String(opts.ticketId) : "";
  const ignoreSchedule = !!opts?.ignoreSchedule;
  const now = Date.now();
  const box = (await loadOutbox()).filter((item) => {
    if (staffOnly && !item.staff) return false;
    if (!staffOnly && item.staff) return false;
    if (ticketId && item.ticketId !== ticketId) return false;
    if (item.imageUri) return false;
    if (!ignoreSchedule && item.nextAttemptAt > now) return false;
    return true;
  });
  if (!box.length) return 0;

  let ok = 0;
  for (const item of box) {
    if (isSupportSendInFlight()) break;
    try {
      const found = await waitForSupportMessage({
        ticketId: item.ticketId,
        body: item.body,
        clientMsgId: item.id,
        hasImage: false,
        staff: !!item.staff,
        attempts: 1,
        delayMs: 0,
      });
      if (found?.id) {
        await removeOutbox(item.id);
        ok += 1;
        continue;
      }
      await sendSupportMessage({
        ticketId: item.ticketId,
        body: item.body,
        clientMsgId: item.id,
        staff: !!item.staff,
        timeoutMs: 12000,
      });
      await removeOutbox(item.id);
      ok += 1;
    } catch {
      await markOutboxAttempt(item.id, true);
    }
  }
  return ok;
}

export async function pendingOutboxForTicket(
  ticketId: string,
  staff: boolean
): Promise<SupportOutboxItem[]> {
  const id = String(ticketId || "").trim();
  if (!id) return [];
  return (await loadOutbox()).filter(
    (item) =>
      item.ticketId === id &&
      !!item.staff === staff &&
      !item.imageUri
  );
}
