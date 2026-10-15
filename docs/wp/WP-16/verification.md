# Verificatie WP-16, ronde 1
Resultaat: NEEDS_LARS

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `npm ci`, `npm run check` (0 errors, 0 warnings), `npm test` (39 bestanden, 408 tests groen), `npm run build`, `npm run verify:build` ("ok"). `uv run pytest`: 1349 passed, 24 skipped (alleen lokale-Supabase-tests). `ruff check` en `ruff format --check` schoon. CI op `wp/WP-16`: success. |
| AC-2 | PASS | `uv run pytest -k rule_resolution_cases`: 21 passed. Het JSON-bestand heeft 20 gevallen met unieke namen. De Python-test importeert de echte `resolve_rule`, `ProfileDefaults.from_row` en `AlertRuleOverride.from_row` uit `shakka.domain.alerts` en vergelijkt het resultaat met `expected`. De bronnen worden uit `FIELD_SOURCES` afgeleid. De dekkingstest eist alle vier de `RuleSource`-niveaus, `conflict` en `invalid`. De vitest-test `rules.test.ts` leest hetzelfde bestand via `node:fs` en draait groen. |
| AC-3 | PASS | `alert-rule-form.test.ts` toetst de checkboxes in de groep "Windrichtingen": exact `onshore`, `side_onshore`, `sideshore`, met Nederlandse labels. De component rendert `ALERT_DEFAULTS.dir_classes.allowed`, en dat zijn alleen de drie rijdbare. |
| AC-4 | PASS | `alert-rule-form.test.ts`, `profile-page.test.ts`, `form-ranges.test.ts` en `forms.test.ts`: min >= max, quivermaat buiten 3–21 en gewicht buiten 30–200 worden geweigerd, met `writeCalls(...) === 0`. Zelf nagelopen met een wegwerptest in een kopie buiten de repo: gewicht 29 en 201, quiver 2,9, 21,1 en 11 kites, en min 20 / max 20 of min 25 / max 20 worden allemaal geweigerd. |
| AC-5 | PASS | `favorite-star.test.ts` en `favorites.test.ts`: gemockte supabase, insert en delete op `favorites` met het juiste `spot_id`. `user-data.ts` doet de insert met `{ user_id, spot_id }` en de delete met `eq('user_id')` en `eq('spot_id')`. |
| AC-6 | PASS | `alerts-page.test.ts` en `profile-page.test.ts`: uitgelogd (en nog onbekende sessie) toont de loginprompt of "Laden…", `fake.current.calls` heeft lengte 0. `favorites.ts` doet bij `s === null` geen query. |
| AC-7 | NEEDS_LARS | Rooktest tegen de lokale stack plus `uv run shakka admin alerts preview --user-id <Lars>`. Vereist Docker (`supabase start`) en een handmatige controle. Zo vermeld in `deviations.md`. Upsert en kolomrechten zijn tot dan alleen met een nep-client getest. |
| AC-8 | PASS | `grep -rli telegram web/src` geeft niets (rc=1). `web/test/no-telegram.test.ts` bewaakt dit. |

## Harde regels
- Offshore en side-offshore zijn nergens instelbaar. De component rendert alleen `ALERT_DEFAULTS.dir_classes.allowed`, en `parseAlertDefaults` weigert alles buiten `RIDABLE_DIR_CLASSES`. Zelf geprobeerd via `parseAlertRuleForm` en `parseRuleFields`: `['offshore']`, `['side_offshore']` en `['onshore','offshore']` geven alle drie `ok: false` met een fout op `dir_classes`, en de waarde blijft `null`.
- `web/src/lib/user-data.ts` is het enige bestand met `.from('profiles'|'favorites'|'alert_rules')`. De andere `.from(`-aanroepen in `data.ts` gaan naar `spots`, `evaluations` en `tide_extremes` (lezen). Het profiel gebruikt alleen `.update` met exact `weight_kg`, `level`, `quiver_m2`, `default_min_kn` en `default_max_kn`. Dat komt overeen met de kolomgrant in `20261015090100_m1_security.sql`. Er is geen `.insert` of `.upsert` op `profiles`. De enige insert gaat naar `favorites`, de upsert naar `alert_rules`.
- Geen secrets in de diff (grep op `sb_secret_`, `service_role`, JWT-achtige strings: niets; `sb_secret_` staat alleen in de bestaande env-guard `env-schema.ts`). `web/.env` is gitignored en niet in de diff.
- Geen client-side Open-Meteo: `scripts/check-no-client-openmeteo.sh` geeft "ok". De enige Open-Meteo-links in `web/src` staan in `Attribution.svelte`.
- Geen tracking of CDN: grep op analytics, gtag, cdn en googleapis geeft alleen de zin "geen analytics" in `over/+page.svelte`. Geen scraping, geen nieuwe betaalde dienst, geen nieuwe dependency in `package.json`.
- Bronvermelding intact: `Attribution` staat in `+layout.svelte` (`<Attribution compact />`) en `layout.test.ts` toetst "shows attribution in the footer on every page". `/profiel` en `/alerts` vallen onder dezelfde layout.
- Offshore blijft `no_go`: `ingest/src` is niet gewijzigd. De gevallen `invalid_offshore_in_rule` en `invalid_side_offshore_in_rule` draaien groen tegen Python en TypeScript.
- Scope: alleen `web/`, `docs/` (blueprint, deviations, review, RUNBOOK, STATUS), `data/contracts/rule_resolution_cases.json` en `ingest/tests/test_rule_resolution_cases.py` zijn gewijzigd. Er zijn geen migraties of `ingest/src`-bestanden gewijzigd.
- Diff komt overeen met de blueprint. De afwijkingen staan in `deviations.md` (alle klein, geen fail).

Extra controles:
- Uren en dagen: `HOUR_OPTIONS` loopt 01:00–23:00 (23 items). `daysAheadOptions('')` geeft 0–6. De selects bieden 00:00, 24:00 en 7 niet aan. `latest_local` 24:00 geeft een fout en 00:00 geeft `latestMidnight`. `timeOptions` en `daysAheadOptions` voegen alleen de al opgeslagen waarde toe (blueprint A7 en E19), zodat die niet stil verandert. De parser (`parseRuleFields`) accepteert uit zichzelf wel `earliest_local` '00:00' en `days_ahead` '7'. Dat is de bedoelde omgang met bestaande CLI-waarden: de UI kan ze niet nieuw kiezen, alleen behouden.
- `ruleHints` gooit nooit. Zelf geprobeerd met omgekeerd tijdvenster, min >= max, min = max, rommelwaarden ('abc', '9999', 'zz', '-1'), offshore en weekdag 0 of 9. Dat is gecombineerd met 6 profielen (waaronder `null`, {20,20}, {null,20}, {99,3} en niet-numerieke waarden) en 4 spots (waaronder default_min_kn `null` en 999). Geen enkele combinatie gooit. Een formulier waarvan `weekdays` `null` is, gooit wel. Dat valt buiten het type (`number[]`) en `ruleToForm` levert dat nooit.

## Problemen
Geen blokkerende problemen.
O-1 (observatie, geen fail): AC-7 en blueprint-stap 10 (rooktest tegen de lokale stack) zijn niet uitgevoerd. Lars moet `supabase start` draaien en controleren: ster, profiel opslaan met alleen de vijf kolommen, regel upsert en reset, ontfavorieten wist de regel, uitgelogd geen requests, en `uv run shakka admin alerts preview --user-id <Lars>` verandert na een wijziging in de app.
