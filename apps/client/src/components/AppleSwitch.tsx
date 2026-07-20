import { Pressable, StyleSheet } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from "react-native-reanimated";
import { useEffect } from "react";

type Props = {
  value: boolean;
  onChange: (v: boolean) => void;
};

/** Apple-like iOS switch — green track when on, soft spring thumb. */
export function AppleSwitch({ value, onChange }: Props) {
  const progress = useSharedValue(value ? 1 : 0);

  useEffect(() => {
    progress.value = withSpring(value ? 1 : 0, {
      damping: 18,
      stiffness: 220,
      mass: 0.7,
    });
  }, [value, progress]);

  const trackStyle = useAnimatedStyle(() => ({
    backgroundColor: progress.value > 0.5 ? "#34C759" : "rgba(120,120,128,0.32)",
  }));

  const thumbStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: 2 + progress.value * 20 }],
  }));

  return (
    <Pressable
      onPress={() => onChange(!value)}
      hitSlop={8}
      accessibilityRole="switch"
      accessibilityState={{ checked: value }}
    >
      <Animated.View style={[styles.track, trackStyle]}>
        <Animated.View style={[styles.thumb, thumbStyle]} />
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  track: {
    width: 51,
    height: 31,
    borderRadius: 16,
    justifyContent: "center",
  },
  thumb: {
    width: 27,
    height: 27,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
});
