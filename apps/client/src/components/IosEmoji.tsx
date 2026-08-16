import {
  Image,
  ImageStyle,
  Platform,
  StyleProp,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from "react-native";
import { resolveEmojiAsset } from "../lib/emojiAssets";

type Props = {
  emoji: string;
  size?: number;
  style?: StyleProp<ViewStyle>;
  imageStyle?: StyleProp<ImageStyle>;
};

/**
 * Apple-style emoji from bundled PNGs (offline). Falls back to system glyph
 * only when the character has no asset (e.g. fullwidth plus).
 */
export function IosEmoji({ emoji, size = 24, style, imageStyle }: Props) {
  if (!emoji) return null;
  const src = resolveEmojiAsset(emoji);

  if (!src) {
    return (
      <View
        style={[
          { width: size, height: size, alignItems: "center", justifyContent: "center" },
          style,
        ]}
      >
        <Text
          style={{
            fontSize: size * 0.9,
            lineHeight: size,
            textAlign: "center",
            includeFontPadding: false,
            fontFamily: Platform.select({
              ios: "System",
              android: undefined,
              default: undefined,
            }),
          }}
          allowFontScaling={false}
        >
          {emoji}
        </Text>
      </View>
    );
  }

  return (
    <View style={[{ width: size, height: size }, style]}>
      <Image
        source={src}
        style={[styles.img, { width: size, height: size }, imageStyle]}
        accessibilityIgnoresInvertColors
      />
    </View>
  );
}

const styles = StyleSheet.create({
  img: { resizeMode: "contain" },
});
