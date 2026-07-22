import { router, useLocalSearchParams } from "expo-router";
import { goBackOr } from "../../src/lib/nav";
import { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { AppText as Text } from "../../src/components/AppText";
import * as WebBrowser from "expo-web-browser";
import { NinaLogo, ScreenTitle } from "../../src/components/NinaLogo";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { api } from "../../src/lib/api";
import { useI18n } from "../../src/lib/i18n";
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
  const params = useLocalSearchParams<{
    plan_key?: string;
    months?: string;
    devices?: string;
    payment_url?: string;
  }>();
  const { t } = useI18n();
  const [status, setStatus] = useState("");
  const [paymentId, setPaymentId] = useState<number | null>(null);
  const [provider, setProvider] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const polling = useRef<ReturnType<typeof setInterval> | null>(null);
  const tRef = useRef(t);
  tRef.current = t;

  useEffect(() => {
    setStatus(t("pay.statusPreparing"));
  }, [t]);

  const stopPoll = () => {
    if (polling.current) {
      clearInterval(polling.current);
      polling.current = null;
    }
  };

  const pollUntilReady = (id: number) => {
    stopPoll();
    setStatus(tRef.current("pay.statusProvisioning"));
    let ticks = 0;
    polling.current = setInterval(async () => {
      ticks += 1;
      try {
        const s = await api<PayStatus>(`/api/v1/payments/${id}/status`);
        if (s.ready) {
          stopPoll();
          setStatus(tRef.current("pay.statusReady"));
          router.replace("/(app)/(tabs)/home");
          return;
        }
        if (s.provision_status === "failed") {
          stopPoll();
          setError(s.provision_error || tRef.current("pay.errorProvision"));
          setStatus(tRef.current("pay.statusProvisionFailed"));
          return;
        }
        setStatus(
          tRef.current("pay.statusDetail", {
            payment: s.payment_status,
            provision: s.provision_status || "",
          })
        );
      } catch {
        /* keep polling */
      }
      if (ticks >= 40) {
        stopPoll();
        setStatus(tRef.current("pay.statusTimeout"));
      }
    }, 2000);
  };

  useEffect(() => () => stopPoll(), []);

  useEffect(() => {
    (async () => {
      try {
        if (params.payment_url) {
          await WebBrowser.openBrowserAsync(String(params.payment_url));
          setStatus(tRef.current("pay.statusFinishBrowser"));
          return;
        }
        if (!params.plan_key && !(params.months && params.devices)) {
          setError(tRef.current("pay.errorNoPlan"));
          return;
        }
        const body: Record<string, string | number> = {};
        if (params.plan_key) body.plan_key = String(params.plan_key);
        if (params.months) body.months = Number(params.months);
        if (params.devices) body.devices = Number(params.devices);
        const checkout = await api<Checkout>("/api/v1/payments/checkout", {
          method: "POST",
          body: JSON.stringify(body),
        });
        setPaymentId(checkout.payment_id);
        setProvider(checkout.provider);
        if (checkout.provider === "mock") {
          setStatus(tRef.current("pay.statusMock"));
        } else {
          await WebBrowser.openBrowserAsync(checkout.payment_url);
          setStatus(tRef.current("pay.statusPayBrowser"));
          pollUntilReady(checkout.payment_id);
        }
      } catch (e: any) {
        setError(e?.message || tRef.current("pay.errorCheckout"));
      }
    })();
  }, [params.plan_key, params.months, params.devices, params.payment_url]);

  const confirmMock = async () => {
    if (!paymentId) return;
    setBusy(true);
    setError("");
    try {
      const s = await api<PayStatus>(`/api/v1/payments/mock/confirm/${paymentId}`, {
        method: "POST",
      });
      if (s.ready) {
        router.replace("/(app)/(tabs)/home");
        return;
      }
      if (s.provision_status === "failed") {
        setError(s.provision_error || t("pay.errorProvision"));
        return;
      }
      pollUntilReady(paymentId);
    } catch (e: any) {
      setError(e?.message || t("pay.errorConfirm"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenBackground>
      <View style={styles.wrap}>
        <Pressable onPress={() => goBackOr("/(app)/(tabs)/home")} hitSlop={12}>
          <Text style={styles.back}>{t("common.back")}</Text>
        </Pressable>
        <NinaLogo size={24} />
        <ScreenTitle>{t("pay.title")}</ScreenTitle>
        <GlassCard style={{ gap: 12 }}>
          <Text style={styles.status}>{status}</Text>
          {!!provider && (
            <Text style={styles.muted}>{t("pay.provider", { provider })}</Text>
          )}
          {!!error && <Text style={styles.error}>{error}</Text>}
          {paymentId && provider === "mock" ? (
            <PrimaryButton
              label={t("pay.confirmMock")}
              onPress={confirmMock}
              busy={busy}
            />
          ) : null}
          {paymentId && provider !== "mock" ? (
            <PrimaryButton
              label={t("pay.checkStatus")}
              onPress={() => pollUntilReady(paymentId)}
            />
          ) : null}
          <PrimaryButton
            variant="secondary"
            label={t("common.backPlain")}
            onPress={() => goBackOr("/(app)/(tabs)/home")}
          />
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
