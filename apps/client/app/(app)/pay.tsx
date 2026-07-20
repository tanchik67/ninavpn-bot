import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import * as WebBrowser from "expo-web-browser";
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { colors, fonts, spacing } from "../../src/lib/theme";

type Checkout = { payment_id: number; payment_url: string; provider: string };
type PayStatus = {
  payment_id: number;
  payment_status: string;
  provider: string;
  provision_status?: string | null;
  provision_error?: string | null;
  ready: boolean;
};

export default function PayScreen() {
  const params = useLocalSearchParams<{ plan_key?: string; payment_url?: string }>();
  const [status, setStatus] = useState("Готовим оплату…");
  const [paymentId, setPaymentId] = useState<number | null>(null);
  const [provider, setProvider] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const polling = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = () => {
    if (polling.current) {
      clearInterval(polling.current);
      polling.current = null;
    }
  };

  const pollUntilReady = (id: number) => {
    stopPoll();
    setStatus("Ожидаем выдачу доступа…");
    let ticks = 0;
    polling.current = setInterval(async () => {
      ticks += 1;
      try {
        const s = await api<PayStatus>(`/api/v1/payments/${id}/status`);
        if (s.ready) {
          stopPoll();
          setStatus("Готово!");
          router.replace("/(app)/home");
          return;
        }
        if (s.provision_status === "failed") {
          stopPoll();
          setError(s.provision_error || "Ошибка выдачи VPN");
          setStatus("Ошибка выдачи");
          return;
        }
        setStatus(
          `Статус: ${s.payment_status}${s.provision_status ? ` · ${s.provision_status}` : ""}`
        );
      } catch {
        /* keep polling */
      }
      if (ticks >= 40) {
        stopPoll();
        setStatus("Проверьте главную или поддержку");
      }
    }, 2000);
  };

  useEffect(() => () => stopPoll(), []);

  useEffect(() => {
    (async () => {
      try {
        if (params.payment_url) {
          await WebBrowser.openBrowserAsync(String(params.payment_url));
          setStatus("Завершите оплату в браузере");
          return;
        }
        if (!params.plan_key) {
          setError("Не выбран тариф");
          return;
        }
        const checkout = await api<Checkout>("/api/v1/payments/checkout", {
          method: "POST",
          body: JSON.stringify({ plan_key: params.plan_key }),
        });
        setPaymentId(checkout.payment_id);
        setProvider(checkout.provider);
        if (checkout.provider === "mock") {
          setStatus("Тестовая оплата (mock)");
        } else {
          await WebBrowser.openBrowserAsync(checkout.payment_url);
          setStatus("Оплатите в браузере");
          pollUntilReady(checkout.payment_id);
        }
      } catch (e: any) {
        setError(e?.message || "Ошибка checkout");
      }
    })();
  }, [params.plan_key, params.payment_url]);

  const confirmMock = async () => {
    if (!paymentId) return;
    setBusy(true);
    setError("");
    try {
      const s = await api<PayStatus>(`/api/v1/payments/mock/confirm/${paymentId}`, {
        method: "POST",
      });
      if (s.ready) {
        router.replace("/(app)/home");
        return;
      }
      if (s.provision_status === "failed") {
        setError(s.provision_error || "Ошибка выдачи");
        return;
      }
      pollUntilReady(paymentId);
    } catch (e: any) {
      setError(e?.message || "confirm failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.back}>‹ Назад</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>Оплата</ScreenTitle>
        <GlassCard style={{ gap: 12 }}>
          <Text style={styles.status}>{status}</Text>
          {!!provider && <Text style={styles.muted}>Провайдер: {provider}</Text>}
          {!!error && <Text style={styles.error}>{error}</Text>}
          {paymentId && provider === "mock" ? (
            <PrimaryButton
              label="Подтвердить mock-оплату"
              onPress={confirmMock}
              busy={busy}
            />
          ) : null}
          {paymentId && provider !== "mock" ? (
            <PrimaryButton
              label="Проверить статус"
              onPress={() => pollUntilReady(paymentId)}
            />
          ) : null}
          <PrimaryButton variant="secondary" label="Назад" onPress={() => router.back()} />
        </GlassCard>
      </View>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: spacing.screen, paddingTop: 56, gap: 14 },
  back: { color: colors.accent, fontFamily: fonts.bodySemi },
  status: { color: colors.text, fontFamily: fonts.bodySemi },
  muted: { color: colors.muted, fontSize: 13, fontFamily: fonts.body },
  error: { color: colors.danger, fontFamily: fonts.body },
});
