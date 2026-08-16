import type { Locale } from "./dictionaries";

type TFn = (path: string) => string;

const MONTH_KEYS = [
  "dates.jan",
  "dates.feb",
  "dates.mar",
  "dates.apr",
  "dates.may",
  "dates.jun",
  "dates.jul",
  "dates.aug",
  "dates.sep",
  "dates.oct",
  "dates.nov",
  "dates.dec",
] as const;

/** Format a date with in-app translations — never device locale (Android ICU). */
export function formatProfileDate(
  iso: string,
  locale: Locale,
  t: TFn
): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const day = d.getDate();
  const year = d.getFullYear();
  const month = t(MONTH_KEYS[d.getMonth()] || "dates.jan");
  if (locale === "en") return `${month} ${day}, ${year}`;
  if (locale === "zh") return `${year}年${month}${day}日`;
  return `${day} ${month} ${year}`;
}
