export const colors = {
  bg: "#060608",
  surface: "#0d0d14",
  card: "#111120",
  bgCard: "#111120",
  glass: "rgba(255,255,255,0.06)",
  glassFill: "rgba(255,255,255,0.07)",
  glassBorder: "rgba(123,47,255,0.18)",
  hairline: "rgba(255,255,255,0.12)",
  text: "#F0EEFF",
  muted: "#6B6B8A",
  accent: "#7B2FFF",
  accentLight: "#A78BFA",
  accent2: "#FF2FA0",
  accent3: "#2FF0D4",
  accentGlow: "rgba(123,47,255,0.28)",
  accentPink: "#FF2FA0",
  accentTeal: "#2FF0D4",
  success: "#4ADE80",
  danger: "#ff6b8a",
  border: "rgba(123,47,255,0.18)",
};

export const materials = {
  blur: 48,
  blurSoft: 28,
  glassOpacity: 0.72,
};

export const gradients = {
  purple: ["#7B2FFF", "#A78BFA"] as const,
  button: ["#7B2FFF", "#FF2FA0"] as const,
  connect: ["#7B2FFF", "#9333EA"] as const,
  brand: ["#7B2FFF", "#FF2FA0"] as const,
  glow: ["rgba(123,47,255,0.22)", "rgba(123,47,255,0)"] as const,
  screen: ["#060608", "#0a0812", "#060608"] as const,
};

export const radii = {
  sm: 12,
  md: 16,
  lg: 20,
  xl: 28,
  pill: 999,
};

/** Apple-like 8pt spacing scale */
export const spacing = {
  xs: 8,
  sm: 12,
  md: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
  screen: 20,
};

export const fonts = {
  display: "Unbounded_900Black",
  displayBold: "Unbounded_700Bold",
  displayRegular: "Unbounded_400Regular",
  body: "Onest_400Regular",
  bodyMedium: "Onest_500Medium",
  bodySemi: "Onest_600SemiBold",
  bodyBold: "Onest_700Bold",
};

export const typography = {
  display: {
    fontFamily: fonts.display,
    fontSize: 34,
    letterSpacing: -0.8,
    color: colors.text,
  },
  title: {
    fontFamily: fonts.displayBold,
    fontSize: 28,
    letterSpacing: -0.5,
    color: colors.text,
  },
  titleSmall: {
    fontFamily: fonts.displayBold,
    fontSize: 22,
    letterSpacing: -0.3,
    color: colors.text,
  },
  body: {
    fontFamily: fonts.body,
    fontSize: 16,
    lineHeight: 22,
    color: colors.text,
  },
  bodyMedium: {
    fontFamily: fonts.bodyMedium,
    fontSize: 16,
    lineHeight: 22,
    color: colors.text,
  },
  caption: {
    fontFamily: fonts.body,
    fontSize: 13,
    lineHeight: 18,
    color: colors.muted,
  },
  label: {
    fontFamily: fonts.bodySemi,
    fontSize: 13,
    color: colors.muted,
  },
};
