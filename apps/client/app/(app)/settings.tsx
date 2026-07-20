import { router } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { ScreenTitle } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { AppleSwitch } from "../../src/components/AppleSwitch";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { useAuth } from "../../src/lib/auth";
import { colors, fonts, spacing } from "../../src/lib/theme";

function SettingToggle({
  label,
  value,
  onChange,
  last,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
  last?: boolean;
}) {
  return (
    <View style={[styles.toggleRow, !last && styles.rowBorder]}>
      <Text style={styles.toggleLabel}>{label}</Text>
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
  const { logout } = useAuth();
  const [autoConnect, setAutoConnect] = useState(false);
  const [killSwitch, setKillSwitch] = useState(true);
  const [lanAccess, setLanAccess] = useState(false);
  const [protocol, setProtocol] = useState(true);

  return (
    <ScreenBackground>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        <ScreenTitle>Настройки</ScreenTitle>

        <Text style={styles.section}>
          <Text style={styles.emoji}>⚙️ </Text>
          Основные
        </Text>
        <GlassCard padded={false}>
          <SettingLink label="Язык" />
          <SettingLink label="Размер текста" last />
        </GlassCard>

        <Text style={styles.section}>
          <Text style={styles.emoji}>🛡️ </Text>
          VPN
        </Text>
        <GlassCard padded={false}>
          <SettingToggle
            label="Автоподключение"
            value={autoConnect}
            onChange={setAutoConnect}
          />
          <SettingToggle label="Kill switch" value={killSwitch} onChange={setKillSwitch} />
          <SettingToggle label="Доступ к LAN" value={lanAccess} onChange={setLanAccess} />
          <SettingToggle
            label="Предпочтения протокола"
            value={protocol}
            onChange={setProtocol}
            last
          />
        </GlassCard>

        <Text style={styles.section}>
          <Text style={styles.emoji}>✨ </Text>
          Ещё
        </Text>
        <GlassCard padded={false}>
          <SettingLink label="Расширенные" />
          <SettingLink label="Статистика" />
          <SettingLink label="FAQ" />
          <SettingLink label="О приложении" last />
        </GlassCard>

        <PrimaryButton
          label="Обратиться в поддержку"
          variant="secondary"
          onPress={() => router.push("/(app)/support-chat")}
          style={{ marginTop: spacing.lg }}
        />

        <PrimaryButton
          label="Выйти"
          variant="secondary"
          onPress={logout}
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
  section: {
    fontFamily: fonts.bodySemi,
    fontSize: 13,
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: spacing.lg,
    marginBottom: 8,
    marginLeft: 4,
  },
  emoji: {
    fontFamily: undefined,
    textTransform: "none",
    letterSpacing: 0,
  },
  toggleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    paddingHorizontal: 16,
    minHeight: 48,
  },
  toggleLabel: {
    color: colors.text,
    fontSize: 16,
    fontFamily: fonts.body,
    flex: 1,
    paddingRight: 12,
  },
  linkRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
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
