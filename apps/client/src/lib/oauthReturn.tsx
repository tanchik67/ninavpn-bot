import { router, useGlobalSearchParams, usePathname } from "expo-router";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { useEffect, useRef } from "react";
import { BrandSplash } from "../components/BrandSplash";
import { useAuth } from "./auth";
import {
  parseGoogleIdTokenFromUrl,
  parseTelegramFromUrl,
} from "./oauth";

function dismissAuthBrowser() {
  try {
    WebBrowser.dismissBrowser();
  } catch {
    /* already closed */
  }
  try {
    WebBrowser.maybeCompleteAuthSession();
  } catch {
    /* ignore */
  }
}

function firstParam(v: unknown): string {
  if (typeof v === "string") return v;
  if (Array.isArray(v) && typeof v[0] === "string") return v[0];
  return "";
}

function looksGoogle(hay: string) {
  return /google-auth/i.test(hay) || /id_token=/i.test(hay);
}

function looksTelegram(hay: string) {
  return /tg-auth/i.test(hay);
}

/**
 * Completes Google / Telegram OAuth when the OS opens the app via deep link
 * instead of returning into WebBrowser.openAuthSessionAsync (common on MIUI).
 */
export function OAuthReturnScreen({
  kind,
}: {
  kind: "google" | "telegram" | "auto";
}) {
  const { loginWithGoogle, loginWithTelegram, user, loading } = useAuth();
  const params = useGlobalSearchParams();
  const pathname = usePathname() || "";
  const incomingUrl = Linking.useURL();
  const ran = useRef(false);

  useEffect(() => {
    dismissAuthBrowser();
  }, []);

  useEffect(() => {
    if (loading) return;
    if (user) {
      router.replace("/(app)/(tabs)/home");
      return;
    }
    if (ran.current) return;

    const hay = `${pathname}\n${incomingUrl || ""}\n${JSON.stringify(params)}`;
    const mode =
      kind === "auto"
        ? looksTelegram(hay)
          ? "telegram"
          : looksGoogle(hay)
            ? "google"
            : null
        : kind;
    if (!mode) {
      ran.current = true;
      router.replace("/");
      return;
    }

    const run = async () => {
      const urls = [incomingUrl, await Linking.getInitialURL()].filter(
        (u): u is string => !!u
      );
      try {
        if (mode === "google") {
          let token = firstParam(params.id_token);
          if (!token) {
            for (const u of urls) {
              try {
                token = parseGoogleIdTokenFromUrl(u);
                if (token) break;
              } catch {
                /* try next */
              }
            }
          }
          if (!token) {
            ran.current = true;
            router.replace("/(auth)/login");
            return;
          }
          ran.current = true;
          await loginWithGoogle(token);
        } else {
          let payload = null as ReturnType<typeof parseTelegramFromUrl> | null;
          const id = firstParam(params.id);
          const hash = firstParam(params.hash);
          if (id && hash) {
            try {
              payload = parseTelegramFromUrl(
                `ninavpn://tg-auth?${new URLSearchParams(
                  Object.fromEntries(
                    Object.entries(params).map(([k, v]) => [k, firstParam(v)])
                  )
                ).toString()}`
              );
            } catch {
              payload = null;
            }
          }
          if (!payload) {
            for (const u of urls) {
              try {
                payload = parseTelegramFromUrl(u);
                if (payload) break;
              } catch {
                /* try next */
              }
            }
          }
          if (!payload) {
            ran.current = true;
            router.replace("/(auth)/login");
            return;
          }
          ran.current = true;
          await loginWithTelegram(payload);
        }
        router.replace("/(app)/(tabs)/home");
      } catch {
        ran.current = false;
        router.replace("/(auth)/login");
      }
    };
    void run();
  }, [
    loading,
    user,
    kind,
    pathname,
    incomingUrl,
    params,
    loginWithGoogle,
    loginWithTelegram,
  ]);

  return <BrandSplash />;
}
