import { LinearGradient } from "expo-linear-gradient";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  ViewStyle,
} from "react-native";
import { colors, fonts, gradients, radii } from "../lib/theme";

type Props = {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  busy?: boolean;
  style?: ViewStyle;
  variant?: "primary" | "secondary";
};

export function PrimaryButton({
  label,
  onPress,
  disabled,
  busy,
  style,
  variant = "primary",
}: Props) {
  if (variant === "secondary") {
    return (
      <Pressable
        onPress={onPress}
        disabled={disabled || busy}
        style={[styles.secondary, style, (disabled || busy) && { opacity: 0.5 }]}
      >
        {busy ? (
          <ActivityIndicator color={colors.text} />
        ) : (
          <Text style={styles.secondaryText}>{label}</Text>
        )}
      </Pressable>
    );
  }

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || busy}
      style={[style, (disabled || busy) && { opacity: 0.55 }]}
    >
      <LinearGradient colors={[...gradients.button]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.btn}>
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.text}>{label}</Text>
        )}
      </LinearGradient>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    borderRadius: radii.pill,
    paddingVertical: 16,
    paddingHorizontal: 28,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 54,
  },
  text: {
    color: "#fff",
    fontFamily: fonts.bodyBold,
    fontSize: 16,
  },
  secondary: {
    backgroundColor: colors.glassFill,
    borderRadius: radii.pill,
    paddingVertical: 16,
    alignItems: "center",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    minHeight: 54,
    justifyContent: "center",
  },
  secondaryText: {
    color: colors.text,
    fontFamily: fonts.bodyBold,
    fontSize: 16,
  },
});
