# Review WP-12, ronde 1
Oordeel: APPROVED

## Blokkerend
Geen.

## Niet-blokkerend
N-1: pgTAP-asserts 14, 18 en 20 in `06_marine_hours.test.sql` gaan uit van een lege `marine_hours` (`count = 2`, `is_empty(select 1 from public.marine_hours)`). Waar: Testplan, pgTAP. Waarom: draait de verifier AC-5 (echte `shakka marine fetch` tegen de lokale stack) vóór `supabase test db` zonder `db reset` of zonder de test-spot op te ruimen, dan falen deze asserts terwijl de code klopt. De bestaande `03_rls_anon.test.sql` heeft hetzelfde patroon, dus het is consistent. Voorstel: filter op `where spot_id = 'pgtap-spot'`, of zet in stap 12 en in de RUNBOOK-sectie expliciet dat je `supabase db reset` draait vóór `supabase test db`.

N-2: `formatMeters` noemt de afronding (`Math.floor(x * 10 + 0.5) / 10`) maar niet de opmaak. Waar: Interfaces, `marine.ts`. Waarom: `'0,0'` en `'1,0'` krijg je alleen met `toFixed(1)` en daarna `.replace('.', ',')`. `toLocaleString` mag niet (test `no-local-date-getters`). Daarnaast geeft binaire afronding bij randwaarden (1.15 → `'1,1'`) een klein verschil. Dat is voor modelwaarden irrelevant, maar zet de voorbeelden in de test niet op zulke randen. Voorstel: één zin over de opmaak toevoegen.

N-3: De notitie verschijnt bij `waves.size > 0`. Waar: Interfaces, `+page.svelte`. Waarom: `waves` bevat ook uren die niet zichtbaar zijn (donker, of buiten de groepen). De notitie kan dus staan zonder één zichtbare golfregel. Voorstel: accepteren (het is alleen een notitie) of de voorwaarde baseren op zichtbare uren. Geen test nodig.

N-4: Er zijn twee plekken die de fallback `om_marine.fetch_marine` bepalen. `_run` lost `marine_fetch or om_marine.fetch_marine` al op bij het bouwen van de context, en `step_marine` doet het daarna nog een keer. Waar: Interfaces, `shakka.pipeline`. Waarom: de fallback in `step_marine` werkt alleen voor een `PipelineContext` die direct in een test wordt gebouwd. Dat is onschuldig, maar de tekst "opzoeken op het moment van aanroepen" klopt alleen voor die route. Voorstel: laten zoals het is (spiegelt `forecast_fetch`) of één van de twee schrappen.

N-5: E27 (`DatabaseError` in de pipeline geeft stap `failed`) verwijst naar `test_marine_exception_is_partial_run`, maar die test gebruikt een `RuntimeError`. Waar: Edge cases. Waarom: het pad loopt via dezelfde `except Exception` in `run_step`, dus de dekking is er feitelijk wel. Alleen de koppeling is onnauwkeurig. Voorstel: verwijzen naar `test_job_database_error_propagates` plus de generieke `run_step`-tests van WP-11.

N-6: `test_resources_closed` eist dat `close()` van de fake één keer wordt aangeroepen. `FakeSupabase.close()` telt niets. Waar: Testplan, `test_cli_marine.py`. Voorstel: noem dat de test een kleine subklasse of wrapper met een teller gebruikt, zodat de builder `fakes.py` hiervoor niet aanpast.

N-7: De modeltabel in de Open-Meteo-docs noemt voor DWD EWAM een horizon van 8 dagen. Live levert `ewam` ca. 80 uur (zelf gecontroleerd: laatste niet-null-index 79 van 168, op 52,47/4,57 en op 52,75/5,30). Waar: Externe afhankelijkheden. Waarom: een builder die de docs leest, kan denken dat A1 overbodig is. Voorstel: één regel toevoegen dat de docs-tabel afwijkt van wat de API live teruggeeft, en dat de live-observatie geldt (R1 dekt het gedrag al).

N-8: `formatKn` wordt hergebruikt voor seconden. De naam suggereert knopen. Dat is functioneel juist (`Math.floor(x + 0.5)`), dus alleen stijl. Laten zoals het is is prima.

N-9: `Attribution.svelte` spreekt van "Weermodellen van … DWD, ECMWF". De Marine-docs eisen "a clear attribution to DWD as well as a reference to Open-Meteo". Daar is aan voldaan: DWD en Open-Meteo staan erin, en de golfnotitie noemt DWD en ECMWF. Het ongewijzigd laten van `Attribution.svelte` (vanwege merges met WP-15/WP-16) is verdedigbaar. Een latere tekstuele aanvulling ("weer- en golfmodellen") kan in WP-23.

Toetsing van de aandachtspunten van de orchestrator:
- Harde regels: Open-Meteo Marine wordt alleen aangeroepen vanuit `shakka/openmeteo/marine.py` (de isolatietest dekt dat). Het gewicht wordt geboekt onder `open_meteo_marine` via de gedeelde `BudgetGuard` (prefix `open_meteo_`). De migratie heeft `enable row level security`, revoke, expliciete grants (`anon`/`authenticated` select, `service_role` CRUD) en een policy, plus pgTAP. De bronvermelding blijft staan en er is geen scraping. De offshore-regel wordt niet geraakt.
- Model-id's en parameters zijn zelf live gecontroleerd. `models=ewam,ecmwf_wam`, `hourly=wave_height,wave_period,wave_direction`, `timezone=GMT`, `timeformat=unixtime`, `forecast_days=7` en `cell_selection=sea` werken allemaal. De sleutels hebben het achtervoegsel `_<model>`, met eenheden `m`, `s` en `°`. `location_id` ontbreekt bij element 0 en is 1 bij element 1. Kust: EWAM 80 uur, ECMWF WAM 168 uur. IJsselmeer: EWAM 80 uur, ECMWF WAM helemaal null. Gewicht: 3 × 2 = 6 variabelen×modellen (≤ 10) en 7 dagen (≤ 14), dus 1,0 per spot.
- Golven tellen niet mee. Geen enkele wijziging raakt `shakka.domain.evaluation`, `jobs/evaluate`, `jobs/alerts` of `jobs/inputs`. In de huidige broncode leest niets `marine_hours`.
- Pipeline: `marine` komt direct na `forecast`. Een `MarineFetchError` of budgetstop geeft `partial`, een andere exception `failed`. De run wordt `partial` met exitcode 0. `step_alerts`, `run_status`, `exit_code_for` en de stale-regel blijven ongewijzigd. Bestaande tests met `run_real` en `patch_runtime` krijgen een fake fetch, dus geen echte sleeps. `test_budget_warning_recorded` (`report.status == "ok"`) blijft groen.
- Web: de wijzigingen zijn additief. Een mislukte golfquery geeft `marine: []` met één anonieme `console.warn`. Rijen met een `fetched_at` ouder dan 3 uur worden verborgen. `data-tables.test.ts` krijgt `marine_hours` erbij. De fixtures kloppen: 12:00Z is 14:00 lokaal, 1.24 wordt `'1,2'`, 5.4 wordt `'5'`, 250° wordt WZW, en `MARINE_STALE` is 3 h 1 min oud.
- Merge-risico: de pagina-, `page-data`-, fixture- en CSS-wijzigingen zijn klein en lokaal. De migratietijdstempel volgt na `20261015150000`. R5 en R6 benoemen dat terecht.
- A1, A9, A14 en A15 zijn onderbouwd en gemarkeerd als keuze of voorstel. Geen bezwaar.

## Gecontroleerde bronnen
- https://open-meteo.com/en/docs/marine-weather-api (endpoint, parameters incl. `forecast_days` 0–8, `cell_selection` standaard `sea`, `timeformat`, modeltabel, variabelen "Instant", richting "from", meervoudige locaties, foutformaat, kustdisclaimer, DWD-attributie)
- https://marine-api.open-meteo.com/v1/marine?latitude=52.4700,52.7500&longitude=4.5700,5.3000&hourly=wave_height,wave_period,wave_direction&models=ewam,ecmwf_wam&timezone=GMT&timeformat=unixtime&forecast_days=7&cell_selection=sea (live, 15-10-2026: lijststructuur, sleutelnamen, eenheden, `location_id`, dekking per model)
- https://open-meteo.com/en/pricing (limieten 10.000/dag, 300.000/maand; weging >10 variabelen of >2 weken)
- Bestaande code: `ingest/src/shakka/{pipeline.py,budget.py,db.py,cli.py}`, `jobs/{forecast.py,runtime.py,inputs.py}`, `openmeteo/{client.py,forecast.py,models.py}`, `domain/forecast.py`; tests `test_pipeline.py`, `test_cli_pipeline.py`, `pipeline_fixtures.py`, `test_migrations.py`, `test_openmeteo_isolation.py`, `openmeteo_payloads.py`, `fakes.py`; `supabase/migrations/*`, `supabase/tests/0{1,2,3,5}_*.sql`; `web/src/lib/{data.ts,page-data.ts,labels.ts,view.ts}`, `web/src/routes/spot/[id]/+page.svelte`, `Attribution.svelte`; `web/test/{schema-columns,data-tables,page-data,no-local-date-getters}.test.ts`, `web/test/fixtures/spot-data.ts`; `docs/RUNBOOK.md`; blueprints WP-01, WP-03, WP-11 en WP-14 (secties over WP-12).
