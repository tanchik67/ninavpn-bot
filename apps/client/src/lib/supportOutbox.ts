import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY = "nv_support_outbox_v4";

export type SupportOutboxItem = {
  id: string;
  ticketId: string;
  body: string;
  imageUri?: string | null;
  staff?: boolean;
  createdAt: string;
  attempts: number;
  nextAttemptAt: number;
};

export async function loadOutbox(): Promise<SupportOutboxItem[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SupportOutboxItem[];
    if (!Array.isArray(parsed)) return [];
    return parsed.map((x) => ({
      ...x,
      attempts: typeof x.attempts === "number" ? x.attempts : 0,
      nextAttemptAt: typeof x.nextAttemptAt === "number" ? x.nextAttemptAt : 0,
    }));
  } catch {
    return [];
  }
}

async function saveOutbox(items: SupportOutboxItem[]) {
  await AsyncStorage.setItem(KEY, JSON.stringify(items.slice(-15)));
}

export async function addOutbox(item: SupportOutboxItem) {
  const cur = await loadOutbox();
  await saveOutbox([...cur.filter((x) => x.id !== item.id), item]);
}

export async function removeOutbox(id: string) {
  const cur = await loadOutbox();
  await saveOutbox(cur.filter((x) => x.id !== id));
}

export async function markOutboxAttempt(id: string, failed: boolean) {
  const cur = await loadOutbox();
  const next = cur
    .map((x) => {
      if (x.id !== id) return x;
      const attempts = x.attempts + 1;
      // Staff replies: more tries, shorter backoff — admin messages were dying in queue
      const maxAttempts = x.staff ? 8 : 4;
      if (failed && attempts >= maxAttempts) return null;
      const delay = failed
        ? x.staff
          ? Math.min(20_000, 2_000 * Math.pow(2, Math.min(attempts, 3)))
          : Math.min(90_000, 10_000 * Math.pow(2, Math.min(attempts, 3)))
        : 0;
      return { ...x, attempts, nextAttemptAt: Date.now() + delay };
    })
    .filter(Boolean) as SupportOutboxItem[];
  await saveOutbox(next);
}

/** Reset schedule so the next flush retries immediately. */
export async function bumpOutboxNow(id?: string) {
  const cur = await loadOutbox();
  const next = cur.map((x) => {
    if (id && x.id !== id) return x;
    return { ...x, nextAttemptAt: 0 };
  });
  await saveOutbox(next);
}

export async function clearOutbox() {
  await AsyncStorage.multiRemove([
    KEY,
    "nv_support_outbox_v1",
    "nv_support_outbox_v2",
    "nv_support_outbox_v3",
  ]);
}
