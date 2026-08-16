import { goBackOr } from "../../src/lib/nav";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppText as Text } from "../../src/components/AppText";
import { BackCircleButton } from "../../src/components/BackCircleButton";
import { GlassCard } from "../../src/components/GlassCard";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { useI18n, type Locale } from "../../src/lib/i18n";
import { getDockClearance, useFontScale } from "../../src/lib/textSize";
import { colors, fonts, spacing } from "../../src/lib/theme";

const OPTIONS: { id: Locale; labelKey: string }[] = [
  { id: "ru", labelKey: "language.ru" },
  { id: "en", labelKey: "language.en" },
  { id: "es", labelKey: "language.es" },
  { id: "tr", labelKey: "language.tr" },
  { id: "fa", labelKey: "language.fa" },
  { id: "zh", labelKey: "language.zh" },
];

export default function LanguageScreen() {
  const { locale, setLocale, t } = useI18n();
  const scale = useFontScale();
  const insets = useSafeAreaInsets();
  const bottomPad = getDockClearance(scale, insets.bottom);

  return (
    <ScreenBackground>
      <ScrollView
        contentContainerStyle={[styles.scroll, { paddingBottom: bottomPad }]}
      >
        <View style={styles.header}>
          <BackCircleButton onPress={() => goBackOr("/(app)/(tabs)/settings")} />
          <Text style={styles.title}>{t("language.title")}</Text>
          <View style={styles.headerSpacer} />
        </View>

        <GlassCard padded={false} style={{ marginTop: spacing.md }}>
          {OPTIONS.map((opt, i) => {
            const selected = locale === opt.id;
            const last = i === OPTIONS.length - 1;
            return (
              <Pressable
                key={opt.id}
                style={[styles.row, !last && styles.rowBorder]}
                onPress={() => setLocale(opt.id)}
              >
                <Text style={styles.label}>{t(opt.labelKey)}</Text>
                {selected ? <Text style={styles.check}>✓</Text> : null}
              </Pressable>
            );
          })}
        </GlassCard>
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: spacing.screen,
    paddingTop: 56,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.lg,
  },
  title: {
    color: colors.text,
    fontSize: 17,
    fontFamily: fonts.bodySemi,
  },
  headerSpacer: { width: 36 },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  rowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.hairline,
  },
  label: {
    color: colors.text,
    fontSize: 16,
    fontFamily: fonts.body,
  },
  check: {
    color: colors.accent,
    fontSize: 18,
    fontFamily: fonts.bodyBold,
  },
});
