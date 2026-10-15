# Review WP-11, ronde 2
Oordeel: APPROVED

Ronde 2 beoordeelt revisie 2 van het blueprint. Beide blokkerende punten uit ronde 1 zijn echt opgelost. De nieuwe onderdelen (getijbudget, JSON-conversie binnen `run_step`, `FlakyIngestRuns`, het escapen van annotaties) heb ik tegen de bestaande code en de toolkit-broncode gecontroleerd. Ze kloppen en introduceren geen blokkerende punten.

## Controle van de punten uit ronde 1

- **B-1 (opgelost).** De AC-1-assertie zoekt nu de eerste `insert` en eist `db.writes[:first_insert] == [("update", "ingest_runs")]`. Dat klopt met de code:
  - `FakeSupabase.writes` is een `list[tuple[str, str]]`;
  - `update` registreert `("update", table)` vóór de match, dus ook bij 0 rijen (`fakes.py` r. 315);
  - `seed` komt niet in `writes` (r. 109-111);
  - `spots_sync` draait pas na de insert.

  `test_progress_update_after_each_step` (`len(steps) + 2`) blijft hiermee consistent.
- **B-2 (opgelost).** De verwachte tekst komt nu uit een aparte fake `db2` met `sync_spots(db2, load_spots(yaml_path))`, `seed_forecasts(db2, fetched_at=NOW)`, `seed_user(db2)` en `run_alerts(..., dry_run=True)`. `seed_forecasts` heeft de keyword `fetched_at` en schrijft dezelfde `MODELS3`/`WINDS`-rijen als `fake_forecast_fetch` via `ForecastHour.to_row(fetched_at=now)` in `run_forecast_ingest`. `run_alerts` heeft `dry_run` (alerts.py r. 318). De toestand is dus gelijk aan die van de CLI-run vóór de alertstap. Er staan drie controles in die voorkomen dat de test ongemerkt niets toetst:
  - `assert len(dry.messages) == 1`;
  - de controle op `counts["events"] == 1` in de CLI-run;
  - de controle van titel en bodyregels tegen log, stdout en stderr.

  Geen enkele bestaande logregel bevat de spotnaam of bodytekst (alle `logger.`-aanroepen nagelopen).
- **N-1 t/m N-10:** verwerkt zoals beschreven in "Verwerking review".

## Controle van de nieuwe onderdelen

- **Getijbudget via `bounded_fetch`.**
  - **`shakka.jobs.tides` blijft echt ongewijzigd.** `run_tide_ingest(db, *, now, force=False, fetch=...)` accepteert een `TideFetcher` `(station, start, end)` en vangt per station elke `Exception` af (r. 119). Een `TimeoutError` uit `bounded_fetch` komt daardoor als `"<station>: TimeoutError: tide step time budget of 240 s reached"` in `failed`/`errors`. Daarna volgen `delete_old_tides` en het normale resultaat.
  - **De testverwachtingen kloppen** (`failed` gesorteerd, de prefix van de errorregel, `budget_skipped == 1`). `STATION_CODE_RE` accepteert `station-a`/`station-b`.
  - **Een lopend request** wordt niet afgebroken. `fetch_tide_extremes` doet geen retries (één `client.post`). De stap duurt dus hooguit 240 s plus één request met de per-fase timeouts van 30 s.
  - **De run blijft binnen `timeout-minutes: 15`.** Daarnaast loopt alleen de forecast-retry (een paar pogingen met backoff, één chunk). Bij een normaal bereikbare database past de run ruim binnen 15 minuten. Een hangende database is het vangnet van E25/A10.
- **JSON-conversie binnen `run_step`.** `shakka.db.to_json` gebruikt `allow_nan=False`, en `json.dumps` geeft dan direct een `ValueError`. Naïeve datetimes en onbekende types geven via `_json_default` ook een `ValueError`. E28 en `test_counts_not_json_fails_step` zijn daarmee correct. `except StepSkipped` staat vóór `except Exception`; dat is correct.
- **`FlakyIngestRuns`.** De vier soorten zijn disjunct en herkenbaar:
  - de wezen-update filtert op `status`;
  - de voortgangs- en slotupdate filteren op `id`;
  - alleen de slotupdate heeft `finished_at` in `values` (de wezen-update ook, maar die heeft geen `id`-filter).

  `DatabaseError("boom", status=503)` klopt met de constructor (`message, *, status, code`). De fout wordt vóór `super()` gegooid, dus `writes` registreert hem niet.
- **Escapen van annotaties.** `escapeData` in `actions/toolkit` (`packages/core/src/command.ts`) vervangt `%`→`%25`, `\r`→`%0D` en `\n`→`%0A`. Dubbele punten en komma's worden alleen in properties geëscapet, niet in de berichtdata. Het blueprint neemt `%`→`%25` over, in de juiste volgorde (eerst `%`), en maakt van CR/LF spaties. Dat is veilig en levert één regel op. De testverwachtingen kloppen: `"83% of\r\nthe guard"` wordt `"::warning::83%25 of  the guard"` met twee spaties, en `"%0A"` wordt `"%250A"`.
- **Budgetgrens 6.400 in de test.** `BudgetGuard.record` rondt af op 2 decimalen (`round(old + weight, 2)`), dus 6.398,8 + 1,2 wordt precies 6400.0. `0.8 * 8000` geeft in float ook precies 6400.0. "Strikt boven" werkt dus zoals de test verwacht.

## Blokkerend
Geen.

## Niet-blokkerend

N-1: Importpad van de hulpfuncties. `short_error` en `db_error_summary` (gebruikt in `run_step` en de stappen) staan in `shakka.jobs.inputs`, niet in `shakka.db`. Het blueprint noemt het pad niet. De builder vindt ze makkelijk, maar één zin in "Interfaces" voorkomt zoekwerk of een kopie.

N-2: Volgorde van stations onder het budget. `run_tide_ingest` loopt de stations alfabetisch af. Blijven de eerste stations bij een gedeeltelijke RWS-storing steeds hangen (30 s per stuk), dan komen latere stations onder het budget van 240 s pas aan bod als die eerste weer reageren. In M1, met een handvol stations, past alles ruim (minstens 8 stations per run, ook als alles time-out geeft). Vermeld het eventueel bij WP-22 (uniform budget).

N-3: `TIDE_STEP_BUDGET_S` is `Final`, maar wordt in `test_tide_budget_zero_still_runs_alerts` gemonkeypatcht. Dat werkt alleen als `step_tides` de module-global bij elke aanroep leest. Gebruik hem dus niet als default-argument of als waarde die bij het importeren vastligt. De pseudocode doet het goed; een korte comment bij de constante helpt de builder.

N-4: Faalt `uv sync`, dan draait de activiteitsstap (`if: !cancelled()`) toch `uv run` en geeft een tweede fout. Dat is onschuldig, want de run is dan al rood. Het kan eventueel worden voorkomen met `if: ${{ !cancelled() && steps.<sync>.outcome == 'success' }}`. Geen actie vereist.

N-5: R10 zegt terecht dat een lopend request niet wordt onderbroken. Let wel: de httpx-timeout van 30 s geldt per fase en per leesoperatie, dus een server die heel langzaam data blijft sturen kan één request langer laten duren. De job-timeout blijft het vangnet (E25). Geen actie.

## Gecontroleerde bronnen
- https://github.com/actions/toolkit/blob/main/packages/core/src/command.ts: `escapeData` vervangt `%`→`%25`, `\r`→`%0D` en `\n`→`%0A`; `escapeProperty` doet daarnaast `:` en `,`. De commandovorm is `::name props::data`. Dat klopt met `escape_command_data` en `github_annotation`.
- De GitHub-documentatie uit ronde 1 (events, concurrency, contexts, notifications, REST commits, workflow commands, httpx logging). Workflow en claims zijn sinds ronde 1 niet inhoudelijk gewijzigd.
- Code in de worktree:
  - `ingest/src/shakka/jobs/tides.py` (signature, `TideFetcher`, foutafhandeling per station);
  - `ingest/src/shakka/rws/tides.py` (`fetch_tide_extremes` zonder retries, `STATION_CODE_RE`, `TideFetchError`);
  - `ingest/src/shakka/db.py` (`to_json`, `DatabaseError`);
  - `ingest/src/shakka/jobs/forecast.py` (`run_forecast_ingest`, `ForecastFetchError` per chunk);
  - `ingest/src/shakka/openmeteo/client.py` (retries);
  - `ingest/src/shakka/jobs/alerts.py` (`run_alerts(..., dry_run)`, logging, `errors`);
  - `ingest/src/shakka/jobs/inputs.py` (`short_error`, `db_error_summary`);
  - `ingest/src/shakka/domain/messages.py` (titel en body);
  - `ingest/src/shakka/budget.py` (afronding in `record`);
  - `ingest/src/shakka/spots/{loader,sync}.py`, `ingest/src/shakka/domain/spot.py` en `ingest/src/shakka/jobs/runtime.py`;
  - `ingest/tests/{fakes.py,job_fixtures.py,evaluation_fixtures.py,test_job_alerts.py}`;
  - `.github/workflows/ci.yml`;
  - de WP-11-sectie in `docs/WORK_PACKAGES.md`.
