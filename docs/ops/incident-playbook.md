# Incident playbook — NinaVPN

Operational runbook for Q4 readiness. Keep this next to deploy access.

## Severity

| Level | Examples | Response |
|-------|----------|----------|
| SEV1 | All payments down, API 5xx > 5 min, mass disconnect | Page owner immediately; status page update |
| SEV2 | Single region / node dead, webhook lag | Failover node; notify support macros |
| SEV3 | Cosmetic, single-user issues | Ticket queue |

## Node blocked / dead

1. Confirm with `scripts/health-monitor.sh` and bot «Серверы / статус».
2. Disable node in `XUI_NODES` / Marzban; redeploy or hot-reload config.
3. Force config refresh for affected users (worker provision / panel regenerate).
4. Post note on `site/status.html` if impact is wide.

## Payment downtime

1. Identify rail: T-Bank / Freekassa / crypto / Stripe stub.
2. Switch cabinet checkout `provider` guidance to crypto if cards fail.
3. Do **not** manually mark payments paid without provider proof.
4. After recovery, reconcile pending `saas_payments`.

## Domain / TLS issues

1. Check nginx + certbot for `ninavpn.store`.
2. Keep a spare domain ready for panel endpoints if the marketing domain is under pressure.

## Comms

- Users: support chat SLA + short status blurb.
- Internal: timestamp, impact, mitigation, follow-up in one note.

## Aftercare

Root cause, monitoring gap, and one preventive task before closing SEV1/2.
