import { router } from "expo-router";

/** Prefer real history; fall back when stack is empty. */
export function goBackOr(fallback: string) {
  if (router.canGoBack()) {
    router.back();
    return;
  }
  router.replace(fallback as any);
}
