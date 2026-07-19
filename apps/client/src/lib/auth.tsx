import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearTokens, getAccessToken, saveTokens, Tokens } from "./api";

type User = {
  id: string;
  email: string;
  role: string;
  tg_id?: number | null;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
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
    setUser(me);
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

  const logout = async () => {
    await clearTokens();
    setUser(null);
  };

  return (
    <Ctx.Provider value={{ user, loading, login, register, logout, refreshMe }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("AuthProvider missing");
  return v;
}
