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
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { colors, fonts, spacing } from "../../src/lib/theme";

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
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.back}>‹ Назад</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>Тарифы</ScreenTitle>
        <Text style={styles.sub}>Выберите план — конфиг появится на главной</Text>
        {loading ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 40 }} />
        ) : (
          <FlatList
            data={plans}
            keyExtractor={(p) => p.id}
            contentContainerStyle={{ gap: 12, paddingBottom: 100, paddingTop: 8 }}
            ListHeaderComponent={!!error ? <Text style={styles.error}>{error}</Text> : null}
            renderItem={({ item, index }) => (
              <GlassCard>
                <View style={styles.row}>
                  <Text style={styles.flag}>
                    {["🇩🇪", "🇺🇸", "🇫🇷", "🇳🇱", "🇬🇧"][index % 5]}
                  </Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.name}>{item.name}</Text>
                    <Text style={styles.desc}>
                      {item.description || `${item.months} мес · ${item.devices} устр.`}
                    </Text>
                  </View>
                  <Text style={styles.price}>{item.price_rub} ₽</Text>
                </View>
                <PrimaryButton
                  label="Оформить"
                  onPress={() =>
                    router.push({
                      pathname: "/(app)/pay",
                      params: { plan_key: item.plan_key },
                    })
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
  wrap: { flex: 1, padding: spacing.screen, paddingTop: 56 },
  back: { color: colors.accent, fontFamily: fonts.bodySemi, marginBottom: 8 },
  sub: { color: colors.muted, marginBottom: 8, fontFamily: fonts.body, marginTop: -8 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 14 },
  flag: { fontSize: 28 },
  name: { color: colors.text, fontSize: 17, fontFamily: fonts.bodyBold },
  desc: { color: colors.muted, marginTop: 2, fontSize: 13, fontFamily: fonts.body },
  price: { color: colors.accent3, fontFamily: fonts.displayBold, fontSize: 18 },
  error: { color: colors.danger, marginBottom: 8, fontFamily: fonts.body },
});
