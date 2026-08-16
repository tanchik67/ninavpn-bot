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

export default function GuidesScreen() {
  const { t, locale } = useI18n();

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll}>
        <BackCircleButton
          onPress={() => goBackOr("/(app)/(tabs)/settings")}
          style={styles.backBtn}
        />
        <NinaLogo size={24} />
        <Text style={styles.title}>{t("guides.title")}</Text>
        <Text style={styles.sub}>{t("guides.subtitle")}</Text>
        <GlassCard style={{ gap: 10 }}>
          <Text style={styles.row}>{t("guides.android")}</Text>
          <Text style={styles.soon}>{t("guides.comingSoon")}</Text>
        </GlassCard>
        <PrimaryButton
          label={t("guides.openWeb")}
          variant="secondary"
          onPress={() => Linking.openURL(siteDocUrl("guides", locale))}
          style={{ marginTop: spacing.md }}
        />
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: spacing.screen, paddingTop: 56, paddingBottom: 48 },
  backBtn: { marginBottom: 8 },
  title: { color: colors.text, fontFamily: fonts.displayBold, fontSize: 28, marginTop: 10, marginBottom: 6 },
  sub: { color: colors.muted, fontFamily: fonts.body, marginBottom: spacing.md },
  row: { color: colors.text, fontFamily: fonts.body, lineHeight: 22 },
  soon: { color: colors.muted, fontFamily: fonts.body, lineHeight: 22 },
});
