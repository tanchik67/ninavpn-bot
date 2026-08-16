import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { Alert, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { AppText as Text } from "../../../src/components/AppText";
import { IosEmoji } from "../../../src/components/IosEmoji";
import { ScreenTitle } from "../../../src/components/NinaLogo";
import { GlassCard } from "../../../src/components/GlassCard";
import { PrimaryButton } from "../../../src/components/PrimaryButton";
import { AppleSwitch } from "../../../src/components/AppleSwitch";
import { ScreenBackground } from "../../../src/components/ScreenBackground";
import { useAuth } from "../../../src/lib/auth";
import { confirmLogout } from "../../../src/lib/confirmLogout";
import { useI18n } from "../../../src/lib/i18n";
import { ninaVpnGetStatus, ninaVpnReconnect } from "../../../src/lib/ninaVpn";
import { colors, fonts, spacing } from "../../../src/lib/theme";
import { loadVpnPrefs, saveVpnPrefs, type VpnPrefs } from "../../../src/lib/vpnPrefs";

function InfoDot({ title, body }: { title: string; body: string }) {
  return (
    <Pressable
      onPress={() => Alert.alert(title, body)}
      hitSlop={10}
      accessibilityRole="button"
      accessibilityLabel={title}
    >
      {({ pressed }) => (
        <View style={[styles.infoDot, pressed && styles.infoDotPressed]}>
          <Ionicons name="information" size={13} color={colors.accentLight} />
        </View>
      )}
    </Pressable>
  );
}

function SettingToggle({
  label,
  hint,
  value,
  onChange,
  last,
}: {
  label: string;
  hint: string;
  value: boolean;
  onChange: (v: boolean) => void;
  last?: boolean;
}) {
  return (
    <View style={[styles.toggleRow, !last && styles.rowBorder]}>
      <View style={styles.labelWrap}>
        <Text style={styles.toggleLabel}>{label}</Text>
        <InfoDot title={label} body={hint} />
      </View>
      <AppleSwitch value={value} onChange={onChange} />
    </View>
  );
}

function SettingLink({
  label,
  onPress,
  last,
}: {
  label: string;
  onPress?: () => void;
  last?: boolean;
}) {
  return (
    <Pressable style={[styles.linkRow, !last && styles.rowBorder]} onPress={onPress}>
      <Text style={styles.linkLabel}>{label}</Text>
      <Text style={styles.chevron}>›</Text>
    </Pressable>
  );
}

export default function SettingsScreen() {
  const { logout, user } = useAuth();
  const { t } = useI18n();
  const isStaff = user?.role === "admin" || user?.role === "support";
  const [prefs, setPrefs] = useState<VpnPrefs>({
    autoConnect: false,
    killSwitch: true,
    lanAccess: false,
  });

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      loadVpnPrefs().then((p) => {
        if (alive) setPrefs(p);
      });
      return () => {
        alive = false;
      };
    }, [user?.id])
  );

  const patchPref = async (partial: Partial<VpnPrefs>) => {
    const next = await saveVpnPrefs(partial);
    setPrefs(next);
    if (partial.killSwitch != null || partial.lanAccess != null) {
      try {
        const st = await ninaVpnGetStatus();
        if (st === "connected") {
          await ninaVpnReconnect();
        }
      } catch {
        /* apply on next connect */
      }
    }
  };

  return (
    <ScreenBackground>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        <ScreenTitle>{t("settings.title")}</ScreenTitle>

        <View style={styles.sectionRow}>
          <IosEmoji emoji="⚙️" size={16} />
          <Text style={styles.section}>{t("settings.general")}</Text>
        </View>
        <GlassCard padded={false}>
          <SettingLink
            label={t("settings.language")}
            onPress={() => router.push("/(app)/language")}
          />
          <SettingLink
            label={t("settings.textSize")}
            onPress={() => router.push("/(app)/text-size")}
            last
          />
        </GlassCard>

        <View style={styles.sectionRow}>
          <IosEmoji emoji="🛡️" size={16} />
          <Text style={styles.section}>{t("settings.vpn")}</Text>
        </View>
        <GlassCard padded={false}>
          <SettingToggle
            label={t("settings.autoConnect")}
            hint={t("settings.autoConnectHint")}
            value={prefs.autoConnect}
            onChange={(v) => void patchPref({ autoConnect: v })}
          />
          <SettingToggle
            label={t("settings.killSwitch")}
            hint={t("settings.killSwitchHint")}
            value={prefs.killSwitch}
            onChange={(v) => void patchPref({ killSwitch: v })}
          />
          <SettingToggle
            label={t("settings.lanAccess")}
            hint={t("settings.lanAccessHint")}
            value={prefs.lanAccess}
            onChange={(v) => void patchPref({ lanAccess: v })}
            last
          />
        </GlassCard>

        <View style={styles.sectionRow}>
          <IosEmoji emoji="✨" size={16} />
          <Text style={styles.section}>{t("settings.more")}</Text>
        </View>
        <GlassCard padded={false}>
          <SettingLink
            label={t("settings.advanced")}
            onPress={() => router.push("/(app)/connection-profiles")}
          />
          <SettingLink
            label={t("servers.title")}
            onPress={() => router.push("/(app)/servers")}
          />
          <SettingLink
            label={t("guides.title")}
            onPress={() => router.push("/(app)/guides")}
          />
          <SettingLink
            label={t("settings.faq")}
            onPress={() => router.push("/(app)/faq")}
          />
          <SettingLink
            label={t("settings.about")}
            onPress={() => router.push("/(app)/about")}
            last
          />
        </GlassCard>

        {isStaff ? (
          <PrimaryButton
            label={t("support.staffChats")}
            variant="secondary"
            onPress={() => router.push("/(app)/admin-inbox")}
            style={{ marginTop: spacing.lg }}
          />
        ) : (
          <PrimaryButton
            label={t("settings.contactSupport")}
            variant="secondary"
            onPress={() => router.push("/(app)/support-chat")}
            style={{ marginTop: spacing.lg }}
          />
        )}

        <PrimaryButton
          label={t("common.logout")}
          variant="secondary"
          onPress={() =>
            confirmLogout({
              message: t("common.logoutConfirm"),
              yes: t("common.yes"),
              no: t("common.no"),
              onConfirm: logout,
            })
          }
          style={{ marginTop: spacing.sm, marginBottom: spacing.md }}
        />
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: spacing.screen,
    paddingTop: 60,
    paddingBottom: 100,
  },
  sectionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: spacing.lg,
    marginBottom: 8,
    marginLeft: 4,
  },
  section: {
    fontFamily: fonts.bodySemi,
    fontSize: 13,
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  toggleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    paddingHorizontal: 16,
    minHeight: 48,
  },
  labelWrap: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingRight: 12,
    gap: 8,
  },
  toggleLabel: {
    color: colors.text,
    fontSize: 16,
    fontFamily: fonts.body,
    flexShrink: 1,
  },
  infoDot: {
    width: 18,
    height: 18,
    borderRadius: 9,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(123,47,255,0.12)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(167,139,250,0.38)",
  },
  infoDotPressed: {
    backgroundColor: "rgba(123,47,255,0.24)",
    borderColor: "rgba(167,139,250,0.62)",
  },
  linkRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    paddingHorizontal: 16,
    minHeight: 48,
  },
  linkLabel: {
    color: colors.text,
    fontSize: 16,
    fontFamily: fonts.body,
  },
  chevron: { color: colors.muted, fontSize: 20 },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.hairline,
  },
});
