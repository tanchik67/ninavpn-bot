import { Redirect } from "expo-router";
import { BrandSplash } from "../src/components/BrandSplash";
import { useAuth } from "../src/lib/auth";

export default function Index() {
  const { user, loading } = useAuth();
  if (loading) return <BrandSplash />;
  if (user) return <Redirect href="/(app)/(tabs)/home" />;
  return <Redirect href="/(auth)/welcome" />;
}
