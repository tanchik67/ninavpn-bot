import { Alert, Platform } from "react-native";

type ConfirmLogoutOpts = {
  message: string;
  yes: string;
  no: string;
  onConfirm: () => void | Promise<void>;
};

/** Confirm before signing out (native Alert / browser confirm on web). */
export function confirmLogout({ message, yes, no, onConfirm }: ConfirmLogoutOpts) {
  if (Platform.OS === "web" && typeof window !== "undefined") {
    if (window.confirm(message)) {
      void onConfirm();
    }
    return;
  }
  Alert.alert("", message, [
    { text: no, style: "cancel" },
    { text: yes, style: "destructive", onPress: () => void onConfirm() },
  ]);
}
