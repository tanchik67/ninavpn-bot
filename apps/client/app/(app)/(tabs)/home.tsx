import { router } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import { AppText as Text } from "../../../src/components/AppText";
import { LinearGradient } from "expo-linear-gradient";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
  cancelAnimation,
} from "react-native-reanimated";
import { NinaLogo } from "../../../src/components/NinaLogo";
import { GlassCard } from "../../../src/components/GlassCard";
import { ScreenBackground } from "../../../src/components/ScreenBackground";
import { api } from "../../../src/lib/api";
import { useI18n } from "../../../src/lib/i18n";
import { colors, fonts, spacing } from "../../../src/lib/theme";

type Sub = {
  status: string;
  plan_name?: string;
  expires_at?: string;
  has_config: boolean;
};

type ServerRow = {
  flag: string;
  name: string;
  protocol: string;
  ping: number;
};

type ConnectPhase = "idle" | "connecting" | "refreshing" | "connected";

const BASE_SERVERS: Omit<ServerRow, "ping">[] = [
  { flag: "🇩🇪", name: "Frankfurt-1", protocol: "VLESS" },
  { flag: "🇺🇸", name: "New York", protocol: "VLESS" },
  { flag: "🇯🇵", name: "Tokyo", protocol: "VLESS" },
  { flag: "🇫🇷", name: "Paris", protocol: "VLESS" },
  { flag: "🇫🇮", name: "Helsinki", protocol: "VLESS" },
];

function randomPing() {
  return Math.round(18 + Math.random() * 40);
}

function formatTimer(totalSec: number) {
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

function SpinRing({ active }: { active: boolean }) {
  const rotation = useSharedValue(0);

  useEffect(() => {
    if (active) {
      rotation.value = 0;
      rotation.value = withRepeat(
        withTiming(360, { duration: 1000, easing: Easing.linear }),
        -1,
        false
      );
    } else {
      cancelAnimation(rotation);
      rotation.value = 0;
    }
  }, [active, rotation]);

  const style = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotation.value}deg` }],
  }));

  if (!active) return null;

  return (
    <Animated.View style={[styles.ringWrap, style]} pointerEvents="none">
      <View style={styles.ringArc} />
    </Animated.View>
  );
}

export default function HomeScreen() {
  const { t } = useI18n();
  const [sub, setSub] = useState<Sub | null>(null);
  const [loading, setLoading] = useState(true);
  const [phase, setPhase] = useState<ConnectPhase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [servers, setServers] = useState<ServerRow[]>(() =>
    BASE_SERVERS.map((s) => ({ ...s, ping: randomPing() }))
  );
  const [hint, setHint] = useState("");
  const startedAt = useRef<number | null>(null);
  const busyRef = useRef(false);

  const refreshSub = useCallback(async () => {
    try {
      const s = await api<Sub | null>("/api/v1/subscriptions/me");
      setSub(s);
      return s;
    } catch {
      setSub(null);
      return null;
    }
  }, []);

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
    if (phase !== "connected") {
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
  }, [phase]);

  const hasAccess = sub?.status === "active" && !!sub?.has_config;
  const spinning = phase === "connecting" || phase === "refreshing";
  const connected = phase === "connected";

  const onConnect = async () => {
    if (busyRef.current) return;

    if (phase === "connected") {
      setPhase("idle");
      setHint(t("home.hintDisconnected"));
      return;
    }

    if (phase !== "idle") return;

    if (!sub) {
      router.push("/(app)/plans");
      return;
    }

    busyRef.current = true;
    setHint("");
    setPhase("connecting");

    try {
      await new Promise((r) => setTimeout(r, 900));
      setPhase("refreshing");

      const [s] = await Promise.all([
        refreshSub(),
        new Promise((r) => setTimeout(r, 1100)),
      ]);

      setServers(BASE_SERVERS.map((row) => ({ ...row, ping: randomPing() })));

      const ok = s?.status === "active" && !!s?.has_config;
      if (!ok && !s) {
        setPhase("idle");
        setHint(t("home.hintNoSub"));
        router.push("/(app)/plans");
        return;
      }

      // Allow connect UI even if config not ready yet (cabinet UX),
      // but prefer success path when access exists.
      setPhase("connected");
      setHint(t("home.hintTapToDisconnect"));
    } catch {
      setPhase("idle");
      setHint(t("home.errorConnect"));
    } finally {
      busyRef.current = false;
    }
  };

  const label =
    phase === "connecting"
      ? t("home.phaseConnecting")
      : phase === "refreshing"
        ? t("home.phaseRefreshing")
        : phase === "connected"
          ? t("home.phaseConnected")
          : t("home.phaseIdle");

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
            <Pressable
              onPress={onConnect}
              style={styles.connectPress}
              disabled={spinning}
            >
              <View
                style={[
                  styles.glow,
                  connected ? styles.glowOn : styles.glowOff,
                ]}
              />
              <SpinRing active={spinning} />
              {connected ? (
                <LinearGradient
                  colors={["#7B2FFF", "#9333EA", "#FF2FA0"]}
                  style={[styles.connectBtn, styles.connectBtnOn]}
                >
                  <Text style={styles.connectLabelOn}>{label}</Text>
                  <Text style={styles.timer}>{formatTimer(elapsed)}</Text>
                </LinearGradient>
              ) : (
                <View style={[styles.connectBtn, styles.connectBtnOff]}>
                  <Text style={styles.connectLabelOff}>{label}</Text>
                </View>
              )}
            </Pressable>
          )}
          <Text style={styles.connectHint}>
            {hint ||
              (connected
                ? t("home.hintTapToDisconnect")
                : hasAccess
                  ? t("home.hintTapToConnect")
                  : t("home.hintNeedPlan"))}
          </Text>
        </View>

        <Text style={styles.section}>
          <Text style={styles.sectionEmoji}>🌐 </Text>
          {t("home.servers")}
        </Text>
        <GlassCard padded={false} style={styles.group}>
          {servers.map((s, i) => (
            <Pressable
              key={s.name}
              style={[styles.row, i < servers.length - 1 && styles.rowBorder]}
              onPress={onConnect}
              disabled={spinning}
            >
              <Text style={styles.flag}>{s.flag}</Text>
              <View style={{ flex: 1 }}>
                <Text style={styles.serverName}>{s.name}</Text>
                <Text style={styles.serverMeta}>{s.protocol}</Text>
              </View>
              <Text style={styles.ping}>{t("home.pingMs", { n: Math.round(s.ping) })}</Text>
            </Pressable>
          ))}
        </GlassCard>
      </ScrollView>
    </ScreenBackground>
  );
}

const RING = 188;

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
    width: RING,
    height: RING,
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
  ringWrap: {
    position: "absolute",
    width: RING,
    height: RING,
    borderRadius: RING / 2,
    alignItems: "center",
    justifyContent: "center",
  },
  ringArc: {
    width: RING,
    height: RING,
    borderRadius: RING / 2,
    borderWidth: 3.5,
    borderTopColor: "#C4B5FD",
    borderRightColor: "#7B2FFF",
    borderBottomColor: "transparent",
    borderLeftColor: "transparent",
    shadowColor: "#7B2FFF",
    shadowOpacity: 0.9,
    shadowRadius: 8,
  },
  connectBtn: {
    width: 168,
    height: 168,
    borderRadius: 84,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
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
    color: "rgba(240,238,255,0.7)",
    fontFamily: fonts.bodySemi,
    fontSize: 12,
    letterSpacing: 0.2,
    textAlign: "center",
    paddingHorizontal: 16,
    lineHeight: 16,
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
    maxWidth: 280,
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
