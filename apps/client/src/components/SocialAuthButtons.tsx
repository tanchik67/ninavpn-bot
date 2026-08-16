import { useState } from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, View } from "react-native";
import { AppText as Text } from "./AppText";
import { useAuth } from "../lib/auth";
import { formatApiError } from "../lib/apiErrors";
import { useI18n } from "../lib/i18n";
import {
  GOOGLE_WEB_CLIENT_ID,
  openGoogleLoginNative,
  openTelegramLogin,
  TELEGRAM_BOT_USERNAME,
  useGoogleIdTokenAuth,
} from "../lib/oauth";
import { colors, fonts, radii } from "../lib/theme";

type Props = {
  onSuccess?: () => void;
  onError?: (msg: string) => void;
  busy?: "google" | "telegram" | null;
  setBusy?: (v: "google" | "telegram" | null) => void;
  googleLabel?: string;
  telegramLabel?: string;
  showDivider?: boolean;
};

/** Web: AuthSession Google provider. */
function GoogleSignInWebButton({
  onSuccess,
  onError,
  busy,
  setBusy,
  googleLabel,
}: Props) {
  const { loginWithGoogle } = useAuth();
  const { t } = useI18n();
  const google = useGoogleIdTokenAuth();

  const onPress = async () => {
    setBusy?.("google");
    try {
      const res = await google.promptAsync();
      if (res.type !== "success") {
        if (res.type === "error") onError?.(t("social.googleError"));
        return;
      }
      const token =
        (res as { params?: { id_token?: string }; authentication?: { idToken?: string | null } })
          .params?.id_token ||
        (res as { authentication?: { idToken?: string | null } }).authentication?.idToken ||
        null;
      if (!token) {
        onError?.(t("social.googleNoToken"));
        return;
      }
      await loginWithGoogle(token);
      onSuccess?.();
    } catch (e: unknown) {
      onError?.(formatApiError(e, t("social.googleFailed")));
    } finally {
      setBusy?.(null);
    }
  };

  return (
    <Pressable style={[styles.btn, styles.google]} onPress={onPress} disabled={!!busy}>
      {busy === "google" ? (
        <ActivityIndicator color={colors.text} />
      ) : (
        <Text style={styles.btnText}>{googleLabel || t("social.google")}</Text>
      )}
    </Pressable>
  );
}

/** Android/iOS: HTTPS bridge page → deep link with id_token. */
function GoogleSignInNativeButton({
  onSuccess,
  onError,
  busy,
  setBusy,
  googleLabel,
}: Props) {
  const { loginWithGoogle } = useAuth();
  const { t } = useI18n();

  const onPress = async () => {
    setBusy?.("google");
    try {
      const token = await openGoogleLoginNative();
      await loginWithGoogle(token);
      onSuccess?.();
    } catch (e: any) {
      if (e?.message === "google_cancelled") return;
      onError?.(formatApiError(e, t("social.googleFailed")));
    } finally {
      setBusy?.(null);
    }
  };

  return (
    <Pressable style={[styles.btn, styles.google]} onPress={onPress} disabled={!!busy}>
      {busy === "google" ? (
        <ActivityIndicator color={colors.text} />
      ) : (
        <Text style={styles.btnText}>{googleLabel || t("social.google")}</Text>
      )}
    </Pressable>
  );
}

export function SocialAuthButtons({
  onSuccess,
  onError,
  googleLabel,
  telegramLabel,
  showDivider = true,
}: Props) {
  const { loginWithTelegram } = useAuth();
  const { t } = useI18n();
  const [busy, setBusy] = useState<"google" | "telegram" | null>(null);
  const googleConfigured = !!GOOGLE_WEB_CLIENT_ID;
  const gLabel = googleLabel || t("social.google");
  const tLabel = telegramLabel || t("social.telegram");

  const onGoogleUnconfigured = () => {
    onError?.(t("social.googleNotConfigured"));
  };

  const onTelegram = async () => {
    if (!TELEGRAM_BOT_USERNAME) {
      onError?.(t("social.telegramNotConfigured"));
      return;
    }
    setBusy("telegram");
    try {
      const payload = await openTelegramLogin();
      await loginWithTelegram(payload);
      onSuccess?.();
    } catch (e: any) {
      if (e?.message !== "telegram_cancelled") {
        onError?.(formatApiError(e, t("social.telegramFailed")));
      }
    } finally {
      setBusy(null);
    }
  };

  const GoogleBtn =
    Platform.OS === "web" ? GoogleSignInWebButton : GoogleSignInNativeButton;

  return (
    <View style={styles.wrap}>
      {showDivider ? (
        <View style={styles.dividerRow}>
          <View style={styles.line} />
          <Text style={styles.or}>{t("social.or")}</Text>
          <View style={styles.line} />
        </View>
      ) : null}

      {googleConfigured ? (
        <GoogleBtn
          onSuccess={onSuccess}
          onError={onError}
          busy={busy}
          setBusy={setBusy}
          googleLabel={gLabel}
        />
      ) : (
        <Pressable
          style={[styles.btn, styles.google]}
          onPress={onGoogleUnconfigured}
          disabled={!!busy}
        >
          <Text style={styles.btnText}>{gLabel}</Text>
        </Pressable>
      )}

      <Pressable style={[styles.btn, styles.telegram]} onPress={onTelegram} disabled={!!busy}>
        {busy === "telegram" ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={[styles.btnText, { color: "#fff" }]}>{tLabel}</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 10, marginTop: 8 },
  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginVertical: 4,
  },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.hairline },
  or: { color: colors.muted, fontFamily: fonts.body, fontSize: 13 },
  btn: {
    borderRadius: radii.pill,
    paddingVertical: 14,
    alignItems: "center",
    minHeight: 48,
    justifyContent: "center",
    borderWidth: StyleSheet.hairlineWidth,
  },
  google: {
    backgroundColor: colors.glassFill,
    borderColor: colors.glassBorder,
  },
  telegram: {
    backgroundColor: "#229ED9",
    borderColor: "#229ED9",
  },
  btnText: {
    fontFamily: fonts.bodyBold,
    fontSize: 15,
    color: colors.text,
  },
});
