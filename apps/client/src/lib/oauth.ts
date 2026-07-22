import * as Google from "expo-auth-session/providers/google";
import * as WebBrowser from "expo-web-browser";
import { Platform } from "react-native";
import Constants from "expo-constants";
import { API_URL } from "./api";

WebBrowser.maybeCompleteAuthSession();

const EXTRA = Constants.expoConfig?.extra as
  | { googleWebClientId?: string; telegramBotUsername?: string; tgLoginUrl?: string }
  | undefined;

export const GOOGLE_WEB_CLIENT_ID =
  process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || EXTRA?.googleWebClientId || "";

export const TELEGRAM_BOT_USERNAME =
  process.env.EXPO_PUBLIC_TELEGRAM_BOT_USERNAME || EXTRA?.telegramBotUsername || "";

export const TG_LOGIN_URL =
  process.env.EXPO_PUBLIC_TG_LOGIN_URL ||
  EXTRA?.tgLoginUrl ||
  "https://ninavpn.store/tg-login.html";

export type TelegramAuthPayload = {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
};

/** Call only when GOOGLE_WEB_CLIENT_ID is non-empty (parent must gate mount). */
export function useGoogleIdTokenAuth() {
  const [request, response, promptAsync] = Google.useIdTokenAuthRequest({
    clientId: GOOGLE_WEB_CLIENT_ID,
    webClientId: GOOGLE_WEB_CLIENT_ID,
  });

  const idToken =
    response?.type === "success"
      ? response.params.id_token || response.authentication?.idToken || null
      : null;

  return {
    ready: !!request,
    configured: !!GOOGLE_WEB_CLIENT_ID,
    response,
    idToken,
    promptAsync,
  };
}

/**
 * Open Telegram Login Widget page.
 * Web: popup + postMessage. Native: open browser and parse redirect URL.
 */
export async function openTelegramLogin(): Promise<TelegramAuthPayload> {
  if (!TELEGRAM_BOT_USERNAME) {
    throw new Error("telegram_not_configured");
  }

  const loginUrl = `${TG_LOGIN_URL}?bot=${encodeURIComponent(TELEGRAM_BOT_USERNAME)}`;

  if (Platform.OS === "web" && typeof window !== "undefined") {
    return new Promise((resolve, reject) => {
      const w = window.open(loginUrl, "tg_login", "width=480,height=640");
      if (!w) {
        reject(new Error("popup_blocked"));
        return;
      }
      const onMsg = (ev: MessageEvent) => {
        if (!ev.data || ev.data.type !== "tg-auth") return;
        window.removeEventListener("message", onMsg);
        try {
          w.close();
        } catch {
          /* ignore */
        }
        resolve(ev.data.user as TelegramAuthPayload);
      };
      window.addEventListener("message", onMsg);
      const timer = setInterval(() => {
        if (w.closed) {
          clearInterval(timer);
          window.removeEventListener("message", onMsg);
          reject(new Error("telegram_cancelled"));
        }
      }, 500);
    });
  }

  const redirect = "ninavpn://tg-auth";
  const url = `${loginUrl}&redirect=${encodeURIComponent(redirect)}`;
  const result = await WebBrowser.openAuthSessionAsync(url, redirect);
  if (result.type !== "success" || !result.url) {
    throw new Error("telegram_cancelled");
  }
  return parseTelegramFromUrl(result.url);
}

export function parseTelegramFromUrl(url: string): TelegramAuthPayload {
  const q = url.includes("?") ? url.split("?")[1] : url.split("#")[1] || "";
  const params = new URLSearchParams(q);
  const id = Number(params.get("id"));
  const hash = params.get("hash");
  const auth_date = Number(params.get("auth_date"));
  if (!id || !hash || !auth_date) {
    throw new Error("invalid_telegram_payload");
  }
  return {
    id,
    first_name: params.get("first_name") || "",
    last_name: params.get("last_name") || undefined,
    username: params.get("username") || undefined,
    photo_url: params.get("photo_url") || undefined,
    auth_date,
    hash,
  };
}

export function oauthApiBase() {
  return API_URL;
}
