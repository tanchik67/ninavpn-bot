import AsyncStorage from "@react-native-async-storage/async-storage";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { dictionaries, type Dictionary, type Locale } from "./dictionaries";

const STORAGE_KEY = "nv_locale";

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
    (async () => {
      try {
        const saved = await AsyncStorage.getItem(STORAGE_KEY);
        if (saved === "ru" || saved === "en") setLocaleState(saved);
      } catch {
        /* keep default */
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const setLocale = useCallback(async (next: Locale) => {
    setLocaleState(next);
    try {
      await AsyncStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback(
    (path: string, vars?: Vars) => {
      const dict = dictionaries[locale];
      const raw =
        lookup(dict, path) ?? lookup(dictionaries.ru, path) ?? path;
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
