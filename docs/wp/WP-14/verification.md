# Verificatie WP-14, ronde 1
Resultaat: NEEDS_LARS

Alle automatisch toetsbare criteria zijn PASS. AC-7 (Cloudflare Pages, `APP_BASE_URL`, gedeployde site) kan alleen Lars doen.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | In `web/`: `npm ci`, `npm run check` (0 errors, 0 warnings, 530 files), `npm test` (27 bestanden, 203 tests groen), `npm run build` en `npm run verify:build` (`verify-build: ok`). Vanuit de root: `bash scripts/check-no-client-openmeteo.sh` geeft `ok`. Ingest: `uv run pytest` 1328 passed, 24 skipped (lokale Supabase-tests), `ruff check` en `ruff format --check` schoon. CI-run op `wp/WP-14` (`docs(WP-14): verifying`): success. |
| AC-2 | PASS | `contracts.test.ts` leest de drie JSON-bestanden via `node:fs` en toetst per code een niet-lege label, niet gelijk aan code of fallback, gelijk aan `label_nl`. Groen. |
| AC-3 | PASS | `spot-page.test.ts` (a)-(g) plus `hour-verdict.test.ts`, `time.test.ts` en `view.test.ts` groen. Dekt 12:00Z als 14:00, oordeel als tekst, Nederlandse redenlabels, offshore als `no_go` met label, banner bij `verified=false`, waarschuwing bij meer dan 3 uur, Attribution. Attribution staat bovendien in `+layout.svelte` en dus op elke pagina. |
| AC-4 | PASS | `spot-list.test.ts`: spot zonder evaluaties toont "Nog geen data" zonder `role="alert"`. Groen. |
| AC-5 | PASS | `time.test.ts` (`parseGoParams`), `go.test.ts` (route geeft 307 naar `/spot/test-strand`, ongeldig naar `/`) en `go-url-fixture.test.ts` (leest `ingest/tests/message_fixtures.py`, gelijk aan de TS-fixtures). Aanvullend headless Chrome op `npm run preview`: `/go?x=1` landt op de spotlijst (kop "Spots"); een geldige `/go` landt op `/spot/test-strand` (toont "Spot niet gevonden", want die spot bestaat niet in de echte database). Slug van maximaal 100 tekens afgedwongen in `parseGoParams` (`MAX_SLUG_LENGTH`). |
| AC-6 | PASS | `grep -n "\.from(" web/src/lib/data.ts` geeft 5 treffers: `spots` (2x), `evaluations` (2x), `tide_extremes` (1x). `data-tables.test.ts` groen. |
| AC-7 | NEEDS_LARS | Cloudflare Pages inrichten volgens RUNBOOK §11.3 (root leeg, build `cd web && npm ci && npm run build`, output `web/build`), Actions-variable `APP_BASE_URL` zetten, `/spot/<ingevulde spot>` openen (actuele uren, "Bijgewerkt" van minder dan 3 uur), een `/go`-URL uit `shakka admin alerts preview` openen. Daarnaast de terugknop-test uit deviations N-4: via client-side navigatie een `/go?...`-link openen, Terug drukken, en controleren dat je niet in een lus op `/go` blijft. |

## Harde regels
- Geen secrets in de diff: de diff bevat geen `sb_secret_`, `service_role`, JWT of wachtwoord. De string `sb_secret_` staat alleen in `web/src/lib/env-schema.ts` (WP-13 prefixguard, geen wijziging in deze WP) en daarmee in een build-chunk; dat is de afwijzingscontrole, geen sleutel. `web/.env` bevat alleen `PUBLIC_*`-sleutels en is gitignored (niet in `git status`).
- Geen Open-Meteo-aanroepen in `web/`: alleen de tekst/link `open-meteo.com` in `Attribution` (geen `api.open-meteo`, `marine-api`, `archive-api`). `check-no-client-openmeteo.sh` ok.
- `data.ts` leest alleen `spots`, `evaluations`, `tide_extremes` (AC-6).
- Bronvermelding: `Attribution` in de root-layout (elke pagina), met open-meteo.com-link.
- Geen tracking, CDN of externe fonts: grep op `fonts.`, `googleapis`, `cdn`, `unpkg`, `jsdelivr` in `web/src` en `web/static` geeft niets; `build/index.html` bevat alleen relatieve en absolute lokale paden, geen externe `src` of `href`; de enige URL in de entry-JS is de kit-constante `sveltekit-redirect.invalid`.
- `dir_class` wordt alleen uit de database gelezen en getoond (`HourVerdict.svelte`); nergens afgeleid uit `dir_deg`.
- Offshore blijft `no_go`: de UI toont `verdict` uit de database en overschrijft niets; de test controleert `data-verdict="no_go"` plus "Aflandige wind: niet kiten".
- Lokale tijd: `no-local-date-getters.test.ts` groen; mijn eigen grep (`getHours`, `getDate(`, `getDay`, `getMonth`, `toLocale*`, `getTimezoneOffset`, `setHours`) in `web/src/lib` en `web/src/routes` geeft geen treffers. Tijd loopt via `Intl.DateTimeFormat` met `Europe/Amsterdam`.
- Drift-tests: `schema-columns.test.ts` (migratie `20261015090000_m1_schema.sql`), `contracts.test.ts` (`data/contracts/*.json`), `labels.test.ts` (`direction.py`) en `go-url-fixture.test.ts` (`message_fixtures.py`) lezen de echte bestanden en zijn groen.
- Rooktest `npm run preview`: `/`, `/spot/bestaat-niet`, `/go?x=1` en een geldige `/go` geven allemaal HTTP 200 `text/html` (SPA-fallback). De build bevat geen externe scripts.
- Scope: buiten `web/` en `docs/` is niets gewijzigd. `docs/RUNBOOK.md`, `docs/STATUS.md`, `web/tsconfig.json` en `web/vite.config.ts` staan in de blueprint. Geen wijzigingen in `ingest/`, `supabase/`, `data/`, `.github/`, `package.json`, service worker.
- Afwijkingen N-1 t/m N-11 staan in `deviations.md` en zijn geen fail.
- Geen nieuwe betaalde dienst, geen scraping.

## Problemen
Geen blokkerende problemen.

F-0 (informatief, geen fail): AC-7 en de N-4-terugknop-test hangen aan Lars (Pages, `APP_BASE_URL`, gedeployde site).
