import { useFocusEffect } from "expo-router";
import { ReactNode, useCallback, useRef } from "react";
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

const EASE = Easing.bezier(0.22, 1, 0.36, 1);

/**
 * Soft fade/slide-in on first mount; a gentler settle when the screen is focused again
 * (tab return / stack pop) so content does not blink from zero.
 */
export function ScreenFade({ children, duration = 340 }: Props) {
  const opacity = useSharedValue(0);
  const translateY = useSharedValue(10);
  const first = useRef(true);

  useFocusEffect(
    useCallback(() => {
      const isFirst = first.current;
      first.current = false;
      const fromOp = isFirst ? 0 : 0.94;
      const fromY = isFirst ? 8 : 3;
      const dur = isFirst ? duration : Math.round(duration * 0.68);
      opacity.value = fromOp;
      translateY.value = fromY;
      opacity.value = withTiming(1, { duration: dur, easing: EASE });
      translateY.value = withTiming(0, { duration: dur + 40, easing: EASE });
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
