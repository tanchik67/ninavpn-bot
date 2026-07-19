import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import * as WebBrowser from "expo-web-browser";
import { api } from "../../src/lib/api";
import { colors } from "../../src/lib/theme";

type Checkout = {
  payment_id: number;
  payment_url: string;
  provider: string;
};

type PayStatus = {
  payment_id: number;
  payment_status: string;
  provider: string;
  provision_status?: string | null;
  provision_error?: string | null;
  has_config: boolean;
  ready: boolean;
};

export default function PayScreen() {
  const params = useLocalSearchParams<{ plan_key?: string; payment_url?: string }>();
  const [status, setStatus] = useState("Готовим оплату…");
  const [paymentId, setPaymentId] = useState<number | null>(null);
  const [provider, setProvider] = useState<string>("");
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
          setStatus("Готово! Открываем конфиг…");
          router.replace("/(app)/config");
          return;
        }
        if (s.provision_status === "failed") {
          stopPoll();
          setError(s.provision_error || "Не удалось создать VPN-доступ. Напишите в поддержку.");
          setStatus("Ошибка выдачи");
          return;
        }
        setStatus(
          `Статус: ${s.payment_status}` +
            (s.provision_status ? ` · provision: ${s.provision_status}` : "")
        );
      } catch (e: any) {
        // keep polling briefly
      }
      if (ticks >= 40) {
        stopPoll();
        setStatus("Выдача занимает больше обычного — проверьте вкладку «Конфиг» или поддержку.");
      }
    }, 2000);
  };

  useEffect(() => {
    return () => stopPoll();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        if (params.payment_url) {
          await WebBrowser.openBrowserAsync(String(params.payment_url));
          setStatus("Завершите оплату в браузере. Затем вернитесь — статус обновится.");
          return;
        }
        if (!params.plan_key) {
          setError("Не выбран тариф");
          return;
        }
        // Server picks T-Bank if configured + PAYMENT_MOCK_ENABLED=false, else mock
        const checkout = await api<Checkout>("/api/v1/payments/checkout", {
          method: "POST",
          body: JSON.stringify({ plan_key: params.plan_key }),
        });
        setPaymentId(checkout.payment_id);
        setProvider(checkout.provider);
        if (checkout.provider === "mock") {
          setStatus("Тестовая оплата (mock). Нажмите подтверждение ниже.");
        } else {
          await WebBrowser.openBrowserAsync(checkout.payment_url);
          setStatus("Оплатите в браузере. Мы проверим статус автоматически.");
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
        setStatus("Готово! Открываем конфиг…");
        router.replace("/(app)/config");
        return;
      }
      if (s.provision_status === "failed") {
        setError(s.provision_error || "Ошибка выдачи VPN");
        setStatus("Ошибка выдачи");
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
    <View style={styles.wrap}>
      <Text style={styles.title}>Оплата</Text>
      {!error && !paymentId && !params.payment_url ? (
        <ActivityIndicator color={colors.accent} />
      ) : null}
      <Text style={styles.status}>{status}</Text>
      {!!provider && <Text style={styles.muted}>Провайдер: {provider}</Text>}
      {!!error && <Text style={styles.error}>{error}</Text>}
      {paymentId && provider === "mock" ? (
        <Pressable style={styles.btn} onPress={confirmMock} disabled={busy}>
          {busy ? (
            <ActivityIndicator color={colors.bg} />
          ) : (
            <Text style={styles.btnText}>Подтвердить mock-оплату</Text>
          )}
        </Pressable>
      ) : null}
      {paymentId && provider !== "mock" ? (
        <Pressable style={styles.btn} onPress={() => pollUntilReady(paymentId)}>
          <Text style={styles.btnText}>Проверить статус оплаты</Text>
        </Pressable>
      ) : null}
      <Pressable style={styles.secondary} onPress={() => router.replace("/(app)/subscription")}>
        <Text style={styles.btnText}>К подписке</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: 20, gap: 14 },
  title: { color: colors.text, fontSize: 28, fontWeight: "800" },
  status: { color: colors.muted },
  muted: { color: colors.muted, fontSize: 13 },
  error: { color: colors.danger },
  btn: {
    backgroundColor: colors.accent,
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
  },
  secondary: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  btnText: { color: colors.text, fontWeight: "700" },
});
