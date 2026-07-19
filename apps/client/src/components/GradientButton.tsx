import { LinearGradient } from "expo-linear-gradient";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  ViewStyle,
} from "react-native";
import { colors, gradients, radii } from "../lib/theme";

type Props = {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  busy?: boolean;
  style?: ViewStyle;
  variant?: "primary" | "ghost";
};

export function GradientButton({
  label,
  onPress,
  disabled,
  busy,
  style,
  variant = "primary",
}: Props) {
  if (variant === "ghost") {
    return (
      <Pressable
        onPress={onPress}
        disabled={disabled || busy}
        style={[styles.ghost, style, (disabled || busy) && { opacity: 0.5 }]}
      >
        {busy ? (
          <ActivityIndicator color={colors.text} />
        ) : (
          <Text style={styles.ghostText}>{label}</Text>
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
      <LinearGradient
        colors={[...gradients.connect]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.btn}
      >
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
    fontWeight: "800",
    fontSize: 16,
    letterSpacing: 0.4,
  },
  ghost: {
    borderRadius: radii.pill,
    paddingVertical: 14,
    paddingHorizontal: 24,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.glassBorder,
    backgroundColor: colors.surface,
  },
  ghostText: {
    color: colors.text,
    fontWeight: "700",
    fontSize: 15,
  },
});
