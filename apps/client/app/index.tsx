import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import { useAuth } from "../src/lib/auth";
import { colors } from "../src/lib/theme";

export default function Index() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.accentPink} />
      </View>
    );
  }
  if (user) return <Redirect href="/(app)/home" />;
  return <Redirect href="/(auth)/login" />;
}
