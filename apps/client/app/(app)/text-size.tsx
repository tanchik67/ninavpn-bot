import { goBackOr } from "../../src/lib/nav";
import { useCallback, useRef, useState } from "react";
import {
  LayoutChangeEvent,
  PanResponder,
  Pressable,
  StyleSheet,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppText as Text } from "../../src/components/AppText";
import { AppleSwitch } from "../../src/components/AppleSwitch";
import { GlassCard } from "../../src/components/GlassCard";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { useI18n } from "../../src/lib/i18n";
import { getDockClearance, useFontScale, useTextSize } from "../../src/lib/textSize";
import { colors, fonts, radii, spacing } from "../../src/lib/theme";

export default function TextSizeScreen() {
  const { t } = useI18n();
  const scale = useFontScale();
  const insets = useSafeAreaInsets();
  const { step, largerSizes, maxStep, setStep, setLargerSizes } = useTextSize();
  const [trackW, setTrackW] = useState(0);
  const trackWRef = useRef(0);
  const bottomClearance = getDockClearance(scale, insets.bottom);

  const onTrackLayout = (e: LayoutChangeEvent) => {
    const w = e.nativeEvent.layout.width;
    trackWRef.current = w;
    setTrackW(w);
  };

  const pickFromX = useCallback(
    (x: number) => {
      const w = trackWRef.current;
      if (w <= 0) return;
      const ratio = Math.max(0, Math.min(1, x / w));
      const idx = Math.round(ratio * maxStep);
      setStep(idx);
    },
    [maxStep, setStep]
  );

  const panHandlers = PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: (e) => pickFromX(e.nativeEvent.locationX),
    onPanResponderMove: (e) => pickFromX(e.nativeEvent.locationX),
  }).panHandlers;

  const thumbLeft =
    trackW > 0 && maxStep > 0 ? (step / maxStep) * trackW : 0;

  return (
    <ScreenBackground>
      <View style={[styles.wrap, { paddingBottom: bottomClearance }]}>
        <View style={styles.header}>
          <Pressable
            onPress={() => goBackOr("/(app)/(tabs)/settings")}
            style={styles.backCircle}
            hitSlop={8}
            accessibilityLabel={t("common.back")}
          >
            <Text style={styles.backChevron}>‹</Text>
          </Pressable>
          <Text style={styles.title}>{t("textSize.title")}</Text>
          <View style={styles.headerSpacer} />
        </View>

        <GlassCard padded={false}>
          <View style={styles.toggleRow}>
            <Text style={styles.toggleLabel}>{t("textSize.largerSizes")}</Text>
            <AppleSwitch value={largerSizes} onChange={setLargerSizes} />
          </View>
        </GlassCard>

        <View style={styles.flex} />

        <GlassCard style={styles.sliderCard}>
          <View style={styles.sliderRow}>
            <Text style={styles.aSmall}>A</Text>
            <View
              style={styles.trackHit}
              onLayout={onTrackLayout}
              {...panHandlers}
            >
              <View style={styles.trackLine} />
              <View style={styles.dotsRow} pointerEvents="none">
                {Array.from({ length: maxStep + 1 }).map((_, i) => (
                  <View key={i} style={styles.dot} />
                ))}
              </View>
              {trackW > 0 && (
                <View
                  pointerEvents="none"
                  style={[
                    styles.thumb,
                    { left: Math.max(0, thumbLeft - 14) },
                  ]}
                />
              )}
            </View>
            <Text style={styles.aLarge}>A</Text>
          </View>
        </GlassCard>
      </View>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    paddingHorizontal: spacing.screen,
    paddingTop: 56,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.lg,
  },
  backCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.glassFill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  backChevron: {
    color: colors.text,
    fontSize: 28,
    marginTop: -2,
    fontFamily: fonts.body,
  },
  title: {
    color: colors.text,
    fontSize: 17,
    fontFamily: fonts.bodySemi,
  },
  headerSpacer: { width: 36 },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 52,
  },
  toggleLabel: {
    color: colors.text,
    fontSize: 16,
    fontFamily: fonts.body,
    flex: 1,
    paddingRight: 12,
  },
  flex: { flex: 1 },
  sliderCard: {
    paddingVertical: 22,
    paddingHorizontal: 16,
  },
  sliderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  aSmall: {
    color: colors.text,
    fontSize: 13,
    fontFamily: fonts.bodySemi,
    width: 18,
    textAlign: "center",
  },
  aLarge: {
    color: colors.text,
    fontSize: 26,
    fontFamily: fonts.bodySemi,
    width: 28,
    textAlign: "center",
  },
  trackHit: {
    flex: 1,
    height: 44,
    justifyContent: "center",
  },
  trackLine: {
    position: "absolute",
    left: 0,
    right: 0,
    height: StyleSheet.hairlineWidth * 2,
    backgroundColor: "rgba(255,255,255,0.22)",
    borderRadius: 1,
  },
  dotsRow: {
    position: "absolute",
    left: 0,
    right: 0,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  dot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: "rgba(255,255,255,0.45)",
  },
  thumb: {
    position: "absolute",
    width: 28,
    height: 28,
    borderRadius: radii.sm,
    backgroundColor: "#FFFFFF",
    shadowColor: "#000",
    shadowOpacity: 0.35,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
});
