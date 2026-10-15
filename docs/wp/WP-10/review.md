# Review WP-10, ronde 1
Oordeel: CHANGES_REQUIRED

Getoetst tegen `CLAUDE.md`, `docs/WORK_PACKAGES.md` (WP-10, WP-11), de blueprints van WP-01, WP-03, WP-05, WP-06, WP-07 en WP-08, en de bestaande code: `shakka/db.py`, `tests/fakes.py`, `tests/conftest.py`, `shakka/config.py`, `shakka/doctor.py`, `shakka/cli.py`, `shakka/jobs/forecast.py`, `shakka/domain/{alerts,dedup,evaluation,kite,messages,spot,forecast,tide,defaults,direction}.py`, de M1-migraties en de bestaande tests die `telegram` noemen.

Sterk punt: de bindende regels zijn goed overgenomen. Er is één `try` per favoriet, met `from_row`, `resolve_rule`, `diff_windows` en `render_alert` samen (WP-07/WP-08). De schrijfvolgorde is updates vóór inserts, en binnen de updates gaat rang 0 (`expired`/`cancelled`) vóór rang 1 (korter) en rang 2 (langer). De aanhaakpunten voor WP-17 (`plan_favorite` → aflevering → `store_plan`, zelf toegekende `id`) kloppen met `AlertStateEntry.to_row()`. Ik heb de scenario-uitkomsten nagerekend tegen de domeincode en ze kloppen: window A 10–16Z en B 12–15Z, bodyregels, kite 9 m² met ideaal 6,9, splitsen (`worsened` + `new`), samensmelten (`expired` vóór `improved`) en de go-URL. `FakeSupabase` registreert ook een `delete` zonder geraakte rijen als write; daarmee kloppen de verwachte `db.writes`. RLS is in orde: alles loopt via de secret key (service_role met grants op alle tabellen), niets via `anon`. Het verwijderen van `telegram_*` raakt precies de drie testbestanden, `config.py`, `.env.example` en RUNBOOK §4. `conftest.py` iterateert over `Settings.model_fields` en blijft dus werken.

## Blokkerend

B-1: Een spot met coördinaten maar zonder forecastrijen wordt `invalid` in plaats van "geladen met lege forecasts".
- Waar: Ontwerp, "Inputs", stap 2 (`newest = max(fromisoformat(r["fetched_at"]))`), plus A4, E10 en `test_no_forecast_data_keeps_state`.
- Waarom: `max()` over een lege reeks geeft een `ValueError`. Volgens de beschreven `try ... except ValueError` belandt zo'n spot dan in `invalid`, met een foutregel `spot <id>: ValueError: max() arg is an empty sequence`. Gevolgen:
  - `run_evaluation` meldt de spot als `failed` en `shakka evaluate` geeft exit 1 voor elke spot zonder forecast. Dat gebeurt bijvoorbeeld bij een nieuwe spot vóór de eerste forecastrun, of als de forecastrun voor zijn chunk faalde. WP-11 zou de evaluatiestap dan als gedeeltelijk mislukt zien.
  - De tak `not inputs.forecasts` → `ineligible ("no forecast data")` uit A4 is onbereikbaar. A4 en E10 lopen dan via "spot not loaded".
  - De test merkt dit niet op, want hij controleert alleen `ineligible == 1`.

  De blueprint spreekt zichzelf hier tegen, en de builder moet zelf kiezen.
- Voorstel:
  - Leg vast: geen forecastrijen in het bereik → `forecasts = []`, geen stalefilter, geen fout. De spot telt dan mee in `inputs` en `run_evaluation` schrijft 0 rijen zonder `failed`.
  - Voeg een inputs-test toe (spot met coördinaten, zonder forecastrijen → in `inputs` met `forecasts == []`, niet in `invalid`).
  - Voeg een evaluatie-test toe (`failed == ()`).
  - Laat `test_no_forecast_data_keeps_state` ook `plan.detail == "no forecast data"` controleren, via `plan_favorite` of `preview_alerts`.

## Niet-blokkerend

N-1: Privacy in de logs via httpx (aandachtspunt voor WP-11, nu nergens vermeld). httpx logt elke request op INFO via logger `httpx`, met de volledige URL (gecontroleerd in de httpx-documentatie). De queries van deze WP zetten user-id's in de URL: `profiles?user_id=in.(...)`, `alert_state?...&user_id=eq.<uuid>` bij elke update, en de admin-filters. AC-4 slaagt met `FakeSupabase`. Maar zodra WP-11 logging op INFO naar stdout zet, komen user-id's in de openbare Actions-logs. Voorstel: zet onder "Gevolgen voor latere WP's → WP-11" expliciet dat de loggers `httpx` en `httpcore` op WARNING moeten, plus een test met de echte `SupabaseRest` en een `httpx.MockTransport` onder caplog. Overweeg ook het extra `user_id`-filter in `store_plan` (de update op `id` is al uniek), zodat er minder user-id's in URL's staan.

N-2: A9 zegt dat de spot-id van een favoriet niet in de log komt. Toch logt `load_inputs_checked` `inputs: spot %s skipped`, en in de alertcontext laadt die alleen favoriete spots. Het lek is klein, omdat `run_evaluation` dezelfde spot ook logt. Overweeg in de alertcontext geen per-spot-waarschuwing te geven, bijvoorbeeld via een parameter of door de log alleen in `run_evaluation` te zetten.

N-3: `test_old_rows_deleted` is zo niet te schrijven. `NOW - 49 h` en `NOW - 47 h` zijn geen hele uren (NOW = 06:17Z), en `HourEvaluation` weigert die (`valid_at must be a whole hour`). Gebruik `floor_hour(NOW) - 49 h` (wordt verwijderd) en `floor_hour(NOW) - 47 h` (blijft staan). Hetzelfde geldt voor `test_forecast_range`: "`NOW + 8 d - 1 h` (heel uur)" en "`+ 8 d + 1 h`" zijn dubbelzinnig. Noem exacte UTC-tijden, anders laat een niet-hele `valid_at` de hele spot falen in `ForecastHour.from_row`.

N-4: "Tabellen en kolommen" noemt `alert_rules (*)` en `alert_state (*)`, terwijl het ontwerp juist expliciete `RULE_COLUMNS`/`STATE_COLUMNS` voorschrijft (nodig voor de fake). Maak dat gelijk. Daarnaast noemt de tekst `_short`, maar de interface `short_error`.

N-5: `profile set --level` staat in de tabel als `[beginner|intermediate|advanced]`, wat op `click.Choice` duidt (exit 2). Elders staat "de CLI-opties zijn gewone str/int, zodat elke domeinfout exitcode 1 geeft", en `set_profile` valideert `level` zelf. Kies één van beide.

N-6: `run_admin` vertaalt een "`ValueError` uit `normalize_base_url`" naar `invalid APP_BASE_URL`, maar zegt niet hoe het die onderscheidt van andere `ValueError`s. Eenvoudiger: laat de preview-actie `normalize_base_url` zelf aanroepen en een `AdminError("invalid APP_BASE_URL")` geven.

N-7: Zet in de RUNBOOK dat `--quiver` komma's als scheidingsteken gebruikt. `--quiver 7,5` wordt `[5.0, 7.0]` en niet 7,5 m²; decimalen typ je met een punt (`10.5`). Voor een Nederlandse gebruiker is dat verraderlijk.

N-8: Bij een update-mismatch maakt `store_plan` een `DatabaseError` zonder `status`/`code`. De foutregel wordt dan `DatabaseError (HTTP None, code None)`. Laat `HTTP`/`code` weg als ze `None` zijn.

N-9: Kosten (R5): de evaluatiejob leest elk uur alle forecastrijen van alle spots, ruwweg 25 × ~600 rijen × ~150 bytes ≈ 2 MB per uur, oftewel ≈ 1,5 GB per maand egress. Dat past binnen de gratis tier (5 GB), maar is geen verwaarloosbaar deel. Noem het als input voor WP-22, of beperk de forecastkolommen voor de evaluatie niet verder dan nodig.

N-10: `errors` "mag in `ingest_runs.steps`". Zet erbij dat WP-11 `errors` niet naar stdout mag schrijven: de regels voor overgeslagen favorieten bevatten de spot-id van een favoriet (zie A9).

## Gecontroleerde bronnen
- https://click.palletsprojects.com/en/stable/options/ (booleaanse vlagparen: `default=None` → `None` als de vlag ontbreekt)
- https://click.palletsprojects.com/en/stable/parameter-types/ (`click.UUID` → `uuid.UUID`, `click.Choice`)
- https://docs.postgrest.org/en/stable/references/api/tables_views.html (POST/PATCH met `return=representation`; niets over ontbrekende kolommen bij `merge-duplicates`, dus update/insert in A10 is terecht)
- https://www.python-httpx.org/logging/ (logger `httpx`, INFO, volledige URL per request; basis voor N-1)
- Lokaal: `ingest/uv.lock` (click 8.5.0, httpx 0.28.1, pydantic 2.14.1)
