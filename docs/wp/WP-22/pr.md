## WP-22: Hardening backend en kostenbewaking

- `with_retries` + stroomonderbreker voor Open-Meteo, Rijkswaterstaat en Supabase REST (alleen idempotente operaties; `alert_state`-schrijfvolgorde ongewijzigd); runbudget 600 s; forecast-veroudering 3 u per spot in evaluate én alerts.
- Push: allowlist van pushdiensten (incl. `jmt17.google.com`), teller `push_non_retryable` met `::warning::` en `partial` (verkeerde `PUBLIC_VAPID_PUBLIC_KEY` valt nu op), 404/410 verwijdert, 401/403 niet; trigger max 20 abonnementen.
- Gebruiksrapport: `shakka usage show`, pipelinestap `usage_report` (weekpush op maandag 08–22 aan `OPERATOR_USER_ID`, drempels DB > 300 MB en Open-Meteo > 70 %, `db_usage()` alleen service_role), `ingest_runs` 90 dagen; `OPERATOR_USER_ID` geredigeerd in logs.
- Migraties: `profiles.telegram_chat_id` weg; `db_usage()`, abonnementsgrens, sessie-horizon ≤ 370 dagen als trigger. pgTAP `10_hardening` (28); `07_sessions` samengevoegd met WP-23.
- Web: `shouldCreateUser: true` (slot = Supabase "Allow new users to sign up" UIT). GitHub Actions op commit-SHA's; `npm audit`/`pip-audit` schoon. RUNBOOK §18 (SMTP: Resend met domein of Gmail; Auth-rate-limits; maandcheck; Open-Meteo-bevestiging).
- 1735 ingest-tests, 904 web-tests; CI groen (pgTAP 449).

**Verificatie:** AC-1..5, AC-7 PASS. AC-6 (SMTP-keuze + magic-link-test, Open-Meteo-mail) doet Lars. `supabase db push --include-all` doet de orchestrator.

**Merge-poort (Lars):** "Allow new users to sign up" UIT in Supabase vóór de merge.

**Hiermee is v1 (M1–M4) compleet.**

🤖 Generated with [Claude Code](https://claude.com/claude-code)
