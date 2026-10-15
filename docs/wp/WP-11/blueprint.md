# Blueprint WP-11: Orkestratie: uurlijkse workflow, logging, foutmeldingen
Status: DRAFT
Revisie: 2

## Doel
Alle M1-stappen elk uur via GitHub Actions in een vaste volgorde draaien, met foutisolatie per stap:
1. `shakka.pipeline` met `STEPS` (`spots_sync`, `forecast`, `tides`, `evaluate`, `alerts`), `run_hourly` en de CLI `shakka run-hourly`.
2. Elke run komt als rij in `ingest_runs`: `running` bij de start, aan het eind `ok`, `partial` of `failed`, met per stap status, duur, tellingen en fout.
3. Operatorsignalen zonder eigen kanaal (A-16): de exitcode laat de workflow-run falen, en GitHub mailt Lars. Een hoog Open-Meteo-verbruik wordt een `::warning::`-annotatie (geen mail).
4. Logging naar stdout zonder secrets en zonder persoonsgegevens. De Actions-logs van deze publieke repo zijn openbaar.
5. `.github/workflows/hourly.yml` en een maatregel tegen het uitschakelen van schedules na 60 dagen zonder activiteit.
6. `docs/RUNBOOK.md`: runs bekijken, `ingest_runs` lezen, handmatig starten, meldingsinstellingen en de 60-dagenmaatregel.

## Aannames
- **A1. Beslispunt GitHub-meldingen (start WP-11), overgenomen volgens de aanbeveling van de architect.**
  - Lars zet in zijn GitHub-account e-mailmeldingen voor Actions aan, desgewenst alleen bij gefaalde workflows. De mail komt van GitHub bij elke gefaalde run.
  - Er is geen eigen deduplicatie. Tijdens een aanhoudende storing komt er elk uur een mail; dat is bewust geaccepteerd. Pauzeren kan via de variable `HOURLY_ENABLED` (A6).
  - Exitcode 1 bij runstatus `failed`, **en ook** als `alerts` is overgeslagen met reden `stale_forecast`. Dan komen er geen alerts, en dat moet Lars weten. Anders exitcode 0, ook bij `partial`.
- **A2. Wanneer is een run `failed`?** De contracten noemen `ok`, `partial` en `failed`, maar geven geen regel. De regel is:
  - `ok`: alle stappen hebben status `ok`;
  - `failed`: de stap `alerts` heeft status `failed` (er zijn geen alerts berekend), of geen enkele stap heeft status `ok` of `partial` (niets werkte), of de run kon niet in `ingest_runs` worden vastgelegd (A9);
  - `partial`: alle andere gevallen.

  Waarom zo: het doel van M1 is dat alerts kloppen. Faalt `forecast` terwijl de data nog vers is, dan draaien de alerts wel. AC-2 eist dan `partial` met exitcode 0. Faalt de alertstap zelf, dan is er geen bruikbaar resultaat, en dat verdient een mail. Een gefaalde `evaluate` raakt in M1 alleen de (nog niet bestaande) app; de alertjob evalueert zelf per regel (WP-10).
- **A3. Stapstatussen.** Een stap is:
  - `ok`;
  - `partial`: de job draaide, maar meldde fouten per onderdeel (forecast: `errors` of `skipped_budget`; tides: `failed`; evaluate: `failed`; alerts: `skipped` of `write_errors`; zie WP-03, WP-04 en WP-10 "Gevolgen");
  - `failed`: de stapfunctie gaf een exception;
  - `skipped`: een voorwaarde ontbrak (in M1 alleen `alerts` met reden `stale_forecast`).
- **A4. Stale-regel.** De alertstap controleert de versheid alleen als de forecaststap niet `ok` is (`failed` of `partial`). Dan wordt de nieuwste `forecast_hours.fetched_at` gelezen (één select met `order=fetched_at.desc`, `limit=1`). Ontbreken er rijen, of is de nieuwste strikt ouder dan `now - 3 h`, dan wordt `alerts` overgeslagen met reden `stale_forecast`. Precies 3 uur oud is nog vers. Is de forecaststap `ok`, dan zijn alle rijen van spots met coördinaten net met `fetched_at = now` geschreven en is controle overbodig. De drempel is de globale nieuwste rij, niet per spot: in M1 (hooguit 50 spots) zitten alle spots in één request (WP-03 A6), dus slagen of falen ze samen en is de globale controle gelijk aan een controle per spot. WP-10 (`load_inputs_checked`) houdt per spot de rijen met `fetched_at >= nieuwste fetch van díe spot - 3 h`. Dat is relatief aan de nieuwste fetch van die spot, níet aan `now`: een spot waarvan alle rijen 10 uur oud zijn, wordt dus nog gebruikt. Bij meer dan één chunk is dat een gat (zie "Gevolgen voor latere WP's", WP-22).
- **A5. De cron draait alleen de code van `main`.** GitHub start geplande workflows altijd op de laatste commit van de **default branch** ([bron](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)), en dat is hier `develop`. Daarom checkt de workflow expliciet `ref: main` uit. Gevolg: het workflowbestand komt van `develop`, de code van `main`. Een `workflow_dispatch` mag via de input `ref` ook `develop` draaien, voor een eerste test vóór de promotie; de schedule gebruikt altijd `main`.
- **A6. Aan/uit via de repository-variable `HOURLY_ENABLED`.** De job draait bij `schedule` alleen als `vars.HOURLY_ENABLED == 'true'`. Een `workflow_dispatch` draait altijd. Waarom: na de merge van WP-11 naar `develop` start de schedule direct, maar `main` bevat `shakka run-hourly` pas na de promotie door Lars. Zonder deze schakelaar faalt elk uur een run (en volgt elk uur een mail) tot de promotie en tot de secrets er zijn. De variable dient ook als pauzeknop bij een lange storing. Een niet-gezette variable geeft een lege string ([bron](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts)), dus de schedule staat standaard uit.
- **A7. Maatregel tegen het uitschakelen na 60 dagen: een vroege waarschuwing, geen automatische keepalive.**
  - GitHub schakelt geplande workflows in een publieke repo stil uit na 60 dagen zonder repository-activiteit. Wat precies als activiteit telt, staat niet in de documentatie.
  - Automatische keepalives (dummycommits of het periodiek aanroepen van de enable-API) vallen af: de bekendste action (`gautamkrishnar/keepalive-workflow`) is door GitHub Staff uitgeschakeld wegens een schending van de voorwaarden (gecontroleerd 15 oktober 2026), en of een enable-call de teller reset, is niet gedocumenteerd.
  - Gekozen aanpak: na de pipeline bepaalt een extra stap de datum van de laatste commit op de default branch (GitHub REST API, `gh api`). Vanaf 45 dagen volgt een `::warning::`-annotatie. Vanaf 53 dagen een `::error::` en exitcode 1, dus elk uur een mail tot Lars iets naar `develop` merget (zie RUNBOOK). Commits op de default branch zijn een conservatieve benadering van "activiteit". Is de workflow toch uitgeschakeld, dan zet Lars hem weer aan met `gh workflow enable hourly.yml` (de meldingen gaan daarna naar wie hem aanzette).
- **A8. Geen `inputs`-keyword om het laden te delen.** WP-10 bood die optie (≈ 30 extra GET-requests per run). De egress blijft volgens WP-10 R5 binnen de gratis tier, dus dat is niet nodig. Dit kan in WP-22.
- **A9. Fail-fast als de run niet kan worden vastgelegd.** Faalt de insert van de `ingest_runs`-rij (`DatabaseError`), dan draait er geen enkele stap: de database is dan vrijwel zeker onbereikbaar. Het resultaat is `failed`, exitcode 1 en geen `run_id`. Faalt alleen de slotupdate, dan blijft de berekende status staan, maar wordt de exitcode 1 (Lars mist anders de details).
- **A10. Wezen-rijen.** Een run die door de job-timeout (15 min) wordt afgebroken, laat een rij met `status = running` achter. Elke nieuwe run zet zulke rijen met `started_at < now - 1 h` eerst op `failed`, met `finished_at = now` en `error_summary = "abandoned: the run did not record its end (timeout or crash)"`. Een fout daarbij wordt gelogd en genegeerd.
- **A11. Additieve uitbreidingen van het contract.** De signatures uit WORK_PACKAGES blijven. Erbij komen:
  - `run_hourly(..., steps=STEPS, forecast_fetch=None, tide_fetch=None, clock=None)` (testnaden, naar het patroon van WP-03 en WP-04);
  - `RunReport.run_id` en `RunReport.annotations`;
  - per stap in `ingest_runs.steps`, naast `{name, status, duration_ms, counts, error}`, ook `error_type`, `reason` en `warnings`;
  - `StepOutcome`, `StepSkipped`, `PipelineContext`, `StepReport` en de stapfuncties;
  - `shakka.logsetup` (logging en redactie), `shakka.activity` en de CLI `shakka check-activity`;
  - `shakka.jobs.runtime.open_http()`;
  - de GitHub Actions-variable `HOURLY_ENABLED` (A6). De orchestrator heeft hem al aan de env-tabel in WORK_PACKAGES op `develop` toegevoegd (commit `ed68d2e`); de builder zet hem alleen in RUNBOOK §4;
  - `TIDE_STEP_BUDGET_S` (tijdsbudget van de getijstap, zie "De stappen") en `shakka.logsetup.github_annotation` (escapen van annotaties).

  `STEPS` is een tuple in plaats van een lijst (onveranderlijk). Latere WP's voegen stappen toe door de tuple in de broncode aan te passen.
- **A12. Geen nieuwe dependencies, geen migratie, geen wijziging aan `shakka.domain`, `shakka.db` of `tests/fakes.py`.** `ingest_runs` bestaat al (WP-01), met een identity-`id`, CHECKs op `status`, op `steps` (JSON-array) en op `finished_at >= started_at`, en alleen rechten voor `service_role`.
- **A13. Geen secrets en geen persoonsgegevens in stdout.** Logregels bevatten alleen scalaire tellingen (int, float, bool), stapnamen, statussen en het type van een fout. Foutteksten (`error`) en lijsten (zoals `AlertJobResult.errors`, met spot-id's van favorieten) staan alleen in `ingest_runs.steps`. Die tabel is alleen met de secret key leesbaar (WP-01). Secrets worden daarnaast uit foutteksten en uit elke geformatteerde logregel geredigeerd (vangnet), en GitHub maskeert geregistreerde secrets in de logs.

## Ontwerp

### Lagen
```
shakka.cli ── run-hourly ──> shakka.pipeline.run_hourly_cli ──> run_hourly
                                   │                               │
                                   ├─ shakka.logsetup              ├─ STEPS: spots_sync, forecast, tides, evaluate, alerts
                                   └─ shakka.jobs.runtime          │     └─ shakka.spots.*, shakka.jobs.{forecast,tides,evaluate,alerts}, shakka.budget
                                      (open_db, open_http, utcnow) └─ ingest_runs via shakka.db
shakka.cli ── check-activity ──> shakka.activity.run_check_activity_cli
```
`shakka.pipeline` bevat geen domeinlogica en roept alleen bestaande jobs aan. Alle stappen krijgen dezelfde `now` (één klokmeting per run, in de CLI).

### Verloop van `run_hourly`
1. `now` naïef → `ValueError`. Zijn `db` of `http` `None`, dan opent `run_hourly` ze zelf (`runtime.open_db(settings)`, `runtime.open_http()`) en sluit ze in een `finally`. Meegegeven clients worden niet gesloten.
2. **Wezen-rijen** (A10): `db.update("ingest_runs", {...}, filters={"status": "eq.running", "started_at": f"lt.{iso_utc(now - ABANDONED_AFTER)}"})`. Een `DatabaseError` → log `WARNING` `pipeline: could not close abandoned runs (<db_error_summary>)` en doorgaan.
3. **Start**: `rows = db.insert("ingest_runs", [{"started_at": now, "status": "running", "steps": []}], returning=True)`; `run_id = int(rows[0]["id"])`. Een `DatabaseError` → log `ERROR` `pipeline: cannot record the run (<db_error_summary>)` en return `RunReport(status="failed", steps=[], exit_code=1, run_id=None, annotations=("::error::run-hourly: cannot record the run in ingest_runs (<db_error_summary>)",))`. Er draait dan geen stap.
4. `ctx = PipelineContext(settings, db, http, now, BudgetGuard(db), forecast_fetch, tide_fetch, secrets=secret_values(settings))`. Defaults: `forecast_fetch = om_forecast.fetch_forecast` en `tide_fetch = functools.partial(rws.fetch_tide_extremes, http=http)`, opgezocht via de module (`import shakka.openmeteo.forecast as om_forecast`, `import shakka.rws.tides as rws`) op het moment van aanroepen, zodat tests ze met `monkeypatch.setattr` kunnen vervangen.
5. **Per stap** in `steps`, op volgorde: `report = run_step(name, fn, ctx)` (zie hieronder), `ctx.reports.append(report)`, één logregel (zie Logging), en een **voortgangsupdate** `db.update("ingest_runs", {"steps": [r.to_json() for r in ctx.reports]}, filters={"id": f"eq.{run_id}"})`. Een `DatabaseError` bij de voortgangsupdate → log `WARNING` `pipeline: could not record progress of run <id> (<db_error_summary>)` (alleen de eerste keer per run) en doorgaan.
6. **Afsluiten**:
   - `status = run_status(ctx.reports)`, `exit_code = exit_code_for(status, ctx.reports)`;
   - `finished_at = max((clock or runtime.utcnow)(), now)` (CHECK `finished_at >= started_at`);
   - `count = db.update("ingest_runs", {"finished_at": finished_at, "status": status, "steps": [...], "error_summary": error_summary(ctx.reports)}, filters={"id": f"eq.{run_id}"})`;
   - een `DatabaseError` of `count != 1` → log `ERROR` `pipeline: could not record the end of run <id>`, `exit_code = 1`, en de annotatie `::error::run-hourly: could not record the end of run <id> in ingest_runs`.
7. `annotations = build_annotations(ctx.reports, run_id=run_id)` (+ de eventuele annotatie uit stap 6), log op `INFO` (of `ERROR` bij exitcode 1): `pipeline: run=<id> status=<status> exit_code=<n> duration_ms=<n>`.
8. Return `RunReport(status, ctx.reports, exit_code, run_id, annotations)`.

`run_hourly` schrijft nooit zelf naar stdout of stderr; dat doet de CLI.

### `run_step(name, fn, ctx) -> StepReport`
```
start = _monotonic()
try:
    outcome = fn(ctx)
    counts = json.loads(to_json(dict(outcome.counts)))   (tuples -> lists, datetimes -> ISO; shakka.db.to_json)
    warnings = tuple(outcome.warnings)
    status = outcome.status
except StepSkipped as skip:                    -> status "skipped", reason = skip.reason, counts {}, warnings ()
except Exception as exc:                       -> status "failed", counts {}, warnings (),
                                                  error = redact(f"{type(exc).__name__}: {short_error(exc)}", ctx.secrets),
                                                  error_type = db_error_summary(exc) if isinstance(exc, DatabaseError) else type(exc).__name__
duration_ms = int((_monotonic() - start) * 1000)
```
De JSON-conversie van `counts` staat **binnen** de `try` (review N-6). Geeft `to_json` een `ValueError` (NaN, een naïeve datetime of een onbekend type in een toekomstige `StepOutcome`), dan wordt de stap `failed` met `error_type == "ValueError"`; de run gaat door en de rij blijft niet op `running` staan. De bijwerkingen van de stap (geschreven rijen) blijven dan staan; alleen het rapport mist de tellingen.

`_monotonic` is een module-attribuut (`_monotonic = time.monotonic`) dat `run_step` en de getijstap op het moment van aanroepen opzoeken, zodat tests het met `monkeypatch.setattr(pipeline, "_monotonic", ...)` vervangen.

`BaseException` die geen `Exception` is (`KeyboardInterrupt`, `SystemExit`) gaat door. Er wordt nooit `logger.exception` of een traceback gelogd.

### De stappen
| Stap | Aanroep | `counts` | Status `partial` als | `warnings` (openbaar) |
|---|---|---|---|---|
| `spots_sync` | `spots = load_spots(ctx.settings.spots_path)`; `result = sync_spots(ctx.db, spots)` | `spots`, `upserted`, `orphaned` (aantal) | nooit | `"spots in the database but not in the YAML: <ids>"` als `orphaned` niet leeg is (spot-id's uit `spots.yaml` zijn openbaar) |
| `forecast` | `result = run_forecast_ingest(ctx.db, ctx.http, ctx.budget, now=ctx.now, fetch=ctx.forecast_fetch)`; daarna het budget (zie onder) | `dataclasses.asdict(result)` (`spots`, `rows`, `calls`, `skipped_budget`, `errors`, `deleted`) plus `usage_daily`, `usage_monthly` | `result.errors` of `result.skipped_budget` | budget, zie onder |
| `tides` | `result = run_tide_ingest(ctx.db, now=ctx.now, fetch=bounded_fetch)` (20-uursregel, geen `force`; `bounded_fetch` zie onder) | `asdict(result)` (`stations`, `rows`, `skipped`, `failed`, `errors`, `deleted`) plus `budget_skipped` (int) | `result.failed` | `"time budget of 240 s reached; <n> station(s) not fetched this run"` als `budget_skipped > 0` |
| `evaluate` | `result = run_evaluation(ctx.db, now=ctx.now)` | `asdict(result)` (`spots`, `rows`, `deleted`, `failed`, `errors`) | `result.failed` | geen |
| `alerts` | stale-regel (A4), dan `result = run_alerts(ctx.db, now=ctx.now, base_url=ctx.settings.app_base_url)` | `alert_counts(result)` (zie Interfaces); **nooit** `messages` | `result.skipped` of `result.write_errors` | geen |

`spots_sync` faalt bij een `SpotValidationError` of `DatabaseError`; de run gaat dan door met de spots die al in de database staan. Een `ValueError` van `run_alerts` (ongeldige `APP_BASE_URL`) of een `DatabaseError` bij het laden maakt de stap `failed` (WP-10 "Gevolgen").

**Budget in de forecaststap** (WP-03 "Gevolgen"): na `run_forecast_ingest`, in een `try ... except DatabaseError`:
- `usage = ctx.budget.usage(now=ctx.now)`; `counts["usage_daily"] = round(usage.daily, 2)`, `counts["usage_monthly"] = round(usage.monthly, 2)`;
- `usage.daily > BUDGET_WARN_FRACTION * ctx.budget.daily_limit` → warning `f"Open-Meteo usage today is {usage.daily:.2f} of {ctx.budget.daily_limit:.0f} calls ({pct:.0f}% of the guard)"` met `pct = 100 * usage.daily / daily_limit`;
- `usage.monthly > BUDGET_WARN_FRACTION * ctx.budget.monthly_limit` → dezelfde vorm met "this month";
- `result.skipped_budget` → warning `"Open-Meteo budget guard reached: a request was skipped"`;
- een `DatabaseError` bij `usage` → warning `"Open-Meteo usage could not be read"` (de stapstatus wijzigt daardoor niet).

De waarschuwing verandert de stapstatus en de exitcode niet (AC-5).

**Tijdsbudget in de getijstap** (review N-5, WP-04 R5). Bij een RWS-storing kost elk station tot de HTTP-timeout van 30 s. Met veel stations kan de getijstap dan zo lang duren dat de job-timeout (15 min) de run afbreekt vóór `evaluate` en `alerts`. Gekozen is de eenvoudigste begrenzing die geen wijziging aan `shakka.jobs.tides` vraagt: een totale deadline voor de stap, afgedwongen in de fetch die de pipeline aan `run_tide_ingest` geeft.
```
deadline = _monotonic() + TIDE_STEP_BUDGET_S          # 240.0
budget_skipped = 0
def bounded_fetch(station, start, end):
    nonlocal budget_skipped
    if _monotonic() >= deadline:
        budget_skipped += 1
        raise TimeoutError(f"tide step time budget of {TIDE_STEP_BUDGET_S:.0f} s reached")
    return ctx.tide_fetch(station, start, end)
```
- `run_tide_ingest` vangt elke `Exception` per station af. Een station na de deadline komt dus in `failed` en `errors` (`"<station>: TimeoutError: tide step time budget of 240 s reached"`), wordt niet aangeroepen, en de stap wordt `partial`. De jobs gaan door; de volgende run probeert die stations opnieuw (de 20-uursregel ziet ze niet als vers).
- Het lopende request wordt niet afgebroken. De stap duurt dus hooguit ongeveer 240 s plus één request (de timeout van `open_http` geldt per fase). Samen met `uv sync`, één Open-Meteo-request en de overige stappen blijft dat ruim onder de 15 minuten, zodat `alerts` altijd aan bod komt.
- `counts["budget_skipped"] = budget_skipped`; bij `> 0` de warning uit de tabel (de getallen uit de constanten, `f"time budget of {TIDE_STEP_BUDGET_S:.0f} s reached; {budget_skipped} station(s) not fetched this run"`).
- De logregel van `run_tide_ingest` per gefaald station bevat alleen de stationscode (openbaar) en deze vaste tekst.

### Runstatus, exitcode en samenvatting
- `run_status` en `exit_code_for` volgen A1 en A2.
- `error_summary(reports)`: `None` als alle stappen `ok` zijn. Anders `"; ".join(...)` over de stappen die niet `ok` zijn: `failed` → `f"{name}: {error}"`, `skipped` → `f"{name}: skipped ({reason})"`, `partial` → `f"{name}: partial"`. Afgekapt op `MAX_ERROR_SUMMARY` (1000) tekens.

### Annotaties (`build_annotations`)
Regels die GitHub als annotatie toont ([bron](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands)). Ze staan altijd aan het begin van een regel. **Elke** annotatie in deze WP (pipeline, CLI en `check-activity`) wordt gemaakt met `github_annotation(level, message)` uit `shakka.logsetup`: `f"::{level}::{escape_command_data(message)}"`. `escape_command_data` vervangt eerst `%` door `%25` en daarna `\r` en `\n` door een spatie, zodat de annotatie één regel blijft (review N-7). GitHub decodeert `%25`, `%0D` en `%0A` in de berichtdata; zie `escapeData` in de officiële toolkit ([bron](https://github.com/actions/toolkit/blob/main/packages/core/src/command.ts)). Voorbeeld: de budgetwarning "… (83% of the guard)" komt op stdout als "… (83%25 of the guard)" en GitHub toont "83%". Volgorde: de stappen op volgorde, per stap:
- `failed` → `f"::error::step {name} failed ({error_type}); details in ingest_runs id {run_id}"`;
- `skipped` met `stale_forecast` → `"::error::alerts skipped (stale_forecast): the newest forecast is older than 3 hours; no alerts this run"`;
- per warning → `f"::warning::{name}: {warning}"`.

Hooguit `MAX_ANNOTATIONS` (10) regels; de rest vervalt. Foutteksten (`error`) komen nooit in een annotatie, alleen `error_type`. De vormen hierboven en elders in dit blueprint (`::error::…`, `::warning::…`) tonen de regel vóór het escapen; de builder bouwt ze allemaal via `github_annotation`.

### Logging (`shakka.logsetup`)
- `configure_logging(*, stream=None, secrets=())`: één `StreamHandler` naar `stream or sys.stdout` met een `RedactingFormatter`, root-level `INFO`, en de loggers `httpx` en `httpcore` op `WARNING` (WP-10 "Gevolgen", bindend: httpx logt anders elke request met de volledige URL op `INFO`, [bron](https://www.python-httpx.org/logging/)). Idempotent: een handler die eerder door `configure_logging` is toegevoegd (attribuut `_shakka_handler = True`), wordt eerst verwijderd. Geeft de handler terug.
- Formaat: `%(asctime)s %(levelname)s %(name)s %(message)s`, tijd in UTC (`converter = time.gmtime`, `datefmt = "%Y-%m-%dT%H:%M:%SZ"`). De berichten zelf zijn `key=value`-paren.
- `RedactingFormatter.format(record)`: eerst `super().format(record)`, daarna elke secret (alleen waarden van minstens 8 tekens) vervangen door `***`.
- Logregel per stap (logger `shakka.pipeline`): `pipeline: step=<name> status=<status> duration_ms=<n>`, gevolgd door ` key=value` voor elke telling waarvan de waarde een `bool`, `int` of `float` is (in de volgorde van `counts`), en bij `failed` ` error_type=<error_type>`, bij `skipped` ` reason=<reason>`, bij warnings ` warnings=<aantal>`. Niveau: `ok` → `INFO`, `partial` en `skipped` → `WARNING`, `failed` → `ERROR`. Lijsten (`errors`, `failed`, `skipped`) en teksten komen dus nooit in de log; ze staan in `ingest_runs`.
- De jobs loggen zelf ook (WP-03, WP-04, WP-10). Die regels bevatten alleen aantallen, en bij de forecast- en getijjob openbare chunk- en stationsfouten; WP-10 garandeert dat `run_alerts` geen user-id's, berichtteksten of favoriete spot-id's logt.

### CLI `shakka run-hourly` (`run_hourly_cli`)
1. `settings = get_settings()`. `ValidationError` → echo `run-hourly: configuration incomplete; run shakka doctor` en `::error::run-hourly: configuration incomplete (check the GitHub Secrets SUPABASE_URL and SUPABASE_SECRET_KEY)`; return 1. Geen waarden in de uitvoer.
2. `configure_logging(secrets=secret_values(settings))`.
3. `db = runtime.open_db(settings)`, `http = runtime.open_http()`; in `try/finally` (`http.close()`, `db.close()`): `report = run_hourly(settings, now=runtime.utcnow(), db=db, http=http)`.
4. Echo elke regel uit `report.annotations`, daarna `run-hourly: status=<status> exit_code=<n> run_id=<id of none>`.
5. Return `report.exit_code`.

Een onverwachte exception uit `run_hourly` (een programmeerfout, geen stapfout) wordt niet gevangen; Python geeft dan exitcode 1 met een traceback. Stapfouten komen daar nooit, en meldingen van `DatabaseError` zijn al geredigeerd (WP-01).

### `shakka check-activity` (`shakka.activity`)
`run_check_activity_cli(last_commit_at: str, *, echo) -> int` (de `::warning::`- en `::error::`-regels via `github_annotation`):
1. `last = parse_commit_date(last_commit_at)` (leeg, ongeldig of zonder tijdzone → `None`).
2. `check = check_activity(last, now=runtime.utcnow())`.
3. Uitvoer en exitcode:
   - `None` → `::warning::Could not determine the date of the last commit; repository activity was not checked.`, exit 0;
   - `ok` (`days < 45`) → `activity: last commit on the default branch <days> day(s) ago; ok`, exit 0;
   - `warn` (`45 <= days < 53`) → `::warning::No commits on the default branch for <days> days. GitHub disables the hourly schedule after 60 days without activity; merge a commit into develop (docs/RUNBOOK.md, section 13).`, exit 0;
   - `fail` (`days >= 53`) → dezelfde tekst als `::error::`, exit 1.

`days = max(0, (now - last) // timedelta(days=1))`; een datum in de toekomst geeft 0.

### Workflow `.github/workflows/hourly.yml`
Exacte inhoud (de builder neemt dit letterlijk over; alleen commentaarregels mogen erbij):
```yaml
name: hourly

on:
  schedule:
    - cron: "17 * * * *"
  workflow_dispatch:
    inputs:
      ref:
        description: "Branch to run. The schedule always runs main."
        required: true
        default: main
        type: choice
        options:
          - main
          - develop

permissions:
  contents: read

concurrency:
  group: hourly
  cancel-in-progress: false

jobs:
  run:
    if: ${{ github.event_name == 'workflow_dispatch' || vars.HOURLY_ENABLED == 'true' }}
    runs-on: ubuntu-latest
    timeout-minutes: 15
    defaults:
      run:
        working-directory: ingest
    env:
      UV_LOCKED: "1"
      PYTHONUNBUFFERED: "1"
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event_name == 'workflow_dispatch' && inputs.ref || 'main' }}
          persist-credentials: false
      - uses: astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884 # v10.3.0
        with:
          working-directory: ingest
      - run: uv sync
      - name: Hourly pipeline
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SECRET_KEY: ${{ secrets.SUPABASE_SECRET_KEY }}
          APP_BASE_URL: ${{ vars.APP_BASE_URL }}
        run: uv run shakka run-hourly
      - name: Repository activity (schedules stop after 60 days without activity)
        if: ${{ !cancelled() }}
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          last="$(gh api "repos/${GITHUB_REPOSITORY}/commits?per_page=1" --jq '.[0].commit.committer.date' || true)"
          uv run shakka check-activity --last-commit-at "${last}"
```
Keuzes:
- Cron `17 * * * *`: niet op het hele uur. GitHub noemt het begin van elk uur als piekmoment waarop runs vertraagd of zelfs geschrapt kunnen worden.
- `concurrency` met `cancel-in-progress: false`: er draait er hooguit één tegelijk (WP-03 A9: `api_usage` heeft geen lock). Er staat hooguit één run in de wacht; een nieuwere wachtende run vervangt een oudere ([bron](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)). Een gemist uur is geen probleem.
- Secrets staan alleen in de `env` van de pipelinestap, niet op jobniveau. `APP_BASE_URL` komt uit `vars`; leeg wordt `None` (`env_ignore_empty=True` in `Settings`).
- `actions/checkout@v7` en de setup-uv-pin zijn gelijk aan `ci.yml`; `persist-credentials: false`, want er wordt niets gepusht.
- `gh` is op GitHub-hosted runners voorgeïnstalleerd en gebruikt `GH_TOKEN` ([bron](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli)). Zonder `sha` geeft "List commits" de default branch ([bron](https://docs.github.com/en/rest/commits/commits)). Faalt de call, dan is `last` leeg en geeft `check-activity` een warning met exit 0.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/logsetup.py` | aanmaken | `LOG_FORMAT`, `QUIET_LOGGERS`, `MIN_SECRET_LENGTH`, `RedactingFormatter`, `redact`, `secret_values`, `configure_logging`, `escape_command_data`, `github_annotation`. |
| `ingest/src/shakka/activity.py` | aanmaken | Drempels, `ActivityCheck`, `parse_commit_date`, `check_activity`, `run_check_activity_cli`. |
| `ingest/src/shakka/pipeline.py` | aanmaken | Constanten, `StepSkipped`, `StepOutcome`, `StepReport`, `RunReport`, `PipelineContext`, de vijf stapfuncties, `STEPS`, `alert_counts`, `newest_forecast_fetch`, `run_step`, `run_status`, `exit_code_for`, `error_summary`, `build_annotations`, `run_hourly`, `run_hourly_cli`. |
| `ingest/src/shakka/jobs/runtime.py` | wijzigen | Erbij: `HTTP_TIMEOUT_S: Final = 30.0` en `open_http() -> httpx.Client` (`make_client(timeout=HTTP_TIMEOUT_S)`). Bestaande functies ongewijzigd. |
| `ingest/src/shakka/cli.py` | wijzigen | Commando's `run-hourly` en `check-activity --last-commit-at TEXT` (default `""`). Imports binnen de functies, zoals de bestaande commando's. |
| `.github/workflows/hourly.yml` | aanmaken | Exact zoals onder Ontwerp. |
| `ingest/tests/pipeline_fixtures.py` | aanmaken | Scenario en helpers (zie Testplan). |
| `ingest/tests/test_logsetup.py` | aanmaken | Redactie, idempotentie, httpx/httpcore-niveaus, escapen van annotaties. |
| `ingest/tests/test_activity.py` | aanmaken | Drempels, parsen, CLI. |
| `ingest/tests/test_pipeline.py` | aanmaken | AC-1, AC-2, AC-5 en de overige pipelinegevallen. |
| `ingest/tests/test_cli_pipeline.py` | aanmaken | CLI `run-hourly` (exitcode, AC-3, AC-5 stdout, privacy, ontbrekende config). |
| `ingest/tests/test_hourly_workflow.py` | aanmaken | AC-4. |
| `docs/RUNBOOK.md` | wijzigen | §4: rij `HOURLY_ENABLED`. Nieuwe §13 "Uurlijkse run (vanaf WP-11)". |

Geen migraties, geen wijziging aan `shakka.domain`, `shakka.db`, de jobs (behalve `runtime.py`), `tests/fakes.py`, `pyproject.toml`, `uv.lock` of `ci.yml`. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### `shakka.logsetup`
```python
LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_DATEFMT: Final = "%Y-%m-%dT%H:%M:%SZ"
QUIET_LOGGERS: Final = ("httpx", "httpcore")
MIN_SECRET_LENGTH: Final = 8

def redact(text: str, secrets: Iterable[str]) -> str: ...
    # every secret with len >= MIN_SECRET_LENGTH replaced by "***"; others ignored
def secret_values(settings: Settings) -> tuple[str, ...]: ...
    # supabase_secret_key and, if set, vapid_private_key (get_secret_value())

class RedactingFormatter(logging.Formatter):
    def __init__(self, fmt: str, datefmt: str, *, secrets: Iterable[str] = ()) -> None: ...
    # converter = time.gmtime; format() = redact(super().format(record), secrets)

def configure_logging(*, stream: TextIO | None = None,
                      secrets: Iterable[str] = ()) -> logging.Handler: ...

def escape_command_data(text: str) -> str: ...
    # text.replace("%", "%25"), then "\r" and "\n" -> " " (one line per annotation)
def github_annotation(level: Literal["warning", "error"], message: str) -> str: ...
    # f"::{level}::{escape_command_data(message)}"
```

### `shakka.activity`
```python
WARN_AFTER_DAYS: Final = 45
FAIL_AFTER_DAYS: Final = 53
DISABLE_AFTER_DAYS: Final = 60      # GitHub's rule, for messages only

ActivityLevel = Literal["ok", "warn", "fail"]

@dataclass(frozen=True, slots=True)
class ActivityCheck:
    level: ActivityLevel
    days: int

def parse_commit_date(text: str) -> datetime | None: ...   # aware UTC or None
def check_activity(last_commit_at: datetime, *, now: datetime) -> ActivityCheck: ...
    # ValueError for naive datetimes
def run_check_activity_cli(last_commit_at: str, *, echo: Callable[[str], None]) -> int: ...
```

### `shakka.pipeline`
```python
StepStatus = Literal["ok", "partial", "failed", "skipped"]
RunStatus = Literal["ok", "partial", "failed"]     # "running" only exists in the database

INGEST_RUNS: Final = "ingest_runs"
STALE_FORECAST: Final = "stale_forecast"
STALE_FORECAST_AGE: Final = timedelta(hours=3)
BUDGET_WARN_FRACTION: Final = 0.8
ABANDONED_AFTER: Final = timedelta(hours=1)
ABANDONED_SUMMARY: Final = "abandoned: the run did not record its end (timeout or crash)"
MAX_ERROR_SUMMARY: Final = 1000
MAX_ANNOTATIONS: Final = 10
TIDE_STEP_BUDGET_S: Final = 240.0
STEP_NAMES: Final = ("spots_sync", "forecast", "tides", "evaluate", "alerts")

_monotonic: Callable[[], float] = time.monotonic   # looked up at call time; tests monkeypatch it

class StepSkipped(Exception):
    def __init__(self, reason: str) -> None: ...      # self.reason = reason

@dataclass(frozen=True, slots=True)
class StepOutcome:
    status: Literal["ok", "partial"]
    counts: Mapping[str, Any]
    warnings: tuple[str, ...] = ()                    # public texts (stdout annotations)

@dataclass(frozen=True, slots=True)
class StepReport:
    name: str
    status: StepStatus
    duration_ms: int
    counts: dict[str, Any]                            # JSON-ready
    error: str | None = None                          # private: ingest_runs only, secrets redacted
    error_type: str | None = None                     # public: exception type or db_error_summary
    reason: str | None = None                         # iff status == "skipped"
    warnings: tuple[str, ...] = ()
    def to_json(self) -> dict[str, Any]: ...
    # {"name", "status", "duration_ms", "counts", "error", "error_type", "reason", "warnings": [...]}

@dataclass(frozen=True, slots=True)
class RunReport:
    status: RunStatus
    steps: list[StepReport]
    exit_code: int
    run_id: int | None = None
    annotations: tuple[str, ...] = ()

@dataclass(slots=True)
class PipelineContext:
    settings: Settings
    db: SupabaseRest
    http: httpx.Client
    now: datetime
    budget: BudgetGuard
    forecast_fetch: FetchForecast                     # shakka.jobs.forecast.FetchForecast
    tide_fetch: TideFetcher                           # shakka.jobs.tides.TideFetcher
    secrets: tuple[str, ...] = ()
    reports: list[StepReport] = field(default_factory=list)
    def report(self, name: str) -> StepReport | None: ...

StepFn = Callable[[PipelineContext], StepOutcome]
Step = tuple[str, StepFn]

def step_spots_sync(ctx: PipelineContext) -> StepOutcome: ...
def step_forecast(ctx: PipelineContext) -> StepOutcome: ...
def step_tides(ctx: PipelineContext) -> StepOutcome: ...    # TIDE_STEP_BUDGET_S deadline via bounded_fetch
def step_evaluate(ctx: PipelineContext) -> StepOutcome: ...
def step_alerts(ctx: PipelineContext) -> StepOutcome: ...   # raises StepSkipped(STALE_FORECAST)

STEPS: Final[tuple[Step, ...]] = (
    ("spots_sync", step_spots_sync),
    ("forecast", step_forecast),
    ("tides", step_tides),
    ("evaluate", step_evaluate),
    ("alerts", step_alerts),
)

def alert_counts(result: AlertJobResult) -> dict[str, Any]: ...
    # exactly: users, events, favorites, ineligible, disabled, skipped, write_errors, deleted,
    # new, improved, worsened, cancelled (per message.kind), errors (list(result.errors)).
    # Never messages, user ids or message texts.
def newest_forecast_fetch(db: SupabaseRest) -> datetime | None: ...
    # select forecast_hours columns="fetched_at" order="fetched_at.desc" limit=1; fromisoformat
def run_step(name: str, fn: StepFn, ctx: PipelineContext) -> StepReport: ...
def run_status(reports: Sequence[StepReport]) -> RunStatus: ...
def exit_code_for(status: RunStatus, reports: Sequence[StepReport]) -> int: ...
def error_summary(reports: Sequence[StepReport]) -> str | None: ...
def build_annotations(reports: Sequence[StepReport], *, run_id: int | None) -> tuple[str, ...]: ...
def run_hourly(settings: Settings, *, now: datetime,
               db: SupabaseRest | None = None, http: httpx.Client | None = None,
               steps: Sequence[Step] = STEPS,
               forecast_fetch: FetchForecast | None = None,
               tide_fetch: TideFetcher | None = None,
               clock: Callable[[], datetime] | None = None) -> RunReport: ...
def run_hourly_cli(*, echo: Callable[[str], None]) -> int: ...
```
`run_status([])` is `ok`. `exit_code_for(status, reports)` is 1 als `status == "failed"` of als een rapport met `name == "alerts"`, `status == "skipped"` en `reason == STALE_FORECAST` bestaat; anders 0.

### `ingest_runs` (bestaande tabel, WP-01)
- Start: insert `{"started_at": now, "status": "running", "steps": []}`, `returning=True`. Nooit een `id` meesturen (identity "generated always"; de fake geeft dan 428C9).
- Voortgang: update `{"steps": [...]}` op `id=eq.<run_id>`.
- Einde: update `{"finished_at", "status", "steps", "error_summary"}` op `id=eq.<run_id>`.
- Voorbeeld van één element in `steps`:
  ```json
  {"name": "forecast", "status": "failed", "duration_ms": 412, "counts": {},
   "error": "RuntimeError: connection reset", "error_type": "RuntimeError",
   "reason": null, "warnings": []}
  ```

### CLI
```python
@cli.command("run-hourly")
def run_hourly_cmd() -> None:
    """Run all hourly steps (spots sync, forecast, tides, evaluate, alerts) and record the run."""
    from shakka.pipeline import run_hourly_cli
    raise SystemExit(run_hourly_cli(echo=click.echo))

@cli.command("check-activity")
@click.option("--last-commit-at", default="", help="ISO date of the last commit on the default branch.")
def check_activity_cmd(last_commit_at: str) -> None:
    """Warn before GitHub disables the hourly schedule (60 days without activity)."""
    from shakka.activity import run_check_activity_cli
    raise SystemExit(run_check_activity_cli(last_commit_at, echo=click.echo))
```

### `shakka.jobs.runtime` (uitbreiding)
```python
HTTP_TIMEOUT_S: Final = 30.0
def open_http() -> httpx.Client: ...   # make_client(timeout=HTTP_TIMEOUT_S); the caller closes it
```
`run_hourly` en `run_hourly_cli` roepen `runtime.open_db`, `runtime.open_http` en `runtime.utcnow` aan via de module (nooit `from ... import`), zoals WP-10. `shakka.activity` gebruikt `runtime.utcnow` op dezelfde manier.

### Gevolgen voor latere WP's
- **WP-12:** voegt `("marine", step_marine)` direct na `forecast` toe aan `STEPS` en geeft een `StepOutcome` terug. De stale-regel kijkt alleen naar `forecast`; golven tellen niet mee in alerts.
- **WP-17:** voegt aan `run_hourly` de keyword `notifiers=None` toe en geeft die via `PipelineContext` door aan `run_alerts`. `alert_counts` krijgt `sent`, `failed` en `no_target`. Pushendpoints komen nooit in `counts`, `warnings` of de log; alleen aantallen.
- **WP-19:** `("sessions_cleanup", ...)` aan het eind.
- **WP-22:**
  - `("usage_report", ...)` aan het eind. Deduplicatie per week via `ingest_runs.steps` (een stap `usage_report` met status `ok` sinds maandag 00:00 lokaal);
  - pushwaarschuwingen kunnen de `warnings` van de stap `forecast` hergebruiken;
  - het succespercentage komt uit `ingest_runs.status`;
  - `ingest_runs` groeit met 24 rijen per dag (orde 1–2 kB per rij); een bewaartermijn kan hier;
  - een `partial` die blijft hangen (bijv. een station dat elke run faalt) geeft geen mail; WP-22 kan daar een drempel voor toevoegen;
  - `actions/checkout@v7` op een commit-SHA pinnen in `ci.yml` en `hourly.yml` (dependency-audit);
  - **stale-regel per spot** (review N-1). Zodra er meer dan 50 spots met coördinaten zijn (meer dan één forecast-chunk), is de globale controle uit A4 niet meer voldoende. Faalt één chunk en slaagt een andere, dan is de globale nieuwste `fetched_at` vers. De spots uit de gefaalde chunk houden dan rijen die uren oud kunnen zijn, en `load_inputs_checked` (WP-10) gebruikt die, want het filtert relatief aan de nieuwste fetch van díe spot en niet aan `now`. Gevolg: alerts op verouderde data, zonder `stale_forecast` en zonder mail. De WP die de 50 spots passeert (uiterlijk WP-22) maakt de regel per spot, bijvoorbeeld door in `load_inputs` rijen met `fetched_at < now - 3 h` weg te laten (die spot wordt dan `ineligible`);
  - **tijdsbudget voor de hele run** (review N-5). WP-11 begrenst alleen de getijstap (`TIDE_STEP_BUDGET_S`). Een uniform budget per netwerkstap (ook de forecast-chunks en latere stappen zoals marine en push), samen met retries, hoort bij WP-22 (WP-04 R5).

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | Alle stappen `ok` | Run `ok`, exitcode 0, `error_summary` leeg, geen annotaties (behalve warnings). |
| E2 | `forecast` geeft een exception, nieuwste `fetched_at` 4 uur oud | `tides` en `evaluate` draaien; `alerts` `skipped` (`stale_forecast`), geen schrijfactie op `alert_state`; run `partial`; exitcode 1; `::error::`-annotaties voor `forecast` en `alerts`. |
| E3 | Idem, nieuwste `fetched_at` 2 uur oud | `alerts` draait; run `partial`; exitcode 0. |
| E4 | `fetched_at` precies 3 uur oud | Vers: `alerts` draait. |
| E5 | `forecast` faalt en `forecast_hours` is leeg | Stale: `alerts` `skipped`, exitcode 1. |
| E6 | `forecast` `partial` (chunkfout of budgetstop) | Stale-controle als bij E2/E3. |
| E7 | `forecast` `ok` met 0 spots met coördinaten (huidige startset) | Geen stale-controle; `alerts` draait; favorieten zijn `ineligible`; run `ok`. |
| E8 | `spots_sync` faalt (ongeldige YAML, DB-fout) | Stap `failed`; de rest draait met de spots in de database; run `partial`, exitcode 0. CI valideert `data/spots.yaml` al (`test_spots_data.py`). |
| E9 | `alerts` geeft een exception (ongeldige `APP_BASE_URL`, DB-fout bij laden) | Stap `failed`; run `failed`; exitcode 1. |
| E10 | De stale-select zelf geeft een `DatabaseError` | Exception in de alertstap → `failed`; run `failed`; exitcode 1. |
| E11 | Alle stappen falen | Run `failed`, exitcode 1. |
| E12 | Insert van de `ingest_runs`-rij faalt | Geen enkele stap draait (de fetchers worden niet aangeroepen); `failed`, exitcode 1, `run_id=None`. |
| E13 | Een voortgangsupdate faalt | Eén `WARNING`; de stappen gaan door; de slotupdate probeert het opnieuw. |
| E14 | De slotupdate faalt of raakt 0 rijen | Exitcode 1 en een `::error::`-annotatie; de status in het rapport blijft de berekende. |
| E15 | Oude rij met `status = running`, `started_at` 2 uur geleden | Wordt `failed` met `ABANDONED_SUMMARY` en `finished_at = now`. Een rij van 30 minuten geleden blijft ongemoeid. |
| E16 | Budget: daggebruik 6.500 (> 6.400) | Warning in de `forecast`-stap en `::warning::` op stdout; status en exitcode ongewijzigd. Precies 6.400 geeft geen warning (strikt "boven"). |
| E17 | Foutmelding van een stap bevat de secret key | In `ingest_runs` als `***`; in de log alleen het type. |
| E18 | `AlertJobResult.errors` niet leeg (kapotte regel) | Alleen in `counts.errors` in `ingest_runs`; niet in de log of op stdout; stap `partial`. |
| E19 | `SUPABASE_URL` of `SUPABASE_SECRET_KEY` ontbreekt (secret niet gezet) | `run-hourly` exitcode 1 met de melding "configuration incomplete"; geen rij in `ingest_runs`. |
| E20 | `APP_BASE_URL`-variable niet gezet | Lege string → `None`; berichten zonder link (WP-08). |
| E21 | Schedule terwijl `HOURLY_ENABLED` niet `true` is | Job overgeslagen; geen run in `ingest_runs`, geen mail. |
| E22 | Twee runs tegelijk gestart (schedule plus dispatch) | `concurrency: hourly`: de tweede wacht; een derde vervangt de wachtende, die in de lijst als "cancelled" verschijnt. Dat is geen storing (RUNBOOK §13). |
| E23 | Laatste commit op de default branch 44, 45, 52, 53 dagen geleden | `ok`, `warn`, `warn`, `fail` (exit 1). |
| E24 | `gh api` faalt of geeft iets onleesbaars | `check-activity` warning, exit 0. |
| E25 | Job-timeout (15 min) | GitHub breekt de job af (run failed → mail); de rij blijft `running` en wordt door de volgende run `failed` (E15). De activiteitsstap draait niet (`!cancelled()`). |
| E26 | `now` naïef | `run_hourly` → `ValueError`. |
| E27 | RWS hangt; de getijstap passeert `TIDE_STEP_BUDGET_S` (240 s) | Resterende stations worden niet aangeroepen en komen in `failed`; `counts["budget_skipped"] = n`; stap `partial` met warning; `evaluate` en `alerts` draaien; exitcode 0 (tenzij een andere regel 1 geeft). |
| E28 | Een stap geeft `counts` die niet naar JSON kunnen (NaN, naïeve datetime, onbekend type) | Stap `failed`, `error_type == "ValueError"`, `counts == {}`; de run gaat door en wordt normaal afgesloten. |
| E29 | Een warning bevat `%`, `\r` of `\n` | In de annotatie: `%25` en spaties; één regel. |

## Testplan
Alle tests in `ingest/tests/`, met `FakeSupabase`, nep-fetchers en een `httpx.Client(transport=httpx.MockTransport(...))` die elke request met 500 beantwoordt, zodat een onbedoelde netwerkcall opvalt. Domeinlogica verandert niet; tests eerst voor de pure stukken (`run_status`, `exit_code_for`, `error_summary`, `build_annotations`, `check_activity`, `redact`).

### Fixtures (`tests/pipeline_fixtures.py`)
- `NOW` en `USER_A` uit `job_fixtures.py` (2026-07-15 06:17Z).
- `PIPELINE_SPOT`: de dict `{"id": "test-strand", "name": "Teststrand", "lat": LAT, "lon": LON, "shore_normal_deg": 270, "status": "allowed", "level": "intermediate", "verified": True}` (`LAT`/`LON` uit `evaluation_fixtures.py`).
- `write_spots_yaml(tmp_path, spots=(PIPELINE_SPOT,)) -> Path`: `yaml.safe_dump({"spots": list(spots)})` naar `tmp_path / "spots.yaml"`.
- `make_settings(spots_path, **overrides) -> Settings`: `Settings(supabase_url="http://127.0.0.1:54321", supabase_secret_key="sb_secret_TESTVALUE", spots_path=spots_path, **overrides)`.
- `fake_forecast_fetch(http, locations, *, forecast_days=7) -> list[ForecastHour]`: per locatie, per model in `MODELS3` en per uur in `WINDS` een `ForecastHour` met `wind_kn = w`, `gust_kn = w + 4`, `dir_deg = 270` (hetzelfde scenario als WP-10).
- `failing_forecast_fetch(exc)`: geeft een fetch die `exc` gooit.
- `no_tides(station, start, end)`: geeft `[]` (wordt in het scenario niet aangeroepen, want de spot heeft geen station).
- `seed_user(db)`: profiel en favoriet voor `USER_A` op `test-strand`, net als in de AC-2-test van WP-10 (`seed_profile`, `seed_favorite`).
- `blocked_http()`: `httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))`.
- Fixture `restore_logging` (in de testbestanden die `configure_logging` aanroepen): bewaart de handlers en het niveau van de root-logger en de niveaus van `httpx` en `httpcore`, en zet ze na de test terug.
- Een `FakeSupabase`-subklasse `FlakyIngestRuns` in `test_pipeline.py` zelf (geen wijziging aan `fakes.py`), review N-2:
  ```python
  IngestRunsCall = Literal["abandon", "insert", "progress", "final"]

  class FlakyIngestRuns(FakeSupabase):
      def __init__(self, fail_on: frozenset[IngestRunsCall]) -> None: ...
      # insert("ingest_runs", ...)                         -> kind "insert"
      # update("ingest_runs", values, filters=...):
      #   "status" in filters                               -> kind "abandon"  (orphan update, A10)
      #   "id" in filters and "finished_at" in values       -> kind "final"    (closing update)
      #   "id" in filters and set(values) == {"steps"}      -> kind "progress" (after each step)
      # kind in fail_on -> raise DatabaseError("boom", status=503) before calling super()
      #                    (so the failed call is not recorded in `writes`)
      # otherwise, and for every other table               -> super()
  ```
  De vier soorten zijn disjunct: de wezen-update filtert op `status` (en `started_at`), de andere twee op `id`; alleen de slotupdate bevat `finished_at`. Elke test noemt precies welke soort faalt (`test_cannot_start_run`: `{"insert"}`; `test_progress_update_failure_continues`: `{"progress"}`; `test_finish_update_failure_exit_1`: `{"final"}`; `test_abandon_failure_continues`: `{"abandon"}`).

### Per acceptatiecriterium
- **AC-1** `test_pipeline.py::test_all_steps_ok_records_run`: YAML met `PIPELINE_SPOT`, `seed_user`, `run_hourly(settings, now=NOW, db=db, http=blocked_http(), forecast_fetch=fake_forecast_fetch, tide_fetch=no_tides, clock=lambda: NOW + timedelta(minutes=1))`. Verwacht:
  - precies één `ingest_runs`-rij met `status == "ok"`, `finished_at` gezet en `error_summary is None`;
  - `[s["name"] for s in row["steps"]] == list(STEP_NAMES)`;
  - elke stap heeft exact de sleutels van `StepReport.to_json`;
  - `report.exit_code == 0` en `report.run_id == row["id"]`;
  - de eerste insert is die op `ingest_runs`, en vóór die insert staat alleen de wezen-update (review B-1; de volgorde wezen sluiten → insert blijft zoals in "Verloop van `run_hourly`"):
    ```python
    first_insert = next(i for i, (kind, _) in enumerate(db.writes) if kind == "insert")
    assert db.writes[first_insert] == ("insert", "ingest_runs")
    assert db.writes[:first_insert] == [("update", "ingest_runs")]  # orphan update comes first
    ```
    `seed_user` gebruikt `db.seed`, dat niet in `writes` komt; de fake registreert de wezen-update ook bij 0 geraakte rijen. Daarmee staat ook vast dat er vóór de start van de run niets naar een andere tabel is geschreven;
  - `alerts.counts["events"] == 1` en `["new"] == 1`.

  Plus `test_steps_contract_order`: `[n for n, _ in STEPS] == ["spots_sync", "forecast", "tides", "evaluate", "alerts"] == list(STEP_NAMES)`.
- **AC-2** `test_pipeline.py`:
  - `test_forecast_exception_with_stale_data_skips_alerts`: seed `forecast_hours` (via `seed_forecasts`, `fetched_at = NOW - 4 h`) en `forecast_fetch=failing_forecast_fetch(RuntimeError("boom"))`. Verwacht: `tides` en `evaluate` `ok`; `alerts` `skipped` met `reason == "stale_forecast"`; `forecast` `failed`, met `error` dat begint met `"RuntimeError: "` en `error_type == "RuntimeError"`; run `partial`; `exit_code == 1`; geen schrijfactie op `alert_state` (`("insert"|"update", "alert_state")` niet in `db.writes`).
  - `test_forecast_exception_with_fresh_data_runs_alerts`: `fetched_at = NOW - 2 h`. `alerts` `ok`; run `partial`; `exit_code == 0`.
  - `test_stale_boundary_exactly_three_hours_is_fresh`.
  - `test_forecast_failed_without_rows_is_stale`.
  - `test_forecast_partial_triggers_stale_check`: een fetch die `ForecastFetchError` geeft → `forecast` `partial`; bij data van 4 uur oud wordt `alerts` overgeslagen.
  - `test_failed_run_exit_code_1`: `settings.app_base_url = "not a url"` → `alerts` `failed`, run `failed`, `exit_code == 1`.
  - `test_all_steps_failed`: `steps` met twee stapfuncties die `RuntimeError` geven → `failed`, 1.
  - CLI-deel in `test_cli_pipeline.py::test_cli_exit_code_follows_report`: monkeypatch `shakka.pipeline.run_hourly` met een functie die `RunReport(status, [], exit_code=e)` teruggeeft, voor `e` in `(0, 1)`; `CliRunner().invoke(cli, ["run-hourly"])` met de env-vars gezet en `runtime.open_db`/`open_http` vervangen → `result.exit_code == e`.
- **AC-3** `test_cli_pipeline.py::test_secret_not_in_log_output`, met `restore_logging`, `caplog.set_level(logging.DEBUG)` en `capsys`:
  - env `SUPABASE_SECRET_KEY=sb_secret_TESTVALUE`, `SUPABASE_URL=http://127.0.0.1:54321`, `SPOTS_PATH=<yaml>`;
  - `runtime.open_db` → `FakeSupabase`, `runtime.open_http` → `blocked_http()`, `runtime.utcnow` → `NOW`;
  - monkeypatch `shakka.openmeteo.forecast.fetch_forecast` met een fetch die `RuntimeError("leak sb_secret_TESTVALUE")` geeft;
  - aanroep `run_hourly_cli(echo=print)`, zodat `configure_logging` actief is.

  Verwacht: `"sb_secret_TESTVALUE"` niet in `caplog.text`, niet in `capsys.readouterr().out` en niet in `err`. De opgeslagen `forecast`-`error` bevat `"***"` en niet de secret.

  Let op (review N-3): `configure_logging` binnen `run_hourly_cli` zet de root-logger na `caplog.set_level(logging.DEBUG)` terug op `INFO`. Deze test toetst dus INFO en hoger. Dat is bewust en voldoende: in de Actions-logs staat de root ook op `INFO`. `caplog.text` gebruikt de formatter van caplog, niet de `RedactingFormatter`; de test toetst dus dat de secret niet eens in een logbericht terechtkomt (strenger dan alleen de redactie). Het DEBUG-niveau toetst `test_httpx_and_httpcore_quiet`, waar `caplog.set_level` ná `configure_logging` komt.
  Plus `test_logsetup.py::test_redacting_formatter`: een record met de secret in het bericht en in `exc_info` wordt in de uitvoer van de handler `***`.
- **AC-4** `test_hourly_workflow.py`. Parse `.github/workflows/hourly.yml` met `yaml.safe_load`. Let op: PyYAML leest de sleutel `on` als `True`, gebruik dus `doc.get("on", doc.get(True))`. Toets:
  - `schedule == [{"cron": "17 * * * *"}]` en `"workflow_dispatch"` in `on`;
  - `concurrency == {"group": "hourly", "cancel-in-progress": False}`;
  - `jobs.run["timeout-minutes"] == 15` en `jobs.run.defaults.run["working-directory"] == "ingest"`;
  - een stap met `run == "uv run shakka run-hourly"`, waarvan de `env` exact `{"SUPABASE_URL": "${{ secrets.SUPABASE_URL }}", "SUPABASE_SECRET_KEY": "${{ secrets.SUPABASE_SECRET_KEY }}", "APP_BASE_URL": "${{ vars.APP_BASE_URL }}"}` is;
  - de checkout-stap heeft een `ref` die `'main'` bevat;
  - `permissions == {"contents": "read"}`;
  - de job-`if` bevat `vars.HOURLY_ENABLED == 'true'`;
  - een stap bevat `shakka check-activity`;
  - alle `secrets.X` in het bestand (regex `secrets\.([A-Z_]+)`) zitten in `{"SUPABASE_URL", "SUPABASE_SECRET_KEY"}`;
  - voor elk `*.yml` in `.github/workflows/` komen `sb_secret_` en `telegram` (hoofdletterongevoelig) niet voor. Dit is de grep van AC-4 als permanente test.
- **AC-5**:
  - `test_pipeline.py::test_budget_warning_recorded`: seed `api_usage` `{"day": "2026-07-15", "source": "open_meteo_forecast", "calls": 6500, "requests": 1}`. Verwacht: de `forecast`-stap is `ok`, met precies één warning die begint met `"Open-Meteo usage today is "`, en `counts["usage_daily"] > 6400`; run `ok`; `exit_code == 0`; `report.annotations` bevat een regel die begint met `"::warning::forecast: Open-Meteo usage today"` en `"%25 of the guard"` bevat (geëscapet, N-7), terwijl de warning in `ingest_runs` `"% of the guard"` bevat (ongeëscapet).
  - `test_budget_below_threshold_no_warning`: 6.000 geeft geen warning; precies 6.400 na de boeking ook niet (seed 6.398,8 plus gewicht 1,2).
  - `test_cli_pipeline.py::test_budget_warning_on_stdout`: zelfde seed via de CLI. `capsys` stdout bevat een regel die begint met `::warning::`; exitcode 0.
- **AC-6** (`NEEDS_LARS`): zie "Nodig van Lars" en RUNBOOK §13. De verifier controleert `gh run list --workflow hourly.yml --limit 3` en, met Lars, de `ingest_runs`-rij.

### Overige tests
- `test_pipeline.py`:
  - `test_spots_sync_failure_continues`: `spots_path` naar een niet-bestaand bestand, spot vooraf in de database → `spots_sync` `failed` (`error_type == "SpotValidationError"`), de andere stappen `ok`, run `partial`, exitcode 0.
  - `test_tides_partial`: spot met `rws_station: hoekvanholland` en `tide_sensitive: none`, `tide_fetch` die `TideFetchError` geeft → `tides` `partial`, `counts["failed"] == ["hoekvanholland"]`.
  - `test_cannot_start_run` (E12): de fetchers registreren aanroepen; 0 aanroepen, `RunReport.status == "failed"`, `steps == []`, `run_id is None`, exitcode 1, annotatie `::error::run-hourly: cannot record the run`.
  - `test_finish_update_failure_exit_1` (E14).
  - `test_progress_update_after_each_step`: telt de `("update", "ingest_runs")` in `db.writes`; dat is precies `len(steps) + 2` (de update van de wezen-rijen, die de fake ook bij 0 rijen registreert, één per stap, en de slotupdate).
  - `test_progress_update_failure_continues` (E13, `FlakyIngestRuns({"progress"})`): alle stappen draaien, precies één `WARNING` `could not record progress`, de slotupdate slaagt, exitcode volgt de status.
  - `test_abandon_failure_continues` (`FlakyIngestRuns({"abandon"})`): één `WARNING` `could not close abandoned runs`; de run start en eindigt normaal.
  - `test_abandoned_runs_marked_failed` (E15, 2 uur en 30 minuten oud).
  - `test_counts_not_json_fails_step` (E28, N-6): `steps` met een stap die `StepOutcome("ok", {"x": float("nan")})` teruggeeft, gevolgd door een gewone `ok`-stap. Verwacht: eerste stap `failed`, `error_type == "ValueError"`, `counts == {}`; de tweede stap `ok`; de rij heeft `finished_at` en een status ongelijk aan `running`.
  - `test_tide_budget_stops_fetching` (E27, N-5), op `step_tides` direct met een met de hand gebouwde `PipelineContext`: `db.seed("spots", [make_spot(id="spot-a", rws_station="station-a").to_row(), make_spot(id="spot-b", rws_station="station-b").to_row()])`; `clock = [0.0]`, `monkeypatch.setattr(pipeline, "_monotonic", lambda: clock[0])`; een `tide_fetch` die de station-code registreert, `clock[0] += pipeline.TIDE_STEP_BUDGET_S + 1` doet en `TideFetchError("down")` geeft. Verwacht: precies één aanroep (`["station-a"]`); `outcome.status == "partial"`; `counts["failed"] == ["station-a", "station-b"]`; `counts["budget_skipped"] == 1`; een `errors`-regel begint met `"station-b: TimeoutError: tide step time budget"`; precies één warning die begint met `"time budget of 240 s reached; 1 station(s)"`.
  - `test_tide_budget_zero_still_runs_alerts` (E27): `monkeypatch.setattr(pipeline, "TIDE_STEP_BUDGET_S", 0.0)`, YAML-spot met `rws_station: hoekvanholland`, `tide_fetch` die bij aanroep de test laat falen. Verwacht: `tides` `partial`, `budget_skipped == 1`; `evaluate` en `alerts` `ok`; run `partial`; exitcode 0; `report.annotations` bevat `"::warning::tides: time budget"`.
  - `test_alert_counts_shape`: sleutels exact zoals in het contract, zonder `messages`.
  - `test_alerts_errors_only_in_ingest_runs` (E18): een favoriet met een regelrij die `AlertRuleOverride.from_row` laat falen (zoals in de WP-10-test voor `skipped`) → `alerts` `partial`; `counts["errors"]` bevat `"spot test-strand:"`; met `restore_logging`, `configure_logging()` en `caplog` komt die tekst niet in `caplog.text` en niet op stdout.
  - `test_naive_now_raises`.
  - Pure tests: `run_status`, `exit_code_for`, `error_summary` (afkappen op 1000), `build_annotations` (volgorde, maximaal 10, geen `error`-tekst, geen `\n` of `\r`, een warning `"50% done\nnext"` wordt `"::warning::<step>: 50%25 done next"`).
- `test_cli_pipeline.py`:
  - `test_no_user_ids_or_message_texts_in_output` (review B-2), met `restore_logging`, `caplog` en `capsys`:
    1. **Verwachte berichttekst bepalen op een aparte fake** met dezelfde toestand als ná de stappen `spots_sync` en `forecast` van de CLI-run:
       ```python
       # load_spots: shakka.spots.loader; sync_spots: shakka.spots.sync; run_alerts: shakka.jobs.alerts
       yaml_path = write_spots_yaml(tmp_path)
       db2 = FakeSupabase()
       sync_spots(db2, load_spots(yaml_path))        # same spot row as the CLI run
       seed_forecasts(db2, fetched_at=NOW)            # same rows as fake_forecast_fetch
       seed_user(db2)
       dry = run_alerts(db2, now=NOW, base_url=None, dry_run=True)
       assert len(dry.messages) == 1                  # the check below must test something
       title = dry.messages[0].message.title
       body_lines = [ln for ln in dry.messages[0].message.body.splitlines() if ln.strip()]
       ```
    2. **De CLI-run** op een tweede `FakeSupabase` `db` met alleen `seed_user(db)`; `runtime.open_db` → `db`, `runtime.open_http` → `blocked_http()`, `runtime.utcnow` → `NOW`, `shakka.openmeteo.forecast.fetch_forecast` → `fake_forecast_fetch`, env zoals bij AC-3 met `SPOTS_PATH=<yaml_path>`; `run_hourly_cli(echo=print)` geeft 0.
    3. **De run maakte echt een bericht**: in `db.rows("ingest_runs")[0]["steps"]` heeft de stap `alerts` status `ok` en `counts["events"] == 1`.
    4. **Niets lekt**: met `out = caplog.text + captured.out + captured.err` komen `USER_A`, `title` en elke regel uit `body_lines` niet voor in `out`.
  - `test_missing_config`: geen env → exitcode 1, uitvoer bevat `configuration incomplete` en een regel die begint met `::error::`.
  - `test_run_hourly_listed_in_help`: `shakka --help` toont `run-hourly` en `check-activity`.
- `test_logsetup.py`:
  - `test_httpx_and_httpcore_quiet` (WP-10 "Gevolgen"): `configure_logging()`, `caplog.set_level(logging.DEBUG)`, de echte `SupabaseRest(url, "sb_secret_TESTVALUE", client=httpx.Client(transport=MockTransport(...)))` en `db.select("profiles", filters={"user_id": f"eq.{USER_A}"})` → `USER_A` staat niet in `caplog.text`. Controle: `logging.getLogger("httpx").level == logging.WARNING`, idem `httpcore`.
  - `test_configure_logging_idempotent`: twee keer aanroepen geeft één handler met `_shakka_handler`.
  - `test_redact_ignores_short_values` (korter dan 8 tekens wordt niet vervangen) en `test_secret_values`.
  - `test_github_annotation_escapes` (N-7): `github_annotation("warning", "83% of\r\nthe guard") == "::warning::83%25 of  the guard"`; `escape_command_data("%0A") == "%250A"` (een letterlijke `%0A` in de tekst wordt niet als nieuwe regel geïnterpreteerd).
- `test_activity.py`:
  - `check_activity` bij 0, 44, 45, 52, 53 en 70 dagen, en bij een datum in de toekomst (0, `ok`);
  - `parse_commit_date` met `"2026-08-01T10:00:00Z"`, `""`, `"garbage"` en `"2026-08-01T10:00:00"` (naïef → `None`);
  - CLI via `CliRunner` met `runtime.utcnow` vervangen: exitcodes 0/0/1 en de prefixen `activity:`, `::warning::`, `::error::`; lege invoer → `::warning::Could not determine`, exit 0.

## Externe afhankelijkheden
Geen nieuwe Python-packages. Gebruikt worden `click`, `httpx`, `pydantic`, `pyyaml` (al dependencies) en de standaardbibliotheek (`logging`, `time`, `functools`, `json`).

GitHub Actions (gecontroleerd op 15 oktober 2026):
- `schedule`: draait op de laatste commit van de default branch; minimaal elke 5 minuten; vertraging en zelfs geschrapte runs bij piekbelasting, "including the start of every hour"; in publieke repo's uitgeschakeld na 60 dagen zonder activiteit. [Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- `workflow_dispatch`: alleen als het workflowbestand op de default branch staat; inputs met `type: choice`, `options` en `default`. Zelfde bron, plus [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
- `concurrency`: hooguit één lopende run per groep. Standaard (`queue: single`) hooguit één wachtende run, die door een nieuwere wordt vervangen. `cancel-in-progress: true` zou de lopende run afbreken; daarom staat het op `false`. [Control workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
- Contexten: `vars` en `inputs` zijn beschikbaar in `jobs.<id>.if`; `secrets` en `vars` in `steps.env`. Een niet-gezette variable geeft een lege string. [Contexts](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts)
- Annotaties: `::warning::{message}` en `::error::{message}` op stdout. [Workflow commands](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands). Die pagina beschrijft het escapen niet; de officiële toolkit (`escapeData` in `packages/core/src/command.ts`) vervangt in de berichtdata `%` → `%25`, `\r` → `%0D`, `\n` → `%0A` ([bron](https://github.com/actions/toolkit/blob/main/packages/core/src/command.ts), gecontroleerd op 15 oktober 2026). WP-11 neemt `%` → `%25` over en maakt van `\r`/`\n` spaties.
- Meldingen voor geplande workflows gaan naar de gebruiker die de workflow heeft aangemaakt. Wijzigt een ander de cron-syntax, dan naar die gebruiker; wordt de workflow uit- en weer aangezet, dan naar wie hem aanzette. Instelbaar: e-mail en/of web, eventueel alleen bij gefaalde runs. [Notifications for workflow runs](https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs)
- Opnieuw aanzetten: `gh workflow enable <workflow>` of via de Actions-tab. [Disable and enable workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)
- GitHub CLI is voorgeïnstalleerd op GitHub-hosted runners; authenticatie via `GH_TOKEN`. [Use GitHub CLI in workflows](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli)
- REST "List commits": `GET /repos/{owner}/{repo}/commits`; `sha` is standaard de default branch; `per_page` max. 100; veld `commit.committer.date`. [Commits](https://docs.github.com/en/rest/commits/commits)
- Actions `actions/checkout@v7` en `astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884` (v10.3.0): dezelfde versies als in `ci.yml` (groen op `develop`).
- Keepalive-actions: `github.com/gautamkrishnar/keepalive-workflow` is door GitHub Staff uitgeschakeld wegens een schending van de voorwaarden (pagina bekeken op 15 oktober 2026). Daarom geen automatische keepalive (A7).

HTTPX-logging: logger `httpx` logt requests op `INFO`, `httpcore` details op `DEBUG`. [HTTPX Logging](https://www.python-httpx.org/logging/) (gecontroleerd door WP-10, 15 oktober 2026).

## Risico's
- **R1. Vertraagde of geschrapte geplande runs.** GitHub geeft geen garantie. De cron op :17 vermijdt het piekmoment. Een gemist uur is opgevangen: de stale-grens is 3 uur en de getijdata loopt 8 dagen vooruit.
- **R2. Workflow van `develop`, code van `main` (A5).** Wijzigt `hourly.yml` op `develop` iets waarvoor nieuwe code nodig is (een nieuw commando of een nieuwe variable), dan draait de schedule dat meteen tegen de oude code op `main`. Regel in de RUNBOOK: wijzigingen aan `hourly.yml` moeten werken met de code op `main`; en anders eerst promoveren of `HOURLY_ENABLED` tijdelijk uitzetten.
- **R3. "Activiteit" is niet gedefinieerd.** Commits op de default branch zijn een conservatieve benadering; mogelijk telt GitHub meer mee. Valt de schedule toch stil, dan ziet Lars dat aan het uitblijven van nieuwe rijen in `ingest_runs` (RUNBOOK); herstel met `gh workflow enable hourly.yml`.
- **R4. Stille `partial`.** Een stap die elk uur `partial` is (bijv. een station dat altijd faalt, WP-04 R4) of een gefaalde `evaluate` geeft geen mail. Wel komt er een `::error::`- of `::warning::`-annotatie en een rij in `ingest_runs`. WP-22 kan een drempel toevoegen.
- **R5. Openbare logs.** Andere bibliotheekloggers zouden op `INFO` gevoelige details kunnen loggen. In het pakket zijn alleen httpx/httpcore relevant (geen requests/urllib3). Tracebacks van programmeerfouten kunnen in de log komen; die bevatten geen data uit de database (DB-fouten zijn geredigeerd), en GitHub maskeert geregistreerde secrets.
- **R6. Eén Supabase-project.** Een dispatch met `ref: develop` schrijft naar dezelfde productiedatabase als `main`. Dat is bedoeld voor de eerste test; de RUNBOOK zegt het.
- **R7. Ontvanger van de mails.** Wie `hourly.yml` aanmaakt, de cron wijzigt of de workflow opnieuw aanzet, krijgt de meldingen. De builder commit als Lars; AC-6 laat Lars dit bevestigen.
- **R8. Supply chain.** `actions/checkout@v7` is een tag, geen SHA (zoals in `ci.yml`). De secrets staan alleen in de env van de pipelinestap. Pinnen hoort bij de dependency-audit van WP-22.
- **R9. Elke run draait `uv sync` inclusief dev-dependencies.** Dat kost een paar seconden; `UV_LOCKED=1` voorkomt dat de lockfile afwijkt. De hele run blijft naar verwachting ruim onder 5 minuten (review N-10); de werkelijke duur staat per stap in `ingest_runs` (`duration_ms`). De repo is publiek, dus Actions-minuten zijn gratis.
- **R10. Getijbudget te krap of te ruim.** 240 s is ruim voor een handvol stations bij normale RWS-responstijden (≈ 1 s per station). Bij een langdurige storing worden per run hooguit zoveel stations geprobeerd als in 240 s passen; de rest volgt in latere runs. De getijdata loopt 8 dagen vooruit, dus dat is geen probleem voor de evaluatie. Het lopende request wordt niet onderbroken (geen threads); een request dat veel langer duurt dan de httpx-timeouts per fase is onwaarschijnlijk, en de job-timeout van 15 minuten blijft het laatste vangnet (E25).

## Buiten scope
- De marine-stap (WP-12), versturen van alerts en `notifiers` (WP-17), sessies opruimen (WP-19), het wekelijkse gebruiksrapport en pushwaarschuwingen aan Lars (WP-22).
- Een bewaartermijn voor `ingest_runs` en een drempel voor aanhoudende `partial`-runs (WP-22).
- Het delen van inputs tussen evaluatie- en alertjob (A8).
- Een uniforme retry-helper (WP-22).
- De default branch op GitHub wijzigen. Dat is een keuze van Lars; met `ref: main` in de workflow is het niet nodig.
- Automatische keepalive-commits of -API-calls (A7).
- Wijzigingen aan `docs/WORK_PACKAGES.md`. De env-tabel met `HOURLY_ENABLED` heeft de orchestrator al bijgewerkt op `develop` (commit `ed68d2e`).
- Een stale-regel per spot en een tijdsbudget voor alle netwerkstappen (zie "Gevolgen voor latere WP's", WP-22).

## Nodig van Lars
1. GitHub Secrets `SUPABASE_URL` en `SUPABASE_SECRET_KEY` (repo Settings → Secrets and variables → Actions → New repository secret).
2. Optioneel de Actions-variable `APP_BASE_URL` (pas zinvol na WP-14).
3. Actions aan voor de repo (Settings → Actions → General).
4. In je GitHub-account e-mailmeldingen voor Actions aan, desgewenst alleen bij gefaalde workflows (RUNBOOK §13). Controleer dat jij de gebruiker bent die `hourly.yml` heeft aangemaakt; die krijgt de meldingen.
5. AC-6, in deze volgorde:
   - direct na de merge naar `develop`: Actions → hourly → Run workflow, met `ref = develop`. De run slaagt en er komt een `ingest_runs`-rij met `status = ok`;
   - promoveer `develop` naar `main` (`git merge --ff-only develop` op `main`) zodra je dat wilt; pas dan heeft de schedule de code;
   - zet de Actions-variable `HOURLY_ENABLED` op `true`. Binnen 2 uur volgt een geplande run (`gh run list --workflow hourly.yml --limit 3`).

## Stappenplan voor de builder
Werk op branch `wp/WP-11` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-11`. Lees of print `.env` nooit. Na elke stap vanuit `ingest/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`. Eén commit per stap, commitberichten in het Engels.

1. **Logging en redactie.** Schrijf eerst `tests/test_logsetup.py`, inclusief `test_httpx_and_httpcore_quiet` (die gebruikt alleen `SupabaseRest` en `MockTransport`) en `test_github_annotation_escapes`. Rood. Implementeer `shakka/logsetup.py` (inclusief `escape_command_data` en `github_annotation`). Groen.
   Commit: `feat(ingest): logging setup with secret redaction and quiet httpx`.
2. **Activiteitscheck.** Schrijf `tests/test_activity.py` (puur deel). Rood. Implementeer `shakka/activity.py`. Voeg `check-activity` toe aan `cli.py` en de CLI-tests. Groen.
   Commit: `feat(ingest): check-activity warns before schedules are disabled`.
3. **Pipelinekern met nepstappen.** Voeg `open_http` en `HTTP_TIMEOUT_S` toe aan `jobs/runtime.py`. Schrijf in `tests/test_pipeline.py` de pure tests (`run_status`, `exit_code_for`, `error_summary`, `build_annotations`) en de levenscyclustests met geïnjecteerde `steps`: `test_all_steps_failed`, `test_cannot_start_run`, `test_finish_update_failure_exit_1`, `test_progress_update_after_each_step` (met een eigen lijst stappen), `test_progress_update_failure_continues`, `test_abandon_failure_continues`, `test_abandoned_runs_marked_failed`, `test_counts_not_json_fails_step`, `test_naive_now_raises`, en de redactie van `error`, met `FlakyIngestRuns` zoals in de Fixtures. Rood. Implementeer in `shakka/pipeline.py` de dataklassen, `_monotonic`, `run_step` (JSON-conversie binnen de `try`), de statusfuncties, `build_annotations` (via `github_annotation`) en `run_hourly` (nog zonder `STEPS`; gebruik tijdelijk `steps` als verplicht keyword). Groen.
   Commit: `feat(ingest): pipeline core with ingest_runs lifecycle`.
4. **Echte stappen.** Schrijf `tests/pipeline_fixtures.py` en de tests voor AC-1, AC-2 (pipelinedeel), AC-5 (pipelinedeel), `test_spots_sync_failure_continues`, `test_tides_partial`, `test_tide_budget_stops_fetching`, `test_tide_budget_zero_still_runs_alerts`, `test_alert_counts_shape` en `test_alerts_errors_only_in_ingest_runs`. Rood. Implementeer de vijf stapfuncties (de getijstap met `TIDE_STEP_BUDGET_S` en `bounded_fetch`), `alert_counts`, `newest_forecast_fetch`, `STEPS`, `STEP_NAMES` en de defaults voor de fetchers. Maak `steps=STEPS` de default. Groen.
   Commit: `feat(ingest): hourly steps with stale-forecast rule and budget warning`.
5. **CLI `run-hourly`.** Schrijf `tests/test_cli_pipeline.py` (AC-2 CLI-deel, AC-3, AC-5 stdout, privacy, ontbrekende config, help). Rood. Implementeer `run_hourly_cli` en het commando in `cli.py`. Groen.
   Commit: `feat(ingest): shakka run-hourly`.
6. **Workflow.** Schrijf `tests/test_hourly_workflow.py` (AC-4). Rood. Maak `.github/workflows/hourly.yml` exact zoals in het Ontwerp. Groen. Controleer ook handmatig: `grep -nE "sb_secret_" .github/workflows/*.yml` en `grep -niE "telegram" .github/workflows/*.yml` geven niets.
   Commit: `ci: hourly workflow`.
7. **RUNBOOK.** §4: rij `| HOURLY_ENABLED | GitHub Actions variable | workflow hourly.yml: schedule aan (true) of uit | WP-11 |`. Nieuwe sectie `## 13. Uurlijkse run (vanaf WP-11)` in het Nederlands met:
   1. **Wat draait er.** Elk uur om :17 UTC (geen garantie; GitHub kan vertragen of een run overslaan): `spots_sync`, `forecast`, `tides`, `evaluate`, `alerts`. De schedule draait de code van `main`, met het workflowbestand van `develop` (de default branch). Alleen als `HOURLY_ENABLED` = `true`. Eén run tegelijk.
   2. **Eenmalige setup.** De punten uit "Nodig van Lars" 1–5. Het menupad voor de meldingen: github.com → Settings → Notifications → System → Actions (e-mail aan; desgewenst "Only notify for failed workflows"). De builder controleert het exacte pad en de namen tegen de actuele GitHub-documentatie of -UI en past de tekst zo nodig aan. Wie de mail krijgt: wie `hourly.yml` heeft aangemaakt, of als laatste de cron wijzigde, of de workflow opnieuw aanzette.
   3. **Handmatig starten.** Actions → hourly → Run workflow (kies `ref`), of `gh workflow run hourly.yml -f ref=main`. `ref = develop` schrijft naar dezelfde database; bedoeld als test vóór een promotie.
   4. **Runs bekijken.** `gh run list --workflow hourly.yml --limit 5` en `gh run view <run-id> --log`. Annotaties (`::warning::`, `::error::`) staan bovenaan de samenvatting van een run. Een run met status "cancelled" in de lijst is geen storing: duurt een run lang en komen er intussen twee nieuwe starts (schedule en/of dispatch), dan vervangt de nieuwste de wachtende, en die wachtende krijgt "cancelled" (`concurrency`, review N-4). Een getijstap met de warning "time budget of 240 s reached" betekent dat RWS traag of onbereikbaar is; de overgeslagen stations volgen in een latere run.
   5. **`ingest_runs` lezen** (Dashboard → SQL Editor): `select id, started_at, finished_at, status, error_summary from public.ingest_runs order by started_at desc limit 24;` en `select jsonb_pretty(steps) from public.ingest_runs where id = <id>;`. Uitleg van de stapvelden (`status`, `duration_ms`, `counts`, `error`, `error_type`, `reason`, `warnings`) en de statussen `ok`, `partial`, `failed`, `skipped`, `running`.
   6. **Wat een gefaalde run betekent** (mail van GitHub):
      - exitcode 1 bij `failed` (alertstap faalde, niets werkte, of de run kon niet worden vastgelegd);
      - bij `stale_forecast` (de forecast faalt en de nieuwste is ouder dan 3 uur: geen alerts);
      - bij een onvolledige configuratie (secrets);
      - bij de activiteitscheck vanaf 53 dagen.

      Waar je de oorzaak vindt: de annotaties en `ingest_runs`. `partial` geeft geen mail. Tijdens een storing komt er elk uur een mail (GitHub dedupliceert niet; bewust geaccepteerd). Pauzeren: zet `HOURLY_ENABLED` op `false`. **Let op:** de uurlijkse run houdt het gratis Supabase-project actief (PROJECT_PLAN §2). Staat `HOURLY_ENABLED` langer dan ongeveer een week op `false` (Supabase pauzeert na 7 dagen zonder activiteit), dan pauzeert het project. Zet de run dus binnen een week weer aan, of start tussendoor handmatig een run (punt 3). Is het project toch gepauzeerd: herstel het via het Supabase-dashboard (review N-8).
   7. **Budgetwaarschuwing.** Boven 80% van de guard (6.400 calls per dag, of 192.000 per maand) volgt een `::warning::`-annotatie en een warning in de stap `forecast`; geen mail.
   8. **60-dagenregel.** De activiteitscheck: vanaf 45 dagen een warning, vanaf 53 dagen een fout (elk uur een mail). Oplossing: merge een kleine wijziging naar `develop` via een PR, bijvoorbeeld de regel "Laatste activiteitscommit: <datum>" onderaan deze sectie bijwerken. Is de schedule toch uitgeschakeld: `gh workflow enable hourly.yml` (de meldingen gaan daarna naar jou als je hem aanzet) en daarna een commit.
   9. **Wijzigingen aan `hourly.yml`** moeten werken met de code op `main` (R2).
   10. **Lokaal.** `cd ingest && uv run shakka run-hourly` doet een echte run tegen de database uit `.env` en legt die vast in `ingest_runs`. De uitvoer bevat geen berichtteksten.
   11. Als laatste regel van de sectie: `Laatste activiteitscommit: <datum van deze WP>`.

   Commit: `docs(runbook): hourly run, ingest_runs and GitHub notifications`.
8. **Eindcontrole.** Volledige suite en lint groen; `uv run shakka --help` toont `run-hourly` en `check-activity`. AC-6 is `NEEDS_LARS` (zie "Nodig van Lars"); noteer dat in `verification.md`. Geen commit nodig als er niets wijzigt.

## Verwerking review
Ronde 1 (`review.md`, CHANGES_REQUIRED).

**Blokkerend**
- **B-1 (AC-1-assertie tegenover de volgorde wezen-update → insert).** Volgorde behouden (beslissing orchestrator). De AC-1-test toetst nu dat de eerste `insert` in `db.writes` `("insert", "ingest_runs")` is, en apart dat daarvoor precies de wezen-update `("update", "ingest_runs")` staat (Testplan, AC-1, met codefragment). `test_progress_update_after_each_step` (`len(steps) + 2`) blijft consistent.
- **B-2 (privacytest niet uitvoerbaar).** De verwachte titel en body komen nu uit een aparte fake met dezelfde toestand ná `spots_sync` en `forecast`: `sync_spots(db2, load_spots(yaml_path))`, `seed_forecasts(db2, fetched_at=NOW)`, `seed_user(db2)`, `run_alerts(db2, ..., dry_run=True)`, met `assert len(dry.messages) == 1`. De test controleert ook dat de CLI-run zelf `alerts.counts["events"] == 1` vastlegt, en toetst `USER_A`, de titel en elke niet-lege bodyregel tegen log, stdout en stderr (Testplan, `test_cli_pipeline.py`).

**Niet-blokkerend**
- **N-1 (stale-regel per spot).** De zin in A4 is gecorrigeerd: WP-10 filtert relatief aan de nieuwste fetch van díe spot, niet aan `now`. Onder "Gevolgen voor latere WP's → WP-22" staat nu dat bij meer dan één chunk een gefaalde chunk tot alerts op oude data kan leiden zonder `stale_forecast`, met de voorgestelde oplossing (`fetched_at < now - 3 h` weglaten in `load_inputs`).
- **N-2 (`FlakyIngestRuns` dubbelzinnig).** Vier disjuncte soorten gedefinieerd (`abandon`, `insert`, `progress`, `final`), met de herkenningsregel per soort (filters en sleutels in `values`). De fout komt vóór `super()`, dus niet in `writes`. Een extra test `test_abandon_failure_continues` (Fixtures en Overige tests).
- **N-3 (caplog-volgorde in AC-3).** Expliciet gemaakt dat de AC-3-test INFO en hoger toetst, dat dat voldoende is, en dat `test_httpx_and_httpcore_quiet` het DEBUG-deel draagt. Ook vermeld dat `caplog.text` niet door de `RedactingFormatter` gaat (de test is daardoor strenger).
- **N-4 ("cancelled"-runs).** RUNBOOK §13 punt 4 legt uit dat een vervangen wachtende run "cancelled" krijgt en geen storing is; E22 aangevuld.
- **N-5 (job-timeout tegenover de getijstap).** Gekozen voor de eenvoudigste harde grens zonder wijziging aan `shakka.jobs.tides`: een totale deadline `TIDE_STEP_BUDGET_S = 240.0` voor de getijstap, afgedwongen in de fetch-wrapper `bounded_fetch` die de pipeline aan `run_tide_ingest` geeft. Stations na de deadline worden niet aangeroepen, komen in `failed` (stap `partial`), krijgen de telling `budget_skipped` en een warning. Zo komt `alerts` altijd aan bod (Ontwerp "De stappen", E27, R10, twee tests). Een uniform budget voor alle netwerkstappen staat bij WP-22.
- **N-6 (JSON-conversie buiten de `try`).** De conversie staat nu binnen de foutisolatie van `run_step`. Een `ValueError` maakt de stap `failed` (`error_type == "ValueError"`); de run gaat door (E28, `test_counts_not_json_fails_step`).
- **N-7 (escapen van annotaties).** Nieuw: `escape_command_data` en `github_annotation` in `shakka.logsetup`. `%` wordt `%25`, `\r` en `\n` worden spaties. Alle annotaties lopen erdoor (pipeline, CLI, `check-activity`). Gecontroleerd tegen `escapeData` in `actions/toolkit`. De AC-5-test en een nieuwe logsetup-test toetsen `%25`.
- **N-8 (Supabase-pauze).** RUNBOOK §13 punt 6: `HOURLY_ENABLED=false` langer dan ongeveer een week laat het gratis Supabase-project pauzeren; zet de run binnen een week weer aan of start een run met de hand.
- **N-9 (`HOURLY_ENABLED` in WORK_PACKAGES).** Al gedaan door de orchestrator: de variable staat in de env-tabel op `develop` (commit `ed68d2e`). A11 en "Buiten scope" zijn daarop aangepast; de builder zet hem alleen in RUNBOOK §4.
- **N-10 (duur van de run).** Geen actie nodig. Vermeld bij R9 dat de duur via `duration_ms` in `ingest_runs` zichtbaar is.
