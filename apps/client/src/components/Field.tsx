import { StyleSheet, Text, TextInput, TextInputProps, View } from "react-native";
import { colors, fonts, radii } from "../lib/theme";

type Props = TextInputProps & { label?: string };

export function Field({ label, style, ...rest }: Props) {
  return (
    <View style={styles.wrap}>
      {!!label && <Text style={styles.label}>{label}</Text>}
      <TextInput
        placeholderTextColor={colors.muted}
        style={[styles.input, style]}
        {...rest}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  label: {
    color: colors.muted,
    fontSize: 13,
    fontFamily: fonts.bodySemi,
  },
  input: {
    backgroundColor: colors.glassFill,
    borderColor: colors.glassBorder,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radii.md,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: colors.text,
    fontSize: 16,
    fontFamily: fonts.body,
  },
});
