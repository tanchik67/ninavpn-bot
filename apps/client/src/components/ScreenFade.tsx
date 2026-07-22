import { useFocusEffect } from "expo-router";
import { ReactNode, useCallback } from "react";
import { StyleSheet } from "react-native";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

type Props = {
  children: ReactNode;
  /** Slightly longer for stack pushes; tabs can use default */
  duration?: number;
};

/**
 * Soft fade/slide-in whenever a screen gains focus (tabs + stack).
 * Complements native stack/tab animations, especially on web.
 */
export function ScreenFade({ children, duration = 320 }: Props) {
  const opacity = useSharedValue(0);
  const translateY = useSharedValue(10);

  useFocusEffect(
    useCallback(() => {
      opacity.value = 0;
      translateY.value = 10;
      opacity.value = withTiming(1, {
        duration,
        easing: Easing.out(Easing.cubic),
      });
      translateY.value = withTiming(0, {
        duration,
        easing: Easing.out(Easing.cubic),
      });
      // No fade-out on blur — native stack/tab animations handle exit
    }, [duration, opacity, translateY])
  );

  const style = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }],
  }));

  return <Animated.View style={[styles.fill, style]}>{children}</Animated.View>;
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
});
