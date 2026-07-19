import { router } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { api } from "../../src/lib/api";
import { useAuth } from "../../src/lib/auth";
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
  const { user, logout } = useAuth();
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

  const buy = (planKey: string) => {
    router.push({ pathname: "/(app)/pay", params: { plan_key: planKey } });
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <Text style={styles.hello}>Привет, {user?.email}</Text>
      {!!error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={plans}
        keyExtractor={(p) => p.id}
        contentContainerStyle={{ gap: 12, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.name}>{item.name}</Text>
            <Text style={styles.desc}>{item.description}</Text>
            <Text style={styles.price}>{item.price_rub} ₽</Text>
            <Pressable style={styles.btn} onPress={() => buy(item.plan_key)}>
              <Text style={styles.btnText}>Оформить</Text>
            </Pressable>
          </View>
        )}
      />
      <Pressable onPress={logout}>
        <Text style={styles.logout}>Выйти</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 20 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: colors.bg },
  hello: { color: colors.muted, marginBottom: 16 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: colors.border,
  },
  name: { color: colors.text, fontSize: 22, fontWeight: "700" },
  desc: { color: colors.muted, marginTop: 6 },
  price: { color: colors.accent, fontSize: 28, fontWeight: "800", marginVertical: 12 },
  btn: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
  },
  btnText: { color: colors.bg, fontWeight: "700" },
  logout: { color: colors.muted, textAlign: "center", marginTop: 8 },
  error: { color: colors.danger, marginBottom: 8 },
});
