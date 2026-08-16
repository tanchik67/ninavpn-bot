import * as Clipboard from "expo-clipboard";
import { useCallback, useMemo, useState } from "react";
import { useFocusEffect } from "expo-router";
import { Pressable, ScrollView, StyleSheet } from "react-native";
import { AppText as Text, AppTextInput as TextInput } from "../../src/components/AppText";
import { BackCircleButton } from "../../src/components/BackCircleButton";
import { GlassCard } from "../../src/components/GlassCard";
import { PrimaryButton } from "../../src/components/PrimaryButton";
import { ScreenBackground } from "../../src/components/ScreenBackground";
import { goBackOr } from "../../src/lib/nav";
import { api, API_URL } from "../../src/lib/api";
import { formatApiError } from "../../src/lib/apiErrors";
import { useAuth } from "../../src/lib/auth";
import { useI18n } from "../../src/lib/i18n";
import { colors, fonts, spacing } from "../../src/lib/theme";

type ReferralMe = {
  code: string;
  link: string;
  bonus_days: number;
  invitee_bonus_days?: number;
  invited_count: number;
  referrer_code?: string | null;
  can_apply?: boolean;
  rewarded?: boolean;
};

type AffiliateMe = {
  commission_percent: number;
};

function codeFromKey(key?: number | null): string {
  if (key == null) return "";
  const n = Number(key);
  if (!Number.isFinite(n) || n <= 0) return "";
  return `nv${n}`;
}

function linkFromCode(code: string): string {
  if (!code) return "";
  const base = (API_URL || "https://ninavpn.store").replace(/\/$/, "");
  return `${base}/?ref=${code}`;
}

export default function ReferralScreen() {
  const { t } = useI18n();
  const { user, patchUser } = useAuth();
  const [data, setData] = useState<ReferralMe | null>(null);
  const [aff, setAff] = useState<AffiliateMe | null>(null);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const localCode = useMemo(() => codeFromKey(user?.panel_user_key), [user?.panel_user_key]);
  const referrerDays = data?.bonus_days ?? 7;
  const inviteeDays = data?.invitee_bonus_days ?? 7;
  const displayCode = data?.code || localCode;
  const displayLink = data?.link || linkFromCode(displayCode);

  const load = useCallback(async () => {
    if (!user?.panel_user_key) {
      try {
        const authMe = await api<{ panel_user_key?: number }>("/api/v1/auth/me", {
          timeoutMs: 8000,
          priority: true,
        });
        if (authMe?.panel_user_key) {
          patchUser({ panel_user_key: authMe.panel_user_key });
        }
      } catch {
        /* still try referrals/me */
      }
    }
    try {
      const me = await api<ReferralMe>("/api/v1/referrals/me", {
        timeoutMs: 10000,
        retries: 1,
        priority: true,
      });
      if (me?.code) setData(me);
      setError("");
    } catch (e: unknown) {
      if (!localCode && !user?.panel_user_key) {
        setError(formatApiError(e, t("referral.error")));
      }
    }
    try {
      const a = await api<AffiliateMe>("/api/v1/referrals/affiliate", {
        timeoutMs: 8000,
        priority: true,
      });
      if (a) setAff(a);
    } catch {
      /* optional */
    }
  }, [t, localCode, user?.panel_user_key, patchUser]);

  useFocusEffect(
    useCallback(() => {
      load().catch(() => {});
    }, [load])
  );

  const copy = async () => {
    if (!displayLink) return;
    await Clipboard.setStringAsync(displayLink);
    setMsg(t("referral.copied"));
  };

  const copyCode = async () => {
    if (!displayCode) return;
    await Clipboard.setStringAsync(displayCode);
    setMsg(t("referral.copied"));
  };

  const applyError = (e: unknown) => {
    const raw = e instanceof Error ? e.message : String(e || "");
    if (
      raw === "already_paid" ||
      /already_paid|уже покупал|already bought|ya compró|satın aldı|قبلاً اشتراک|已购买/i.test(
        raw
      )
    ) {
      return t("referral.alreadyPaid");
    }
    return formatApiError(e, t("referral.error"));
  };

  const apply = async () => {
    if (!code.trim()) return;
    setBusy(true);
    setMsg("");
    setError("");
    try {
      const me = await api<ReferralMe>("/api/v1/referrals/apply", {
        method: "POST",
        body: JSON.stringify({ code: code.trim() }),
        timeoutMs: 12000,
        retries: 1,
        priority: true,
      });
      setData(me);
      setMsg(t("referral.applied", { days: referrerDays, inviteeDays }));
      setCode("");
    } catch (e: unknown) {
      setError(applyError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.scroll}>
        <BackCircleButton
          onPress={() => goBackOr("/(app)/(tabs)/profile")}
          style={styles.backBtn}
        />
        <Text style={styles.title}>{t("referral.title")}</Text>
        <Text style={styles.sub}>{t("referral.subtitle")}</Text>

        {!!error && <Text style={styles.error}>{error}</Text>}
        {!!msg && <Text style={styles.ok}>{msg}</Text>}

        <GlassCard style={{ gap: 8 }}>
          <Text style={styles.label}>{t("referral.yourCode")}</Text>
          <Pressable onPress={() => void copyCode()} disabled={!displayCode} hitSlop={8}>
            <Text style={styles.code} selectable>
              {displayCode || "—"}
            </Text>
          </Pressable>
          <Text style={styles.label}>{t("referral.yourLink")}</Text>
          <Text style={styles.link} numberOfLines={3} selectable>
            {displayLink || "—"}
          </Text>
          <Text style={styles.meta}>
            {t("referral.invited", { n: data?.invited_count ?? 0 })}
          </Text>
          <Text style={styles.meta}>
            {t("referral.bonus", { days: referrerDays })}
          </Text>
          <Text style={styles.meta}>
            {t("referral.inviteeBonus", { days: inviteeDays })}
          </Text>
          {!!aff && (
            <Text style={styles.meta}>
              {t("referral.affiliate", { percent: aff.commission_percent })}
            </Text>
          )}
          <PrimaryButton
            label={t("referral.copy")}
            onPress={copy}
            style={{ marginTop: 8 }}
          />
        </GlassCard>

        {data?.referrer_code ? (
          <GlassCard style={{ gap: 8, marginTop: spacing.md }}>
            <Text style={styles.label}>{t("referral.applyTitle")}</Text>
            <Text style={styles.meta}>
              {data.rewarded
                ? t("referral.inviteeBonus", { days: inviteeDays })
                : t("referral.waitingPay", { days: referrerDays, inviteeDays })}
            </Text>
          </GlassCard>
        ) : (
          <GlassCard style={{ gap: 10, marginTop: spacing.md }}>
            <Text style={styles.label}>{t("referral.applyTitle")}</Text>
            <Text style={styles.meta}>{t("referral.applyHint")}</Text>
            <TextInput
              style={styles.input}
              placeholder={t("referral.applyPlaceholder")}
              placeholderTextColor={colors.muted}
              value={code}
              onChangeText={setCode}
              autoCapitalize="none"
            />
            <PrimaryButton
              label={t("referral.apply")}
              onPress={apply}
              busy={busy}
              variant="secondary"
            />
          </GlassCard>
        )}
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  scroll: { paddingHorizontal: spacing.screen, paddingTop: 56, paddingBottom: 48 },
  backBtn: { marginBottom: 8 },
  title: { color: colors.text, fontFamily: fonts.displayBold, fontSize: 28, marginBottom: 6 },
  sub: { color: colors.muted, fontFamily: fonts.body, marginBottom: spacing.md },
  label: { color: colors.muted, fontFamily: fonts.bodySemi, fontSize: 12 },
  code: { color: colors.accent, fontFamily: fonts.bodyBold, fontSize: 22 },
  link: { color: colors.text, fontFamily: fonts.body, fontSize: 13 },
  meta: { color: colors.muted, fontFamily: fonts.body, marginTop: 4 },
  input: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
    backgroundColor: colors.glassFill,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: colors.text,
    fontFamily: fonts.body,
  },
  error: { color: colors.danger, fontFamily: fonts.body, marginBottom: 8 },
  ok: { color: colors.accent, fontFamily: fonts.body, marginBottom: 8 },
});
