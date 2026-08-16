import { Image, StyleSheet, View } from "react-native";

/** Matches native splash: black screen + centered NINAVPN mark. */
export function BrandSplash() {
  return (
    <View style={styles.root}>
      <Image
        source={require("../../assets/splash-icon.png")}
        style={styles.logo}
        resizeMode="contain"
        accessibilityLabel="NinaVPN"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#000000",
    alignItems: "center",
    justifyContent: "center",
  },
  logo: {
    width: "78%",
    maxWidth: 360,
    aspectRatio: 1,
  },
});
