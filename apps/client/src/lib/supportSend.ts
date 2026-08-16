import { manipulateAsync, SaveFormat } from "expo-image-manipulator";
import {
  API_URL,
  ensureAccessToken,
  forceRefreshAccess,
  getAccessToken,
} from "./api";
import { ninaVpnEnsureNetwork } from "./ninaVpn";
import {
  pauseSupportPrefetch,
  resumeSupportPrefetch,
} from "./supportChatPrefetch";
import {
  pauseAdminSupportPrefetch,
  resumeAdminSupportPrefetch,
} from "./adminSupportPrefetch";

export type SupportMessageResult = {
  id: string;
  body: string;
  created_at: string;
  is_staff: boolean;
  image_url?: string | null;
  client_msg_id?: string | null;
};

/** SQLite/API often returns naive UTC without Z — treat as UTC. */
export function parseServerTime(iso: string): number {
  if (!iso) return 0;
  const s = String(iso).trim();
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(s)) return new Date(s).getTime();
  return new Date(s.replace(" ", "T") + "Z").getTime();
}

export function formatMsgTime(iso: string): string {
  const ms = parseServerTime(iso);
  if (!ms) return "";
  return new Date(ms).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * MIUI: GETs before POST starve photo uploads.
 * ~3 paced POSTs work. Do not set single-JPEG cap below ~6–8k b64 —
 * real screenshots often exceed 3.5k even at 200px (caused image_compress_failed).
 */
const TEXT_PART = 4000;
const GAP_MS = 400;
const PHOTO_SINGLE_MAX = 7500;
const PHOTO_CHUNK = 2500;
const PHOTO_CHUNK_MAX = PHOTO_CHUNK * 3; // ~7.5k
const PHOTO_MIME = "image/jpeg";

let sendingLock = false;

export function isSupportSendInFlight() {
  return sendingLock;
}

/** Call when UI hard-times-out a hung send so GETs/reconcile can run again. */
export function forceUnlockSupportSend() {
  sendingLock = false;
  resumeSupportPrefetch();
  resumeAdminSupportPrefetch();
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function splitText(text: string, size: number): string[] {
  if (text.length <= size) return [text];
  const parts: string[] = [];
  let i = 0;
  while (i < text.length) {
    let end = Math.min(i + size, text.length);
    if (end < text.length) {
      const slice = text.slice(i, end);
      const sp = Math.max(slice.lastIndexOf(" "), slice.lastIndexOf("\n"));
      if (sp > size * 0.4) end = i + sp + 1;
    }
    parts.push(text.slice(i, end).trimEnd());
    i = end;
    while (i < text.length && (text[i] === " " || text[i] === "\n")) i += 1;
  }
  return parts.filter(Boolean);
}

/**
 * XHR with a real wall-clock deadline. On this Xiaomi, xhr.timeout / fetch abort
 * sometimes never fire — the UI then stays on spinner forever.
 */
function xhrJson<T>(opts: {
  method: string;
  path: string;
  token: string;
  body?: string;
  timeoutMs: number;
}): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    let settled = false;
    const done = (fn: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(hardTimer);
      fn();
    };
    const hardTimer = setTimeout(() => {
      try {
        xhr.abort();
      } catch {
        /* ignore */
      }
      done(() => reject(new Error("network_timeout")));
    }, Math.max(2000, opts.timeoutMs + 1000));

    xhr.open(opts.method, `${API_URL}${opts.path}`);
    xhr.timeout = opts.timeoutMs;
    xhr.setRequestHeader("Authorization", `Bearer ${opts.token}`);
    if (opts.body != null) {
      xhr.setRequestHeader("Content-Type", "application/json");
    }
    xhr.onload = () => {
      done(() => {
        if (xhr.status === 401) {
          reject(new Error("not_authenticated"));
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          reject(new Error(xhr.responseText || `HTTP ${xhr.status}`));
          return;
        }
        // MIUI: HTTP 200 with empty body after the server already saved the row
        if (!xhr.responseText) {
          if (opts.method === "POST") {
            reject(new Error("ack_needed"));
            return;
          }
          resolve(undefined as T);
          return;
        }
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          if (opts.method === "POST") {
            reject(new Error("ack_needed"));
            return;
          }
          reject(new Error("bad_response"));
        }
      });
    };
    xhr.ontimeout = () => done(() => reject(new Error("network_timeout")));
    xhr.onerror = () => done(() => reject(new Error("network_error")));
    xhr.onabort = () => done(() => reject(new Error("network_timeout")));
    try {
      xhr.send(opts.body ?? null);
    } catch {
      done(() => reject(new Error("network_error")));
    }
  });
}

export async function sendSupportMessage(opts: {
  ticketId: string;
  body: string;
  imageUri?: string | null;
  staff?: boolean;
  clientMsgId: string;
  timeoutMs?: number;
}): Promise<SupportMessageResult> {
  const hasImage = !!opts.imageUri;
  const staff = !!opts.staff;
  pauseSupportPrefetch();
  if (staff) pauseAdminSupportPrefetch();
  sendingLock = true;
  try {
    await ninaVpnEnsureNetwork();

    const textPath = staff
      ? `/api/v1/support/admin/tickets/${opts.ticketId}/messages`
      : `/api/v1/support/tickets/${opts.ticketId}/messages`;
    const text = (opts.body || "").trim();

    if (hasImage && opts.imageUri) {
      return await sendPhotoReliable({
        ticketId: opts.ticketId,
        imageUri: opts.imageUri,
        caption: text || "Фото",
        clientMsgId: opts.clientMsgId,
        staff,
        textPath,
      });
    }

    if (staff) {
      // Hard wall clock — never leave admin UI on "…" for minutes
      return await Promise.race([
        sendStaffText({
          path: textPath,
          text,
          clientMsgId: opts.clientMsgId,
          ticketId: opts.ticketId,
        }),
        sleep(14000).then(() => {
          throw new Error("network_timeout");
        }),
      ]);
    }

    return await Promise.race([
      sendTextPaced({
        path: textPath,
        text,
        clientMsgId: opts.clientMsgId,
        ticketId: opts.ticketId,
        staff: false,
      }),
      sleep(15000).then(() => {
        throw new Error("network_timeout");
      }),
    ]);
  } finally {
    sendingLock = false;
    resumeSupportPrefetch();
    if (staff) resumeAdminSupportPrefetch();
  }
}

/**
 * Staff replies MUST bypass the shared fetch gate. On MIUI, hung admin GETs
 * (inbox/chat warm) hold both slots and `api({priority})` still waits forever
 * while the bubble shows "…".
 */
async function sendStaffText(opts: {
  path: string;
  text: string;
  clientMsgId: string;
  ticketId: string;
}): Promise<SupportMessageResult> {
  const parts = splitText(opts.text, TEXT_PART);
  let last: SupportMessageResult | null = null;
  for (let i = 0; i < parts.length; i++) {
    const body =
      parts.length > 1 ? `${parts[i]}\n\n…(${i + 1}/${parts.length})` : parts[i];
    const cid =
      parts.length > 1 ? `${opts.clientMsgId}-${i}` : opts.clientMsgId;

    // Prefer cached access token — avoid any gated work before the POST leaves.
    let token = (await getAccessToken()) || (await ensureAccessToken());
    if (!token) throw new Error("not_authenticated");

    const postOnce = async (_access: string) =>
      postJson<SupportMessageResult>({
        path: opts.path,
        body: { body, client_msg_id: cid },
        timeoutMs: 10000,
      });

    try {
      try {
        last = await postOnce(token);
      } catch (e: unknown) {
        if (String((e as Error)?.message) === "not_authenticated") {
          const next = await forceRefreshAccess();
          if (!next) throw new Error("not_authenticated");
          token = next;
          last = await postOnce(next);
        } else {
          throw e;
        }
      }
    } catch (e: unknown) {
      const msg = String((e as Error)?.message || "");
      if (
        msg === "ack_needed" ||
        msg === "network_error" ||
        msg === "network_timeout" ||
        msg === "send_failed" ||
        /timeout|network/i.test(msg)
      ) {
        // One immediate retry after a short quiet window (MIUI)
        await sleep(500);
        try {
          const tok2 =
            (await getAccessToken()) || (await ensureAccessToken()) || token;
          last = await postOnce(tok2);
        } catch {
          const hit = await ackByClientId(opts.ticketId, cid, 2, true);
          if (hit) last = hit;
          else throw e instanceof Error ? e : new Error(String(e));
        }
      } else {
        throw e instanceof Error ? e : new Error(String(e));
      }
    }
    if (!last?.id) {
      const hit = await ackByClientId(opts.ticketId, cid, 2, true);
      if (hit) last = hit;
    }
    if (!last?.id) throw new Error("send_failed");
    if (i < parts.length - 1) await sleep(GAP_MS);
  }
  if (!last) throw new Error("send_failed");
  return last;
}

async function sendTextPaced(opts: {
  path: string;
  text: string;
  clientMsgId: string;
  ticketId: string;
  staff: boolean;
}): Promise<SupportMessageResult> {
  const parts = splitText(opts.text, TEXT_PART);
  let last: SupportMessageResult | null = null;
  for (let i = 0; i < parts.length; i++) {
    const body =
      parts.length > 1 ? `${parts[i]}\n\n…(${i + 1}/${parts.length})` : parts[i];
    const cid =
      parts.length > 1 ? `${opts.clientMsgId}-${i}` : opts.clientMsgId;
    try {
        last = await postJsonWithRetry({
          path: opts.path,
          body: { body, client_msg_id: cid },
          timeoutMs: 8000,
          retries: 1,
        });
      } catch (e: unknown) {
        const msg = String((e as Error)?.message || "");
        if (
          msg === "ack_needed" ||
          msg === "network_error" ||
          msg === "network_timeout" ||
          msg === "send_failed"
        ) {
          last = deliveredStub(cid, body, opts.staff);
          void ackByClientId(opts.ticketId, cid, 3, opts.staff);
        } else {
          throw e instanceof Error ? e : new Error(String(e));
        }
      }
    if (!last?.id) throw new Error("send_failed");
    if (i < parts.length - 1) await sleep(GAP_MS);
  }
  if (!last) throw new Error("send_failed");
  return last;
}

function deliveredStub(
  cid: string,
  body: string,
  staff: boolean
): SupportMessageResult {
  return {
    id: `sent-${cid.replace(/^local-/, "")}`.slice(0, 64),
    body,
    created_at: new Date().toISOString(),
    is_staff: staff,
    client_msg_id: cid,
  };
}

function isMessageResult(v: unknown): v is SupportMessageResult {
  if (!v || typeof v !== "object") return false;
  if ("ok" in v && !("body" in v)) return false;
  return !!(v as SupportMessageResult).id;
}

async function sendPhotoReliable(opts: {
  ticketId: string;
  imageUri: string;
  caption: string;
  clientMsgId: string;
  staff: boolean;
  textPath: string;
}): Promise<SupportMessageResult> {
  const cid = opts.clientMsgId;

  // Pack once — never fail the user with image_compress_failed for a normal screenshot
  const packed = await packPhotoBase64(opts.imageUri, PHOTO_SINGLE_MAX, 640, 0.55);

  // Primary: /messages (same path as working text)
  try {
    const msg = await postJsonWithRetry<SupportMessageResult>({
      path: opts.textPath,
      body: {
        body: opts.caption,
        image_base64: packed.b64,
        image_mime: packed.mime,
        client_msg_id: cid,
      },
      timeoutMs: 15000,
      retries: 3,
    });
    if (msg?.id) return msg;
  } catch (e: unknown) {
    const msg = String((e as Error)?.message || "");
    if (msg === "ack_needed" || msg === "network_error" || msg === "network_timeout") {
      const hit = await ackByClientId(opts.ticketId, cid, 5, opts.staff);
      if (hit?.image_url || hit?.id) return hit;
    }
    /* chunked backup */
  }

  if (opts.staff) throw new Error("send_failed");

  await sleep(800);

  // Backup: 3 paced chunks, same client_msg_id (idempotent on server)
  const total = Math.max(1, Math.ceil(packed.b64.length / PHOTO_CHUNK));
  const chunkPath = `/api/v1/support/tickets/${opts.ticketId}/photo-chunk`;

  for (let index = 0; index < total; index++) {
    const data = packed.b64.slice(index * PHOTO_CHUNK, (index + 1) * PHOTO_CHUNK);
    try {
      const last = await postJsonWithRetry<
        SupportMessageResult | { ok?: boolean; received?: number; total?: number }
      >({
        path: chunkPath,
        body: {
          client_msg_id: cid,
          index,
          total,
          data,
          body: index === 0 ? opts.caption : "",
          image_mime: packed.mime,
        },
        timeoutMs: 12000,
        retries: 2,
      });
      if (isMessageResult(last)) return last;
    } catch {
      break;
    }
    if (index < total - 1) await sleep(900);
  }

  const hit = await ackByClientId(opts.ticketId, cid, 4, false);
  if (hit) return hit;
  throw new Error("send_failed");
}

async function ackByClientId(
  ticketId: string,
  clientMsgId: string,
  attempts: number,
  staff = false
): Promise<SupportMessageResult | null> {
  for (let i = 0; i < attempts; i++) {
    await sleep(i === 0 ? 350 : 650);
    const hit = await lookupByClientIdRaw({ ticketId, clientMsgId, staff });
    if (hit?.id) return hit;
  }
  return null;
}

async function postJsonWithRetry<T = SupportMessageResult>(opts: {
  path: string;
  body: unknown;
  timeoutMs: number;
  retries: number;
}): Promise<T> {
  let lastErr: Error | null = null;
  for (let i = 0; i <= opts.retries; i++) {
    try {
      return await postJson<T>({
        path: opts.path,
        body: opts.body,
        timeoutMs: opts.timeoutMs,
      });
    } catch (e: unknown) {
      lastErr = e instanceof Error ? e : new Error(String(e));
      await ninaVpnEnsureNetwork();
      await sleep(450 + i * 350);
    }
  }
  throw lastErr || new Error("send_failed");
}

async function postJson<T = SupportMessageResult>(opts: {
  path: string;
  body: unknown;
  timeoutMs: number;
}): Promise<T> {
  let token = (await getAccessToken()) || (await ensureAccessToken());
  if (!token) throw new Error("not_authenticated");

  const once = async (access: string, refreshed: boolean): Promise<T> => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), Math.max(3000, opts.timeoutMs));
    try {
      const res = await fetch(`${API_URL}${opts.path}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${access}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(opts.body),
        signal: ctrl.signal,
      });
      if (res.status === 401) {
        if (refreshed) throw new Error("not_authenticated");
        const next = await forceRefreshAccess();
        if (!next) throw new Error("not_authenticated");
        return once(next, true);
      }
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const raw = await res.text();
      if (!raw) throw new Error("ack_needed");
      try {
        return JSON.parse(raw) as T;
      } catch {
        throw new Error("ack_needed");
      }
    } catch (e: unknown) {
      const msg = String((e as Error)?.message || e || "");
      if (msg === "not_authenticated" || msg === "ack_needed") throw e;
      if (/abort/i.test(msg)) throw new Error("network_timeout");
      if (/load failed|failed to fetch|networkerror/i.test(msg)) {
        throw new Error("network_error");
      }
      throw e instanceof Error ? e : new Error(msg || "network_error");
    } finally {
      clearTimeout(timer);
    }
  };

  try {
    return await once(token, false);
  } catch (e: unknown) {
    const msg = String((e as Error)?.message || "");
    if (msg !== "network_timeout" && msg !== "network_error") throw e;
    throw e instanceof Error ? e : new Error(msg);
  }
}

type PackedPhoto = { b64: string; mime: string };

/**
 * Encode JPEG ≤ maxB64 via manipulateAsync base64 (no FileSystem —
 * EncodingType/read path was throwing on this device → false "compress failed").
 */
async function packPhotoBase64(
  uri: string,
  maxB64: number,
  startWidth: number,
  startQuality: number
): Promise<PackedPhoto> {
  let width = startWidth;
  let quality = startQuality;
  let last = "";
  const hardMax = Math.max(maxB64, PHOTO_CHUNK_MAX);

  for (let i = 0; i < 18; i++) {
    try {
      const out = await manipulateAsync(
        uri,
        [{ resize: { width: Math.max(160, width) } }],
        {
          compress: Math.max(0.12, quality),
          format: SaveFormat.JPEG,
          base64: true,
        }
      );
      last = out.base64 || "";
      if (last && last.length <= maxB64) {
        return { b64: last, mime: PHOTO_MIME };
      }
    } catch {
      /* shrink further */
    }
    width = Math.max(160, Math.floor(width * 0.72));
    quality = Math.max(0.12, quality - 0.04);
  }

  // Accept anything under hardMax for chunked upload rather than failing the user
  if (last && last.length <= hardMax) {
    return { b64: last, mime: PHOTO_MIME };
  }

  try {
    const out = await manipulateAsync(
      uri,
      [{ resize: { width: 160 } }],
      { compress: 0.1, format: SaveFormat.JPEG, base64: true }
    );
    last = out.base64 || last;
  } catch {
    /* ignore */
  }
  if (!last) throw new Error("image_compress_failed");
  if (last.length > hardMax) {
    const out = await manipulateAsync(
      uri,
      [{ resize: { width: 120 } }],
      { compress: 0.08, format: SaveFormat.JPEG, base64: true }
    );
    last = out.base64 || last;
  }
  if (!last) throw new Error("image_compress_failed");
  return { b64: last, mime: PHOTO_MIME };
}

async function lookupByClientIdRaw(opts: {
  ticketId: string;
  clientMsgId: string;
  staff?: boolean;
}): Promise<SupportMessageResult | null> {
  try {
    let token = await ensureAccessToken();
    if (!token) return null;
    const path = opts.staff
      ? `/api/v1/support/admin/tickets/${opts.ticketId}/messages`
      : `/api/v1/support/tickets/${opts.ticketId}/messages/by-client/${encodeURIComponent(opts.clientMsgId)}`;

    const once = async (access: string) =>
      xhrJson<SupportMessageResult | SupportMessageResult[]>({
        method: "GET",
        path,
        token: access,
        timeoutMs: 4000,
      });

    try {
      const data = await once(token);
      if (opts.staff && Array.isArray(data)) {
        return (
          data.find((m) => m.client_msg_id === opts.clientMsgId) || null
        );
      }
      return data as SupportMessageResult;
    } catch (e: unknown) {
      if (String((e as Error)?.message) !== "not_authenticated") return null;
      const next = await forceRefreshAccess();
      if (!next) return null;
      const data = await once(next);
      if (opts.staff && Array.isArray(data)) {
        return (
          data.find((m) => m.client_msg_id === opts.clientMsgId) || null
        );
      }
      return data as SupportMessageResult;
    }
  } catch {
    return null;
  }
}

export async function lookupByClientId(opts: {
  ticketId: string;
  clientMsgId: string;
  staff?: boolean;
}): Promise<SupportMessageResult | null> {
  return lookupByClientIdRaw(opts);
}

export async function waitForSupportMessage(opts: {
  ticketId: string;
  body: string;
  clientMsgId?: string;
  hasImage?: boolean;
  staff?: boolean;
  attempts?: number;
  delayMs?: number;
}): Promise<SupportMessageResult | null> {
  if (!opts.clientMsgId) return null;
  const attempts = opts.hasImage ? Math.max(opts.attempts ?? 3, 3) : opts.attempts ?? 2;
  const delayMs = opts.delayMs ?? 700;
  for (let i = 0; i < attempts; i++) {
    if (i > 0) await sleep(delayMs);
    const ids = opts.hasImage
      ? [opts.clientMsgId]
      : [opts.clientMsgId, `${opts.clientMsgId}-0`, `${opts.clientMsgId}-1`];
    for (const cid of ids) {
      const hit = await lookupByClientId({
        ticketId: opts.ticketId,
        clientMsgId: cid,
        staff: opts.staff,
      });
      if (!hit?.id) continue;
      if (opts.hasImage && !hit.image_url) continue;
      return hit;
    }
  }
  return null;
}
