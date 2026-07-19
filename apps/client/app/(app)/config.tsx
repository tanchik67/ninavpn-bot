import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { api } from "../../src/lib/api";
import { colors } from "../../src/lib/theme";

type Config = {
  subscription_url?: string;
  links: string[];
  qr_base64?: string;
  deeplinks: Record<string, string>;
  expires_at?: string;
  status: string;
};

export default function ConfigScreen() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        try {
          const data = await api<Config>("/api/v1/subscriptions/me/config");
          if (alive) setCfg(data);
        } catch (e: any) {
          if (alive) {
            setCfg(null);
            setError("Конфиг пока недоступен — оплатите тариф или дождитесь выдачи.");
          }
        }
      })();
      return () => {
        alive = false;
      };
    }, [])
  );

  if (!cfg && !error) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (!cfg) {
    return (
      <View style={styles.wrap}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  const url = cfg.subscription_url || cfg.links[0];

  return (
    <ScrollView contentContainerStyle={styles.wrap}>
      <Text style={styles.title}>Подключение</Text>
      <Text style={styles.muted}>Статус: {cfg.status}</Text>
      {cfg.qr_base64 ? (
        <Image
          source={{ uri: `data:image/png;base64,${cfg.qr_base64}` }}
          style={styles.qr}
        />
      ) : null}
      <Text style={styles.url} selectable>
        {url}
      </Text>
      <Pressable
        style={styles.btn}
        onPress={async () => {
          if (url) {
            await Clipboard.setStringAsync(url);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }
        }}
      >
        <Text style={styles.btnText}>{copied ? "Скопировано" : "Копировать ссылку"}</Text>
      </Pressable>
      {Object.entries(cfg.deeplinks || {}).map(([name, link]) =>
        name === "raw" ? null : (
          <Pressable key={name} style={styles.secondary} onPress={() => Linking.openURL(link)}>
            <Text style={styles.btnText}>Открыть в {name}</Text>
          </Pressable>
        )
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: 20, gap: 12 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  title: { color: colors.text, fontSize: 28, fontWeight: "800" },
  muted: { color: colors.muted },
  qr: { width: 220, height: 220, alignSelf: "center", backgroundColor: "#fff", borderRadius: 12 },
  url: { color: colors.text, fontSize: 13 },
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
  error: { color: colors.danger },
});
