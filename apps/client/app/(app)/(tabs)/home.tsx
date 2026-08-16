import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import { AppText as Text } from "../../../src/components/AppText";
import { LinearGradient } from "expo-linear-gradient";
import Animated, {
  Easing,
  cancelAnimation,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { NinaLogo } from "../../../src/components/NinaLogo";
import { GlassCard } from "../../../src/components/GlassCard";
import { ScreenBackground } from "../../../src/components/ScreenBackground";
import { api } from "../../../src/lib/api";
import { useI18n } from "../../../src/lib/i18n";
import {
  ninaVpnAddStatusListener,
  ninaVpnConnect,
  ninaVpnDisconnect,
  ninaVpnGetStatus,
  ninaVpnPrepare,
  ninaVpnRequestQuickTile,
  ninaVpnSupported,
} from "../../../src/lib/ninaVpn";
import {
  loadCachedConfig,
  loadCachedServers,
  saveCachedConfig,
  saveCachedServers,
  type CachedConfigPayload,
  type CachedServerRow,
} from "../../../src/lib/serverCache";
import { pingServerUri } from "../../../src/lib/serverPing";
import { tryAutoConnect } from "../../../src/lib/autoConnect";
import { applyTunnelAccess, loadVpnPrefs } from "../../../src/lib/vpnPrefs";
import {
  getSelectedServerId,
  setSelectedServerId,
} from "../../../src/lib/selectedServer";
import {
  applyIdOrder,
  loadServerOrder,
} from "../../../src/lib/serverOrder";
import {
  isSubscriptionActive,
  loadCachedSubscription,
  saveCachedSubscription,
  type CachedSubscription,
} from "../../../src/lib/subscriptionCache";
import { colors, fonts, radii, spacing } from "../../../src/lib/theme";

type Sub = CachedSubscription;

type ServerRow = CachedServerRow;

type ConfigPayload = CachedConfigPayload;

type ConnectPhase =
  | "idle"
  | "connecting"
  | "switching"
  | "refreshing"
  | "connected"
  | "disconnecting";

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
      rotation.value = withTiming(0, { duration: 200 });
    }
  }, [active, rotation]);

  const style = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotation.value}deg` }],
    opacity: active ? 1 : 0,
  }));

  return (
    <Animated.View style={[styles.ringWrap, style]} pointerEvents="none">
      <View style={styles.ringArc} />
    </Animated.View>
  );
}

function PhaseLabel({ text, lit }: { text: string; lit: boolean }) {
  const [display, setDisplay] = useState(text);
  const opacity = useSharedValue(1);
  const translateY = useSharedValue(0);

  useEffect(() => {
    if (text === display) return;
    opacity.value = withTiming(0, { duration: 160, easing: Easing.out(Easing.cubic) });
    translateY.value = withTiming(-6, { duration: 160 }, (finished) => {
      if (!finished) return;
      runOnJS(setDisplay)(text);
    });
  }, [text, display, opacity, translateY]);

  useEffect(() => {
    translateY.value = 8;
    opacity.value = 0;
    translateY.value = withTiming(0, { duration: 220, easing: Easing.out(Easing.cubic) });
    opacity.value = withTiming(1, { duration: 220, easing: Easing.out(Easing.cubic) });
  }, [display, opacity, translateY]);

  const style = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }],
  }));

  return (
    <Animated.View style={style}>
      <Text style={lit ? styles.connectLabelOn : styles.connectLabelOff}>{display}</Text>
    </Animated.View>
  );
}

function AnimatedDigit({ char }: { char: string }) {
  const [shown, setShown] = useState(char);
  const opacity = useSharedValue(1);
  const translateY = useSharedValue(0);

  useEffect(() => {
    if (char === shown || char === ":") {
      if (char !== shown) setShown(char);
      return;
    }
    opacity.value = withTiming(0, { duration: 120 });
    translateY.value = withTiming(-7, { duration: 120 }, (finished) => {
      if (!finished) return;
      runOnJS(setShown)(char);
      translateY.value = 7;
      opacity.value = 0;
      translateY.value = withTiming(0, { duration: 160, easing: Easing.out(Easing.cubic) });
      opacity.value = withTiming(1, { duration: 160 });
    });
  }, [char, shown, opacity, translateY]);

  const style = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }],
  }));

  if (char === ":") {
    return <Text style={styles.timerChar}>:</Text>;
  }

  return (
    <Animated.View style={[styles.timerDigit, style]}>
      <Text style={styles.timerChar}>{shown}</Text>
    </Animated.View>
  );
}

function SmoothTimer({ seconds }: { seconds: number }) {
  const text = formatTimer(seconds);
  return (
    <View style={styles.timerRow}>
      {text.split("").map((ch, i) => (
        <AnimatedDigit key={`${i}-${text.length}`} char={ch} />
      ))}
    </View>
  );
}

function sanitizeUri(uri: string) {
  const q = uri.indexOf("?");
  if (q < 0) return uri;
  const hash = uri.indexOf("#", q);
  const head = uri.slice(0, q);
  const query = hash >= 0 ? uri.slice(q + 1, hash) : uri.slice(q + 1);
  const frag = hash >= 0 ? uri.slice(hash) : "";
  const kept = query.split("&").filter((part) => {
    if (!part) return false;
    const key = part.split("=")[0]?.toLowerCase() || "";
    if (["pqv", "pqc", "mlkem", "pq"].includes(key)) return false;
    return part.length <= 800;
  });
  return kept.length ? `${head}?${kept.join("&")}${frag}` : `${head}${frag}`;
}

function ServerRowItem({
  flag,
  name,
  protocol,
  pingLabel,
  selected,
  bordered,
}: {
  flag: string;
  name: string;
  protocol: string;
  pingLabel: string;
  selected: boolean;
  bordered: boolean;
}) {
  const sel = useSharedValue(selected ? 1 : 0);

  useEffect(() => {
    sel.value = withTiming(selected ? 1 : 0, {
      duration: 260,
      easing: Easing.out(Easing.cubic),
    });
  }, [selected, sel]);

  const rowAnim = useAnimatedStyle(() => ({
    backgroundColor: `rgba(123, 47, 255, ${0.14 * sel.value})`,
  }));

  const barAnim = useAnimatedStyle(() => ({
    opacity: sel.value,
    transform: [{ scaleY: 0.35 + sel.value * 0.65 }],
  }));

  const checkAnim = useAnimatedStyle(() => ({
    opacity: sel.value,
    transform: [{ scale: 0.7 + sel.value * 0.3 }],
  }));

  return (
    <Animated.View style={[styles.row, bordered && styles.rowBorder, rowAnim]}>
        <Animated.View style={[styles.selBar, barAnim]} />
        <Text style={styles.flag}>{flag}</Text>
        <View style={{ flex: 1 }}>
          <Text style={styles.serverName}>{name}</Text>
          <Text style={styles.serverMeta} numberOfLines={1}>
            {protocol}
          </Text>
        </View>
        <SmoothPing label={pingLabel} selected={selected} />
        <Animated.View style={[styles.checkDot, checkAnim]}>
          <View style={styles.checkInner} />
        </Animated.View>
    </Animated.View>
  );
}

function SmoothPing({ label, selected }: { label: string; selected: boolean }) {
  const op = useSharedValue(1);
  const [shown, setShown] = useState(label);
  const prev = useRef(label);

  useEffect(() => {
    if (label === prev.current) return;
    const fromEmpty = prev.current === "—" || prev.current === "";
    prev.current = label;
    if (fromEmpty) {
      setShown(label);
      op.value = withTiming(1, { duration: 320, easing: Easing.out(Easing.cubic) });
      return;
    }
    op.value = withTiming(0.22, { duration: 180, easing: Easing.out(Easing.quad) }, (done) => {
      if (!done) return;
      runOnJS(setShown)(label);
      op.value = withTiming(1, { duration: 320, easing: Easing.out(Easing.cubic) });
    });
  }, [label, op]);

  const fade = useAnimatedStyle(() => ({ opacity: op.value }));
  return (
    <Animated.View style={fade}>
      <Text style={[styles.ping, selected && styles.pingSelected]}>{shown}</Text>
    </Animated.View>
  );
}

export default function HomeScreen() {
  const { t } = useI18n();
  const [sub, setSub] = useState<Sub | null>(null);
  const [phase, setPhase] = useState<ConnectPhase>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [servers, setServers] = useState<ServerRow[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hintKey, setHintKey] = useState<string | null>(null);
  const [subReady, setSubReady] = useState(false);
  const [welcomeAttempt, setWelcomeAttempt] = useState(0);
  const startedAt = useRef<number | null>(null);
  const busyRef = useRef(false);
  const phaseRef = useRef<ConnectPhase>("idle");
  const disconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const phaseWatchdog = useRef<ReturnType<typeof setTimeout> | null>(null);
  const configCache = useRef<ConfigPayload | null>(null);
  const serversRef = useRef<ServerRow[]>([]);
  const selectedIdRef = useRef<string | null>(null);

  const pressScale = useSharedValue(1);
  const lit = useSharedValue(0);
  const timerVis = useSharedValue(0);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);
  useEffect(() => {
    serversRef.current = servers;
  }, [servers]);
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  const applyServerRows = useCallback(async (rows: ServerRow[]) => {
    if (!rows.length) return;
    const savedOrder = await loadServerOrder();
    const prevIds = serversRef.current.map((s) => s.id);
    const ordered = applyIdOrder(rows, prevIds.length ? prevIds : savedOrder);
    setServers(ordered);
    serversRef.current = ordered;
    void saveCachedServers(ordered);
    const saved = await getSelectedServerId();
    if (saved && ordered.some((r) => r.id === saved)) {
      setSelectedId(saved);
      selectedIdRef.current = saved;
    } else if (!selectedIdRef.current || !ordered.some((r) => r.id === selectedIdRef.current)) {
      setSelectedId(ordered[0].id);
      selectedIdRef.current = ordered[0].id;
      await setSelectedServerId(ordered[0].id);
    }
  }, []);

  const refreshPings = useCallback(async () => {
    const list = serversRef.current.filter((s) => !!s.uri);
    if (!list.length) return;
    await Promise.all(
      list.map(async (s) => {
        const ms = await pingServerUri(s.uri);
        if (ms == null) return;
        const cur = serversRef.current;
        const idx = cur.findIndex((x) => x.id === s.id);
        if (idx < 0) return;
        await applyServerRows(cur.map((row, i) => (i === idx ? { ...row, ping: ms } : row)));
      })
    );
  }, [applyServerRows]);

  const refreshSub = useCallback(async () => {
    try {
      const s = await api<Sub | null>("/api/v1/subscriptions/me", {
        timeoutMs: 12000,
        retries: 1,
      });
      setSub(s);
      void saveCachedSubscription(s);
      const allowed = !!s && isSubscriptionActive(s) && !!s.has_config;
      void applyTunnelAccess(allowed);
      if (allowed) void tryAutoConnect();
      return s;
    } catch (e: any) {
      const msg = String(e?.message || "");
      if (msg === "not_authenticated" || /invalid_refresh|unauthorized/i.test(msg)) {
        setSub(null);
        void saveCachedSubscription(null);
        void applyTunnelAccess(false);
        return null;
      }
      // Keep last known / cache on blips
      const cached = await loadCachedSubscription();
      if (cached) {
        setSub(cached);
        return cached;
      }
      return null;
    } finally {
      setSubReady(true);
    }
  }, []);

  const refreshServers = useCallback(async () => {
    type Loc = {
      id: string;
      flag: string;
      city: string;
      protocol: string;
      protocols?: string[];
      latency_ms?: number | null;
    };

    const peelFlag = (raw: string): { flag?: string; name: string } => {
      const s = (raw || "").trim();
      // Regional indicator pair (national flags) at start
      const m = s.match(/^([\u{1F1E6}-\u{1F1FF}]{2})\s*(.+)$/u);
      if (m) return { flag: m[1], name: m[2].trim() };
      return { name: s };
    };

    const locForNode = (n: { id: string; city?: string }, locs: Loc[]): Loc | undefined => {
      const byId = locs.find((l) => l.id === n.id);
      if (byId) return byId;
      const city = (n.city || "").trim().toLowerCase();
      if (!city) return undefined;
      return locs.find((l) => {
        const lc = (l.city || "").trim().toLowerCase();
        return lc === city || lc.includes(city) || city.includes(lc);
      });
    };

    const protocolLabel = (
      fromNode?: { protocol?: string; protocols?: string[] },
      fromLoc?: Loc,
      prev?: string
    ) => {
      if (fromNode?.protocol && fromNode.protocol !== "VLESS") return fromNode.protocol;
      if (fromNode?.protocols?.length) return fromNode.protocols.join(" · ");
      if (fromLoc?.protocol) return fromLoc.protocol;
      if (fromLoc?.protocols?.length) return fromLoc.protocols.join(" · ");
      if (fromNode?.protocol) return fromNode.protocol;
      return prev || "VLESS";
    };

    const mergeRows = (cfg: ConfigPayload | null, locs: Loc[]): ServerRow[] => {
      if (cfg?.nodes?.length) {
        return cfg.nodes.map((n) => {
          const loc = locForNode(n, locs);
          const prev = serversRef.current.find((s) => s.id === n.id);
          const peeled = peelFlag(n.city || loc?.city || prev?.name || n.id);
          const flag =
            (n.flag && n.flag !== "🌐" ? n.flag : undefined) ||
            loc?.flag ||
            peeled.flag ||
            prev?.flag ||
            "🌐";
          const locPing =
            typeof loc?.latency_ms === "number" ? loc.latency_ms : null;
          return {
            id: n.id,
            flag,
            name: peeled.name || loc?.city || prev?.name || n.id,
            protocol: protocolLabel(n, loc, prev?.protocol),
            ping: prev?.ping ?? locPing ?? null,
            uri: n.uri || prev?.uri,
          };
        });
      }
      if (!locs.length) return [];
      return locs.map((l) => {
        const prev = serversRef.current.find((s) => s.id === l.id);
        return {
          id: l.id,
          flag: l.flag || prev?.flag || "🌐",
          name: l.city || prev?.name || l.id,
          protocol: protocolLabel(undefined, l, prev?.protocol),
          ping: prev?.ping ?? (typeof l.latency_ms === "number" ? l.latency_ms : null),
          uri: prev?.uri,
        };
      });
    };

    const cfgPromise = api<ConfigPayload>("/api/v1/subscriptions/me/config", {
      timeoutMs: 12000,
    })
      .then((cfg) => {
        if (cfg?.nodes?.length) {
          configCache.current = cfg;
          void saveCachedConfig(cfg);
        }
        return cfg;
      })
      .catch(() => null);

    const locsPromise = api<Loc[]>("/api/v1/network/locations", {
      auth: false,
      timeoutMs: 8000,
    }).catch(() => [] as Loc[]);

    // Show nodes as soon as config arrives — don't wait for slow location pings
    const cfg = await cfgPromise;
    if (cfg?.nodes?.length) {
      await applyServerRows(mergeRows(cfg, []));
    }

    const locs = await locsPromise;
    const rows = mergeRows(cfg || configCache.current, locs);
    if (rows.length) {
      await applyServerRows(rows);
    }

    await refreshPings();
    // Never clear an existing list on network failure
  }, [applyServerRows, refreshPings]);

  const syncNativePhase = useCallback(async () => {
    if (!ninaVpnSupported()) return;
    try {
      const st = await ninaVpnGetStatus();
      if (
        busyRef.current &&
        (phaseRef.current === "connecting" ||
          phaseRef.current === "switching" ||
          phaseRef.current === "refreshing")
      ) {
        if (st === "connected") {
          setPhase("connected");
          setHintKey("home.hintTapToDisconnect");
          busyRef.current = false;
        }
        return;
      }
      if (st === "connected") {
        if (phaseRef.current !== "connected" && phaseRef.current !== "disconnecting") {
          setPhase("connected");
          setHintKey("home.hintTapToDisconnect");
        }
      } else if (st === "connecting") {
        if (phaseRef.current === "idle") {
          setPhase("connecting");
        }
      } else if (st === "disconnected" || st === "unavailable") {
        if (phaseRef.current === "connected") {
          setPhase("idle");
          setHintKey(null);
        } else if (
          phaseRef.current === "connecting" ||
          phaseRef.current === "switching" ||
          phaseRef.current === "refreshing"
        ) {
          // Native never reached connected — don't leave UI spinning
          setPhase("idle");
          busyRef.current = false;
        }
      }
    } catch {
      /* ignore */
    }
  }, [t]);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        // Instant UI from cache — never block the connect button on network
        const [cachedServers, cachedCfg, savedId, cachedSub, savedOrder] = await Promise.all([
          loadCachedServers(),
          loadCachedConfig(),
          getSelectedServerId(),
          loadCachedSubscription(),
          loadServerOrder(),
        ]);
        if (!alive) return;
        if (cachedSub) setSub(cachedSub);
        if (cachedCfg) {
          configCache.current = cachedCfg;
          if (!cachedSub && cachedCfg.status) {
            setSub({
              status: cachedCfg.status,
              expires_at: cachedCfg.expires_at ?? null,
              has_config: !!(cachedCfg.nodes?.length || cachedCfg.links?.length),
            });
          }
        }
        if (cachedServers.length) {
          const ordered = applyIdOrder(cachedServers, savedOrder);
          setServers(ordered);
          serversRef.current = ordered;
          if (savedId && ordered.some((r) => r.id === savedId)) {
            setSelectedId(savedId);
            selectedIdRef.current = savedId;
          } else {
            setSelectedId(ordered[0].id);
            selectedIdRef.current = ordered[0].id;
          }
        } else if (savedId) {
          setSelectedId(savedId);
          selectedIdRef.current = savedId;
        }

        await syncNativePhase();
        if (!alive) return;

        await loadVpnPrefs();
        const cachedAllowed =
          !!cachedSub && isSubscriptionActive(cachedSub) && !!cachedSub.has_config;
        void applyTunnelAccess(cachedAllowed);
        if (!cachedAllowed && ninaVpnSupported()) {
          const st = await ninaVpnGetStatus();
          if (st === "connected" || st === "connecting") {
            await ninaVpnDisconnect();
            setPhase("idle");
          }
        }
        if (!alive) return;

        setWelcomeAttempt(0);
        void refreshSub();
        if (serversRef.current.some((s) => !!s.uri)) {
          void refreshPings();
        } else {
          void refreshServers().catch(() => undefined);
        }
      })();
      return () => {
        alive = false;
      };
    }, [refreshServers, refreshSub, refreshPings, syncNativePhase])
  );

  useEffect(() => {
    return ninaVpnAddStatusListener((st) => {
      if (st === "connecting") {
        if (phaseRef.current !== "disconnecting" && phaseRef.current !== "connected") {
          setPhase(phaseRef.current === "switching" ? "switching" : "connecting");
        }
      }
      if (st === "connected") {
        setPhase("connected");
        setHintKey("home.hintTapToDisconnect");
        busyRef.current = false;
      }
      if (st === "disconnected") {
        if (
          phaseRef.current === "connected" ||
          phaseRef.current === "connecting" ||
          phaseRef.current === "switching" ||
          phaseRef.current === "refreshing"
        ) {
          if (phaseRef.current !== "disconnecting") {
            setPhase("idle");
            busyRef.current = false;
          }
        }
      }
    });
  }, [t]);

  // Watchdog: never leave the button stuck on a spinner
  useEffect(() => {
    if (phaseWatchdog.current) {
      clearTimeout(phaseWatchdog.current);
      phaseWatchdog.current = null;
    }
    if (phase !== "connecting" && phase !== "switching" && phase !== "refreshing") return;
    phaseWatchdog.current = setTimeout(() => {
      void (async () => {
        const st = ninaVpnSupported() ? await ninaVpnGetStatus() : "disconnected";
        if (st === "connected") {
          setPhase("connected");
          setHintKey("home.hintTapToDisconnect");
        } else {
          setPhase("idle");
          setHintKey("home.errorConnect");
        }
        busyRef.current = false;
      })();
    }, 25000);
    return () => {
      if (phaseWatchdog.current) clearTimeout(phaseWatchdog.current);
    };
  }, [phase, t]);

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

  useEffect(() => {
    const on = phase === "connected";
    const switching = phase === "switching";
    const fadingOut = phase === "disconnecting";
    lit.value = withTiming(on ? 1 : switching ? 0.4 : 0, {
      duration: fadingOut ? 520 : on ? 640 : switching ? 280 : 480,
      easing: Easing.inOut(Easing.cubic),
    });
    timerVis.value = withTiming(on ? 1 : 0, {
      duration: 300,
      easing: Easing.out(Easing.cubic),
    });
  }, [phase, lit, timerVis]);

  useEffect(() => {
    return () => {
      if (disconnectTimer.current) clearTimeout(disconnectTimer.current);
      if (phaseWatchdog.current) clearTimeout(phaseWatchdog.current);
    };
  }, []);

  const hasAccess = !!sub && isSubscriptionActive(sub) && !!sub.has_config;

  useEffect(() => {
    if (!hasAccess || Platform.OS !== "android") return;
    void ninaVpnRequestQuickTile();
  }, [hasAccess]);

  const subStatus = String(sub?.status || "").toLowerCase();
  const welcomeSettled =
    hasAccess ||
    subStatus === "expired" ||
    subStatus === "cancelled" ||
    welcomeAttempt >= 36;
  const waitingWelcome = subReady && !hasAccess && !welcomeSettled;

  useEffect(() => {
    if (!waitingWelcome) return;
    const timer = setTimeout(() => {
      setWelcomeAttempt((n) => n + 1);
      void refreshSub();
      void refreshServers().catch(() => undefined);
    }, 2500);
    return () => clearTimeout(timer);
  }, [waitingWelcome, welcomeAttempt, refreshSub, refreshServers]);

  // Ring for connect + server switch — never for background refresh
  const spinning = phase === "connecting" || phase === "switching";
  const connected = phase === "connected";
  const showTimer = connected;
  const buttonLit = connected || phase === "disconnecting";

  const onPressIn = () => {
    if (spinning) return;
    pressScale.value = withTiming(0.93, { duration: 90, easing: Easing.out(Easing.quad) });
  };

  const onPressOut = () => {
    pressScale.value = withSequence(
      withSpring(1.06, { damping: 11, stiffness: 220 }),
      withSpring(1, { damping: 14, stiffness: 180 })
    );
  };

  const pressStyle = useAnimatedStyle(() => ({
    transform: [{ scale: pressScale.value }],
  }));

  const glowStyle = useAnimatedStyle(() => ({
    opacity: 0.25 + lit.value * 0.75,
    transform: [{ scale: 0.92 + lit.value * 0.1 }],
  }));

  const litFillStyle = useAnimatedStyle(() => ({
    opacity: lit.value,
  }));

  const offBorderStyle = useAnimatedStyle(() => ({
    opacity: 1 - lit.value,
  }));

  const timerWrapStyle = useAnimatedStyle(() => ({
    opacity: timerVis.value,
    transform: [{ translateY: (1 - timerVis.value) * 6 }],
    height: timerVis.value * 28,
    marginTop: timerVis.value * 6,
    overflow: "hidden" as const,
  }));

  const pickUri = (cfg: ConfigPayload | null, nodeId: string | null) => {
    const list = serversRef.current;
    if (nodeId) {
      const cachedRow = list.find((s) => s.id === nodeId && s.uri);
      if (cachedRow?.uri) {
        return { uri: sanitizeUri(cachedRow.uri), nodeId: cachedRow.id };
      }
      const hit = cfg?.nodes?.find((n) => n.id === nodeId);
      if (hit?.uri) return { uri: sanitizeUri(hit.uri), nodeId: hit.id };
    }
    if (cfg?.nodes?.[0]?.uri) {
      return { uri: sanitizeUri(cfg.nodes[0].uri), nodeId: cfg.nodes[0].id };
    }
    const fromServers = list.find((s) => !!s.uri);
    if (fromServers?.uri) {
      return { uri: sanitizeUri(fromServers.uri), nodeId: fromServers.id };
    }
    const link =
      cfg?.links?.find((L) => L.startsWith("vless://")) ||
      cfg?.links?.[0] ||
      cfg?.subscription_url;
    return link ? { uri: sanitizeUri(link), nodeId: nodeId || "default" } : null;
  };

  const startTunnel = useCallback(
    async (nodeId: string | null) => {
      if (Platform.OS === "web") {
        setHintKey("home.hintNeedApp");
        return false;
      }
      if (!ninaVpnSupported()) {
        setHintKey("home.hintNeedApp");
        return false;
      }

      let s = sub;
      if (!s || !s.has_config || !isSubscriptionActive(s)) {
        const next = await refreshSub();
        if (next) s = next;
      }
      const ok = !!s && !!s.has_config && isSubscriptionActive(s);
      if (!ok) {
        setPhase("idle");
        setHintKey(waitingWelcome ? "home.hintPreparing" : "home.hintBuySub");
        return false;
      }
      setPhase(phaseRef.current === "switching" ? "switching" : "connecting");
      await applyTunnelAccess(true);

      const prepared = await ninaVpnPrepare();
      if (!prepared) {
        setPhase("idle");
        setHintKey("home.vpnPermission");
        return false;
      }

      let cfg = configCache.current;
      let picked = pickUri(cfg, nodeId);
      if (!picked?.uri?.startsWith("vless://")) {
        cfg = await api<ConfigPayload>("/api/v1/subscriptions/me/config", {
          timeoutMs: 20000,
        });
        configCache.current = cfg;
        void saveCachedConfig(cfg);
        picked = pickUri(cfg, nodeId);
      }
      if (!picked?.uri || !picked.uri.startsWith("vless://")) {
        setPhase("idle");
        setHintKey("home.errorConnect");
        return false;
      }

      if (picked.nodeId) {
        setSelectedId(picked.nodeId);
        selectedIdRef.current = picked.nodeId;
        await setSelectedServerId(picked.nodeId);
      }

      await Promise.race([
        ninaVpnConnect(picked.uri, picked.nodeId),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("vpn_connect_timeout")), 25000)
        ),
      ]);
      setPhase("connected");
      setHintKey("home.hintTapToDisconnect");
      void refreshPings();
      return true;
    },
    [refreshSub, refreshPings, sub, t, waitingWelcome]
  );

  const onSelectServer = async (id: string) => {
    if (id === selectedIdRef.current && phaseRef.current === "connected") return;
    if (busyRef.current && (phaseRef.current === "switching" || phaseRef.current === "connecting")) {
      return;
    }

    // Instant visual selection — tunnel catch-up feels smoother
    setSelectedId(id);
    selectedIdRef.current = id;
    void setSelectedServerId(id);

    const live =
      phaseRef.current === "connected" ||
      phaseRef.current === "connecting" ||
      phaseRef.current === "switching" ||
      phaseRef.current === "refreshing";
    if (!live) {
      void refreshPings();
      return;
    }

    busyRef.current = true;
    setHintKey(null);
    setPhase("switching");
    try {
      // Brief beat so the row highlight settles before tunnel tear-down
      await new Promise((r) => setTimeout(r, 180));
      if (selectedIdRef.current !== id) return;
      await startTunnel(id);
    } catch (e: any) {
      setPhase("idle");
      const msg = String(e?.message || e?.code || "");
      if (msg.includes("vpn_permission") || msg.includes("VPN_PERMISSION")) {
        setHintKey("home.vpnPermission");
      } else {
        setHintKey("home.errorConnect");
      }
    } finally {
      busyRef.current = false;
    }
  };

  const onConnect = async () => {
    if (busyRef.current) return;
    if (phase === "disconnecting") return;

    // Allow canceling a stuck/spinning connect by tapping again
    if (phase === "connecting" || phase === "switching" || phase === "refreshing") {
      busyRef.current = true;
      setPhase("disconnecting");
      try {
        await ninaVpnDisconnect();
      } catch {
        /* ignore */
      }
      setPhase("idle");
      setHintKey("home.hintTapToConnect");
      busyRef.current = false;
      void refreshPings();
      return;
    }

    if (phase === "connected") {
      busyRef.current = true;
      setHintKey(null);
      setPhase("disconnecting");
      try {
        await ninaVpnDisconnect();
      } catch {
        /* ignore */
      }
      if (disconnectTimer.current) clearTimeout(disconnectTimer.current);
      disconnectTimer.current = setTimeout(() => {
        setPhase("idle");
        setHintKey("home.hintTapToConnect");
        busyRef.current = false;
        void refreshPings();
      }, 720);
      return;
    }

    if (phase !== "idle") return;

    busyRef.current = true;
    setHintKey(null);

    try {
      await startTunnel(selectedIdRef.current);
    } catch (e: any) {
      setPhase("idle");
      const msg = String(e?.message || e?.code || "");
      if (msg.includes("vpn_permission") || msg.includes("VPN_PERMISSION")) {
        setHintKey("home.vpnPermission");
      } else if (
        msg.includes("vpn_core_missing") ||
        msg.includes("vpn_failed") ||
        msg.includes("VPN_CONNECT")
      ) {
        setHintKey("home.errorConnect");
      } else if (msg.includes("vpn_unavailable")) setHintKey("home.hintNeedApp");
      else if (msg.includes("network_timeout") || msg.includes("timeout")) {
        setHintKey("home.errorConnect");
      } else setHintKey("home.errorConnect");
    } finally {
      busyRef.current = false;
    }
  };

  const label =
    phase === "switching"
      ? t("home.phaseSwitching")
      : phase === "connecting"
        ? t("home.phaseConnecting")
        : phase === "connected"
          ? t("home.phaseConnected")
          : phase === "disconnecting"
            ? t("home.hintDisconnected")
            : t("home.phaseIdle");
  const showBuyWarn =
    subReady && !hasAccess && !waitingWelcome && phase === "idle" && !connected && !spinning;

  return (
    <ScreenBackground>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        <NinaLogo size={26} />

        <View style={styles.connectBlock}>
          <Pressable
            onPress={onConnect}
            onPressIn={onPressIn}
            onPressOut={onPressOut}
            style={styles.connectPress}
            disabled={phase === "disconnecting"}
          >
            <Animated.View style={[styles.pressWrap, pressStyle]}>
              <Animated.View style={[styles.glow, glowStyle]} />
              <SpinRing active={spinning} />
              <View style={styles.connectBtn}>
                <Animated.View
                  style={[styles.connectBtnOff, StyleSheet.absoluteFillObject, offBorderStyle]}
                />
                <Animated.View
                  style={[StyleSheet.absoluteFillObject, styles.litClip, litFillStyle]}
                  pointerEvents="none"
                >
                  <LinearGradient
                    colors={["#7B2FFF", "#9333EA", "#FF2FA0"]}
                    style={StyleSheet.absoluteFillObject}
                  />
                </Animated.View>
                <PhaseLabel text={label} lit={buttonLit} />
                <Animated.View
                  style={[styles.timerWrap, timerWrapStyle]}
                  pointerEvents="none"
                >
                  {(showTimer || phase === "disconnecting") && (
                    <SmoothTimer seconds={elapsed} />
                  )}
                </Animated.View>
              </View>
            </Animated.View>
          </Pressable>
          <Text style={[styles.connectHint, showBuyWarn && styles.connectHintWarn]}>
            {hintKey
              ? t(hintKey)
              : connected
                ? t("home.hintTapToDisconnect")
                : phase === "disconnecting" || spinning
                  ? ""
                  : hasAccess
                    ? t("home.hintTapToConnect")
                    : waitingWelcome
                      ? t("home.hintPreparing")
                      : subReady
                        ? t("home.hintBuySub")
                        : ""}
          </Text>
        </View>

        <Text style={styles.section}>
          <Text style={styles.sectionEmoji}>🌐 </Text>
          {t("home.servers")}
        </Text>
        <GlassCard padded={false} radius={radii.xl} style={styles.group}>
          {servers.length === 0 ? (
            <Pressable style={styles.row} onPress={() => void refreshServers()}>
              <Text style={styles.serverMeta}>{t("servers.empty")}</Text>
            </Pressable>
          ) : (
            servers.map((s, i) => (
              <Pressable key={s.id} onPress={() => void onSelectServer(s.id)}>
                <ServerRowItem
                  flag={s.flag}
                  name={s.name}
                  protocol={s.protocol}
                  pingLabel={
                    s.ping != null ? t("home.pingMs", { n: Math.round(s.ping) }) : "—"
                  }
                  selected={selectedId === s.id}
                  bordered={i < servers.length - 1}
                />
              </Pressable>
            ))
          )}
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
  pressWrap: {
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
    backgroundColor: "rgba(123,47,255,0.42)",
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
    overflow: "hidden",
  },
  litClip: {
    borderRadius: 84,
    overflow: "hidden",
  },
  connectBtnOff: {
    backgroundColor: "rgba(255,255,255,0.06)",
    borderWidth: 1.5,
    borderColor: "rgba(123,47,255,0.28)",
    borderRadius: 84,
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
    paddingHorizontal: 16,
    lineHeight: 17,
  },
  timerWrap: {
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  timerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  timerDigit: {
    minWidth: 10,
    alignItems: "center",
  },
  timerChar: {
    color: "rgba(255,255,255,0.92)",
    fontFamily: fonts.bodyMedium,
    fontSize: 16,
    letterSpacing: 0.6,
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
    minHeight: 20,
  },
  connectHintWarn: {
    color: colors.accentPink,
    fontFamily: fonts.bodyMedium,
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
  group: {
    overflow: "hidden",
    borderRadius: radii.xl,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
    paddingLeft: 14,
    gap: 12,
  },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.hairline,
  },
  selBar: {
    position: "absolute",
    left: 0,
    top: 10,
    bottom: 10,
    width: 3,
    borderRadius: 2,
    backgroundColor: colors.accent,
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
    color: colors.muted,
    minWidth: 52,
    textAlign: "right",
  },
  pingSelected: {
    color: colors.accent,
  },
  checkDot: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1.5,
    borderColor: "rgba(123,47,255,0.55)",
    alignItems: "center",
    justifyContent: "center",
  },
  checkInner: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.accent,
  },
});
