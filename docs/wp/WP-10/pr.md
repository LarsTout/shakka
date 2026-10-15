## WP-10: Evaluatie- en alertjobs plus beheer-CLI

- `shakka.jobs.{runtime,inputs,evaluate,alerts,admin}`: `run_evaluation` (evaluaties per spot per uur, opruimen na 48 u), `run_alerts` in drie stappen (`load_alert_context` → `plan_favorite` → `store_plan`) met de hook voor aflevering in WP-17. Alerts alleen voor `verified: true`; één kapotte rij stopt de job niet; schrijfvolgorde `alert_state` uit WP-08.
- CLI: `shakka evaluate`, `shakka alerts run [--dry-run]`, `shakka admin profile|favorite|rule|alerts`. RUNBOOK §12 (M1-opzet).
- Telegram volledig verwijderd uit `Settings`, `.env.example`, tests en RUNBOOK (A-16); permanente "geen telegram"-test.
- Privacy: geen user-id's, berichtteksten of secrets in logs; `run_alerts` zet geen user-id in request-URL's.
- 1254 tests groen; CI groen.

**Verificatie:** AC-1..10 PASS. AC-11 (M1-check met echte `.env`, auth-user en een geverifieerde spot) doet Lars; commando's in `docs/wp/WP-10/verification.md` en RUNBOOK §12.

**Gevolg voor WP-11:** loggers `httpx` en `httpcore` op WARNING (spot-id's staan in request-URL's; Actions-logs zijn openbaar); `AlertJobResult.errors` niet naar stdout.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
