import AsyncStorage from "@react-native-async-storage/async-storage";
import { getSessionUserId } from "./sessionUser";

const LEGACY = "nv_selected_server_id";

function key() {
  const uid = getSessionUserId();
  return uid ? `${LEGACY}:${uid}` : LEGACY;
}

export async function getSelectedServerId(): Promise<string | null> {
  const uid = getSessionUserId();
  if (!uid) return null;
  return AsyncStorage.getItem(key());
}

export async function setSelectedServerId(id: string): Promise<void> {
  const uid = getSessionUserId();
  if (!uid) return;
  await AsyncStorage.setItem(key(), id);
}
