import AsyncStorage from "@react-native-async-storage/async-storage";

const USER_KEY = "nv_cached_user_v1";

export type CachedUser = {
  id: string;
  email: string;
  role: string;
  tg_id?: number | null;
  panel_user_key?: number | null;
  has_password?: boolean;
  profile_emoji?: string | null;
};

export async function loadCachedUser(): Promise<CachedUser | null> {
  try {
    const raw = await AsyncStorage.getItem(USER_KEY);
    if (!raw) return null;
    const u = JSON.parse(raw) as CachedUser;
    if (!u?.id || !u?.email) return null;
    return u;
  } catch {
    return null;
  }
}

export async function saveCachedUser(user: CachedUser): Promise<void> {
  try {
    await AsyncStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* ignore */
  }
}

export async function clearCachedUser(): Promise<void> {
  try {
    await AsyncStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}
