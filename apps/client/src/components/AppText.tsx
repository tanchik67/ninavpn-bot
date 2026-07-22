import {
  StyleSheet,
  Text as RNText,
  TextInput as RNTextInput,
  type TextInputProps,
  type TextProps,
} from "react-native";
import { useFontScale } from "../lib/textSize";

function scaleStyle(style: TextProps["style"], scale: number) {
  const flat = StyleSheet.flatten(style);
  if (!flat || typeof flat.fontSize !== "number") return style;
  const next: Record<string, unknown> = {
    fontSize: Math.round(flat.fontSize * scale * 10) / 10,
  };
  if (typeof flat.lineHeight === "number") {
    next.lineHeight = Math.round(flat.lineHeight * scale * 10) / 10;
  }
  return [style, next];
}

/** Drop-in Text that respects the in-app text size setting. */
export function AppText({ style, allowFontScaling = false, ...rest }: TextProps) {
  const scale = useFontScale();
  return (
    <RNText
      {...rest}
      allowFontScaling={allowFontScaling}
      style={scaleStyle(style, scale)}
    />
  );
}

/** Drop-in TextInput that respects the in-app text size setting. */
export function AppTextInput({
  style,
  allowFontScaling = false,
  ...rest
}: TextInputProps) {
  const scale = useFontScale();
  return (
    <RNTextInput
      {...rest}
      allowFontScaling={allowFontScaling}
      style={scaleStyle(style, scale)}
    />
  );
}
