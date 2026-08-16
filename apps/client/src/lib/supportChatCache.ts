import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY = "nv_support_chat_v2";

export type CachedSupportChat = {
  ticket: { id: string; status: string };
  messages: Array<{
    id: string;
    body: string;
    created_at: string;
    is_staff: boolean;
    image_url?: string | null;
    client_msg_id?: string | null;
  }>;
};

export async function loadCachedSupportChat(): Promise<CachedSupportChat | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedSupportChat;
    if (!parsed?.ticket?.id || !Array.isArray(parsed.messages)) return null;
    parsed.messages = (parsed.messages || []).map((m) => ({
      ...m,
      pending: false,
    })) as CachedSupportChat["messages"];
    return parsed;
  } catch {
    return null;
  }
}

export async function saveCachedSupportChat(chat: CachedSupportChat): Promise<void> {
  try {
    const safe = {
      ...chat,
      messages: (chat.messages || []).map((m) => ({ ...m, pending: false })),
    };
    await AsyncStorage.setItem(KEY, JSON.stringify(safe));
  } catch {
    /* ignore */
  }
}

export async function clearCachedSupportChat(): Promise<void> {
  try {
    await AsyncStorage.removeItem(KEY);
    await AsyncStorage.removeItem("nv_support_chat_v1");
  } catch {
    /* ignore */
  }
}
