/** Map API / auth error codes to short user-facing messages. */
const CODE_MESSAGES: Record<string, string> = {
  use_telegram_login:
    "Этот аккаунт создан через Telegram. Войдите кнопкой «Через Telegram» — у него нет пароля для email-входа.",
  invalid_credentials: "Неверный email или пароль",
  banned: "Аккаунт заблокирован",
  email_taken: "Этот email уже зарегистрирован",
  network_error: "Не удалось подтвердить отправку — нажмите ↑ ещё раз",
  network_timeout: "Не удалось подтвердить отправку — нажмите ↑ ещё раз",
  ack_needed: "Не удалось подтвердить отправку — нажмите ↑ ещё раз",
  not_authenticated: "Нужно войти заново",
  ticket_closed: "Обращение закрыто — откройте чат ещё раз",
  telegram_not_configured: "Telegram-вход не настроен",
  google_not_configured: "Google-вход не настроен",
  popup_blocked: "Разрешите всплывающие окна для входа",
  image_too_large: "Не удалось сжать фото — попробуйте ещё раз",
  image_compress_failed: "Не удалось обработать фото — попробуйте ещё раз",
  already_paid:
    "Вы уже покупали подписку на этом аккаунте (email, Google или Telegram), поэтому стать приглашённым нельзя.",
  referrer_already_set: "Реферальный код уже применён",
  invalid_code: "Неверный реферальный код",
};

const NETWORK_FAIL_RE =
  /network request failed|failed to fetch|load failed|networkerror|network_error/i;

function firstValidationMsg(detail: unknown): string | null {
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const first = detail[0] as { msg?: string; loc?: unknown[] };
  const loc = Array.isArray(first?.loc) ? first.loc.filter((x) => x !== "body").join(".") : "";
  const msg = typeof first?.msg === "string" ? first.msg : "";
  if (!msg) return null;
  if (/special-use|reserved name|not a valid email/i.test(msg)) {
    return "Этот email нельзя использовать для входа по паролю. Если аккаунт из Telegram — нажмите «Войти через Telegram».";
  }
  return loc ? `${loc}: ${msg}` : msg;
}

/** Turn FastAPI / fetch errors into a short string for UI. */
export function formatApiError(err: unknown, fallback = "Ошибка"): string {
  const raw =
    err instanceof Error
      ? err.message
      : typeof err === "string"
        ? err
        : fallback;
  if (!raw) return fallback;

  if (CODE_MESSAGES[raw]) return CODE_MESSAGES[raw];
  if (NETWORK_FAIL_RE.test(raw)) return CODE_MESSAGES.network_error;
  if (/timeout|timed out|aborted/i.test(raw)) return CODE_MESSAGES.network_timeout;

  // Raw JSON body sometimes surfaces as Error.message
  if (raw.trim().startsWith("{") || raw.trim().startsWith("[")) {
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        return CODE_MESSAGES[parsed.detail] || parsed.detail;
      }
      const fromVal = firstValidationMsg(parsed.detail);
      if (fromVal) return fromVal;
    } catch {
      /* keep raw */
    }
  }

  return raw.length > 220 ? `${raw.slice(0, 200)}…` : raw;
}

export function formatApiDetail(detail: unknown, bodyText: string, status: number): string {
  if (typeof detail === "string") {
    return CODE_MESSAGES[detail] || detail;
  }
  const fromVal = firstValidationMsg(detail);
  if (fromVal) return fromVal;
  return bodyText || `HTTP ${status}`;
}
