/** Measure RTT from the phone to a VPN node (native TCP, XHR fallback). */

import { ninaVpnTcpPingMs } from "./ninaVpn";

export function hostPortFromUri(uri?: string | null): { host: string; port: number } | null {
  const raw = String(uri || "").trim();
  if (!raw || !raw.includes("://")) return null;
  try {
    const rest = raw.split("://", 2)[1] || "";
    const authority = rest.split("?", 1)[0].split("#", 1)[0];
    const hostPort = authority.includes("@") ? authority.split("@").pop() || "" : authority;
    const m = hostPort.match(/^\[([^\]]+)\]:(\d+)$/); // IPv6
    if (m) return { host: m[1], port: Number(m[2]) };
    const lastColon = hostPort.lastIndexOf(":");
    if (lastColon <= 0) return null;
    const host = hostPort.slice(0, lastColon).replace(/^\[|\]$/g, "");
    const port = Number(hostPort.slice(lastColon + 1));
    if (!host || !Number.isFinite(port) || port <= 0) return null;
    return { host, port };
  } catch {
    return null;
  }
}

function pingOnce(url: string, timeoutMs: number): Promise<number | null> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    let settled = false;
    const done = (ms: number | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(hard);
      resolve(ms);
    };
    const t0 = Date.now();
    const hard = setTimeout(() => {
      try {
        xhr.abort();
      } catch {
        /* ignore */
      }
      done(null);
    }, timeoutMs);
    try {
      xhr.open("GET", url);
      xhr.timeout = timeoutMs;
      const finish = () => done(Date.now() - t0);
      xhr.onload = finish;
      xhr.onerror = finish;
      xhr.ontimeout = () => done(null);
      xhr.onabort = () => done(null);
      xhr.send();
    } catch {
      done(null);
    }
  });
}

/** TCP RTT to host:port. Native socket on Android; XHR handshake elsewhere. */
export async function pingHostPort(
  host: string,
  port: number,
  timeoutMs = 2500
): Promise<number | null> {
  const native = await ninaVpnTcpPingMs(host, port, timeoutMs);
  if (native != null) return native;
  const enc = host.includes(":") ? `[${host}]` : host;
  // Prefer https on 443/8443, otherwise http — we only need the connect RTT.
  const scheme = port === 443 || port === 8443 ? "https" : "http";
  const ms = await pingOnce(`${scheme}://${enc}:${port}/`, timeoutMs);
  if (ms == null) return null;
  return Math.max(1, Math.round(ms));
}

export async function pingServerUri(uri?: string | null): Promise<number | null> {
  const hp = hostPortFromUri(uri);
  if (!hp) return null;
  return pingHostPort(hp.host, hp.port);
}
