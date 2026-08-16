import * as Linking from "expo-linking";
import { ScrollView, StyleSheet } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { BackCircleButton } from "../../src/components/BackCircleButton";
import { GlassCard } from "../../src/components/GlassCard";
import { NinaLogo } from "../../src/components/NinaLogo";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { goBackOr } from "../../src/lib/nav";
import { useI18n } from "../../src/lib/i18n";
import { siteDocUrl } from "../../src/lib/siteDocs";
import { colors, fonts, spacing } from "../../src/lib/theme";

export default function AboutScreen() {
  const { t, locale } = useI18n();

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll}>
        <BackCircleButton
          onPress={() => goBackOr("/(app)/(tabs)/settings")}
          style={styles.backBtn}
        />
        <NinaLogo size={24} />
        <Text style={styles.title}>{t("about.title")}</Text>
        <GlassCard>
          <Text style={styles.body}>{t("about.body")}</Text>
          <Text style={styles.ver}>{t("about.version")}</Text>
        </GlassCard>
        <PrimaryButton
          label={t("about.trust")}
          variant="secondary"
          onPress={() => Linking.openURL(siteDocUrl("howWeWork", locale))}
          style={{ marginTop: spacing.md }}
        />
        <PrimaryButton
          label={t("about.security")}
          variant="secondary"
          onPress={() => Linking.openURL(siteDocUrl("security", locale))}
          style={{ marginTop: spacing.sm }}
        />
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: spacing.screen, paddingTop: 56, paddingBottom: 48 },
  backBtn: { marginBottom: 8 },
  title: { color: colors.text, fontFamily: fonts.displayBold, fontSize: 28, marginTop: 10, marginBottom: 12 },
  body: { color: colors.text, fontFamily: fonts.body, lineHeight: 22 },
  ver: { color: colors.muted, fontFamily: fonts.body, marginTop: 12, fontSize: 13 },
});
