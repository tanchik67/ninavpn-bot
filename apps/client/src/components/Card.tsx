import { StyleSheet, ViewStyle } from "react-native";
import { GlassCard } from "./GlassCard";

/** Alias to GlassCard for screens still importing Card. */
export function Card({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: ViewStyle;
}) {
  return <GlassCard style={style}>{children}</GlassCard>;
}
