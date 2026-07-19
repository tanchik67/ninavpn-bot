import { router } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { BrandMark } from "../../src/components/BrandMark";
import { GlassCard } from "../../src/components/GlassCard";
import { GradientButton } from "../../src/components/GradientButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { colors } from "../../src/lib/theme";

type Plan = {
  id: string;
  plan_key: string;
  name: string;
  description?: string;
  months: number;
  devices: number;
  price_rub: number;
};

export default function PlansScreen() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const data = await api<Plan[]>("/api/v1/plans", { auth: false });
        setPlans(data);
      } catch (e: any) {
        setError(e?.message || "Не удалось загрузить тарифы");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <BrandMark size={26} />
        <Text style={styles.title}>Plans</Text>
        <Text style={styles.sub}>Выберите тариф — конфиг появится на Home</Text>
        {loading ? (
          <ActivityIndicator color={colors.accentPink} style={{ marginTop: 40 }} />
        ) : (
          <FlatList
            data={plans}
            keyExtractor={(p) => p.id}
            contentContainerStyle={{ gap: 12, paddingBottom: 40, paddingTop: 8 }}
            ListHeaderComponent={!!error ? <Text style={styles.error}>{error}</Text> : null}
            renderItem={({ item, index }) => (
              <GlassCard>
                <View style={styles.row}>
                  <Text style={styles.flag}>{["🇩🇪", "🇺🇸", "🇫🇷", "🇳🇱", "🇬🇧"][index % 5]}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.name}>{item.name}</Text>
                    <Text style={styles.desc}>
                      {item.description || `${item.months} мес · ${item.devices} устр.`}
                    </Text>
                  </View>
                  <Text style={styles.price}>{item.price_rub} ₽</Text>
                </View>
                <GradientButton
                  label="Оформить"
                  onPress={() =>
                    router.push({ pathname: "/(app)/pay", params: { plan_key: item.plan_key } })
                  }
                />
              </GlassCard>
            )}
          />
        )}
      </View>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 20, paddingTop: 56 },
  title: { color: colors.text, fontSize: 28, fontWeight: "900", marginTop: 8 },
  sub: { color: colors.muted, marginBottom: 8 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 14 },
  flag: { fontSize: 28 },
  name: { color: colors.text, fontSize: 18, fontWeight: "800" },
  desc: { color: colors.muted, marginTop: 2, fontSize: 13 },
  price: { color: colors.accentTeal, fontWeight: "900", fontSize: 18 },
  error: { color: colors.danger, marginBottom: 8 },
});
