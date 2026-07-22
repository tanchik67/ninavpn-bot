import { router } from "expo-router";
import { goBackOr } from "../../src/lib/nav";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { useI18n } from "../../src/lib/i18n";
import {
  calculatePriceRub,
  customPlanKey,
  monthlyEquivalent,
  savingVsMonthly,
} from "../../src/lib/pricing";
import { colors, fonts, radii, spacing } from "../../src/lib/theme";

type Plan = {
  id: string;
  plan_key: string;
  name: string;
  description?: string;
  months: number;
  devices: number;
  price_rub: number;
};

const MONTHS = [1, 6, 12] as const;

export default function PlansScreen() {
  const { t, locale } = useI18n();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [months, setMonths] = useState<1 | 6 | 12>(6);
  const [devices, setDevices] = useState(3);
  const numLocale = locale === "en" ? "en-US" : "ru-RU";

  useEffect(() => {
    (async () => {
      try {
        const data = await api<Plan[]>("/api/v1/plans", { auth: false });
        setPlans(data);
      } catch (e: any) {
        setError(e?.message || t("plans.errorLoad"));
      } finally {
        setLoading(false);
      }
    })();
  }, [t]);

  const total = useMemo(() => calculatePriceRub(months, devices), [months, devices]);
  const perMonth = useMemo(() => monthlyEquivalent(total, months), [total, months]);
  const saving = useMemo(() => savingVsMonthly(months, devices), [months, devices]);

  const buyCustom = () => {
    router.push({
      pathname: "/(app)/pay",
      params: {
        plan_key: customPlanKey(months, devices),
        months: String(months),
        devices: String(devices),
      },
    });
  };

  return (
    <ScreenBackground>
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        <Pressable onPress={() => goBackOr("/(app)/(tabs)/home")} hitSlop={12}>
          <Text style={styles.back}>{t("common.back")}</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>{t("plans.title")}</ScreenTitle>
        <Text style={styles.sub}>{t("plans.subtitle")}</Text>

        {!!error && <Text style={styles.error}>{error}</Text>}

        <Text style={styles.section}>{t("plans.constructor")}</Text>
        <GlassCard style={styles.constructorCard}>
          <Text style={styles.label}>{t("plans.period")}</Text>
          <View style={styles.pills}>
            {MONTHS.map((m) => (
              <Pressable
                key={m}
                onPress={() => setMonths(m)}
                style={[styles.pill, months === m && styles.pillActive]}
              >
                <Text style={[styles.pillText, months === m && styles.pillTextActive]}>
                  {t("plans.monthsShort", { m })}
                </Text>
              </Pressable>
            ))}
          </View>

          <Text style={styles.label}>{t("plans.devicesLabel", { devices })}</Text>
          <View style={styles.deviceRow}>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((d) => (
              <Pressable
                key={d}
                onPress={() => setDevices(d)}
                style={[styles.devChip, devices === d && styles.devChipActive]}
              >
                <Text
                  style={[styles.devChipText, devices === d && styles.devChipTextActive]}
                >
                  {d}
                </Text>
              </Pressable>
            ))}
          </View>

          <View style={styles.totalBlock}>
            <Text style={styles.totalLabel}>{t("plans.total")}</Text>
            <Text style={styles.totalPrice}>
              {t("plans.priceRub", { price: total.toLocaleString(numLocale) })}
            </Text>
            <Text style={styles.totalDetail}>
              {t("plans.totalDetail", { perMonth, devices, months })}
            </Text>
            {saving != null ? (
              <Text style={styles.saving}>
                {t("plans.saving", { saving: saving.toLocaleString(numLocale) })}
              </Text>
            ) : null}
          </View>

          <PrimaryButton label={t("plans.buyNow")} onPress={buyCustom} />
        </GlassCard>

        <Text style={styles.section}>{t("plans.readyPlans")}</Text>
        {loading ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 20 }} />
        ) : (
          plans.map((item) => (
            <GlassCard key={item.id} style={{ marginBottom: 12 }}>
              <View style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.name}>{item.name}</Text>
                  <Text style={styles.desc}>
                    {item.description ||
                      t("plans.planFallbackDesc", {
                        months: item.months,
                        devices: item.devices,
                      })}
                  </Text>
                </View>
                <Text style={styles.price}>
                  {t("plans.priceRub", { price: item.price_rub })}
                </Text>
              </View>
              <PrimaryButton
                label={t("plans.checkout")}
                onPress={() =>
                  router.push({
                    pathname: "/(app)/pay",
                    params: { plan_key: item.plan_key },
                  })
                }
              />
            </GlassCard>
          ))
        )}
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: {
    padding: spacing.screen,
    paddingTop: 56,
    paddingBottom: 110,
  },
  back: { color: colors.accent, fontFamily: fonts.bodySemi, marginBottom: 8 },
  sub: {
    color: colors.muted,
    marginBottom: 16,
    fontFamily: fonts.body,
    marginTop: -8,
  },
  section: {
    fontFamily: fonts.bodySemi,
    fontSize: 13,
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginBottom: 10,
    marginTop: 8,
    marginLeft: 4,
  },
  constructorCard: { gap: 12, marginBottom: 20 },
  label: {
    color: colors.muted,
    fontFamily: fonts.bodySemi,
    fontSize: 13,
  },
  pills: { flexDirection: "row", gap: 8 },
  pill: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: radii.pill,
    alignItems: "center",
    backgroundColor: colors.glassFill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
  },
  pillActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  pillText: { color: colors.text, fontFamily: fonts.bodySemi },
  pillTextActive: { color: "#fff" },
  deviceRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  devChip: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.glassFill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
  },
  devChipActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  devChipText: { color: colors.text, fontFamily: fonts.bodySemi },
  devChipTextActive: { color: "#fff" },
  totalBlock: { marginTop: 4, marginBottom: 4 },
  totalLabel: { color: colors.muted, fontFamily: fonts.body, fontSize: 13 },
  totalPrice: {
    color: colors.text,
    fontFamily: fonts.display,
    fontSize: 32,
    marginTop: 4,
  },
  totalDetail: {
    color: colors.muted,
    fontFamily: fonts.body,
    marginTop: 4,
  },
  saving: {
    color: colors.accent3,
    fontFamily: fonts.bodySemi,
    marginTop: 8,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 14 },
  name: { color: colors.text, fontSize: 17, fontFamily: fonts.bodyBold },
  desc: { color: colors.muted, marginTop: 2, fontSize: 13, fontFamily: fonts.body },
  price: { color: colors.accent3, fontFamily: fonts.displayBold, fontSize: 18 },
  error: { color: colors.danger, marginBottom: 8, fontFamily: fonts.body },
});
