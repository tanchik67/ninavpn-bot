import type { Locale } from "./i18n";

const SITE = "https://ninavpn.store";

/** Site document paths: RU at root, EN under /en/. Non-RU app locales use English pages. */
const DOCS = {
  security: { ru: "/security.html", en: "/en/security.html" },
  howWeWork: { ru: "/how-we-work.html", en: "/en/how-we-work.html" },
  guides: { ru: "/guides.html", en: "/en/guides.html" },
  privacy: { ru: "/ninavpn-privacy-2.html", en: "/en/privacy.html" },
  terms: { ru: "/ninavpn-terms-2.html", en: "/en/terms.html" },
  oferta: { ru: "/ninavpn-oferta-2.html", en: "/en/oferta.html" },
  status: { ru: "/status.html", en: "/en/status.html" },
} as const;

export type SiteDoc = keyof typeof DOCS;

export function siteDocLang(locale: Locale): "ru" | "en" {
  return locale === "ru" ? "ru" : "en";
}

export function siteDocUrl(doc: SiteDoc, locale: Locale): string {
  const lang = siteDocLang(locale);
  return `${SITE}${DOCS[doc][lang]}`;
}
