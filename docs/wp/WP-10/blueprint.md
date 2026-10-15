# Blueprint WP-10: Evaluatie- en alertjobs plus beheer-CLI
Status: DRAFT
Revisie: 1

## Doel
De pure engines van WP-05 t/m WP-08 aan de database koppelen, zonder meldingskanaal (A-16):
1. `shakka.jobs.inputs`: per spot met coördinaten het profiel, de forecasts en de getij-extremen laden.
2. `shakka.jobs.evaluate`: per spot evalueren met `default_limits(spot)`, opslaan in `evaluations` en oude rijen opruimen.
3. `shakka.jobs.alerts`: per favoriet de effectieve regel bepalen, evalueren met `rider_limits(rule)`, windows zoeken, deduplicatie tegen `alert_state`, berichten renderen en de state opslaan. De berichten komen terug in `AlertJobResult.messages`; er wordt niets verstuurd.
4. `shakka.jobs.admin` en de CLI-groep `shakka admin`: profiel, favorieten en alertregels van Lars beheren zonder UI, plus een preview zonder schrijfacties.
5. CLI `shakka evaluate` en `shakka alerts run [--dry-run]`.
6. Het env-contract bijwerken: `telegram_*` uit `Settings`, `TELEGRAM_*` uit `.env.example`, de tests en de RUNBOOK.

M1 is daarmee af: Lars kan via CLI en Supabase-dashboard controleren dat de alerts kloppen. Versturen komt in WP-17.

## Aannames
- **A1. Alerts alleen voor spots met `verified: true`** (besluit Lars, "Beslissingen voor Lars", start WP-10). Niet-geverifieerde spots worden wel geëvalueerd en in `evaluations` opgeslagen (voor de app, met label in WP-14), maar een favoriet op zo'n spot telt als `ineligible`: geen evaluatie per regel, geen diff, geen schrijfacties, geen berichten. Bestaande `alert_state`-rijen van zo'n favoriet blijven ongewijzigd en verlopen vanzelf via de opruimregel.
- **A2. `last_notified_at` blijft in M1 `NULL`.** Er wordt niets afgeleverd, dus er is geen moment om in te vullen. Dit sluit aan op WP-08 A9 (`diff_windows` wijzigt het veld nooit) en op WP-08 "Gevolgen" (WP-17: actieve rijen met `last_notified_at is None` zijn de rijen die in M1 een event kregen zonder aflevering). Het open punt uit WORK_PACKAGES is hiermee beslist zoals voorgesteld.
- **A3. Uitgeschakelde regel (`enabled = false`): geen diff.** WP-07 laat dit open ("de evaluatie kan worden overgeslagen"). Liep de diff wel, dan zou elke toekomstige actieve entry een `cancelled`-event krijgen ("Gaat niet door"), terwijl het window nog steeds go is. Dat is misleidend. Daarom: bij `enabled = false` geen evaluatie, geen diff, geen schrijfacties (teller `disabled`). Zet de gebruiker de regel weer aan, dan koppelt `diff_windows` de nog actieve entries gewoon, zonder dubbele `new`.
- **A4. Geen forecastdata: geen diff.** Heeft een geverifieerde favoriete spot na het laden geen enkele forecastrij, dan is "geen window" geen informatie maar een gat in de data. Een diff zou dan alle toekomstige windows annuleren. Zo'n favoriet telt als `ineligible` ("no forecast data"). Een verouderde forecast in het algemeen bewaakt WP-11 (`stale_forecast`).
- **A5. Verouderde forecastrijen negeren** (aanbeveling WP-03 A8 en "Gevolgen"). Per spot: rijen met `fetched_at < max(fetched_at van die spot) - 3 h` worden weggelaten. Alle modellen van een spot komen uit één request (WP-03), dus na een geslaagde run zijn alle actuele rijen even oud; een model dat een uur niet meer levert, laat een oudere rij achter die zo wegvalt. Als de laatste forecastrun voor een spot faalde, blijft de vorige set intact.
- **A6. Laadbereik.** Forecasts: `valid_at` in `[floor_hour(now) - 1 h, now + 8 d)` (contract: `now - 1h` tot `now + 8 dagen`; het vorige hele uur telt mee). Getij per station: `at` in `[floor_hour(now) - 1 h - 12 h, now + 8 d + 12 h]`. WP-05 eist minstens 10 uur vóór het eerste en 11 uur na het laatste uur, WP-04 minstens 9; 12 uur dekt beide. De getij-ingest bewaart 48 uur terug (WP-04), dus de data is er.
- **A7. Eén query per spot voor forecasts en één per station voor getij.** Bij 25 spots zijn dat ongeveer 25 + aantal stations requests van hooguit één pagina. Zo blijft een fout in de data van één spot geïsoleerd (A8) en hoeft niets in het geheugen gegroepeerd te worden over spots heen.
- **A8. Foutisolatie.**
  - Per spot (laden en evalueren): een `ValueError` (ook `pydantic.ValidationError`) bij `SpotProfile.from_row`, `ForecastHour.from_row`, `TideExtreme.from_row` of `evaluate_spot` slaat die spot over (WP-02 A10). De spot-id komt in de foutregel en in de log; spot-id's zijn openbare data (`data/spots.yaml`).
  - Per favoriet (WP-07 "Gevolgen", bindend; WP-08 "Gevolgen", bindend): `ProfileDefaults.from_row`, `AlertRuleOverride.from_row`, `resolve_rule`, het `RiderProfile`, `AlertStateEntry.from_row`, `evaluate_spot`, `find_windows`, `diff_windows` en `render_alert` staan samen in één `try ... except ValueError`. Een fout slaat die favoriet over (teller `skipped`) en er wordt voor die favoriet niets geschreven. Eén kapotte rij stopt de job nooit.
  - `DatabaseError` bij het laden stopt de hele job (de aanroeper, WP-11, legt dat vast). `DatabaseError` bij het schrijven van één favoriet stopt alleen de schrijfacties van die favoriet (WP-08 "Gevolgen"); andere favorieten gaan door (teller `write_errors`).
- **A9. Logging zonder persoonsgegevens gaat vóór de logsuggestie van WP-07.** WP-07 "Gevolgen" stelt voor bij een overgeslagen favoriet `user_id` en `spot_id` te loggen. De repo is publiek en de Actions-logs zijn openbaar, dus WP-10 logt per favoriet **niets** behalve het exceptietype, en verder alleen aantallen. Ook de spot-id van een favoriet komt niet in de log (een favoriet is een gebruikersvoorkeur). De details (spot-id plus foutmelding, nooit een user-id) staan in `AlertJobResult.errors`, die de CLI lokaal toont. `DatabaseError`-meldingen kunnen een user-id bevatten (bijv. de detailtekst van een FK-fout); daarom komt van een `DatabaseError` alleen het type, de HTTP-status en de code in `errors`, nooit de melding.
- **A10. Schrijfacties op `alert_state` via `update` en `insert`, nooit `upsert`.** Updates op `id`, inserts zonder `id` (de database kent hem toe via `gen_random_uuid()`); de teruggegeven `id` is de `state_id`. Eén insert per nieuwe entry (`returning=True`), zodat de koppeling rij ↔ entry niet afhangt van de volgorde van een bulkantwoord. Ook in de beheer-CLI geen upsert met een deel van de kolommen: de PostgREST-documentatie zegt niet welke kolommen bij `merge-duplicates` worden bijgewerkt als de payload maar een deel bevat (gecontroleerd, zie Externe afhankelijkheden). Daarom eerst lezen, dan `update` of `insert`.
- **A11. Berichten van een favoriet waarvan het opslaan faalt, komen niet in het resultaat.** In M1 is het resultaat "wat is vastgelegd". Faalt het schrijven halverwege, dan berekent de volgende run dezelfde of een herstelde diff (WP-08 A15) en komen de berichten dan alsnog.
- **A12. `APP_BASE_URL` wordt één keer per run gecontroleerd.** `render_alert` geeft een `ValueError` bij een niet-lege, ongeldige `base_url` (WP-08: "configuratiefout, moet opvallen"). Binnen de per-favoriet-`try` zou die fout stil elke favoriet overslaan. Daarom normaliseert `run_alerts` de `base_url` vooraf (`None` of leeg na `strip()` → `None`) en controleert hem met `build_go_url`; een ongeldige waarde geeft een `ValueError` vóór enige lees- of schrijfactie.
- **A13. Additieve uitbreidingen van het contract.** De signatures uit WORK_PACKAGES blijven exact zo. Erbij komen, allemaal met een default:
  - `load_inputs(..., spot_ids=None)` en de functie `load_inputs_checked` met `InputsLoad` (voor de foutregels van `run_evaluation`);
  - `EvaluationJobResult.failed` en `.errors`;
  - `AlertJobResult.favorites`, `.ineligible`, `.disabled`, `.skipped`, `.write_errors`, `.deleted`, `.errors`;
  - de interne bouwstenen `load_alert_context`, `plan_favorite` en `store_plan` (publiek binnen `shakka.jobs.alerts`, zodat WP-17 de aflevering ertussen kan zetten);
  - `shakka.jobs.runtime` (testnaden voor de CLI);
  - CLI-uitvoer en exitcodes (hieronder vastgelegd).
- **A14. Beheer-CLI zonder "wissen".** Het contract kent geen optie om een veld weer op `NULL` (default) te zetten. Behalve de quiver (`--quiver ""` maakt hem leeg, want de kolom is `not null default '{}'`) blijft dat buiten scope; Lars kan het in het Supabase-dashboard doen, en WP-16 krijgt het in de UI.
- **A15. Een verwijderde favoriet laat zijn `alert_state`-rijen staan.** De FK van `alert_state` wijst naar `auth.users` en `spots`, niet naar `favorites`. De job kijkt alleen naar favorieten, dus zulke rijen doen niets meer en verdwijnen via de opruimregel 48 uur na `window_end`. Bij opnieuw toevoegen worden ze weer gewoon meegenomen.
- **A16. Geen nieuwe dependencies, geen migratie, geen wijziging aan `shakka.domain`.** Alleen `click`, `pydantic`, `httpx` (via `shakka.db`) en de standaardbibliotheek.

## Ontwerp

### Lagen
```
shakka.cli ──> shakka.jobs.{evaluate, alerts, admin} ──> shakka.jobs.inputs ──> shakka.db
                              │                                   │
                              └──────────> shakka.domain.* <──────┘
shakka.jobs.runtime: open_db(settings), utcnow()   (testnaden voor de CLI)
```
`shakka.jobs.*` importeert nooit `shakka.notify` (bestaat nog niet; AC-3). Alle jobfuncties krijgen `now` als parameter; alleen `runtime.utcnow()` leest de klok, en alleen de CLI-runners roepen die aan. Elke jobfunctie geeft bij een naïeve `now` een `ValueError`.

### Inputs (`shakka.jobs.inputs`)
`load_inputs_checked(db, *, now, spot_ids=None)`:
1. `rows = db.select("spots", columns=",".join(SPOT_COLUMNS), order="id")`, met `filters={"id": in_filter(sorted(spot_ids))}` als `spot_ids` gegeven is. Is `spot_ids` een lege verzameling, dan geen query en een leeg resultaat.
2. Per rij, op volgorde van `id`:
   - `lat` of `lon` is `None` → `without_coords` (geen fout, geen query);
   - anders in één `try ... except ValueError`:
     - `spot = SpotProfile.from_row(row)`;
     - forecasts: `db.select("forecast_hours", columns=FORECAST_COLUMNS, filters={"spot_id": f"eq.{spot.id}", "valid_at": [f"gte.{iso_utc(start)}", f"lt.{iso_utc(end)}"]})` met `start = floor_hour(now) - FORECAST_LOOKBACK` en `end = now + FORECAST_HORIZON`;
     - verouderde rijen weglaten (A5): `newest = max(fromisoformat(r["fetched_at"]))`; houd rijen met `fetched_at >= newest - STALE_FETCH_AGE`;
     - `forecasts = [ForecastHour.from_row(r) for r in kept]`, gesorteerd op `(valid_at, model)`;
     - getij: als `spot.rws_station` gezet is, `station = spot.rws_station.strip()`, en de extremen van dat station uit een cache per station (zelfde run). Eerste keer: `db.select("tide_extremes", columns=TIDE_COLUMNS, filters={"station": f"eq.{station}", "at": [f"gte.{iso_utc(start - TIDE_MARGIN)}", f"lte.{iso_utc(end + TIDE_MARGIN)}"]}, order="at")`, dan `[TideExtreme.from_row(r) for r in rows]`. Een `ValueError` bij het parsen wordt in de cache onthouden en geldt voor elke spot van dat station. Zonder station: `tides = []`;
     - `inputs[spot.id] = SpotInputs(spot, forecasts, tides)`;
   - bij `ValueError`: de id van de rij (`str(row.get("id"))`) gaat in `invalid`, plus een foutregel `f"spot {id}: {type(exc).__name__}: {_short(exc)}"`, en een log-waarschuwing `inputs: spot %s skipped (%s)` met id en exceptietype.
3. Resultaat `InputsLoad(inputs, invalid=sorted, without_coords=sorted, errors)`.

`load_inputs(db, *, now, spot_ids=None)` geeft `load_inputs_checked(...).inputs` terug.

`_short(exc) = " ".join(str(exc).split())[:200]` (één regel, hooguit 200 tekens).

### Evaluatiejob (`shakka.jobs.evaluate`)
`run_evaluation(db, *, now)`:
1. `load = load_inputs_checked(db, now=now)`.
2. Per spot (op volgorde van id): `evals = evaluate_spot(spot, forecasts, tides, default_limits(spot))` in een `try ... except ValueError` (fout → `failed` plus foutregel, log `evaluate: spot %s failed (%s)`). Rijen: `[e.to_row(evaluated_at=now) for e in evals]`.
3. Alle rijen samen: `db.upsert("evaluations", rows, on_conflict="spot_id,valid_at")` als er rijen zijn (de client batcht per 500). `evaluate_spot` geeft per spot elke `valid_at` één keer, dus er zijn geen dubbele sleutels (WP-01 "Gevolgen").
4. `deleted = db.delete("evaluations", filters={"valid_at": f"lt.{iso_utc(now - EVALUATION_RETENTION)}"})`.
5. Log `evaluate: spots=%d rows=%d deleted=%d failed=%d`.
6. `EvaluationJobResult(spots=<aantal geëvalueerde spots>, rows=len(rows), deleted, failed=tuple(sorted(load.invalid + evaluatiefouten)), errors=tuple(load.errors + evaluatiefoutregels))`.

Niet-geverifieerde spots worden gewoon geëvalueerd (A1). De alertjob leest `evaluations` niet: die evalueert per regel opnieuw met de grenzen van de gebruiker (WP-07 A11).

### Alertjob (`shakka.jobs.alerts`)
Drie stappen per favoriet, bewust gescheiden zodat WP-17 de aflevering tussen 2 en 3 kan zetten:
1. **Laden** (`load_alert_context`, alle databasereads van de run vooraf);
2. **Plannen** (`plan_favorite`, geen I/O: regel, evaluatie, windows, diff, berichten renderen);
3. **Opslaan** (`store_plan`, alleen schrijfacties op `alert_state`).

**`load_alert_context(db, *, now, user_id=None)`** (alleen `select`):
1. `favorites = db.select("favorites", columns="user_id,spot_id", order="user_id,spot_id")`, met `filters={"user_id": f"eq.{user_id}"}` als `user_id` gegeven is.
2. Geen favorieten → lege context zonder verdere queries.
3. `rules`: `db.select("alert_rules", columns=RULE_COLUMNS)` (zelfde `user_id`-filter), per `(user_id, spot_id)`.
4. `profiles`: `db.select("profiles", columns=PROFILE_COLUMNS, filters={"user_id": in_filter(sorted(user_ids))})`, per `user_id`. Een gebruiker zonder profielrij krijgt `None`.
5. `state`: twee selects op `alert_state` met `columns=STATE_COLUMNS` (zelfde `user_id`-filter): `{"status": "eq.active"}` en `{"status": "eq.cancelled", "window_end": f"gt.{iso_utc(now)}"}`, gegroepeerd per `(user_id, spot_id)` in de volgorde van de select (standaard op `id`). Dit is de laadregel van WP-08 "Gevolgen": alle actieve rijen, plus geannuleerde rijen die nog niet voorbij zijn; `expired`-rijen niet.

Overal expliciete kolomlijsten in plaats van `*`: PostgREST geeft altijd alle kolommen, maar `FakeSupabase` bewaart alleen de kolommen die geschreven zijn (plus een paar defaults). Met een projectie vult de fake ontbrekende kolommen met `None`, net als de database voor nullable kolommen zonder default. Zo werken `AlertRuleOverride.from_row` en `AlertStateEntry.from_row` (die alle kolommen eisen) ook op rijen die de beheer-CLI met een deel van de kolommen heeft aangemaakt.
6. `inputs = load_inputs(db, now=now, spot_ids={f.spot_id for f in favorites})`.
7. `AlertContext(favorites=[FavoriteRows(...)], inputs)`, waarbij elke `FavoriteRows` zijn eigen profielrij, regelrij (of `None`) en staterijen krijgt.

**`plan_favorite(fav, inputs, *, now, base_url)`** (geen I/O; `base_url` al genormaliseerd, A12):
1. `inputs is None` → `ineligible`, detail `"spot not loaded (unknown, invalid or without coordinates)"`.
2. `not inputs.spot.verified` → `ineligible`, detail `"spot not verified"` (A1).
3. In één `try ... except ValueError` (A8):
   - `profile = ProfileDefaults.from_row(fav.profile_row)` of `None`;
   - `override = AlertRuleOverride.from_row(fav.rule_row)` of `None`;
   - `rule = resolve_rule(spot, profile, override)`;
   - `rider = rider_from_profile(fav.profile_row)`;
   - `previous = [AlertStateEntry.from_row(r) for r in fav.state_rows]`;
   - `rule.enabled is False` → `disabled` (met `rule`; A3);
   - `not inputs.forecasts` → `ineligible`, detail `"no forecast data"` (A4);
   - `evaluations = evaluate_spot(spot, inputs.forecasts, inputs.tides, rider_limits(rule))`;
   - `windows = find_windows(evaluations, rule, now=now)`;
   - `diff = diff_windows(previous, windows, now=now)` (dezelfde `now`, WP-08 "Gevolgen");
   - per event in `diff.events` (al gesorteerd op `state_index`):
     - `kind != cancelled` en `rider is not None`: `w = window_for(event, windows)` (het window met `start == event.current.start` en `end == event.current.end`; niet gevonden → `ValueError`) en `kite = recommend_for_window(rider, [h.wind_kn for h in w.hours if h.wind_kn is not None])`;
     - anders `kite = None` (bij `cancelled` negeert `render_alert` hem toch, WP-08 A10);
     - `message = render_alert(event, spot, kite=kite, tides=inputs.tides, base_url=base_url)`.
   - Bij `ValueError`: `skipped`, detail `f"{type(exc).__name__}: {_short(exc)}"`.
4. Anders `planned`, met `rule`, `windows`, `previous`, `diff` en `messages = ((event.state_index, message), ...)`.

`rider_from_profile(row)`: `None` als `row is None`, `row["weight_kg"] is None` of `row["level"] is None` (WP-06 "Contract richting WP-10"); anders `RiderProfile(weight_kg=row["weight_kg"], level=row["level"], quiver_m2=row.get("quiver_m2") or [])`. Een lege quiver mag; `recommend_for_window` geeft dan `None`.

**`store_plan(db, user_id, plan) -> list[str | None]`** (alleen voor `planned`; geeft per index van `new_state` de `id` terug):
1. `ids = [e.id for e in plan.diff.new_state]`; `n = len(plan.previous)`.
2. **Updates eerst** (WP-08 "Gevolgen", bindend): `changed = [i for i in range(n) if new_state[i] != previous[i]]`, gesorteerd op `(update_rank(previous[i], new_state[i]), i)`:
   - rang 0: de nieuwe status is `expired` of `cancelled`;
   - rang 1: de nieuwe status is `active` en de nieuwe span ligt binnen de oude (`new.window_start >= old.window_start` en `new.window_end <= old.window_end`), dus korter of gelijk;
   - rang 2: al het andere (langer, verschoven of heractiveerd).

   Per update: `row = new_state[i].to_row()` zonder `id`; `count = db.update("alert_state", row, filters={"id": f"eq.{previous[i].id}", "user_id": f"eq.{user_id}"})`. `count != 1` → `DatabaseError(f"update alert_state: expected 1 row, got {count}")`.
3. **Daarna de inserts**, voor `i` van `n` tot `len(new_state)` op volgorde: `stored = db.insert("alert_state", [new_state[i].to_row() | {"user_id": user_id}], returning=True)`; `ids[i] = str(stored[0]["id"])`.
4. Zijn er geen updates en geen inserts, dan geen enkele schrijfactie.

Een `DatabaseError` in stap 2 of 3 gaat naar de aanroeper; de resterende schrijfacties van deze favoriet worden dus niet meer gedaan.

**`run_alerts(db, *, now, base_url, dry_run=False)`**:
1. `now` naïef → `ValueError`. `base = normalize_base_url(base_url)` (A12; `ValueError` bij een ongeldige waarde).
2. `ctx = load_alert_context(db, now=now)`.
3. Per favoriet (op volgorde van `(user_id, spot_id)`):
   - `plan = plan_favorite(fav, ctx.inputs.get(fav.spot_id), now=now, base_url=base)`;
   - tellers bijwerken; bij `skipped`: foutregel `f"spot {spot_id}: {detail}"` en log `alerts: skipped a favorite (%s)` met alleen het exceptietype;
   - niet `planned` → volgende favoriet;
   - `dry_run`: `ids = [e.id for e in plan.diff.new_state]` (nieuwe entries hebben dan `None`);
   - anders: `ids = store_plan(db, fav.user_id, plan)`; bij `DatabaseError`: `write_errors += 1`, foutregel `f"spot {spot_id}: DatabaseError (HTTP {exc.status}, code {exc.code})"`, log `alerts: storing alert state failed for a favorite (DatabaseError)`, en door naar de volgende favoriet zonder berichten (A11);
   - per `(index, message)` in `plan.messages`: `RenderedAlert(user_id=fav.user_id, state_id=ids[index], message=message)`.
4. Niet bij `dry_run`: `deleted = db.delete("alert_state", filters={"window_end": f"lt.{iso_utc(now - ALERT_STATE_RETENTION)}"})`.
5. Eén logregel op `INFO` (alleen aantallen, A9):
   `alerts: users=%d favorites=%d events=%d new=%d improved=%d worsened=%d cancelled=%d ineligible=%d disabled=%d skipped=%d write_errors=%d deleted=%d dry_run=%s`.
6. `AlertJobResult(users=<aantal verschillende user_id's in favorites>, events=len(messages), messages, favorites, ineligible, disabled, skipped, write_errors, deleted, errors)`.

`run_alerts` schrijft nooit naar stdout of stderr. In M1 schuift de state na elk event altijd door (geen aflevering die kan falen); de afleverregel komt in WP-17.

`normalize_base_url(value)`: `None` of leeg na `strip()` → `None`; anders `base = value.strip()` en `build_go_url(base, "probe", PROBE_START, PROBE_START + 1 h)` met `PROBE_START = datetime(2026, 1, 1, tzinfo=UTC)`. Een `ValueError` daaruit wordt `ValueError("invalid APP_BASE_URL: expected http(s)://host[/path] without query, fragment or spaces")`. Geeft `base` terug.

### Beheer (`shakka.jobs.admin`)
Bewerkingen op de database die bij een gebruikersfout `AdminError(message)` geven (exitcode 1 in de CLI). Validatie gebeurt vóór elke schrijfactie, met dezelfde grenzen als de DB-CHECKs (WP-01 "Gevolgen": eerst valideren, anders faalt pas de database).

- **`set_profile`**: minstens één veld, anders `AdminError("nothing to change")`. Valideer per veld: `weight_kg` binnen `WEIGHT_RANGE_KG`; `level` een `Level`; quiver via `parse_quiver`; `min_kn`/`max_kn` binnen `ALERT_KN_RANGE`. Lees de huidige rij (`select profiles`, `user_id=eq`); geen rij → `AdminError("no profile for this user id; create the user in Supabase Authentication first")`. Combineer `default_min_kn`/`default_max_kn` met de opgeslagen waarden en valideer met `ProfileDefaults(...)` (`ValueError` → `AdminError(f"invalid profile: {_short(exc)}")`). Daarna `db.update("profiles", <alleen de opgegeven kolommen>, filters={"user_id": eq})`; `count != 1` → `AdminError("profile not updated")`. Geeft de nieuwe rij terug (opnieuw gelezen).
- **`get_profile`**: de rij, of `AdminError` zoals hierboven.
- **`add_favorite`**: `spot_id` moet aan `SPOT_ID_PATTERN` voldoen en in `spots` staan, anders `AdminError(f"unknown spot '{spot_id}'")`. Bestaat de favoriet al, dan `added=False` (geen schrijfactie). Anders `db.insert("favorites", [{"user_id", "spot_id"}])`; een `DatabaseError` met `code == "23503"` (FK) → `AdminError("unknown user id (no Supabase auth user with this id)")`. Geeft `FavoriteAdded(added, verified)`.
- **`remove_favorite`**: `db.delete("favorites", filters={"user_id": eq, "spot_id": eq})`; geeft `count > 0`. De database verwijdert de bijbehorende `alert_rules`-rij via de cascade (WP-01 AC-2 h).
- **`list_favorites`**: favorieten van de gebruiker (op `spot_id`), met naam en `verified` uit `spots` (`id=in.(...)`) en of er een `alert_rules`-rij is.
- **`set_rule`**: minstens één veld, anders `AdminError("nothing to change")`. De favoriet moet bestaan, anders `AdminError(f"{spot_id} is not a favorite of this user; run 'shakka admin favorite add' first")`. Parse en valideer de opties (zie Interfaces). Combineer met de bestaande regelrij (gelezen met `columns=RULE_COLUMNS`; geen rij → alle `RULE_FIELDS` `None`), valideer met `AlertRuleOverride.from_row(merged)`, en daarna met `resolve_rule(SpotProfile.from_row(spot_row), ProfileDefaults.from_row(profile_row) of None, override)`; elke `ValueError` → `AdminError(f"invalid rule: {_short(exc)}")`. Schrijf: bestaat de rij, dan `db.update("alert_rules", <opgegeven kolommen>, filters={user_id, spot_id})`, anders `db.insert("alert_rules", [{user_id, spot_id, **opgegeven kolommen}])`. Geeft de effectieve `AlertRule` terug.
- **`preview_alerts`**: `load_alert_context(db, now=now, user_id=user_id)` en per favoriet `plan_favorite(...)` met `normalize_base_url(base_url)`. Nooit `store_plan`, nooit een schrijfactie (AC-8).
- **`run_admin(label, action, *, echo)`**: laadt `get_settings()` (`ValidationError` → `"admin: configuration incomplete; run shakka doctor"`, exit 1), opent de database via `runtime.open_db`, roept `action(db, now, settings)` aan met `now = runtime.utcnow()`, echoot de teruggegeven regels (exit 0). `AdminError` → `f"{label}: {message}"`, exit 1. `DatabaseError` → `f"{label}: database error: {exc}"`, exit 1. `ValueError` uit `normalize_base_url` → `f"{label}: invalid APP_BASE_URL"`, exit 1. De database wordt altijd gesloten.

### CLI
`shakka evaluate`, `shakka alerts run [--dry-run]` en de groep `shakka admin` (exacte uitvoer onder Interfaces). Alle runners gebruiken `runtime.open_db(settings)` en `runtime.utcnow()` en sluiten de database in een `finally`. Tests vervangen die twee functies met `monkeypatch.setattr(shakka.jobs.runtime, ...)`; daarom roepen de modules ze aan als `runtime.open_db(...)`, nooit via `from shakka.jobs.runtime import open_db`.

`shakka alerts run` toont berichtteksten. Dat is bedoeld voor lokaal gebruik; de uurlijkse workflow (WP-11) roept `run_alerts` aan, niet deze CLI, zodat er geen berichten in de openbare Actions-logs komen (RUNBOOK).

### Env-contract (A-16)
- `Settings` verliest `telegram_bot_token` en `telegram_chat_id`. `extra="ignore"` blijft, dus een `.env` met `TELEGRAM_*` laadt zonder fout.
- `.env.example` verliest `TELEGRAM_BOT_TOKEN` en `TELEGRAM_CHAT_ID`.
- `shakka doctor` noemt al geen Telegram-variabelen (`doctor.py` gebruikt alleen `REQUIRED_ENV_VARS` en de publishable key); geen codewijziging, wel een test.
- RUNBOOK §4: de twee `TELEGRAM_*`-rijen weg.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/config.py` | wijzigen | Velden `telegram_bot_token` en `telegram_chat_id` weg. Verder niets. |
| `.env.example` | wijzigen | Regels `TELEGRAM_BOT_TOKEN=` en `TELEGRAM_CHAT_ID=` weg. Commentaarregels blijven. |
| `ingest/src/shakka/jobs/runtime.py` | aanmaken | `open_db(settings) -> SupabaseRest` (`SupabaseRest.from_settings`) en `utcnow() -> datetime` (`datetime.now(UTC)`). |
| `ingest/src/shakka/jobs/inputs.py` | aanmaken | Constanten, `SpotInputs`, `InputsLoad`, `load_inputs_checked`, `load_inputs`, helpers `floor_hour`, `short_error`. |
| `ingest/src/shakka/jobs/evaluate.py` | aanmaken | `EvaluationJobResult`, `run_evaluation`, `run_evaluate_cli`. |
| `ingest/src/shakka/jobs/alerts.py` | aanmaken | `RenderedAlert`, `AlertJobResult`, `FavoriteRows`, `AlertContext`, `FavoritePlan`, `normalize_base_url`, `rider_from_profile`, `window_for`, `load_alert_context`, `plan_favorite`, `update_rank`, `store_plan`, `delete_old_alert_state`, `run_alerts`, `format_rule`, `run_alerts_cli`. |
| `ingest/src/shakka/jobs/admin.py` | aanmaken | `AdminError`, parsers, `set_profile`, `get_profile`, `add_favorite`, `remove_favorite`, `list_favorites`, `set_rule`, `preview_alerts`, formatters voor de uitvoer, `run_admin`. |
| `ingest/src/shakka/cli.py` | wijzigen | Commando `evaluate`; groep `alerts` met `run`; groep `admin` met subgroepen `profile` (`set`, `show`), `favorite` (`add`, `remove`, `list`), `rule` (`set`) en `alerts` (`preview`). Bestaande commando's ongewijzigd. |
| `docs/RUNBOOK.md` | wijzigen | §4: `TELEGRAM_*`-rijen weg. Nieuwe §12 "Alerts in M1" (zie Stappenplan stap 7). |
| `ingest/tests/job_fixtures.py` | aanmaken | Seed-helpers en het vaste scenario (zie Testplan). |
| `ingest/tests/test_job_inputs.py` | aanmaken | Laden, bereiken, verouderde rijen, foutisolatie. |
| `ingest/tests/test_job_evaluate.py` | aanmaken | AC-1. |
| `ingest/tests/test_job_alerts.py` | aanmaken | AC-2, AC-4 t/m AC-7, schrijfvolgorde, foutisolatie, dry run. |
| `ingest/tests/test_cli_jobs.py` | aanmaken | `shakka evaluate` en `shakka alerts run` (incl. AC-8 voor `--dry-run`). |
| `ingest/tests/test_admin.py` | aanmaken | AC-9, AC-8 voor `admin alerts preview`, overige beheercommando's. |
| `ingest/tests/test_config.py` | wijzigen | Telegram-asserts in `test_defaults` weg; `test_secrets_not_in_repr` gebruikt `VAPID_PRIVATE_KEY=TESTVAPIDPRIV`; nieuwe tests `test_no_telegram_fields` en `test_old_telegram_env_is_ignored` (AC-10). |
| `ingest/tests/test_cli.py` | wijzigen | `test_doctor_partial_env_does_not_leak_values` gebruikt `vapid_private_key="TESTVAPIDPRIV"` in plaats van `telegram_bot_token`, en controleert dat `TESTVAPIDPRIV` niet in de uitvoer staat. Nieuwe test `test_doctor_never_mentions_telegram`. |
| `ingest/tests/test_repo_hygiene.py` | wijzigen | `ENV_KEYS` zonder de twee `TELEGRAM_*`; nieuwe test `test_no_telegram_in_ingest_src_and_env_example` (AC-3). |

Geen migraties, geen wijziging aan `shakka.domain`, `shakka.db`, `tests/fakes.py`, `pyproject.toml` of `uv.lock`. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### `shakka.jobs.runtime`
```python
def open_db(settings: Settings) -> SupabaseRest: ...   # SupabaseRest.from_settings(settings)
def utcnow() -> datetime: ...                           # datetime.now(UTC)
```

### `shakka.jobs.inputs`
```python
FORECAST_LOOKBACK: Final = timedelta(hours=1)
FORECAST_HORIZON: Final = timedelta(days=8)
TIDE_MARGIN: Final = timedelta(hours=12)
STALE_FETCH_AGE: Final = timedelta(hours=3)
FORECAST_COLUMNS: Final = "spot_id,model,valid_at,wind_kn,gust_kn,dir_deg,fetched_at"
TIDE_COLUMNS: Final = "station,at,kind,level_cm"

@dataclass(frozen=True, slots=True)
class SpotInputs:
    spot: SpotProfile
    forecasts: list[ForecastHour]   # sorted by (valid_at, model), stale rows removed (A5)
    tides: list[TideExtreme]        # only spot.rws_station.strip(), sorted by at

@dataclass(frozen=True, slots=True)
class InputsLoad:
    inputs: dict[str, SpotInputs]   # by spot id, in id order
    invalid: list[str]              # spot ids skipped because of a ValueError, sorted
    without_coords: list[str]       # sorted
    errors: list[str]               # "spot <id>: <ExcType>: <short message>"

def floor_hour(value: datetime) -> datetime: ...        # aware -> UTC, minutes/seconds zeroed
def short_error(exc: BaseException) -> str: ...         # " ".join(str(exc).split())[:200]
def load_inputs_checked(db: SupabaseRest, *, now: datetime,
                        spot_ids: Collection[str] | None = None) -> InputsLoad: ...
def load_inputs(db: SupabaseRest, *, now: datetime,
                spot_ids: Collection[str] | None = None) -> dict[str, SpotInputs]: ...
```
`db` is getypeerd als `SupabaseRest`; `FakeSupabase` heeft dezelfde methoden (zelfde patroon als `jobs.forecast`). Naïeve `now` → `ValueError`. `DatabaseError` gaat door naar de aanroeper.

### `shakka.jobs.evaluate`
```python
EVALUATION_RETENTION: Final = timedelta(hours=48)
EVALUATIONS_ON_CONFLICT: Final = "spot_id,valid_at"

@dataclass(frozen=True, slots=True)
class EvaluationJobResult:
    spots: int                      # spots evaluated (with coordinates, valid)
    rows: int                       # rows upserted
    deleted: int                    # rows removed (valid_at < now - 48h)
    failed: tuple[str, ...] = ()    # spot ids: invalid rows plus evaluation errors, sorted
    errors: tuple[str, ...] = ()    # one line per failed spot

def run_evaluation(db: SupabaseRest, *, now: datetime) -> EvaluationJobResult: ...
def run_evaluate_cli(*, echo: Callable[[str], None]) -> int: ...
```
CLI-uitvoer van `shakka evaluate`:
```
evaluate: spots=<n> rows=<n> deleted=<n> failed=<n>
error   <regel uit errors>          (per fout)
evaluate: ok | evaluate: failed
```
Exitcode 1 bij `failed` niet leeg, bij een onvolledige config (`evaluate: configuration incomplete; run shakka doctor`) of een databasefout (`evaluate: database error: <exc>`); anders 0.

### `shakka.jobs.alerts`
```python
ALERT_STATE_RETENTION: Final = timedelta(hours=48)
PROFILE_COLUMNS: Final = "user_id,weight_kg,level,quiver_m2,default_min_kn,default_max_kn"
RULE_COLUMNS: Final = "user_id,spot_id," + ",".join(RULE_FIELDS)          # alerts.RULE_FIELDS
STATE_COLUMNS: Final = "user_id," + ",".join(ALERT_STATE_COLUMNS)          # dedup.ALERT_STATE_COLUMNS
PROBE_START: Final = datetime(2026, 1, 1, tzinfo=UTC)
PlanOutcome = Literal["planned", "ineligible", "disabled", "skipped"]

@dataclass(frozen=True, slots=True)
class RenderedAlert:
    user_id: str
    state_id: str | None            # alert_state.id after storing; None in dry_run for new rows
    message: AlertMessage

@dataclass(frozen=True, slots=True)
class AlertJobResult:
    users: int                      # distinct user_ids with at least one favorite
    events: int                     # == len(messages)
    messages: list[RenderedAlert]   # by (user_id, spot_id), then state_index
    favorites: int = 0
    ineligible: int = 0             # spot not loaded, not verified, or no forecast data
    disabled: int = 0
    skipped: int = 0                # ValueError while planning (bad rule/profile/state row)
    write_errors: int = 0
    deleted: int = 0                # alert_state rows removed (window_end < now - 48h)
    errors: tuple[str, ...] = ()    # "spot <id>: ..." -- never a user id (A9)

@dataclass(frozen=True, slots=True)
class FavoriteRows:
    user_id: str
    spot_id: str
    profile_row: dict[str, Any] | None
    rule_row: dict[str, Any] | None
    state_rows: list[dict[str, Any]]

@dataclass(frozen=True, slots=True)
class AlertContext:
    favorites: list[FavoriteRows]   # sorted by (user_id, spot_id)
    inputs: dict[str, SpotInputs]

@dataclass(frozen=True, slots=True)
class FavoritePlan:
    user_id: str
    spot_id: str
    outcome: PlanOutcome
    detail: str | None = None                       # reason for ineligible / skipped
    spot: SpotProfile | None = None
    rule: AlertRule | None = None
    windows: tuple[Window, ...] = ()
    previous: tuple[AlertStateEntry, ...] = ()
    diff: DiffResult | None = None                  # set iff outcome == "planned"
    messages: tuple[tuple[int, AlertMessage], ...] = ()   # (state_index, message)

def normalize_base_url(value: str | None) -> str | None: ...
def rider_from_profile(row: Mapping[str, Any] | None) -> RiderProfile | None: ...
def window_for(event: AlertEvent, windows: Sequence[Window]) -> Window: ...   # ValueError if absent
def load_alert_context(db: SupabaseRest, *, now: datetime,
                       user_id: str | None = None) -> AlertContext: ...
def plan_favorite(fav: FavoriteRows, inputs: SpotInputs | None, *, now: datetime,
                  base_url: str | None) -> FavoritePlan: ...
def update_rank(old: AlertStateEntry, new: AlertStateEntry) -> int: ...       # 0, 1 or 2
def store_plan(db: SupabaseRest, user_id: str, plan: FavoritePlan) -> list[str | None]: ...
def delete_old_alert_state(db: SupabaseRest, *, now: datetime) -> int: ...
def run_alerts(db: SupabaseRest, *, now: datetime, base_url: str | None,
               dry_run: bool = False) -> AlertJobResult: ...
def format_rule(rule: AlertRule) -> str: ...
def run_alerts_cli(*, dry_run: bool, echo: Callable[[str], None]) -> int: ...
```
- `run_alerts` heeft geen parameter met `offshore`, `allow`, `force` of `unsafe` in de naam (getest). WP-17 voegt de keyword-parameter `notifiers` en de velden `sent`, `failed` en `no_target` toe; bestaande aanroepen blijven werken.
- `format_rule(rule)`, exact: `f"min {rule.min_kn:g} kn, max {rule.max_kn:g} kn, dirs {dirs}, days {days}, after {after}, before {before}, min {rule.min_go_hours} h, {rule.days_ahead} days ahead, {'enabled' if rule.enabled else 'disabled'}"`, met `dirs` = de klassen in `DirClass`-declaratievolgorde, kommagescheiden; `days` = de weekdagen oplopend, kommagescheiden; `after`/`before` = `HH:MM` of `-`. Voorbeeld: `min 12 kn, max 30 kn, dirs onshore,side_onshore,sideshore, days 1,2,3,4,5,6,7, after -, before -, min 2 h, 3 days ahead, enabled`.

CLI-uitvoer van `shakka alerts run [--dry-run]`:
```
<kind> <spot_id>: <title>              per bericht, kind = message.kind.value
  <bodyregel>                          per regel van de body, twee spaties ervoor
  link: <go_url>                       alleen als go_url gezet is
alerts: users=<n> favorites=<n> events=<n> (new=<n> improved=<n> worsened=<n> cancelled=<n>) ineligible=<n> disabled=<n> skipped=<n> write_errors=<n> deleted=<n>
alerts: dry run, nothing stored        alleen bij --dry-run
error   <regel uit errors>             per fout
alerts: ok | alerts: failed
```
Geen user-id's in de uitvoer. Exitcode 1 bij `skipped > 0` of `write_errors > 0`, bij een onvolledige config (`alerts: configuration incomplete; run shakka doctor`), bij een databasefout (`alerts: database error: <exc>`) of bij een ongeldige `APP_BASE_URL` (`alerts: invalid APP_BASE_URL`, zonder de waarde); anders 0. `base_url = settings.app_base_url`.

### `shakka.jobs.admin`
```python
class AdminError(Exception): """User-facing error; the CLI prints it and exits with 1."""

@dataclass(frozen=True, slots=True)
class FavoriteAdded:
    added: bool
    verified: bool

@dataclass(frozen=True, slots=True)
class FavoriteInfo:
    spot_id: str
    name: str
    verified: bool
    has_rule: bool

def parse_quiver(text: str) -> list[float]: ...
def parse_dir_classes(text: str) -> list[DirClass]: ...
def parse_weekdays(text: str) -> list[int]: ...
def parse_local_time(text: str) -> time: ...

def set_profile(db, user_id: str, *, weight_kg: int | None = None, level: str | None = None,
                quiver_m2: list[float] | None = None, min_kn: int | None = None,
                max_kn: int | None = None) -> dict[str, Any]: ...
def get_profile(db, user_id: str) -> dict[str, Any]: ...
def add_favorite(db, user_id: str, spot_id: str) -> FavoriteAdded: ...
def remove_favorite(db, user_id: str, spot_id: str) -> bool: ...
def list_favorites(db, user_id: str) -> list[FavoriteInfo]: ...
def set_rule(db, user_id: str, spot_id: str, *, min_kn: int | None = None,
             max_kn: int | None = None, dir_classes: list[DirClass] | None = None,
             weekdays: list[int] | None = None, earliest_local: time | None = None,
             latest_local: time | None = None, min_go_hours: int | None = None,
             days_ahead: int | None = None, enabled: bool | None = None) -> AlertRule: ...
def preview_alerts(db, user_id: str, *, now: datetime,
                   base_url: str | None) -> list[FavoritePlan]: ...
def run_admin(label: str, action: Callable[[SupabaseRest, datetime, Settings], list[str]],
              *, echo: Callable[[str], None]) -> int: ...
```
Parsers (allemaal `AdminError` bij een fout; de CLI-opties zijn gewone `str`/`int`, zodat elke domeinfout exitcode 1 geeft en niet de click-exitcode 2):
- `parse_quiver`: `""` (na `strip()`) → `[]`. Anders splitsen op `,`, elk deel `float(...)` na `strip()`; niet-numeriek, niet-eindig of buiten `QUIVER_SIZE_RANGE_M2` → `AdminError("quiver sizes must be numbers between 3 and 21 m2")`; meer dan `MAX_QUIVER_KITES` delen (vóór ontdubbelen, zoals de DB-CHECK) → `AdminError("at most 10 kites")`. Resultaat gesorteerd en ontdubbeld.
- `parse_dir_classes`: splitsen op `,`, `strip()`, leeg deel of lege lijst → `AdminError("dir classes must not be empty")`. Een waarde in `{"offshore", "side_offshore"}` → `AdminError(f"dir class '{v}' is not allowed: offshore and side_offshore are never ridable; choose from onshore, side_onshore, sideshore")`. Een andere onbekende waarde → `AdminError(f"unknown dir class '{v}'; choose from onshore, side_onshore, sideshore")`. Resultaat ontdubbeld in `DirClass`-declaratievolgorde.
- `parse_weekdays`: gehele getallen 1–7 (ISO, 1 = maandag), niet leeg → anders `AdminError("weekdays must be numbers 1-7 (1 = Monday)")`. Ontdubbeld en oplopend.
- `parse_local_time`: exact `([01][0-9]|2[0-3]):[0-5][0-9]` → `time(h, m)`; anders `AdminError("times must be HH:MM (00:00-23:59)")`.
- Gehele opties in `set_profile`/`set_rule`: `weight_kg` binnen `WEIGHT_RANGE_KG` (30–200), `min_kn`/`max_kn` binnen `ALERT_KN_RANGE` (5–60), `min_go_hours` binnen `MIN_GO_HOURS_RANGE` (1–24), `days_ahead` binnen `DAYS_AHEAD_RANGE` (0–7); anders `AdminError(f"{name} must be between {lo} and {hi}")`.
- `user_id` komt als `uuid.UUID` uit click (`click.UUID`) en wordt `str(value)` (kleine letters, zoals PostgREST het teruggeeft).

Schrijfwaarden: `quiver_m2` als lijst van floats, `dir_classes` als lijst van strings (`DirClass`-volgorde), `weekdays` als oplopende lijst van ints, tijden als `datetime.time` (`shakka.db.to_json` maakt er `"17:00:00"` van), `enabled` als bool.

CLI `shakka admin` (exacte opties; de kolomnaam staat erachter):

| Commando | Opties |
|---|---|
| `profile set` | `--user-id UUID` (verplicht), `--weight INT` (`weight_kg`), `--level [beginner\|intermediate\|advanced]` (`level`), `--quiver TEXT` (`quiver_m2`), `--min-kn INT` (`default_min_kn`), `--max-kn INT` (`default_max_kn`) |
| `profile show` | `--user-id UUID` |
| `favorite add` / `favorite remove` | `--user-id UUID`, `--spot TEXT` (verplicht) |
| `favorite list` | `--user-id UUID` |
| `rule set` | `--user-id UUID`, `--spot TEXT`, `--min-kn INT`, `--max-kn INT`, `--dir-classes TEXT`, `--weekdays TEXT`, `--after HH:MM` (`earliest_local`), `--before HH:MM` (`latest_local`), `--min-go-hours INT`, `--days-ahead INT`, `--enable/--disable` (`enabled`, default `None` = niet wijzigen) |
| `alerts preview` | `--user-id UUID` |

Er is geen optie `--telegram-chat-id` (AC-9: click meldt "No such option", exitcode 2).

Uitvoer (exact, `<...>` ingevuld; `-` voor `NULL`):
- `profile set`: `profile set: saved`, gevolgd door de regels van `profile show`.
- `profile show`:
  ```
  weight_kg: <int|->
  level: <level|->
  quiver_m2: <sizes met :g, kommagescheiden zonder spatie, of ->
  default_min_kn: <int|->
  default_max_kn: <int|->
  ```
  `telegram_chat_id` wordt nooit gelezen of getoond (kolom ongebruikt, A-16); `PROFILE_COLUMNS` noemt hem niet.
- `favorite add`: `favorite add: added <spot>` of `favorite add: <spot> is already a favorite`; bij een niet-geverifieerde spot daarna `note: <spot> is not verified; it is evaluated but gives no alerts until verified: true`.
- `favorite remove`: `favorite remove: removed <spot> (and its alert rule)` of `favorite remove: <spot> was not a favorite` (beide exit 0).
- `favorite list`: per favoriet `<spot_id>\t<name>\t<verified|not verified>\t<own rule|default rule>`, daarna `<n> favorite(s)`.
- `rule set`: `rule set: saved for <spot>`, daarna `rule: <format_rule(effectieve regel)>`.
- `alerts preview`:
  ```
  alerts preview: <n> favorite(s)
  spot <spot_id>                                   (outcome planned)
    rule: <format_rule>
    windows: none | windows: <n>
      <format_window_local(start, end)> · <lo>–<hi> kn      (per window)
    state: <a> active, <c> cancelled (snapshot = last reported)
    <kind>: <title>                                (per bericht)
      <bodyregel>
      link: <go_url>
    no change                                      (als er geen berichten zijn)
  spot <spot_id>: not eligible (<detail>)
  spot <spot_id>: disabled
  spot <spot_id>: skipped (<detail>)
  ```
  `<lo>`/`<hi>` = `math.floor(x + 0.5)` van de laagste en hoogste `wind_kn` in het window; `a` en `c` tellen de geladen staterijen met status `active` en `cancelled`.

### Tabellen en kolommen (WP-01, ongewijzigd)
- Leest: `spots` (`SPOT_COLUMNS`), `forecast_hours` (`FORECAST_COLUMNS`), `tide_extremes` (`TIDE_COLUMNS`), `favorites`, `alert_rules` (`*`), `profiles` (`PROFILE_COLUMNS`), `alert_state` (`*`).
- Schrijft: `evaluations` (upsert `spot_id,valid_at`, delete op `valid_at`), `alert_state` (update op `id` + `user_id`, insert, delete op `window_end`), `profiles` (update), `favorites` (insert, delete), `alert_rules` (update, insert).
- `alert_state.last_notified_at` blijft `NULL` (A2). `profiles.telegram_chat_id` wordt nergens gelezen of geschreven.

### `shakka.config.Settings` na deze WP
`supabase_url`, `supabase_publishable_key`, `supabase_secret_key`, `app_base_url`, `vapid_public_key`, `vapid_private_key`, `vapid_subject`, `spots_path` (contract WP-10).

### Consistentie met afhankelijke WP's
- WP-01: kolomnamen, CHECK-grenzen (via de domeinconstanten), `TABLE_KEYS`; geen upsert met dubbele sleutels.
- WP-02: `SpotProfile.from_row` per spot in een `try`; `verified` (A1).
- WP-03: `ForecastHour.from_row`, horizon, `fetched_at`-filter (A5).
- WP-04: `TideExtreme.from_row`, filter op station en `at`-bereik.
- WP-05: `evaluate_spot` met `default_limits` (evaluatiejob) en `rider_limits(rule)` (alertjob); alleen spots met coördinaten; `to_row(evaluated_at=now)`; klasse nooit uit `dir_deg`.
- WP-06: `RiderProfile` alleen bij `weight_kg` en `level`; `recommend_for_window` met de `wind_kn` van de window-uren.
- WP-07: één `try` per favoriet voor `from_row` en `resolve_rule` (bindend); `find_windows` met dezelfde `now`; `enabled=false` (A3).
- WP-08: laadregel van `alert_state`, `from_row`/`to_row`, `diff_windows` met dezelfde `now`, kite/getij/`base_url` bij `render_alert`, schrijfvolgorde (bindend), `last_notified_at` ongemoeid, renderen en opslaan als aparte stappen.

### Gevolgen voor latere WP's
- **WP-11:**
  - Roep `run_evaluation(db, now=now)` en `run_alerts(db, now=now, base_url=settings.app_base_url)` aan, nooit de CLI-runners (berichtteksten horen niet in de openbare logs).
  - `run_alerts` geeft een `ValueError` bij een ongeldige `APP_BASE_URL` en laat een `DatabaseError` bij het laden door; beide zijn een gefaalde stap. `skipped` en `write_errors` zijn voorstellen voor `partial`; `errors` bevat geen user-id's en mag in `ingest_runs.steps`.
  - Beide jobs laden de inputs zelf (dubbel werk, ongeveer 30 extra GET-requests per run). Wil WP-11 dat besparen, dan kan het een keyword `inputs` toevoegen; dat is hier niet nodig.
- **WP-17:**
  - De aflevering past tussen `plan_favorite` en `store_plan`. De alles-of-niets-regel van WP-08 betekent: niet `store_plan` aanroepen voor die favoriet als de aflevering een niet-permanente fout geeft.
  - Nieuwe entries krijgen hun `id` pas bij de insert. Heeft WP-17 de `id` vóór de aflevering nodig (push-`tag`), dan kent het hem zelf toe (`uuid4`) en zet het hem in `new_state[i].id` vóór `store_plan`; `to_row()` neemt hem dan mee in de insert.
  - `last_notified_at` vullen gebeurt in `store_plan` (of een variant) na een geslaagde aflevering.
  - AC-3 van WP-10 (`shakka.notify` niet in `shakka/jobs`) is een momentopname van M1, geen permanente test.
- **WP-14:** `evaluations` bevat ook niet-geverifieerde spots; rijen ouder dan 48 uur verdwijnen.
- **WP-16:** de validatie van de beheer-CLI (bereiken, `dir_classes` alleen rijdbaar, conflict tussen niveaus via `resolve_rule`) is wat de UI ook moet doen.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | Spot zonder `lat`/`lon` | Niet in `inputs`, wel in `without_coords`; geen forecast- of getijquery; geen evaluaties. |
| E2 | Spotrij die `SpotProfile.from_row` niet doorstaat | Die spot in `invalid` plus foutregel; andere spots gaan door. `shakka evaluate` exit 1. |
| E3 | Forecastrijen buiten `[floor_hour(now) - 1 h, now + 8 d)` | Niet geladen. |
| E4 | Verouderde rij (`fetched_at` meer dan 3 uur ouder dan de nieuwste van de spot) | Weggelaten (A5); precies 3 uur ouder blijft. |
| E5 | Getij van een ander station of buiten het bereik | Niet geladen. Twee spots met hetzelfde station: één query. |
| E6 | Getijgevoelige spot zonder `rws_station` | `tides = []`; de evaluatie geeft `tide_unknown` (WP-05). |
| E7 | Geen favorieten | Alleen de select op `favorites` (plus de opruim-delete als het geen dry run is); resultaat met nullen. |
| E8 | Favoriet op een niet-geverifieerde spot | `ineligible`; geen evaluatie, geen schrijfacties (A1). |
| E9 | Favoriet op een spot die niet geladen is (ongeldige rij) | `ineligible` ("spot not loaded ..."). |
| E10 | Geverifieerde spot zonder forecastrijen, met een toekomstige actieve entry | `ineligible` ("no forecast data"); de entry blijft `active` (A4). |
| E11 | Regel met `enabled = false` en een actieve entry | `disabled`; geen events, geen update (A3). |
| E12 | Conflict tussen niveaus (regel `min_kn 25`, profiel `default_max_kn 20`) | `ValueError` in `resolve_rule` → `skipped`, andere favorieten gaan door. |
| E13 | `earliest_local = "24:00:00"` in de database | `ValidationError` → `skipped` (WP-07 E37). |
| E14 | Kapotte `alert_state`-rij (bijv. `snapshot` zonder `dir_class`) | `ValueError` in `from_row` → `skipped`; voor die favoriet wordt niets geschreven. |
| E15 | Profielrij ontbreekt | `profile = None`, `rider = None`; regel uit regel/spot/systeem; geen kite-regel. |
| E16 | Profiel zonder `weight_kg` of `level`, of met lege quiver | Geen kite-regel. |
| E17 | Tweede run met dezelfde data | 0 events; geen update of insert op `alert_state` (alleen de opruim-delete). |
| E18 | Window splitst (10–16 wordt 10–13 en 14–16) | Eerst de update (`worsened`), dan de insert (`new`). |
| E19 | Twee entries smelten samen | Eerst de update naar `expired` (rang 0), dan de entry die langer wordt (rang 2). |
| E20 | `update` raakt 0 rijen (rij intussen verwijderd) | `DatabaseError` → `write_errors`; resterende schrijfacties van die favoriet niet; geen berichten van die favoriet. |
| E21 | Insert faalt voor één gebruiker | Zijn updates zijn al gedaan, de insert niet; `write_errors = 1`; de andere gebruiker wordt normaal verwerkt. De volgende run herstelt (WP-08 A15). |
| E22 | `APP_BASE_URL` leeg of alleen spaties | `base_url = None`, geen link, geen fout. |
| E23 | `APP_BASE_URL` ongeldig (`example.org`) | `ValueError` vóór elke databaseactie; CLI `alerts: invalid APP_BASE_URL`, exit 1. |
| E24 | `--dry-run` | Geen enkele schrijfactie (ook geen opruimen); `state_id` is de bestaande id, of `None` voor een nieuwe entry. |
| E25 | Offshore of side-offshore in elk uur | Elk uur `no_go` → geen windows → 0 events, geen rijen (AC-6). |
| E26 | Naïeve `now` | `ValueError` in elke jobfunctie. |
| E27 | Actieve `alert_state`-rij van een verwijderde favoriet | Genegeerd; na 48 uur voorbij `window_end` opgeruimd (A15). |
| E28 | `admin rule set --dir-classes offshore` of `side_offshore` | Exit 1 met "never ridable"; geen schrijfactie. |
| E29 | `admin rule set` voor een spot die geen favoriet is | Exit 1; geen schrijfactie. |
| E30 | `admin rule set --after 18:00 --before 17:00` (of combinatie met een opgeslagen waarde) | Exit 1 ("invalid rule: ..."). |
| E31 | `admin rule set --disable` op een bestaande regel | Alleen `enabled` wijzigt; andere kolommen blijven. |
| E32 | `admin profile set --min-kn 25` terwijl `default_max_kn = 20` is opgeslagen | Exit 1 ("invalid profile: ..."); geen schrijfactie. |
| E33 | `admin profile set` voor een user-id zonder profielrij | Exit 1. |
| E34 | `admin favorite add` met een onbekende user-id (FK) | Exit 1 "unknown user id ...". |
| E35 | `admin favorite add` twee keer | Tweede keer "is already a favorite", exit 0, geen schrijfactie. |
| E36 | `admin profile set --quiver ""` | `quiver_m2 = []`. `--quiver 12,9,9` → `[9.0, 12.0]`. `--quiver 2,9` → exit 1. |
| E37 | `admin ... --user-id geen-uuid` | Click weigert (exit 2). |

## Testplan
Tests eerst. Geen netwerk, geen klok: `now` is altijd een expliciete aware datetime; CLI-tests vervangen `runtime.open_db` en `runtime.utcnow`. Ruff `DTZ` staat aan. Alle databasetests gebruiken `FakeSupabase` (`tests/fakes.py`). Kalender: 2026-07-15 is een woensdag (CEST, UTC+2).

### Fixtures (`ingest/tests/job_fixtures.py`)
```python
NOW = datetime(2026, 7, 15, 6, 17, tzinfo=UTC)          # 08:17 local
FETCHED = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)
USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
USER_C = "33333333-3333-4333-8333-333333333333"
SPOT = "test-strand"
MODELS3 = (ModelKey.KNMI, ModelKey.ICON, ModelKey.ECMWF)
# Scenario winds (kn) per UTC hour on 2026-07-15; gust = wind + 4, dir 270.
WINDS = {8: 6.0, 9: 6.0, 10: 14.0, 11: 18.0, 12: 24.0, 13: 25.0, 14: 24.0, 15: 18.0, 16: 6.0}

def at(h: int) -> datetime: ...                           # 2026-07-15 h:00Z
def seed_spot(db, **overrides) -> SpotProfile: ...        # make_spot(**overrides); db.seed("spots", [spot.to_row()])
def seed_forecasts(db, spot_id=SPOT, winds=WINDS, *, dir_deg=270, models=MODELS3,
                   fetched_at=FETCHED, gust_delta=4.0) -> None: ...
    # one row per model and hour: wind, gust = wind + gust_delta, dir_deg; stored with
    # db.upsert(..., on_conflict="spot_id,model,valid_at") so a second call replaces the
    # forecast between runs. Tests call db.writes.clear() after seeding.
def seed_profile(db, user_id, **cols) -> None: ...        # db.seed("profiles", [{user_id, **cols}])
def seed_favorite(db, user_id, spot_id=SPOT, **rule) -> None:
    # db.seed favorites row; if rule kwargs: alert_rules row with all nine RULE_FIELDS
    # (None unless given)
def alert_rows(db) -> list[dict]: ...                     # db.rows("alert_state")
```
`seed_spot` gebruikt `evaluation_fixtures.make_spot` (coördinaten 52,47 / 4,57 zijn testdata). Standaard in de alerttests: `seed_spot(db, verified=True)`.

Verwachte uitkomst van het scenario (gecontroleerd met de drempels in `defaults.py`: `WIND_BORDERLINE_KN = 2`, `GUST_MIN_DELTA_KN = 8`, dus vlaag +4 geeft geen vlaagreden; drie gelijke modellen):
- gebruiker A met regel `min_kn = 12` (afgeleide `max_kn` 30): go-uren 10–15Z → window `[10:00Z, 16:00Z)`, wind 14–25, vlagen tot 29; eerste bodyregel `wo 15 jul 12:00–18:00 · 14–25 kn, vlagen tot 29 kn`, titel `Go: Teststrand`;
- gebruiker B met regel `min_kn = 20`: 14 en 18 te licht, 24/25/24 go (boven 20 + 2) → window `[12:00Z, 15:00Z)`; eerste bodyregel `wo 15 jul 14:00–17:00 · 24–25 kn, vlagen tot 29 kn`;
- kite voor A met profiel `weight_kg 75`, `level intermediate`, `quiver_m2 [9.0, 12.0]`: `median_high([14, 18, 24, 25, 24, 18]) = 24`, ideaal `2,2 × 75 / 24 = 6,875 → 6,9`, keuze 9 (grens √108 ≈ 10,4), 9 > 6,9 × 1,25 → overpowered: regel `Kite: 9 m² (aan de grote kant, ideaal 6,9 m²)`.

### `tests/test_job_inputs.py`
- `test_loads_spot_with_coords_only` (E1): twee spots, één zonder coördinaten → `inputs` heeft alleen de eerste; `without_coords == ["zonder-coords"]`; geen `forecast_hours`-select voor de tweede (subklasse van `FakeSupabase` die selects vastlegt).
- `test_forecast_range` (E3): rijen op `floor_hour(NOW) - 2 h`, `- 1 h`, `NOW + 8 d - 1 h` (heel uur) en `+ 8 d + 1 h` → alleen de middelste twee geladen.
- `test_stale_rows_dropped` (E4): model knmi met `fetched_at = FETCHED - 4 h` voor een uur dat de andere modellen ook hebben (`FETCHED`), plus een rij met `FETCHED - 3 h` → de rij van 4 uur oud valt weg, die van precies 3 uur blijft.
- `test_tides_per_station_and_range` (E5): station `teststation` met extremen binnen en buiten `[floor_hour(NOW) - 13 h, NOW + 8 d + 12 h]`, plus een extreem van `anderstation` → alleen de extremen van het station binnen het bereik, gesorteerd; twee spots met hetzelfde station → één `tide_extremes`-select.
- `test_invalid_spot_isolated` (E2): een spotrij met `lat = 10.0` (buiten NL, DB staat het toe) en een geldige spot → geldige spot geladen, `invalid == [id]`, één foutregel die met `spot <id>: ValidationError` begint.
- `test_spot_ids_filter`: `spot_ids={"a"}` laadt alleen spot `a`; `spot_ids=set()` doet geen enkele select.
- `test_naive_now`: `ValueError`.

### AC-1: `tests/test_job_evaluate.py`
- `test_evaluates_only_spots_with_coords` (AC-1): spot `test-strand` met `rws_station="teststation"` (`tide_sensitive` none) en spot `zonder-coords` zonder coördinaten; forecasts van 3 modellen voor 08–16Z voor beide spots; getij `teststation`: 07:00Z low −80, 13:15Z high 110, 19:30Z low −70. Na `run_evaluation(db, now=NOW)`:
  - alle rijen met `evaluated_at == NOW` hebben `spot_id == "test-strand"`;
  - hun `valid_at`'s zijn exact de 9 uren 08–16Z, elk één keer;
  - `tide_level_cm` is gezet voor het uur 12Z;
  - `result == EvaluationJobResult(spots=1, rows=9, deleted=0)`.
- `test_old_rows_deleted` (AC-1): vooraf `evaluations`-rijen op `NOW - 49 h` en `NOW - 47 h` (via `HourEvaluation(...).to_row(evaluated_at=...)`) → de eerste is weg, de tweede staat er nog; `deleted == 1`.
- `test_unverified_spot_is_evaluated` (A1): `verified=False` → evaluaties worden opgeslagen.
- `test_upsert_is_idempotent`: twee runs → nog steeds 9 rijen voor de uren 08–16Z.
- `test_invalid_spot_reported` (E2): ongeldige spotrij → `failed == ("<id>",)`, de geldige spot wordt geëvalueerd.
- `test_naive_now`: `ValueError`.

### AC-2, AC-4 t/m AC-7: `tests/test_job_alerts.py`
- **AC-2** `test_end_to_end_new_repeat_cancel`: verified spot, scenario-forecasts, `seed_favorite(db, USER_A, min_kn=12)`.
  1. `r1 = run_alerts(db, now=NOW, base_url=None)` → `len(r1.messages) == 1`, `m = r1.messages[0]`, `m.message.kind == "new"`, `"Teststrand" in m.message.title`, `m.user_id == USER_A`; één `alert_state`-rij met `status == "active"`, `last_event == "new"`, `last_notified_at is None`, `user_id == USER_A`; `m.state_id == rows[0]["id"]`. Eerste bodyregel exact `wo 15 jul 12:00–18:00 · 14–25 kn, vlagen tot 29 kn`.
  2. `before = alert_rows(db)`; `db.writes.clear()`; `r2 = run_alerts(db, now=NOW, base_url=None)` → `r2.messages == []`, `alert_rows(db) == before`, en `db.writes` bevat voor `alert_state` alleen `("delete", "alert_state")`.
  3. Forecasts overschrijven met wind 6 kn voor elk uur (`fetched_at = FETCHED + 10 min`, via `upsert`) en `r3 = run_alerts(db, now=NOW, base_url=None)` → één bericht met `kind == "cancelled"` en titel `Gaat niet door: Teststrand`; de rij heeft `status == "cancelled"` en `last_event == "cancelled"`; `r3.messages[0].state_id` is dezelfde id.
- **AC-5** `test_users_get_different_windows`: gebruikers A (`min_kn=12`) en B (`min_kn=20`) op dezelfde spot en data → twee rijen; A heeft `window_start/end` 10:00Z/16:00Z, B 12:00Z/15:00Z; de eerste bodyregels zijn zoals onder Fixtures.
- **AC-6** `test_offshore_never_alerts`, geparametriseerd over `dir_deg` 90 (offshore) en 135 (side-offshore), elk met vier regels: zonder regelrij, `dir_classes=["sideshore"]`, `min_kn=5`, en `min_go_hours=1, days_ahead=7` → 0 berichten en 0 `alert_state`-rijen.
- **AC-7** `test_unverified_spot_gives_no_alerts`: `verified=False` → 0 berichten, 0 rijen, `ineligible == 1`; dezelfde opzet met `verified=True` geeft 1 bericht.
- **AC-4** `test_logs_contain_no_user_ids_or_bodies(caplog, capsys)`: `caplog.set_level(logging.DEBUG)`; A en B als favoriet, plus een tweede spot `tweede-strand` (verified, dezelfde forecasts) als favoriet van A met regel `earliest_local="24:00:00"` (wordt `skipped`), en een `FakeSupabase`-subklasse die `insert` op `alert_state` weigert met `DatabaseError("insert alert_state: HTTP 409 23503: Key (user_id)=(22222222-...) is not present", status=409, code="23503")` als de rij `user_id == USER_B` heeft. Na `run_alerts`:
  - `USER_A` en `USER_B` komen niet voor in `caplog.text` en niet in `capsys.readouterr()` (out en err leeg);
  - geen enkele bodyregel van de berichten (`for line in m.message.body.splitlines()`) komt voor in `caplog.text`;
  - geen user-id in `"\n".join(result.errors)`;
  - `result.skipped == 1`, `result.write_errors == 1`, en de samenvattingsregel (`alerts: users=2 ...`) staat in `caplog.text`.
- `test_kite_line_from_profile`: profiel A zoals onder Fixtures → body bevat `Kite: 9 m² (aan de grote kant, ideaal 6,9 m²)`; zonder `weight_kg` geen regel die met `Kite:` begint (E16).
- `test_go_url`: `base_url="https://example.org"` → `go_url == "https://example.org/go?spot=test-strand&start=2026-07-15T10%3A00%3A00Z&end=2026-07-15T16%3A00%3A00Z"`; `base_url="  "` → `None` (E22).
- `test_invalid_base_url_fails_before_db` (E23): `base_url="example.org"` → `ValueError`; `db.writes == []` en geen select uitgevoerd (subklasse die selects telt).
- `test_write_order_split` (E18, WP-08 bindend): run 1 met het scenario (A), dan forecasts zo dat 13Z 13 kn is (A: 13 < 12 + 2, dus `wind_borderline` → marginal; windows 10–13Z en 14–16Z) en `db.writes.clear()`; run 2 → `[w for w in db.writes if w[1] == "alert_state"] == [("update", "alert_state"), ("insert", "alert_state"), ("delete", "alert_state")]`; events `worsened` (state 0) en `new` (state 1); de `state_id` van `new` is de id van de nieuwe rij.
- `test_write_order_merge` (E19): run 1 met 13Z op 13 kn (twee entries: 10–13 en 14–16), run 2 met het volledige scenario. Een `FakeSupabase`-subklasse legt per `update` op `alert_state` `(filters["id"], values["status"])` vast → eerst de entry 14–16 met `"expired"`, dan de entry 10–13 met `"active"`; één event `improved`.
- `test_update_rank`: rang 0 voor `expired` en `cancelled`; rang 1 voor een kortere of gelijke actieve span; rang 2 voor een langere, verschoven of heractiveerde span.
- `test_skipped_favorite_does_not_stop_job` (E12, E13, E14): drie gebruikers op dezelfde spot: A met een conflict (regel `min_kn=25`, profiel `default_max_kn=20`), B met regel `earliest_local="24:00:00"`, C met regel `min_kn=12` → `skipped == 2`, één bericht (`user_id == USER_C`); voor A en B geen `alert_state`-rij. Daarna een tweede test: een geseede actieve staterij van C met `snapshot = {}` → `skipped == 1`, en die rij blijft ongewijzigd.
- `test_write_error_isolated` (E20, E21): zie AC-4-opzet → het bericht van A staat in het resultaat, dat van B niet; `errors` bevat `spot test-strand: DatabaseError (HTTP 409, code 23503)`.
- `test_update_count_mismatch` (E20): subklasse waarvan `update` 0 teruggeeft → `write_errors == 1`, geen berichten van die favoriet.
- `test_disabled_rule` (E11): run 1 maakt een actieve entry; dan `enabled=false` in `alert_rules` en forecasts op 6 kn; run 2 → 0 berichten, `disabled == 1`, de entry is nog `active` en ongewijzigd.
- `test_no_forecast_data_keeps_state` (E10): run 1 maakt een entry; dan alle `forecast_hours` verwijderen; run 2 → `ineligible == 1`, entry ongewijzigd `active`.
- `test_dry_run` (E24): `run_alerts(..., dry_run=True)` op een lege state → één bericht met `state_id is None`, `db.writes == []`. Na een echte run en een splitsing (zoals `test_write_order_split`) geeft een dry run voor het `worsened`-event de bestaande id en voor het `new`-event `None`, en `db.writes == []`.
- `test_cleanup_old_state`: rijen met `window_end` op `NOW - 49 h` (status `expired`) en `NOW - 47 h` → de eerste wordt verwijderd, `deleted == 1`.
- `test_no_favorites` (E7): `AlertJobResult(users=0, events=0, messages=[])`, alleen de select op `favorites` en de opruim-delete.
- `test_state_loading` (laadregel WP-08): geseede rijen voor A op de spot: `active` met `window_end` vóór `NOW`, `cancelled` met `window_end <= NOW`, `cancelled` met `window_end > NOW`, `expired` met `window_end > NOW`. `load_alert_context(db, now=NOW)` geeft voor die favoriet precies de eerste en de derde rij. Daarna `run_alerts` met het scenario, waarbij de derde rij (`cancelled`, 10:00Z–16:00Z) overlapt met het window → één `new`-event met `state_id` gelijk aan de id van die rij (heractivering, WP-08 A8), en er komt geen nieuwe rij bij.
- `test_no_bypass_parameters`: `inspect.signature` van `run_alerts`, `plan_favorite`, `load_alert_context` en `run_evaluation` bevat geen parameter met `offshore`, `allow`, `force` of `unsafe`; `now` is keyword-only.

### CLI: `tests/test_cli_jobs.py`
Seams: `monkeypatch.setattr(shakka.jobs.runtime, "open_db", lambda s: db)` en `"utcnow", lambda: NOW`; env `SUPABASE_URL=http://127.0.0.1:54321`, `SUPABASE_SECRET_KEY=test-secret-key`, geen `APP_BASE_URL`.
- `test_evaluate_cli`: scenario → exit 0, uitvoer `["evaluate: spots=1 rows=9 deleted=0 failed=0", "evaluate: ok"]`; met een ongeldige spotrij exit 1 en een regel die begint met `error   spot `.
- `test_alerts_run_cli`: scenario met A → exit 0; regel 0 `new test-strand: Go: Teststrand`, regel 1 `  wo 15 jul 12:00–18:00 · 14–25 kn, vlagen tot 29 kn`; de samenvatting `alerts: users=1 favorites=1 events=1 (new=1 improved=0 worsened=0 cancelled=0) ineligible=0 disabled=0 skipped=0 write_errors=0 deleted=0`; laatste regel `alerts: ok`; `USER_A` niet in de uitvoer.
- **AC-8** `test_alerts_run_dry_run_writes_nothing`: `alerts run --dry-run` → exit 0, `db.writes == []`, de regel `alerts: dry run, nothing stored` staat erin.
- `test_alerts_run_exit_1_on_skip`: een favoriet met een conflictregel → exit 1, laatste regel `alerts: failed`.
- `test_alerts_run_invalid_base_url`: `APP_BASE_URL=example.org` → exit 1, `alerts: invalid APP_BASE_URL`, `example.org` niet in de uitvoer.
- `test_missing_config`: geen env → exit 1 met `... configuration incomplete; run shakka doctor` voor `evaluate` en `alerts run`; `open_db` niet aangeroepen.
- `test_database_error`: een fake die bij `select` een `DatabaseError` geeft → exit 1, `alerts: database error: ...`; de fake is gesloten (`close` aangeroepen).
- `test_help_lists_new_commands`: `shakka --help` toont `evaluate`, `alerts` en `admin`; `shakka alerts run --help` toont `--dry-run`.

### AC-9 en AC-8: `tests/test_admin.py`
Zelfde seams en env.
- **AC-9** `test_profile_set_weight_only`: profielrij `{user_id: A, weight_kg: 70, level: "advanced", quiver_m2: [9.0, 12.0], default_min_kn: 14, default_max_kn: None}`; `profile set --user-id A --weight 80` → exit 0; daarna is de rij gelijk aan de oude op `weight_kg` (80) en `updated_at` na; `db.writes == [("update", "profiles")]`.
- **AC-9** `test_profile_set_unknown_option`: `profile set --user-id A --telegram-chat-id 1` → exit code ongelijk aan 0 (click: 2), `No such option` in de uitvoer, `db.writes == []`.
- **AC-9** `test_rule_set_offshore_rejected`, geparametriseerd over `offshore`, `side_offshore` en `onshore,offshore` → exit 1, uitvoer bevat `not allowed` en `never ridable`, `db.writes == []`.
- **AC-9** `test_favorite_add_unknown_spot` → exit 1, `favorite add: unknown spot 'bestaat-niet'`, `db.writes == []`.
- `test_profile_set_validation` (E32, E33, E36): `--min-kn 25` bij opgeslagen max 20 → exit 1; onbekende user → exit 1; `--quiver ""` → `[]`; `--quiver 12,9,9` → `[9.0, 12.0]`; `--quiver 2,9` → exit 1; `--weight 20` → exit 1; geen opties → exit 1 `nothing to change`.
- `test_profile_show`: exacte vijf regels; `telegram_chat_id` staat niet in de uitvoer, ook niet als de rij hem heeft.
- `test_favorite_add_remove_list` (E35): add → `favorite add: added test-strand` plus de `note:`-regel bij een niet-geverifieerde spot; tweede add → `is already a favorite`, geen schrijfactie; list → één regel met tabs en `1 favorite(s)`; remove → `removed`; tweede remove → `was not a favorite`, exit 0.
- `test_favorite_add_unknown_user` (E34): een fake die bij `insert` op `favorites` `DatabaseError(..., code="23503")` geeft → exit 1 `unknown user id`.
- `test_rule_set_insert_then_update` (E31): `rule set --weekdays 6,7 --after 17:00` → één `alert_rules`-rij; gelezen met `db.select("alert_rules", columns=RULE_COLUMNS)` heeft hij `weekdays [6, 7]`, `earliest_local "17:00:00"`, `enabled True` (fake-default, gelijk aan de DB-default) en de andere velden `None`; `AlertRuleOverride.from_row` op die rij slaagt; uitvoer bevat `rule: ... days 6,7, after 17:00, ...`. Daarna `rule set --disable` → alleen `enabled` wijzigt naar `False` (`db.writes` laatste item `("update", "alert_rules")`).
- `test_rule_set_errors` (E29, E30): geen favoriet → exit 1; `--after 18:00 --before 17:00` → exit 1; `--after 17:00` bij een opgeslagen `latest_local "16:00:00"` → exit 1; `--weekdays 0` → exit 1; `--min-kn 25` bij profiel `default_max_kn 20` → exit 1 (conflict, WP-07 A6); `--dir-classes onshore,bogus` → exit 1 `unknown dir class`; geen opties → exit 1. Telkens `db.writes == []`.
- **AC-8** `test_alerts_preview_writes_nothing`: scenario met A als favoriet → exit 0; `db.writes == []`; uitvoer bevat `spot test-strand`, `windows: 1`, `new: Go: Teststrand`. Na een echte `run_alerts` geeft preview `no change` en `state: 1 active, 0 cancelled (snapshot = last reported)`. Een niet-geverifieerde favoriet geeft `spot <id>: not eligible (spot not verified)`.

### AC-10 en AC-3: env-contract en kanaalvrij
- `tests/test_repo_hygiene.py::test_env_example_exact` met `ENV_KEYS = ["SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "APP_BASE_URL", "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"]` (AC-10).
- `tests/test_config.py::test_no_telegram_fields`: geen naam in `Settings.model_fields` begint met `telegram` (AC-10).
- `tests/test_config.py::test_old_telegram_env_is_ignored`: met `TELEGRAM_BOT_TOKEN=123:TESTTOKEN` en `TELEGRAM_CHAT_ID=1` in de omgeving (en via een tijdelijk `.env`-bestand) laadt `get_settings()` zonder fout (AC-10).
- `tests/test_cli.py::test_doctor_never_mentions_telegram`: `doctor` met lege omgeving en met volledige omgeving → `telegram` (hoofdletterongevoelig) staat niet in de uitvoer.
- `tests/test_repo_hygiene.py::test_no_telegram_in_ingest_src_and_env_example` (AC-3, eerste deel): geen bestand onder `ingest/src` en niet `.env.example` bevat `telegram` (hoofdletterongevoelig; gelezen met `Path.rglob("*.py")` en `read_text`).
- AC-3 tweede deel (`shakka.notify` niet in `ingest/src/shakka/jobs`) controleert de verifier met grep; geen permanente test (zie Gevolgen, WP-17).
- AC-10 laatste punt: `cd ingest && uv run pytest` volledig groen.

### AC-11 (`NEEDS_LARS`)
Met Lars' `.env`, een auth-user en minstens één favoriete, geverifieerde spot: `uv run shakka evaluate`, `uv run shakka admin alerts preview --user-id <id>` (windows of `windows: none`, zonder fouten), daarna `uv run shakka alerts run`; bij een window een `alert_state`-rij in het dashboard. De stappen staan in RUNBOOK §12.

## Externe afhankelijkheden
- **Geen nieuwe packages.** Gebruikt: `click` (lock: 8.5.0), `pydantic`, `httpx` via `shakka.db`, standaardbibliotheek.
- **Click** (gecontroleerd op 15 oktober 2026, documentatie 8.5.x):
  - booleaanse vlagparen (`--enable/--disable`) met `default=None` geven `None` als de vlag ontbreekt ([Options, "Boolean flag pairs"](https://click.palletsprojects.com/en/stable/options/));
  - `click.UUID` bestaat en levert een `uuid.UUID` ([Parameter types](https://click.palletsprojects.com/en/stable/parameter-types/));
  - `UsageError` (en dus `NoSuchOption` en `BadParameter`) heeft `exit_code = 2`, `ClickException` 1 ([src/click/exceptions.py](https://github.com/pallets/click/blob/main/src/click/exceptions.py)). Daarom valideert WP-10 domeinwaarden zelf (exit 1) en laat het alleen onbekende opties en een ongeldige UUID aan click over (exit 2).
- **PostgREST** (via de bestaande `SupabaseRest` uit WP-01; geen nieuwe endpoints): `POST` met `Prefer: return=representation` geeft de aangemaakte rij terug; `PATCH` met filters ondersteunt `return=representation`. Over `resolution=merge-duplicates` met een payload met een deel van de kolommen zegt de documentatie niets; daarom gebruikt WP-10 voor gedeeltelijke wijzigingen `update`/`insert` (A10). Bron: [PostgREST, Tables and Views](https://docs.postgrest.org/en/stable/references/api/tables_views.html). De upsert op `evaluations` stuurt altijd volledige rijen (zelfde patroon als `forecast_hours` in WP-03).
- Geen Open-Meteo-, RWS- of andere externe aanroepen in deze WP.

## Risico's
- **R1. Niet-transactionele schrijfacties.** Een crash tussen updates en inserts laat een halve diff achter. Mitigatie: de bindende schrijfvolgorde (updates eerst, korter/expired vóór langer) en het herstel in `diff_windows` (WP-08 A15); prijs: hooguit een dubbele `new` (WP-08 R7).
- **R2. Ontbrekende forecastdata en annuleringen.** Zonder rijen geen diff (A4), maar gedeeltelijke data (bijv. alleen de eerste dagen) kan windows aan het eind laten verdwijnen en dus annuleren. WP-11 slaat de alertstap over bij een forecast ouder dan 3 uur; de getoonde horizon (8 dagen) ligt ruim achter `days_ahead` (standaard 3).
- **R3. Berichtteksten in CLI-uitvoer.** `shakka alerts run` en `admin alerts preview` tonen bodies. Wie die in een workflow zet, publiceert ze. RUNBOOK §12 waarschuwt; WP-11 roept de functies aan, niet de CLI.
- **R4. Verificatie-eis maakt M1 afhankelijk van Lars.** Alle 25 startspots hebben `verified: false` en (deels) lege velden; zonder ingevuld en geverifieerd profiel geen alerts (WP-05 R4). AC-11 is daarom `NEEDS_LARS`.
- **R5. Dubbel laden per run.** Evaluatie- en alertjob laden elk de inputs (ongeveer 30 GET-requests extra per uur, ruim binnen de gratis Supabase-tier). Optimalisatie kan in WP-11.
- **R6. Stalefilter op 3 uur** (A5) kan bij een tijdelijk haperende forecastrun voor één spot een model een uur missen. Effect: lagere betrouwbaarheid, nooit een onveilig oordeel.
- **R7. Kosten per favoriet.** Elke favoriet evalueert opnieuw (geen cache per `(spot, limits)`). Bij M1 (één gebruiker) verwaarloosbaar; bij M4 te herzien in WP-22.

## Buiten scope
- Versturen, `Notifier`, `DeliveryTarget`, `load_targets`, de afleverregel en `last_notified_at` vullen (WP-17).
- De uurlijkse volgorde, `ingest_runs`, operatormeldingen en de stalecheck (WP-11).
- UI voor profiel, favorieten en regels (WP-16); velden terugzetten op `NULL` via de CLI (A14).
- De kolom `profiles.telegram_chat_id` verwijderen (WP-22); de pgTAP-tests die hem nog noemen blijven ongewijzigd.
- Wijzigingen aan `shakka.domain`, `shakka.db`, `tests/fakes.py`, migraties en contractbestanden.
- `forecast_days` naar 8 of `days_ahead` begrenzen (WP-03 "Gevolgen"; besluit voor WP-16).
- Stille uren voor meldingen (niet in het plan).

## Stappenplan voor de builder
Werk op branch `wp/WP-10` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-10`. Lees of print `.env` nooit. Draai na elke stap vanuit `ingest/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`. Eén commit per stap, commitberichten in het Engels.

1. **Env-contract (A-16), eerst de tests.**
   - Pas `tests/test_repo_hygiene.py` (`ENV_KEYS`, nieuwe test `test_no_telegram_in_ingest_src_and_env_example`), `tests/test_config.py` (asserts weg, `VAPID_PRIVATE_KEY` in de repr-test, `test_no_telegram_fields`, `test_old_telegram_env_is_ignored`) en `tests/test_cli.py` (lektest met `vapid_private_key`, `test_doctor_never_mentions_telegram`) aan. Rood.
   - Haal de twee velden uit `config.py`, de twee regels uit `.env.example` en de twee rijen uit RUNBOOK §4. Groen.

   Commit: `chore(config): drop telegram settings from the env contract`.
2. **Runtime en inputs, eerst de tests.**
   - Maak `tests/job_fixtures.py` en `tests/test_job_inputs.py`. Rood.
   - Maak `src/shakka/jobs/runtime.py` en `src/shakka/jobs/inputs.py`. Groen.

   Commit: `feat(jobs): load spot inputs for evaluation and alerts`.
3. **Evaluatiejob en `shakka evaluate`, eerst de tests.**
   - Schrijf `tests/test_job_evaluate.py` en de `evaluate`-tests in `tests/test_cli_jobs.py`. Rood.
   - Maak `src/shakka/jobs/evaluate.py` en voeg het commando `evaluate` toe aan `cli.py`. Groen.

   Commit: `feat(jobs): store hourly evaluations per spot`.
4. **Alertjob, eerst de tests.**
   - Schrijf `tests/test_job_alerts.py` volledig. Rood.
   - Maak `src/shakka/jobs/alerts.py` zonder de CLI-runner: `normalize_base_url`, `rider_from_profile`, `window_for`, `load_alert_context`, `plan_favorite`, `update_rank`, `store_plan`, `delete_old_alert_state`, `run_alerts`, `format_rule`. Groen. Controleer met `grep -n "print(" src/shakka/jobs/*.py` dat er geen `print` in staat.

   Commit: `feat(jobs): compute alerts and record them in alert_state`.
5. **`shakka alerts run`, eerst de tests.**
   - Voeg de `alerts`-tests toe aan `tests/test_cli_jobs.py`. Rood.
   - Voeg `run_alerts_cli` toe en de groep `alerts` met `run` in `cli.py`. Groen.

   Commit: `feat(cli): add alerts run with dry run`.
6. **Beheer-CLI, eerst de tests.**
   - Schrijf `tests/test_admin.py`. Rood.
   - Maak `src/shakka/jobs/admin.py` en voeg de groep `admin` met alle subcommando's toe aan `cli.py`. Groen.

   Commit: `feat(cli): add admin commands for profile, favorites, rules and alert preview`.
7. **RUNBOOK §12 "Alerts in M1"** (Nederlands), met:
   1. een auth-user maken (Supabase Dashboard, Authentication, Users, Add user) en de user-id (UUID) kopiëren;
   2. `uv run shakka admin profile set --user-id <id> --weight <kg> --level <niveau> --quiver 7,9,12` en `profile show`;
   3. `uv run shakka admin favorite add --user-id <id> --spot <spot-id>` en `favorite list`;
   4. optioneel `uv run shakka admin rule set ...` (met de opties uit de tabel, en dat offshore/side-offshore nooit kan);
   5. alerts gaan alleen af voor spots met `verified: true`: profiel invullen in `data/spots.yaml` volgens `docs/SPOT_DATA.md`, `verified: true`, en `uv run shakka spots sync`;
   6. volgorde: `forecast fetch`, `tides fetch`, `evaluate`, `admin alerts preview --user-id <id>`, `alerts run` (eerst eventueel `alerts run --dry-run`);
   7. `alert_state` bekijken in het dashboard (Table Editor): `status`, `last_event`, `snapshot` is de laatst gemelde stand (niet de nieuwste verwachting), `last_notified_at` is in M1 altijd leeg; rijen verdwijnen 48 uur na `window_end`;
   8. exitcodes en betekenis van `ineligible`, `disabled`, `skipped`, `write_errors`;
   9. waarschuwing: `alerts run` en `admin alerts preview` tonen berichtteksten; gebruik ze lokaal en niet in een GitHub-workflow (openbare logs);
   10. optioneel `TELEGRAM_*` uit de lokale `.env` halen (wordt genegeerd).

   Commit: `docs(runbook): describe the M1 alert setup`.
8. **Eindcontrole.**
   - Volledige suite en ruff groen.
   - `grep -rniE "telegram" ingest/src .env.example` geeft niets; `grep -rn "shakka.notify" ingest/src/shakka/jobs` geeft niets (AC-3).
   - `git diff --stat $(git merge-base develop HEAD) -- ingest supabase data web .env.example` toont alleen de bestanden uit "Bestanden"; geen wijziging onder `ingest/src/shakka/domain`, `supabase/` of `data/`.
