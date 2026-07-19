import { router } from "expo-router";
import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import { BrandMark } from "../../src/components/BrandMark";
import { GlassCard } from "../../src/components/GlassCard";
import { GradientButton } from "../../src/components/GradientButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
import { colors, radii } from "../../src/lib/theme";

type Sub = {
  status: string;
  plan_name?: string;
  expires_at?: string;
  has_config: boolean;
};

type Config = {
  subscription_url?: string;
  links: string[];
  qr_base64?: string;
  deeplinks: Record<string, string>;
  status: string;
  expires_at?: string;
};

export default function HomeScreen() {
  const { user } = useAuth();
  const [sub, setSub] = useState<Sub | null>(null);
  const [cfg, setCfg] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        setLoading(true);
        try {
          const s = await api<Sub | null>("/api/v1/subscriptions/me");
          if (!alive) return;
          setSub(s);
          if (s?.has_config) {
            try {
              const c = await api<Config>("/api/v1/subscriptions/me/config");
              if (alive) setCfg(c);
            } catch {
              if (alive) setCfg(null);
            }
          } else if (alive) setCfg(null);
        } catch {
          if (alive) {
            setSub(null);
            setCfg(null);
          }
        } finally {
          if (alive) setLoading(false);
        }
      })();
      return () => {
        alive = false;
      };
    }, [])
  );

  const active = sub?.status === "active" && !!cfg;
  const url = cfg?.subscription_url || cfg?.links?.[0];

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <BrandMark size={28} />
        <Text style={styles.hello}>Привет{user?.email ? `, ${user.email.split("@")[0]}` : ""}</Text>

        <GlassCard style={styles.connectCard}>
          {loading ? (
            <ActivityIndicator color={colors.accentPink} />
          ) : (
            <>
              <Pressable
                style={[styles.power, active && styles.powerOn]}
                onPress={() => {
                  if (active) router.push("/(app)/config");
                  else router.push("/(app)/plans");
                }}
              >
                <Text style={styles.powerIcon}>⏻</Text>
                <Text style={styles.powerLabel}>{active ? "ACTIVE" : "CONNECT"}</Text>
              </Pressable>
              <Text style={styles.hint}>
                {active
                  ? "Доступ готов — откройте конфиг или импортируйте в клиент"
                  : "Выберите тариф, чтобы получить доступ"}
              </Text>
            </>
          )}
        </GlassCard>

        <GlassCard style={styles.statusCard}>
          <Text style={[styles.statusTitle, { color: active ? colors.success : colors.muted }]}>
            {active ? "CONNECTED" : sub ? sub.status.toUpperCase() : "NO SUBSCRIPTION"}
          </Text>
          <Text style={styles.statusLine}>{sub?.plan_name || "Тариф не выбран"}</Text>
          <Text style={styles.statusLine}>
            {sub?.expires_at
              ? `До ${new Date(sub.expires_at).toLocaleString()}`
              : "Оформите подписку на вкладке Plans"}
          </Text>
        </GlassCard>

        {active && url ? (
          <GlassCard>
            <Text style={styles.section}>Quick access</Text>
            {cfg?.qr_base64 ? (
              <Image
                source={{ uri: `data:image/png;base64,${cfg.qr_base64}` }}
                style={styles.qr}
              />
            ) : null}
            <Text style={styles.url} numberOfLines={2} selectable>
              {url}
            </Text>
            <GradientButton
              label={copied ? "Скопировано" : "Копировать ссылку"}
              onPress={async () => {
                await Clipboard.setStringAsync(url);
                setCopied(true);
                setTimeout(() => setCopied(false), 1200);
              }}
            />
            <View style={{ height: 10 }} />
            <GradientButton
              variant="ghost"
              label="Открыть в Happ / v2rayTun"
              onPress={() => {
                const link = cfg?.deeplinks?.happ || cfg?.deeplinks?.v2raytun || url;
                Linking.openURL(link);
              }}
            />
          </GlassCard>
        ) : (
          <GradientButton label="Выбрать тариф" onPress={() => router.push("/(app)/plans")} />
        )}
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: 20, paddingTop: 56, paddingBottom: 40, gap: 16 },
  hello: { color: colors.muted, marginTop: -4, marginBottom: 8 },
  connectCard: { alignItems: "center", paddingVertical: 28 },
  power: {
    width: 168,
    height: 168,
    borderRadius: 84,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.08)",
    borderWidth: 2,
    borderColor: "rgba(244,114,182,0.45)",
  },
  powerOn: {
    borderColor: colors.accentTeal,
    shadowColor: colors.accentTeal,
    shadowOpacity: 0.55,
    shadowRadius: 24,
  },
  powerIcon: { fontSize: 42, color: "#fff", marginBottom: 4 },
  powerLabel: { color: "#fff", fontWeight: "900", letterSpacing: 1.5, fontSize: 13 },
  hint: { color: colors.muted, textAlign: "center", marginTop: 16, lineHeight: 20 },
  statusCard: { gap: 4 },
  statusTitle: { fontWeight: "900", fontSize: 18, letterSpacing: 1 },
  statusLine: { color: colors.muted, fontSize: 14 },
  section: { color: colors.text, fontWeight: "800", marginBottom: 10, fontSize: 16 },
  qr: {
    width: 180,
    height: 180,
    alignSelf: "center",
    backgroundColor: "#fff",
    borderRadius: radii.md,
    marginBottom: 12,
  },
  url: { color: colors.muted, fontSize: 12, marginBottom: 12 },
});
