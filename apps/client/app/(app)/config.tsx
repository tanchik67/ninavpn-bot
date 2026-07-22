import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import { useCallback, useState } from "react";
import { useFocusEffect, router } from "expo-router";
import { goBackOr } from "../../src/lib/nav";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
} from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, radii, spacing } from "../../src/lib/theme";

type Config = {
  subscription_url?: string;
  links: string[];
  qr_base64?: string;
  deeplinks: Record<string, string>;
  expires_at?: string;
  status: string;
};

export default function ConfigScreen() {
  const { t } = useI18n();
  const [cfg, setCfg] = useState<Config | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        try {
          const data = await api<Config>("/api/v1/subscriptions/me/config");
          if (alive) setCfg(data);
        } catch {
          if (alive) {
            setCfg(null);
            setError(t("config.unavailable"));
          }
        }
      })();
      return () => {
        alive = false;
      };
    }, [t])
  );

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Pressable onPress={() => goBackOr("/(app)/(tabs)/home")} hitSlop={12}>
          <Text style={styles.back}>{t("common.back")}</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>{t("config.title")}</ScreenTitle>

        {!cfg && !error ? (
          <ActivityIndicator color={colors.accent} />
        ) : !cfg ? (
          <GlassCard style={{ gap: 12 }}>
            <Text style={styles.error}>{error}</Text>
            <PrimaryButton
              label={t("config.toPlans")}
              onPress={() => router.push("/(app)/plans")}
            />
          </GlassCard>
        ) : (
          <GlassCard style={{ gap: 12 }}>
            <Text style={styles.muted}>{t("config.status", { status: cfg.status })}</Text>
            {cfg.qr_base64 ? (
              <Image
                source={{ uri: `data:image/png;base64,${cfg.qr_base64}` }}
                style={styles.qr}
              />
            ) : null}
            <Text style={styles.url} selectable>
              {cfg.subscription_url || cfg.links[0]}
            </Text>
            <PrimaryButton
              label={copied ? t("config.copied") : t("config.copy")}
              onPress={async () => {
                const u = cfg.subscription_url || cfg.links[0];
                if (u) {
                  await Clipboard.setStringAsync(u);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1200);
                }
              }}
            />
            {Object.entries(cfg.deeplinks || {}).map(([name, link]) =>
              name === "raw" ? null : (
                <PrimaryButton
                  key={name}
                  variant="secondary"
                  label={t("config.openIn", { name })}
                  onPress={() => Linking.openURL(link)}
                />
              )
            )}
          </GlassCard>
        )}
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    padding: spacing.screen,
    paddingTop: 56,
    paddingBottom: 100,
    gap: 14,
  },
  back: {
    color: colors.accent,
    fontFamily: fonts.bodySemi,
    marginBottom: 8,
  },
  muted: { color: colors.muted, fontFamily: fonts.body },
  qr: {
    width: 200,
    height: 200,
    alignSelf: "center",
    backgroundColor: "#fff",
    borderRadius: radii.md,
  },
  url: { color: colors.text, fontSize: 12, fontFamily: fonts.body },
  error: { color: colors.danger, marginBottom: 4, fontFamily: fonts.body },
});
