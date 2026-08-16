import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { BackCircleButton } from "../../src/components/BackCircleButton";
import { GlassCard } from "../../src/components/GlassCard";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import {
  ConnectionProfileId,
  loadConnectionProfile,
  saveConnectionProfile,
} from "../../src/lib/connectionProfile";
import { goBackOr } from "../../src/lib/nav";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

type ApiProfile = {
  id: string;
  name_en: string;
  name_ru: string;
  description_en: string;
  description_ru: string;
};

export default function ConnectionProfilesScreen() {
  const { t, locale } = useI18n();
  const [selected, setSelected] = useState<ConnectionProfileId>("low_latency");
  const [profiles, setProfiles] = useState<ApiProfile[]>([]);
  const [msg, setMsg] = useState("");

  useFocusEffect(
    useCallback(() => {
      loadConnectionProfile().then(setSelected);
      api<ApiProfile[]>("/api/v1/network/profiles", { auth: false })
        .then(setProfiles)
        .catch(() => setProfiles([]));
    }, [])
  );

  const pick = async (id: string) => {
    if (id !== "low_latency" && id !== "streaming" && id !== "max_stealth") return;
    setSelected(id);
    await saveConnectionProfile(id);
    setMsg(t("profiles.saved"));
  };

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll}>
        <BackCircleButton
          onPress={() => goBackOr("/(app)/(tabs)/settings")}
          style={styles.backBtn}
        />
        <Text style={styles.title}>{t("profiles.title")}</Text>
        <Text style={styles.sub}>{t("profiles.subtitle")}</Text>
        {!!msg && <Text style={styles.ok}>{msg}</Text>}
        {profiles.map((p) => {
          const name = locale === "ru" ? p.name_ru : p.name_en;
          const desc = locale === "ru" ? p.description_ru : p.description_en;
          const active = selected === p.id;
          return (
            <Pressable key={p.id} onPress={() => pick(p.id)}>
              <GlassCard style={active ? { ...styles.card, ...styles.cardActive } : styles.card}>
                <View style={styles.row}>
                  <Text style={styles.name}>{name}</Text>
                  {active ? <Text style={styles.check}>✓</Text> : null}
                </View>
                <Text style={styles.desc}>{desc}</Text>
              </GlassCard>
            </Pressable>
          );
        })}
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: spacing.screen, paddingTop: 56, paddingBottom: 48, gap: 10 },
  backBtn: { marginBottom: 8 },
  title: { color: colors.text, fontFamily: fonts.displayBold, fontSize: 28 },
  sub: { color: colors.muted, fontFamily: fonts.body, marginBottom: 8 },
  ok: { color: colors.accent, fontFamily: fonts.body, marginBottom: 4 },
  card: { gap: 6 },
  cardActive: { borderColor: colors.accent, borderWidth: 1 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  name: { color: colors.text, fontFamily: fonts.bodySemi, fontSize: 16 },
  check: { color: colors.accent, fontFamily: fonts.bodyBold },
  desc: { color: colors.muted, fontFamily: fonts.body, lineHeight: 20 },
});
