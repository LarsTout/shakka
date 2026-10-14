# Review WP-03, ronde 1
Oordeel: CHANGES_REQUIRED

De blueprint is grondig en grotendeels uitvoerbaar zoals hij er staat. Ik heb de model-id's, de parameters, de responsvorm (lijst bij 2 locaties met `location_id` alleen vanaf element 1, object bij 1 locatie, achtervoegsels `_<model-id>`, eenheden `kn` en `°`, `utc_offset_seconds = 0`, `time` als Unix-seconden) en de gewichtsformule zelf gecontroleerd. Dat klopt allemaal. Er is één blokkerend punt: de tijdsemantiek van de vlagen.

## Blokkerend

B-1: De tijdsemantiek van `gust_kn` is niet vastgelegd en wijkt stilzwijgend af van de projectconventie. Waar: Ontwerp/Parser (regel 6: `valid_at = datetime.fromtimestamp(t, tz=UTC)` voor alle drie de variabelen), contract `ForecastHour`, "Gevolgen voor latere WP's" (WP-05). Waarom: volgens de Open-Meteo-documentatie zijn `wind_speed_10m` en `wind_direction_10m` momentane waarden op tijdstip T, maar `wind_gusts_10m` is "Preceding hour max", het maximum over [T-1h, T). De projectafspraak in `WORK_PACKAGES.md` is: "Uurwaarden horen bij het uur dat begint op `valid_at`" ([T, T+1h)). Met de huidige parser hoort de vlaag die bij `valid_at = T` wordt opgeslagen dus bij het vorige uur. Dat verschuift `too_gusty`/`gusty` in WP-05 en de windows in WP-07 een uur, en WP-05 kan dat niet zien, omdat het contract er niets over zegt. Voorstel: maak hier een expliciete keuze (eventueel als **[keuze Lars]**) en leg die vast in een aanname, in de docstring van `ForecastHour` en onder "Gevolgen voor latere WP's". Er zijn twee opties:
  (a) Vlagen een uur terugschuiven, zodat `gust_kn` bij T de ruwe waarde van T+1h is. Dat is conform de conventie. Het laatste uur van de horizon krijgt dan `gust_kn = None`. Pas regel 6 van de parser en `test_fixture_values_match_raw_json`/`test_fixture_sample_per_model` aan (vlaag op index i+1), en voeg een edge case toe voor het laatste uur.
  (b) De ruwe mapping houden en als bewuste afwijking documenteren ("`gust_kn` op `valid_at` T = max over [T-1h, T), zoals Open-Meteo die levert"), met een expliciete regel voor WP-05.
  Optie (a) is correcter. Optie (b) is ook acceptabel, mits vastgelegd.

## Niet-blokkerend

N-1: De volgorde in Job stap 3 is dubbelzinnig. "`ForecastFetchError` → een regel in `errors` en door naar de volgende chunk" staat vóór "boek het gewicht (ook na een fout)". Een letterlijke `continue` slaat de boeking over, terwijl A5 het tegendeel wil. Formuleer het als: fetch in try → bij een fout errors aanvullen → altijd boeken → alleen bij succes dedupliceren en upserten. Laat `test_job_three_500_reports_error` ook asserten dat `api_usage` na de fout `calls == 1,2` en `requests == 1` heeft.

N-2: `test_fixture_knmi_horizon` eist "168 rijen per locatie" voor ICON, ECMWF en GFS. Dat hangt af van de toevallige inhoud van de capture: één `null`-uur en de test faalt, waarna de builder zelf moet kiezen. Leid het verwachte aantal liever af uit de ruwe JSON (aantal indexen waarop niet alle drie de waarden `null` zijn), of eis `== len(time)` alleen als de builder na de capture heeft gecontroleerd dat er geen `null` in zit (stap 2).

N-3: De fixture bevat Open-Meteo-data (CC BY 4.0) en komt in een publieke repo. Zet de bronvermelding erbij, bijvoorbeeld "Weather data by Open-Meteo.com, CC BY 4.0" in de docstring van `test_openmeteo_forecast.py` of in een korte `README.md` in `tests/fixtures/openmeteo/`. De JSON zelf blijft onbewerkt.

N-4: `forecast_days=7` met `timezone=GMT` levert data van vandaag 00:00Z tot vandaag+7 00:00Z. Een lokale dag "vandaag+7" (`days_ahead = 7` in `alert_rules`, toegestaan door de CHECK 0–7) heeft dus nooit data. A10 noemt dit al. Maak expliciet dat `days_ahead = 7` zonder wijziging leeg blijft, zodat Lars dit in WP-10/WP-16 kan besluiten (8 dagen kost hetzelfde gewicht, maar vergt een AC-2-wijziging).

N-5: `run_forecast_cli` en `_open_resources`: leg vast dat `SupabaseRest` en de `httpx.Client` altijd worden gesloten (`with` of `try/finally`), ook bij `DatabaseError`.

N-6: CLI-tests: door de autouse-fixture in `conftest.py` is de env leeg. `test_fetch_success_output`, `test_fetch_errors_exit_1`, `test_dry_run_...` en `test_database_error_exit_1` moeten dus `SUPABASE_URL` en `SUPABASE_SECRET_KEY` met `monkeypatch.setenv` zetten (zoals WP-02 doet). Noem dat in het Testplan.

N-7: Leg vast dat de job `fetch(http, chunk)` zonder `forecast_days` aanroept en het gewicht schat met `DEFAULT_FORECAST_DAYS`, zodat schatting en request niet uit elkaar kunnen lopen.

N-8: `shakka/cli.py` wordt ook door WP-02 gewijzigd (groep `spots`). Bij de merge geeft dat een triviaal conflict; even melden aan de builder.

N-9: In `test_weight_matches_open_meteo_up_to_14_days` is `v` het product variabelen × modellen, terwijl de functie die als twee argumenten krijgt. Schrijf voor wat er wordt aangeroepen, bijvoorbeeld `estimate_call_weight(1, v, 1, d)`.

## Gecontroleerde bronnen
- https://open-meteo.com/en/docs (`cell_selection` land/sea/nearest, `timeformat=unixtime`, `wind_speed_unit=kn`, `forecast_days` 0–16 standaard 7, `timezone` standaard GMT, lijstuitvoer bij meerdere locaties, foutformaat 400 `error`/`reason`; variabeletabel: `wind_gusts_10m` = "Preceding hour max", `wind_speed_10m`/`wind_direction_10m` = "Instant")
- https://open-meteo.com/en/docs/knmi-api (`knmi_harmonie_arome_netherlands`, 2 km, elk uur, 2,5 dag; `knmi_seamless` vult aan met ECMWF IFS)
- https://open-meteo.com/en/docs/dwd-api (`dwd_icon_seamless`)
- https://open-meteo.com/en/docs/ecmwf-api (`ecmwf_ifs` = IFS HRES 9 km, open data sinds 1-10-2025; `ecmwf_ifs025`)
- https://open-meteo.com/en/pricing (600/min, 5.000/uur, 10.000/dag, 300.000/maand; fractionele telling)
- https://github.com/open-meteo/open-meteo/blob/main/Sources/App/Helper/Writer/ForecastApiResult.swift (`calculateQueryWeight`: per locatie `max(1, max(v/10, d/14·v/10))`, `v` = variabelen × domeinen)
- Live: https://api.open-meteo.com/v1/forecast?latitude=52.4700,52.1000&longitude=4.5700,4.2700&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m&models=knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless&wind_speed_unit=kn&timezone=GMT&timeformat=unixtime&forecast_days=1&cell_selection=sea (lijst van 2; `location_id` ontbreekt bij element 0 en is 1 bij element 1; sleutels `<var>_<model-id>`; eenheden `kn`/`°`; `utc_offset_seconds` 0)
- Live: dezelfde query met één locatie en `forecast_days=7` (object, geen `location_id`; KNMI-arrays eindigen in `null`, de andere modellen niet)
- Bestaande code: `ingest/src/shakka/db.py`, `http.py`, `cli.py`, `config.py`, `doctor.py`; `ingest/tests/fakes.py`, `conftest.py`, `test_domain_purity.py`, `test_repo_hygiene.py`; `supabase/migrations/20261015090000_m1_schema.sql`; `docs/wp/WP-01/blueprint.md` en `deviations.md`
