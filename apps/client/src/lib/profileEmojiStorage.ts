import AsyncStorage from "@react-native-async-storage/async-storage";

const key = (userId: string) => `nv_profile_emoji:${userId}`;

export async function loadLocalProfileEmoji(userId: string): Promise<string | null> {
  try {
    return (await AsyncStorage.getItem(key(userId))) || null;
  } catch {
    return null;
  }
}

export async function saveLocalProfileEmoji(
  userId: string,
  emoji: string | null
): Promise<void> {
  try {
    if (!emoji) await AsyncStorage.removeItem(key(userId));
    else await AsyncStorage.setItem(key(userId), emoji);
  } catch {
    /* ignore storage failures */
  }
}

/** API not deployed yet → FastAPI `{"detail":"Not Found"}` */
export function isEmojiEndpointMissing(err: unknown): boolean {
  const msg = String((err as any)?.message ?? err ?? "");
  return (
    msg.includes("Not Found") ||
    msg.includes('"detail":"Not Found"') ||
    /\b404\b/.test(msg)
  );
}
