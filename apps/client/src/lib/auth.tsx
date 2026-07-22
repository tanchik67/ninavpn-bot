import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearTokens, getAccessToken, saveTokens, Tokens } from "./api";
import type { TelegramAuthPayload } from "./oauth";
import { loadLocalProfileEmoji, saveLocalProfileEmoji } from "./profileEmojiStorage";

type User = {
  id: string;
  email: string;
  role: string;
  tg_id?: number | null;
  has_password?: boolean;
  profile_emoji?: string | null;
};

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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    const token = await getAccessToken();
    if (!token) {
      setUser(null);
      return;
    }
    const me = await api<User>("/api/v1/auth/me");
    const localEmoji = await loadLocalProfileEmoji(me.id);
    // Prefer server value; fall back to device cache until API is deployed
    setUser({
      ...me,
      profile_emoji: me.profile_emoji ?? localEmoji ?? null,
    });
  }, []);

  useEffect(() => {
    (async () => {
      try {
        await refreshMe();
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [refreshMe]);

  const login = async (email: string, password: string) => {
    const tokens = await api<Tokens>("/api/v1/auth/login", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ email, password }),
    });
    await saveTokens(tokens);
    await refreshMe();
  };

  const register = async (email: string, password: string) => {
    const tokens = await api<Tokens>("/api/v1/auth/register", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ email, password }),
    });
    await saveTokens(tokens);
    await refreshMe();
  };

  const loginWithGoogle = async (idToken: string) => {
    const tokens = await api<Tokens>("/api/v1/auth/google", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ id_token: idToken }),
    });
    await saveTokens(tokens);
    await refreshMe();
  };

  const loginWithTelegram = async (payload: TelegramAuthPayload) => {
    const tokens = await api<Tokens>("/api/v1/auth/telegram", {
      method: "POST",
      auth: false,
      body: JSON.stringify(payload),
    });
    await saveTokens(tokens);
    await refreshMe();
  };

  const logout = async () => {
    await clearTokens();
    setUser(null);
  };

  const patchUser = useCallback((partial: Partial<User>) => {
    setUser((prev) => {
      if (!prev) return prev;
      const next = { ...prev, ...partial };
      if ("profile_emoji" in partial) {
        void saveLocalProfileEmoji(prev.id, next.profile_emoji ?? null);
      }
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
