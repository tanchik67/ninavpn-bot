import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import { useCallback, useState } from "react";
import { useFocusEffect, router } from "expo-router";
import {
  ActivityIndicator,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { BrandMark } from "../../src/components/BrandMark";
import { GlassCard } from "../../src/components/GlassCard";
import { GradientButton } from "../../src/components/GradientButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { colors, radii } from "../../src/lib/theme";

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
        <BrandMark size={26} />
        <Text style={styles.title}>Config</Text>

        {!cfg && !error ? (
          <ActivityIndicator color={colors.accentPink} />
        ) : !cfg ? (
          <GlassCard>
            <Text style={styles.error}>{error}</Text>
            <GradientButton label="К тарифам" onPress={() => router.push("/(app)/plans")} />
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
            <GradientButton
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
                <GradientButton
                  key={name}
                  variant="ghost"
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
  scroll: { padding: 20, paddingTop: 56, gap: 14 },
  title: { color: colors.text, fontSize: 28, fontWeight: "900" },
  muted: { color: colors.muted },
  qr: {
    width: 200,
    height: 200,
    alignSelf: "center",
    backgroundColor: "#fff",
    borderRadius: radii.md,
  },
  url: { color: colors.text, fontSize: 12 },
  error: { color: colors.danger, marginBottom: 12 },
});
