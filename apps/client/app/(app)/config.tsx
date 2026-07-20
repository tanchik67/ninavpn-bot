import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import { useCallback, useState } from "react";
import { useFocusEffect, router } from "expo-router";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
} from "react-native";
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
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
            setError("Конфиг пока недоступен — оплатите тариф.");
          }
        }
      })();
      return () => {
        alive = false;
      };
    }, [])
  );

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.back}>‹ Назад</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>Конфиг</ScreenTitle>

        {!cfg && !error ? (
          <ActivityIndicator color={colors.accent} />
        ) : !cfg ? (
          <GlassCard style={{ gap: 12 }}>
            <Text style={styles.error}>{error}</Text>
            <PrimaryButton label="К тарифам" onPress={() => router.push("/(app)/plans")} />
          </GlassCard>
        ) : (
          <GlassCard style={{ gap: 12 }}>
            <Text style={styles.muted}>Статус: {cfg.status}</Text>
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
              label={copied ? "Скопировано" : "Копировать"}
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
                  label={`Открыть в ${name}`}
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
