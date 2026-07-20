import { router } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { NinaLogo } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { colors, fonts, spacing } from "../../src/lib/theme";

type Sub = {
  status: string;
  plan_name?: string;
  expires_at?: string;
  has_config: boolean;
};

const SERVERS = [
  { flag: "🇩🇪", name: "Frankfurt-1", protocol: "VLESS", ping: "19.3" },
  { flag: "🇺🇸", name: "New York", protocol: "VLESS", ping: "23.6" },
  { flag: "🇯🇵", name: "Tokyo", protocol: "VLESS", ping: "31.2" },
  { flag: "🇫🇷", name: "Paris", protocol: "VLESS", ping: "27.8" },
  { flag: "🇫🇮", name: "Helsinki", protocol: "VLESS", ping: "32.1" },
];

function formatTimer(totalSec: number) {
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export default function HomeScreen() {
  const [sub, setSub] = useState<Sub | null>(null);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef<number | null>(null);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        setLoading(true);
        try {
          const s = await api<Sub | null>("/api/v1/subscriptions/me");
          if (alive) setSub(s);
        } catch {
          if (alive) setSub(null);
        } finally {
          if (alive) setLoading(false);
        }
      })();
      return () => {
        alive = false;
      };
    }, [])
  );

  useEffect(() => {
    if (!connected) {
      startedAt.current = null;
      setElapsed(0);
      return;
    }
    startedAt.current = Date.now();
    setElapsed(0);
    const id = setInterval(() => {
      if (startedAt.current) {
        setElapsed(Math.floor((Date.now() - startedAt.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(id);
  }, [connected]);

  const hasAccess = sub?.status === "active" && !!sub?.has_config;

  const onConnect = () => {
    // Tap toggles bright connected state + session timer.
    // No account subscription at all → go pick a plan first.
    if (!connected && !sub) {
      router.push("/(app)/plans");
      return;
    }
    setConnected((v) => !v);
  };

  return (
    <ScreenBackground>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        <NinaLogo size={26} />

        <View style={styles.connectBlock}>
          {loading ? (
            <ActivityIndicator color={colors.accent} size="large" />
          ) : (
            <Pressable onPress={onConnect} style={styles.connectPress}>
              <View
                style={[
                  styles.glow,
                  connected ? styles.glowOn : styles.glowOff,
                ]}
              />
              {connected ? (
                <LinearGradient
                  colors={["#7B2FFF", "#FF2FA0"]}
                  style={[styles.connectBtn, styles.connectBtnOn]}
                >
                  <Text style={styles.connectLabelOn}>В сети</Text>
                  <Text style={styles.timer}>{formatTimer(elapsed)}</Text>
                </LinearGradient>
              ) : (
                <View style={[styles.connectBtn, styles.connectBtnOff]}>
                  <Text style={styles.connectLabelOff}>Подключиться</Text>
                </View>
              )}
            </Pressable>
          )}
          <Text style={styles.connectHint}>
            {connected
              ? "Нажмите ещё раз, чтобы отключить"
              : hasAccess
                ? "Нажмите, чтобы подключиться"
                : "Оформите тариф, чтобы подключиться"}
          </Text>
        </View>

        <Text style={styles.section}>
          <Text style={styles.sectionEmoji}>🌐 </Text>
          Серверы
        </Text>
        <GlassCard padded={false} style={styles.group}>
          {SERVERS.map((s, i) => (
            <Pressable
              key={s.name}
              style={[styles.row, i < SERVERS.length - 1 && styles.rowBorder]}
              onPress={onConnect}
            >
              <Text style={styles.flag}>{s.flag}</Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.serverName}>{s.name}</Text>
                <Text style={styles.serverMeta}>{s.protocol}</Text>
              </View>
              <Text style={styles.ping}>{s.ping}</Text>
            </Pressable>
          ))}
        </GlassCard>
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: spacing.screen,
    paddingTop: 60,
    paddingBottom: 100,
    gap: spacing.md,
  },
  connectBlock: {
    alignItems: "center",
    marginTop: spacing.xl,
    marginBottom: spacing.lg,
  },
  connectPress: {
    alignItems: "center",
    justifyContent: "center",
  },
  glow: {
    position: "absolute",
    width: 200,
    height: 200,
    borderRadius: 100,
  },
  glowOff: {
    backgroundColor: "rgba(123,47,255,0.08)",
  },
  glowOn: {
    backgroundColor: "rgba(123,47,255,0.4)",
  },
  connectBtn: {
    width: 168,
    height: 168,
    borderRadius: 84,
    alignItems: "center",
    justifyContent: "center",
  },
  connectBtnOff: {
    backgroundColor: "rgba(255,255,255,0.06)",
    borderWidth: 1.5,
    borderColor: "rgba(123,47,255,0.28)",
    shadowOpacity: 0,
    elevation: 0,
  },
  connectBtnOn: {
    shadowColor: colors.accent,
    shadowOpacity: 0.6,
    shadowRadius: 28,
    shadowOffset: { width: 0, height: 8 },
    elevation: 14,
  },
  connectLabelOff: {
    color: "rgba(240,238,255,0.55)",
    fontFamily: fonts.bodySemi,
    fontSize: 12,
    letterSpacing: 0.2,
    textAlign: "center",
    paddingHorizontal: 16,
  },
  connectLabelOn: {
    color: "#fff",
    fontFamily: fonts.bodySemi,
    fontSize: 13,
    letterSpacing: 0.3,
    textAlign: "center",
  },
  timer: {
    marginTop: 8,
    color: "#fff",
    fontFamily: fonts.displayBold,
    fontSize: 22,
    letterSpacing: 1,
    fontVariant: ["tabular-nums"],
  },
  connectHint: {
    marginTop: spacing.md,
    color: colors.muted,
    fontFamily: fonts.body,
    fontSize: 14,
    textAlign: "center",
    maxWidth: 260,
    lineHeight: 20,
  },
  section: {
    fontFamily: fonts.bodySemi,
    fontSize: 13,
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: spacing.sm,
    marginLeft: 4,
  },
  sectionEmoji: {
    fontFamily: undefined,
    textTransform: "none",
  },
  group: { overflow: "hidden" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 12,
  },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.hairline,
  },
  flag: {
    fontSize: 22,
    fontFamily: undefined,
  },
  serverName: {
    fontFamily: fonts.bodySemi,
    fontSize: 16,
    color: colors.text,
  },
  serverMeta: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.muted,
    marginTop: 2,
  },
  ping: {
    fontFamily: fonts.bodyBold,
    fontSize: 15,
    color: colors.accent,
  },
});
