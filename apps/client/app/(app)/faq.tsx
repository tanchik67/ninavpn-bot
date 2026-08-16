import { ScrollView, StyleSheet } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { BackCircleButton } from "../../src/components/BackCircleButton";
import { GlassCard } from "../../src/components/GlassCard";
import { NinaLogo } from "../../src/components/NinaLogo";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { goBackOr } from "../../src/lib/nav";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

export default function FaqScreen() {
  const { t } = useI18n();
  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll}>
        <BackCircleButton
          onPress={() => goBackOr("/(app)/(tabs)/settings")}
          style={styles.backBtn}
        />
        <NinaLogo size={24} />
        <Text style={styles.title}>{t("faq.title")}</Text>
        <GlassCard style={styles.card}>
          <Text style={styles.q}>{t("faq.q1")}</Text>
          <Text style={styles.a}>{t("faq.a1")}</Text>
        </GlassCard>
        <GlassCard style={styles.card}>
          <Text style={styles.q}>{t("faq.q2")}</Text>
          <Text style={styles.a}>{t("faq.a2")}</Text>
        </GlassCard>
        <GlassCard style={styles.card}>
          <Text style={styles.q}>{t("faq.q3")}</Text>
          <Text style={styles.a}>{t("faq.a3")}</Text>
        </GlassCard>
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: spacing.screen, paddingTop: 56, paddingBottom: 48, gap: 10 },
  backBtn: { marginBottom: 8 },
  title: { color: colors.text, fontFamily: fonts.displayBold, fontSize: 28, marginTop: 10, marginBottom: 8 },
  card: { gap: 6 },
  q: { color: colors.text, fontFamily: fonts.bodySemi, fontSize: 16 },
  a: { color: colors.muted, fontFamily: fonts.body, lineHeight: 21 },
});
