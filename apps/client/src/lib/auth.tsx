import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { router } from "expo-router";
import * as Linking from "expo-linking";
import {
  api,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  hasSessionTokens,
  saveTokens,
  Tokens,
} from "./api";
import type { TelegramAuthPayload } from "./oauth";
import { parseGoogleIdTokenFromUrl, parseTelegramFromUrl } from "./oauth";
import { loadLocalProfileEmoji, saveLocalProfileEmoji } from "./profileEmojiStorage";
import { ninaVpnClearSession } from "./ninaVpn";
import { clearHomeCaches } from "./serverCache";
import { bindVpnPrefsUser } from "./vpnPrefs";
import { setSessionUserId } from "./sessionUser";
import {
  clearCachedUser,
  loadCachedUser,
  saveCachedUser,
  type CachedUser,
} from "./sessionCache";
import { clearCachedSubscription } from "./subscriptionCache";
import {
  prefetchSupportChat,
  resetSupportChatPrefetch,
} from "./supportChatPrefetch";

let googleLockToken: string | null = null;
let telegramLockHash: string | null = null;

type User = CachedUser;

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  loginWithTelegram: (payload: TelegramAuthPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  patchUser: (partial: Partial<User>) => void;
};

const Ctx = createContext<AuthCtx | null>(null);

function isAuthFailure(msg: string): boolean {
  return (
    msg === "not_authenticated" ||
    /invalid_refresh|unauthorized|not authenticated|banned/i.test(msg)
  );
}

function isTransient(msg: string): boolean {
  return /network_timeout|network_error|timeout/i.test(msg);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const applyUser = useCallback(async (me: User) => {
    const localEmoji = await loadLocalProfileEmoji(me.id);
    const next = {
      ...me,
      profile_emoji: me.profile_emoji ?? localEmoji ?? null,
    };
    setUser(next);
    setSessionUserId(next.id);
    void saveCachedUser(next);
    void bindVpnPrefsUser(next.id);
  }, []);

  const refreshMe = useCallback(async () => {
    const access = await getAccessToken();
    const refresh = await getRefreshToken();
    if (!access && !refresh) {
      setUser(null);
      return;
    }
    try {
      const me = await api<User>("/api/v1/auth/me", { timeoutMs: 10000, retries: 1 });
      await applyUser(me);
      // Kick off support warm-up right after session is confirmed
      if (me.role === "admin" || me.role === "support") {
        const { prefetchAdminInbox } = await import("./adminSupportPrefetch");
        void prefetchAdminInbox({ force: true, attempts: 2 });
      } else {
        void prefetchSupportChat({ force: true, attempts: 3 });
      }
    } catch (e: any) {
      const msg = String(e?.message || "");
      if (isAuthFailure(msg)) {
        await clearTokens();
        await clearCachedUser();
        setSessionUserId(null);
        void bindVpnPrefsUser(null);
        void ninaVpnClearSession();
        setUser(null);
        return;
      }
      if (isTransient(msg)) {
        // Keep session on flaky network — restore cache if memory is empty
        const cached = await loadCachedUser();
        if (cached && (await hasSessionTokens())) {
          await applyUser(cached);
        }
        return;
      }
      throw e;
    }
  }, [applyUser]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [tokensOk, cached] = await Promise.all([
          hasSessionTokens(),
          loadCachedUser(),
        ]);
        if (!alive) return;

        // Instant restore — never send a logged-in user to welcome on cold start
        if (tokensOk && cached) {
          setSessionUserId(cached.id);
          void bindVpnPrefsUser(cached.id);
          setUser(cached);
          setLoading(false);
          void refreshMe().catch(() => undefined);
          return;
        }

        if (tokensOk) {
          try {
            await refreshMe();
          } catch {
            const again = await loadCachedUser();
            if (alive && again && (await hasSessionTokens())) {
              setSessionUserId(again.id);
              void bindVpnPrefsUser(again.id);
              setUser(again);
            } else if (alive) {
              setSessionUserId(null);
              void bindVpnPrefsUser(null);
              setUser(null);
            }
          }
        } else {
          setUser(null);
          setSessionUserId(null);
          void bindVpnPrefsUser(null);
          void ninaVpnClearSession();
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- bootstrap once
  }, []);

  const finishLogin = async (tokens: Tokens) => {
    await saveTokens(tokens);
    // One short /me — warm support caches in background so the spinner stops sooner.
    const me = await api<User>("/api/v1/auth/me", {
      timeoutMs: 8000,
      retries: 0,
      priority: true,
    });
    await applyUser(me);
    if (me.role === "admin" || me.role === "support") {
      void import("./adminSupportPrefetch").then(({ prefetchAdminInbox }) =>
        prefetchAdminInbox({ force: true, attempts: 1 })
      );
    } else {
      void prefetchSupportChat({ force: true, attempts: 2 });
    }
  };

  const login = async (email: string, password: string) => {
    await ninaVpnClearSession();
    await bindVpnPrefsUser(null);
    const tokens = await api<Tokens>("/api/v1/auth/login", {
      method: "POST",
      auth: false,
      timeoutMs: 10000,
      retries: 0,
      priority: true,
      body: JSON.stringify({ email, password }),
    });
    await finishLogin(tokens);
  };

  const register = async (email: string, password: string) => {
    await ninaVpnClearSession();
    await bindVpnPrefsUser(null);
    const tokens = await api<Tokens>("/api/v1/auth/register", {
      method: "POST",
      auth: false,
      timeoutMs: 20000,
      retries: 1,
      body: JSON.stringify({ email, password }),
    });
    await finishLogin(tokens);
  };

  const loginWithGoogle = async (idToken: string) => {
    if (googleLockToken === idToken) return;
    googleLockToken = idToken;
    try {
      await ninaVpnClearSession();
      await bindVpnPrefsUser(null);
      const tokens = await api<Tokens>("/api/v1/auth/google", {
        method: "POST",
        auth: false,
        timeoutMs: 20000,
        retries: 1,
        body: JSON.stringify({ id_token: idToken }),
      });
      await finishLogin(tokens);
    } catch (e) {
      googleLockToken = null;
      throw e;
    }
  };

  const loginWithTelegram = async (payload: TelegramAuthPayload) => {
    if (telegramLockHash === payload.hash) return;
    telegramLockHash = payload.hash;
    try {
      await ninaVpnClearSession();
      await bindVpnPrefsUser(null);
      const tokens = await api<Tokens>("/api/v1/auth/telegram", {
        method: "POST",
        auth: false,
        timeoutMs: 20000,
        retries: 1,
        body: JSON.stringify(payload),
      });
      await finishLogin(tokens);
    } catch (e) {
      telegramLockHash = null;
      throw e;
    }
  };

  useEffect(() => {
    const seen = new Set<string>();
    const onUrl = (url: string | null) => {
      if (!url || seen.has(url)) return;
      if (!/google-auth|tg-auth/i.test(url)) return;
      seen.add(url);
      void (async () => {
        try {
          if (/google-auth/i.test(url) && /id_token=/i.test(url)) {
            await loginWithGoogle(parseGoogleIdTokenFromUrl(url));
            router.replace("/(app)/(tabs)/home");
          } else if (/tg-auth/i.test(url) && /hash=/i.test(url)) {
            await loginWithTelegram(parseTelegramFromUrl(url));
            router.replace("/(app)/(tabs)/home");
          } else {
            seen.delete(url);
          }
        } catch {
          seen.delete(url);
        }
      })();
    };
    const sub = Linking.addEventListener("url", (e) => onUrl(e.url));
    void Linking.getInitialURL().then(onUrl);
    return () => sub.remove();
    // Deep-link listener for the life of the provider.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const logout = async () => {
    await ninaVpnClearSession();
    await bindVpnPrefsUser(null);
    setSessionUserId(null);
    await clearTokens();
    await clearCachedUser();
    await clearCachedSubscription();
    await clearHomeCaches();
    await resetSupportChatPrefetch();
    try {
      const { resetAdminSupportPrefetch } = await import("./adminSupportPrefetch");
      await resetAdminSupportPrefetch();
    } catch {
      /* ignore */
    }
    setUser(null);
  };

  const patchUser = useCallback((partial: Partial<User>) => {
    setUser((prev) => {
      if (!prev) return prev;
      const next = { ...prev, ...partial };
      if ("profile_emoji" in partial) {
        void saveLocalProfileEmoji(prev.id, next.profile_emoji ?? null);
      }
      void saveCachedUser(next);
      return next;
    });
  }, []);

  return (
    <Ctx.Provider
      value={{
        user,
        loading,
        login,
        register,
        loginWithGoogle,
        loginWithTelegram,
        logout,
        refreshMe,
        patchUser,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("AuthProvider missing");
  return v;
}
