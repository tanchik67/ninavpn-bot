import { Pressable, StyleSheet, Text, ViewStyle } from "react-native";
import { useI18n } from "../lib/i18n";
import { colors } from "../lib/theme";

type Props = {
  onPress: () => void;
  style?: ViewStyle;
};

/** Round chevron back control — size fixed, ignores in-app font scale. */
export function BackCircleButton({ onPress, style }: Props) {
  const { t } = useI18n();
  return (
    <Pressable
      onPress={onPress}
      style={[styles.circle, style]}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={t("common.back")}
    >
      <Text style={styles.chevron} allowFontScaling={false} maxFontSizeMultiplier={1}>
        ‹
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  circle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.glassFill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  chevron: {
    color: colors.text,
    fontSize: 28,
    lineHeight: 30,
    marginTop: -2,
    textAlign: "center",
    includeFontPadding: false,
  },
});
