import AsyncStorage from "@react-native-async-storage/async-storage";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

const STORAGE_KEY = "nv_text_size";

/** 7 steps like iOS Dynamic Type slider */
export const TEXT_SIZE_STEPS = 7;
/** Without "larger sizes", user can only use the first 4 steps (indices 0–3) */
export const TEXT_SIZE_STANDARD_MAX = 3;
/** Default = middle of standard range */
export const TEXT_SIZE_DEFAULT_STEP = 2;

const MULTIPLIERS = [0.85, 0.92, 1.0, 1.1, 1.22, 1.38, 1.55] as const;

/** Floating tab dock height — never below 68; grows with text scale. */
export function getDockHeight(scale: number): number {
  const s = Math.max(1, scale);
  const icon = 22 * Math.min(s, 1.45);
  const label = 10 * s * 1.25;
  const gap = Math.max(4, 4 * s);
  const pad = 20; // top + bottom breathing room
  const content = icon + gap + label + pad;
  // Original default dock was 68; only grow from there
  return Math.max(68, Math.round(Math.max(20 + 48 * s, content)));
}

export function getDockClearance(scale: number, bottomInset = 12): number {
  return getDockHeight(scale) + 16 + Math.max(bottomInset, 12);
}

type Stored = {
  step: number;
  largerSizes: boolean;
};

type TextSizeCtx = {
  step: number;
  largerSizes: boolean;
  maxStep: number;
  scale: number;
  ready: boolean;
  setStep: (step: number) => void;
  setLargerSizes: (on: boolean) => void;
};

const Ctx = createContext<TextSizeCtx | null>(null);

function clampStep(step: number, largerSizes: boolean) {
  const max = largerSizes ? TEXT_SIZE_STEPS - 1 : TEXT_SIZE_STANDARD_MAX;
  return Math.max(0, Math.min(max, Math.round(step)));
}

export function TextSizeProvider({ children }: { children: React.ReactNode }) {
  const [step, setStepState] = useState(TEXT_SIZE_DEFAULT_STEP);
  const [largerSizes, setLargerState] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw) as Stored;
          const larger = !!parsed.largerSizes;
          setLargerState(larger);
          setStepState(clampStep(parsed.step ?? TEXT_SIZE_DEFAULT_STEP, larger));
        }
      } catch {
        /* defaults */
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const persist = useCallback(async (next: Stored) => {
    try {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }, []);

  const setStep = useCallback(
    (next: number) => {
      setStepState((prev) => {
        const larger = largerSizes;
        const clamped = clampStep(next, larger);
        if (clamped === prev) return prev;
        void persist({ step: clamped, largerSizes: larger });
        return clamped;
      });
    },
    [largerSizes, persist]
  );

  const setLargerSizes = useCallback(
    (on: boolean) => {
      setLargerState(on);
      setStepState((prev) => {
        const clamped = clampStep(prev, on);
        void persist({ step: clamped, largerSizes: on });
        return clamped;
      });
    },
    [persist]
  );

  const maxStep = largerSizes ? TEXT_SIZE_STEPS - 1 : TEXT_SIZE_STANDARD_MAX;
  const scale = MULTIPLIERS[clampStep(step, largerSizes)] ?? 1;

  const value = useMemo(
    () => ({
      step: clampStep(step, largerSizes),
      largerSizes,
      maxStep,
      scale,
      ready,
      setStep,
      setLargerSizes,
    }),
    [step, largerSizes, maxStep, scale, ready, setStep, setLargerSizes]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTextSize() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTextSize outside TextSizeProvider");
  return ctx;
}

export function useFontScale() {
  return useTextSize().scale;
}
