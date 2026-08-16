# Growth plan — product foundations shipped

Code/docs that implement the 12‑month NinaVPN growth plan (product layer). Business execution (ads, audits, hiring) still follows the calendar.

## Q1 — Stabilize
- Trust: `site/how-we-work.html`, `site/status.html`, `site/guides.html`
- Cabinet: referral screen, FAQ, guides, about
- Health: `scripts/health-monitor.sh`

## Q2 — Global foundation
- EN landing: `site/en/`
- FX display + Stripe stub gateway (`adapters/payments/stripe.py`, `core/services/fx_display.py`)
- Locations API + cabinet Servers map
- Dual-currency on Plans

## Q3 — Growth engines
- Blog: `site/blog/`
- Affiliate endpoint `/api/v1/referrals/affiliate`
- Family badge on multi-device plans
- Distribution page `site/download.html`
- `scripts/deploy-site.sh` rsyncs full site tree

## Q4 — Scale brand
- Connection profiles (Low latency / Streaming / Max stealth)
- Locales ES + TR in cabinet
- `site/security.html`, `site/uptime.html`
- `docs/ops/incident-playbook.md`, `docs/ops/hiring-checklist.md`
