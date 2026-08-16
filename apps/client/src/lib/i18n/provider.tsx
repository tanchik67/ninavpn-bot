import AsyncStorage from "@react-native-async-storage/async-storage";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { getSessionUserId, onSessionUserId } from "../sessionUser";
import { dictionaries, type Dictionary, type Locale } from "./dictionaries";

const STORAGE_KEY = "nv_locale";
const LOCALES: Locale[] = ["ru", "en", "es", "tr", "fa", "zh"];

function isLocale(v: string | null): v is Locale {
  return !!v && (LOCALES as string[]).includes(v);
}

function keyFor(userId: string | null) {
  return userId ? `${STORAGE_KEY}:${userId}` : STORAGE_KEY;
}

async function readLocale(userId: string | null): Promise<Locale> {
  try {
    const saved = await AsyncStorage.getItem(keyFor(userId));
    if (isLocale(saved)) return saved;
  } catch {
    /* defaults */
  }
  return "ru";
}

type Vars = Record<string, string | number>;

type I18nCtx = {
  locale: Locale;
  setLocale: (locale: Locale) => Promise<void>;
  t: (path: string, vars?: Vars) => string;
  ready: boolean;
};

const Ctx = createContext<I18nCtx | null>(null);

function lookup(dict: Dictionary, path: string): string | undefined {
  const parts = path.split(".");
  let cur: unknown = dict;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return typeof cur === "string" ? cur : undefined;
}

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, key: string) =>
    vars[key] != null ? String(vars[key]) : `{${key}}`
  );
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("ru");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async (userId: string | null) => {
      const next = await readLocale(userId);
      if (alive) {
        setLocaleState(next);
        setReady(true);
      }
    };
    void load(getSessionUserId());
    const stop = onSessionUserId((id) => {
      void load(id);
    });
    return () => {
      alive = false;
      stop();
    };
  }, []);

  const setLocale = useCallback(async (next: Locale) => {
    setLocaleState(next);
    try {
      await AsyncStorage.setItem(keyFor(getSessionUserId()), next);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback(
    (path: string, vars?: Vars) => {
      const dict = dictionaries[locale];
      // Prefer active locale → English → Russian (never leave half-RU UI for other langs)
      const raw =
        lookup(dict, path) ??
        (locale !== "en" ? lookup(dictionaries.en, path) : undefined) ??
        lookup(dictionaries.ru, path) ??
        path;
      return interpolate(raw, vars);
    },
    [locale]
  );

  const value = useMemo(
    () => ({ locale, setLocale, t, ready }),
    [locale, setLocale, t, ready]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}

export function useT() {
  return useI18n().t;
}
