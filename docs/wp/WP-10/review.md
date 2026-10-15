# Review WP-10, ronde 2
Oordeel: APPROVED

Getoetst: revisie 2 van de blueprint tegen de review van ronde 1 en tegen de bestaande code in de worktree: `shakka/db.py` (`select` met paginering, `TABLE_KEYS`, `in_filter`, `iso_utc`), `tests/fakes.py` (projectie, filters met lijstwaarden, `in.`), `shakka/domain/evaluation.py` (`evaluate_spot`, `_station_tides`, `default_limits`), `shakka/domain/dedup.py` (`ALERT_STATE_COLUMNS`, `diff_windows`), `shakka/domain/alerts.py` (`RULE_FIELDS`, `resolve_rule`, `rider_limits`, `find_windows`), `shakka/domain/messages.py` (`build_go_url`, `render_alert`), `shakka/domain/kite.py` (`recommend_for_window`) en `shakka/domain/spot.py` (`SPOT_COLUMNS`).

**B-1 (ronde 1) is opgelost, en consistent in alle lagen:**
- **Inputs:** geen rijen geeft `forecasts = []`. Er is geen stalefilter en er komt geen `max()` over een lege reeks. De spot staat in `inputs` en niet in `invalid`, en het getij wordt nog steeds geladen.
- **Evaluatie:** `evaluate_spot` geeft bij lege forecasts echt `[]`. Ik heb de code nagelezen: `_station_tides` gooit niets, er is geen fout, de spot telt mee in `spots` en `shakka evaluate` geeft exit 0.
- **Alertjob:** de tak `not inputs.forecasts` is nu bereikbaar en geeft `ineligible` met detail `"no forecast data"`. `ineligible` maakt de exitcode nooit 1.
- **Edge cases:** E10 is aangepast en E38 is nieuw.
- **Tests:** ze dekken het op alle niveaus: `test_spot_without_forecast_rows` (met een variant voor rijen buiten het bereik), `test_spot_without_forecasts_is_not_a_failure`, de twee CLI-tests, `test_no_forecast_data_keeps_state` (met `ctx.inputs[SPOT].forecasts == []`, `plan.detail`, `skipped == 0` en `errors == ()`) en de preview.

**Privacy-aanpassingen (N-1) zijn correct en kosten geen correctheid:**
- **`store_plan` filtert alleen op `id`.** `alert_state.id` is de enige PK (`TABLE_KEYS`). `previous[i].id` komt uit een rij die in dezelfde run voor precies die `(user_id, spot_id)` is geladen, en `count != 1` blijft als vangnet.
- **`profiles` zonder filter in de uurlijkse run** is gelijkwaardig aan een `in.(...)`-filter, omdat de opzoeking per `user_id` gaat. Ook boven 1000 rijen gaat er niets verloren: `SupabaseRest.select` pagineert met `limit`/`offset` per `PAGE_SIZE = 1000` tot een lege pagina, met een deterministische volgorde op de PK (`effective_order`). Hetzelfde geldt voor `favorites`, `alert_rules` en `alert_state` zonder filter. De forecastquery per spot (ongeveer 3 × 194 rijen) blijft sowieso onder één pagina.
- **`run_alerts` zet geen user-id in een filter- of order-parameter.** User-id's staan alleen in de insert-body.
- **Test en WP-11:** `test_no_user_id_in_request_filters` legt dit vast. De eis dat `httpx`/`httpcore` op `WARNING` gaan, staat met een testvoorstel onder "Gevolgen → WP-11".

**`--quiver`-parsing** heb ik nagelopen voor de lijstvorm (`;`/spaties) en de kommavorm:
- `"10,5; 12"` en `" 10,5 ; 12 "` geven `[10.5, 12.0]`.
- `"1,2,5 9"` geeft een `AdminError`, omdat `float` op twee komma's faalt.
- `"7,9,12"` geeft drie maten.
- `"10,5"` geeft `[5.0, 10.0]` met een note.
- `"9,12"` geeft geen note.

Een gevaarlijke stille misinterpretatie vond ik niet: dubbelzinnige gevallen worden óf geweigerd, óf gemeld via de note en `profile show`.

De overige N-punten uit ronde 1 (N-2 t/m N-10) zijn verwerkt zoals beschreven in "Verwerking review". De revisie introduceert geen nieuwe blokkerende punten.

## Blokkerend
Geen.

## Niet-blokkerend
N-1: Spot-id's van favorieten staan wel in request-URL's van `run_alerts`.
- Waar: A9 (de zin "Ook de spot-id van een favoriet komt niet in de log"), de stappen 6 van `load_alert_context` en 1 van `load_inputs_checked`.
- Wat: `load_inputs(..., spot_ids=<favoriete spots>)` vraagt `spots?id=in.(...)` op, plus per favoriete spot `forecast_hours?spot_id=eq.<id>`. Dat is geaggregeerd over alle gebruikers en zonder koppeling aan een user-id, dus geen persoonsgegeven. Maar zonder de httpx-instelling van WP-11 ziet een buitenstaander welke spots minstens één favoriet hebben.
- Waarom niet blokkerend: WP-11 zet `httpx` op `WARNING`, en die eis staat er al. Voorstel: voeg in A9 één zin toe dat dit restlek ook door die WP-11-eis wordt afgedekt.

N-2: Volgorde in `plan_favorite`. Een favoriet zonder forecastdata maar met een kapotte regel- of profielrij wordt `skipped` (exit 1), niet `ineligible`. Dat komt doordat de `from_row`-stappen vóór de check `not inputs.forecasts` staan. Ik vind dat verdedigbaar (een kapotte rij hoort op te vallen), maar het staat nergens expliciet. Een zin in A4 of E10 voorkomt twijfel bij de builder.

N-3: `parse_quiver` met komma plus spatie.
- Wat: `"7, 9, 12"` valt in de lijstvorm (er zit witruimte in). De delen `"7,"` en `"9,"` worden `"7."`/`"9."`, en `float` geeft dan 7.0 en 9.0. Het resultaat klopt dus. `"7, 5"` wordt `[5.0, 7.0]`, zonder note, omdat de note alleen in de kommavorm verschijnt.
- Voorstel: neem `"7, 9, 12"` op in `test_parse_quiver`. Dit is waarschijnlijk de meest getypte vorm, en zo ligt het gedrag vast.
- Kleinigheid: `float` accepteert ook `"1_0"` en `"1e1"`. Dat is onschadelijk, want het bereik wordt nog gecontroleerd.

N-4: De egress-schatting en de groei van `profiles` zonder filter staan terecht onder WP-22. Vermeld daar ook dat paginering de correctheid boven 1000 rijen al dekt (`SupabaseRest.select`), zodat WP-22 alleen naar kosten hoeft te kijken.

## Gecontroleerde bronnen
- https://www.python-httpx.org/logging/ (logger `httpx` op INFO per request met de request-URL; `httpcore` op DEBUG voor verbindingsdetails)
- Lokaal: `ingest/src/shakka/db.py` (`PAGE_SIZE = 1000`, paginerende `select`, `TABLE_KEYS`, `effective_order`), `ingest/tests/fakes.py` (projectie vult ontbrekende kolommen met `None`, `in.`-filters en lijstfilters), `ingest/src/shakka/domain/{evaluation,dedup,alerts,messages,kite,spot}.py`
- Uit ronde 1, niet opnieuw gewijzigd: Click-documentatie (vlagparen, `click.UUID`, exitcodes) en PostgREST Tables and Views
