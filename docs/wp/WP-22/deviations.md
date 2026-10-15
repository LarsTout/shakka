# Afwijkingen WP-22

Geen afwijking raakt een contract, schema, externe API, dependency of acceptatiecriterium.

## Voor orchestrator/WP-23 (review ronde 2)

- **N-1.** De zin in RUNBOOK §17.8 ("de grens van 5.000 map sessions uit het projectplan geldt alleen voor die SDK en is hier niet van toepassing") spreekt `docs/PROJECT_PLAN.md` sectie 2 tegen. De builder raakt `docs/PROJECT_PLAN.md` niet aan. De orchestrator trekt het plan bij de afsluiting van de WP gelijk.
- **N-2.** Gmail vermeldt "Google verwerkt de adressen van de ontvangers" in RUNBOOK §17.6. Neem dat ook mee in de vervolgwijziging van "De maildienst" op `/privacy` en in `docs/PRIVACY.md` (na de SMTP-keuze van Lars).
- `docs/PRIVACY.md` bestaat niet in deze werkboom (WP-23 is nog niet gemerged) en is niet aangeraakt. Wie als tweede merget, haalt in de rij "Profiel" de bijzin "; plus een ongebruikte, altijd lege legacy-kolom die WP-22 verwijdert" weg.
- RUNBOOK-nummer: de nieuwe sectie heet nu §17 (WP-23 niet gemerged). Merget WP-23 eerst, dan moeten de verwijzingen naar §17 in de WP-22-tekst (§4 niet; wel §11.2, §11.5, §13.1, §13.6, §14.7, §14.14 en de sectie zelf) worden hernummerd.
- `07_sessions.test.sql` regels 68 en 69: alleen `db_usage` toegevoegd. Na de merge van beide WP's zie je de eindvorm in de blueprint (Interfaces), met `delete_my_account`.

## Klein (genoteerd, doorgegaan)

1. **pgTAP niet lokaal gedraaid.** Docker is niet bereikbaar. In plaats daarvan zijn de twee migraties en de asserts van `10_hardening.test.sql` uitgevoerd op een tijdelijke lokale PostgreSQL 18 met een stub voor `auth`, de rollen en een eigen mini-shim voor de pgTAP-functies. Alle asserts gaven ok (één shim-artefact bij `has_function` met een lege argumentenlijst). De echte pgTAP-run (inclusief `plan`-aantallen 70/54/40/112/28 van 01, 02, 04, 07 en 10) komt uit de CI-job `db`.
2. **`with_retries[T]`** gebruikt PEP 695-syntaxis in plaats van een `TypeVar`, omdat ruff (UP047) dat afdwingt. Zelfde gedrag.
3. **Open-Meteo met `attempts=0`** geeft nu `ValueError` (van `with_retries`) in plaats van "failed after 0 attempts". Geen aanroeper gebruikt dat.
4. **Extra note** `push configuration invalid: usage push not sent` bij een `ValueError` uit de notifier-factory, naast de standaardnote `push disabled or misconfigured: usage push not sent` (de blueprint noemt "een aparte note"). De factory wordt niet aangeroepen zolang er geen geldige operator is.
5. **Extra tests**: `test_blocked_host_is_not_posted`, `test_load_all_targets_checked_blocks_and_does_not_log_endpoint`, `test_blocked_target_warning`, `test_deliver_plan_passes_non_retryable_when_deferred`, `test_builtin_db_usage` en een aantal extra gevallen in `test_job_usage.py`.
6. **`npm run build`** lokaal alleen met de placeholders `PUBLIC_SUPABASE_URL` en `PUBLIC_SUPABASE_PUBLISHABLE_KEY` uit `ci.yml` (zonder falen ze de build, zoals op `develop`).
7. **Dependency-audit (A17):** `npm audit --omit=dev --audit-level=high` gaf `found 0 vulnerabilities` (exitcode 0); `pip-audit` op de vergrendelde Python-dependencies gaf `No known vulnerabilities found`. Geen versie-updates nodig. De SHA's van `actions/checkout` v7.0.1 en `actions/setup-node` v7.1.0 kwamen met `gh api` overeen met de blueprint.

## Nodig van Lars (niet aan de builder)

Zie de blueprint, "Nodig van Lars": (1) "Allow new users to sign up" uit voor de merge, (2) `supabase db push` na de merge (met `--include-all` als WP-23 al gepusht is), (3) `OPERATOR_USER_ID` in `.env` en als GitHub Secret, (4) SMTP-dienst kiezen en de test van AC-6, (5) de mail aan Open-Meteo. De velden "Gekozen SMTP-dienst" en "Open-Meteo-bevestiging" in RUNBOOK §17 staan op "nog in te vullen door Lars".
