/** Pricing mirror of ninavpn.store + display FX for global UX. */
export const BASE_PRICES: Record<number, number> = { 1: 100, 6: 500, 12: 1000 };
export const BASE_DEVICES: Record<number, number> = { 1: 1, 6: 3, 12: 5 };
export const EXTRA_DEVICE_COST: Record<number, number> = { 1: 70, 6: 280, 12: 490 };

/** Approximate display rates (cabinet UX). Settlement may still be RUB/crypto/Stripe. */
export const USD_PER_RUB = 0.011;
export const EUR_PER_RUB = 0.01;

export function calculatePriceRub(months: number, devices: number): number {
  const m = months as 1 | 6 | 12;
  const d = Math.max(1, Math.min(10, devices));
  const base = BASE_PRICES[m];
  if (base == null) throw new Error("invalid_months");
  const included = BASE_DEVICES[m];
  const extra = Math.max(0, d - included);
  return base + extra * EXTRA_DEVICE_COST[m];
}

export function rubToUsd(amountRub: number): number {
  return Math.round(amountRub * USD_PER_RUB * 100) / 100;
}

export function rubToEur(amountRub: number): number {
  return Math.round(amountRub * EUR_PER_RUB * 100) / 100;
}

export function formatDualPrice(amountRub: number): string {
  return `${amountRub} ₽ · $${rubToUsd(amountRub)} · €${rubToEur(amountRub)}`;
}

export function monthlyEquivalent(total: number, months: number): number {
  return Math.round(total / Math.max(1, months));
}

export function savingVsMonthly(months: number, devices: number): number | null {
  if (months === 1) return null;
  const saved = calculatePriceRub(1, devices) * months - calculatePriceRub(months, devices);
  return saved > 0 ? saved : null;
}

export function customPlanKey(months: number, devices: number): string {
  const d = Math.max(1, Math.min(10, devices));
  return `custom_${months}m_${d}d`;
}

export function isFamilyPack(devices: number): boolean {
  return devices >= 3;
}
