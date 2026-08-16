import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { BackCircleButton } from "../../src/components/BackCircleButton";
import { GlassCard } from "../../src/components/GlassCard";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { formatApiError } from "../../src/lib/apiErrors";
import { goBackOr } from "../../src/lib/nav";
import { useI18n } from "../../src/lib/i18n";
import {
  loadCachedServers,
  saveCachedServers,
  type CachedServerRow,
} from "../../src/lib/serverCache";
import {
  getSelectedServerId,
  setSelectedServerId,
} from "../../src/lib/selectedServer";
import { colors, fonts, spacing } from "../../src/lib/theme";

type Loc = {
  id: string;
  flag: string;
  city: string;
  country: string;
  region: string;
  protocol: string;
  status: string;
  latency_ms?: number | null;
};

function toRows(locs: Loc[]): CachedServerRow[] {
  return locs.map((l) => ({
    id: l.id,
    flag: l.flag || "🌐",
    name: l.city,
    protocol: l.protocol || "VLESS",
    ping: typeof l.latency_ms === "number" ? l.latency_ms : null,
  }));
}

export default function ServersScreen() {
  const { t } = useI18n();
  const [rows, setRows] = useState<Loc[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        // Instant paint from home cache
        const cached = await loadCachedServers();
        const saved = await getSelectedServerId();
        if (!alive) return;
        if (cached.length) {
          setRows(
            cached.map((c) => ({
              id: c.id,
              flag: c.flag,
              city: c.name,
              country: "",
              region: "",
              protocol: c.protocol,
              status: "online",
              latency_ms: c.ping,
            }))
          );
          setLoading(false);
          if (saved && cached.some((r) => r.id === saved)) setSelectedId(saved);
          else setSelectedId(cached[0]?.id ?? null);
        } else {
          setLoading(true);
        }

        try {
          const data = await api<Loc[]>("/api/v1/network/locations", {
            auth: false,
            timeoutMs: 12000,
            retries: 1,
          });
          if (!alive) return;
          setRows(data || []);
          setError("");
          if (data?.length) void saveCachedServers(toRows(data));
          if (saved && data?.some((r) => r.id === saved)) setSelectedId(saved);
          else if (data?.[0]) {
            setSelectedId(data[0].id);
            await setSelectedServerId(data[0].id);
          }
        } catch (e: unknown) {
          if (!alive) return;
          if (!cached.length) {
            setError(formatApiError(e, t("servers.empty")));
          }
        } finally {
          if (alive) setLoading(false);
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
        <BackCircleButton
          onPress={() => goBackOr("/(app)/(tabs)/settings")}
          style={styles.backBtn}
        />
        <Text style={styles.title}>{t("servers.title")}</Text>
        <Text style={styles.sub}>{t("servers.subtitle")}</Text>
        {loading && !rows.length && <ActivityIndicator color={colors.accent} />}
        {!!error && <Text style={styles.error}>{error}</Text>}
        {rows.map((l) => (
          <Pressable
            key={l.id}
            onPress={async () => {
              setSelectedId(l.id);
              await setSelectedServerId(l.id);
            }}
          >
            <GlassCard
              style={[styles.card, selectedId === l.id && styles.cardSelected]}
            >
              <View style={styles.row}>
                <Text style={styles.flag}>{l.flag}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.city}>
                    {l.city}
                    {l.country ? <Text style={styles.muted}> · {l.country}</Text> : null}
                  </Text>
                  <Text style={styles.muted} numberOfLines={2}>
                    {[l.region, l.protocol].filter(Boolean).join(" · ")}
                  </Text>
                </View>
                <View style={{ alignItems: "flex-end", gap: 4 }}>
                  <Text
                    style={
                      l.status === "online" ? styles.online : styles.offline
                    }
                  >
                    {l.status === "online"
                      ? t("servers.online")
                      : t("servers.offline")}
                  </Text>
                  <Text style={styles.ping}>
                    {typeof l.latency_ms === "number"
                      ? t("home.pingMs", { n: Math.round(l.latency_ms) })
                      : "—"}
                  </Text>
                </View>
              </View>
            </GlassCard>
          </Pressable>
        ))}
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: spacing.screen, paddingTop: 56, paddingBottom: 48, gap: 10 },
  backBtn: { marginBottom: 8 },
  title: { color: colors.text, fontFamily: fonts.displayBold, fontSize: 28 },
  sub: { color: colors.muted, fontFamily: fonts.body, marginBottom: 8 },
  card: { paddingVertical: 14 },
  cardSelected: { borderColor: colors.accent, borderWidth: StyleSheet.hairlineWidth },
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  flag: { fontSize: 28 },
  city: { color: colors.text, fontFamily: fonts.bodySemi, fontSize: 16 },
  muted: { color: colors.muted, fontFamily: fonts.body, fontSize: 13 },
  online: { color: "#4ade80", fontFamily: fonts.bodySemi, fontSize: 12 },
  offline: { color: colors.muted, fontFamily: fonts.bodySemi, fontSize: 12 },
  ping: { color: colors.accent, fontFamily: fonts.bodySemi, fontSize: 13 },
  error: { color: colors.danger, fontFamily: fonts.body },
});
