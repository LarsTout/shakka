# Verificatie WP-07, ronde 1
Resultaat: PASS

Suite: `cd ingest && uv run pytest` geeft 1061 passed, 24 skipped (de skips zijn bestaande tests die een lokale Supabase vragen: `test_fake_parity`, `test_spots_sync_local`). `uv run ruff check .` en `uv run ruff format --check .` zijn groen. CI-run 38724149412 op `wp/WP-07`: ingest, web en db success.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `tests/test_alert_rules.py::test_priority` is geparametriseerd over alle 9 velden x 4 niveaus (regel, profiel, spot, systeem); `test_priority_spot_level_derived_max` toetst `spot.default_min_kn` als regel en profiel leeg zijn (16 en 28 kn). Groen. |
| AC-2 | PASS | Eigen steekproeven: `offshore` en `side_offshore` (als string, enum, los, gemengd met `onshore`, als lijst, via `model_validate`, `model_validate_json`, `from_row`) geven allemaal `ValueError` in `AlertRuleOverride`. `AlertRule(...)` en `resolve_rule` weigeren ze ook. `min_kn >= max_kn` en weekdag 0 of 8 geven `ValueError` (override, regel en `model_copy`). Tests `test_override_rejects_offshore`, `test_rule_rejects_offshore`, `test_min_ge_max_rejected`, `test_weekday_out_of_range` groen. |
| AC-3 | PASS | `tests/test_windows.py` bevat alle negen gevallen: `test_three_go_hours_min_two` (end = laatste uur + 1u), `test_single_go_hour_no_window`, `test_go_marginal_go_min_one`, `test_weekend_filter_local_date`, `test_earliest_17_summer`/`_winter`, `test_days_ahead_one`, `test_hours_before_now_excluded`, `test_missing_hour_splits`, `test_dir_class_outside_rule_splits`. Alle 31 tests in het bestand groen; de semantiek is ook met eigen probes bevestigd (zie hieronder). |
| AC-4 | PASS | `test_disabled_returns_empty`; eigen probe: `find_windows(evs, rule(enabled=False), now=...)` geeft `[]`. |
| AC-5 | PASS | `uv run shakka contracts export --check` geeft `ok` voor alle vier de bestanden. Twee keer opnieuw exporteren en `PYTHONHASHSEED=1` en `=999`: `alert_defaults.json` byte-identiek, `git status` schoon. Het bestand bevat de defaults, bronnen, grenzen en `allowed` voor `dir_classes` (alleen `onshore`, `side_onshore`, `sideshore`; het woord `offshore` komt er 0 keer in voor). |
| AC-6 | PASS | `uv run pytest tests/test_domain_purity.py` 31 passed. |

## Harde regels
- Offshore en side-offshore altijd `no_go`: PASS. Eigen steekproeven (alles `ValueError`):
  - `AlertRuleOverride` via constructor, `model_validate`, JSON, `from_row`, `model_copy(update=...)`, ook met `deep=True`.
  - `AlertRule(...)`, `AlertRule.model_copy(update={"dir_classes": ...})`, lege `dir_classes`, en `setattr` op het bevroren model.
  - `resolve_rule` met een via `model_construct` omzeild override-object herstelt de validatie (de `AlertRule`-constructie weigert).
  - `Window(...)` met een offshore-uur of een marginal-uur wordt geweigerd; `Window.model_copy(update={"hours": (offshore,)})` ook.
  - `find_windows` sluit een via `model_construct` gebouwd uur met `verdict=go` en `dir_class=offshore` uit (aparte `RIDABLE_DIR_CLASSES`-check in `_qualifies`). Opmerking: `AlertRule.model_construct(...)` zelf is standaard pydantic en omzeilt validatie; dat is geen aanvaardbare productiepad en valt buiten het contract, en `find_windows` blijft veilig doordat een uur zonder ridable `dir_class` nooit meetelt.
  - `model_copy` hervalideert aantoonbaar: `dict(self)` plus `update` gaat door `type(self).model_validate`; ongeldige updates (offshore, `min_kn=40` boven `max_kn`, weekdag 0/8) falen.
- Geen secrets in de diff: PASS (grep op secret/key/token/http geeft alleen doc-URL's in de blueprint).
- Geen client-side Open-Meteo, geen scraping, geen nieuwe betaalde dienst: PASS (diff raakt alleen `ingest/src/shakka/{domain/alerts,contracts,cli}.py`, tests, contractbestand en docs; `domain/` blijft zuiver volgens AC-6).
- Bronvermelding: onaangetast.
- Scope: PASS. Gewijzigd: `alerts.py`, `contracts.py`, `cli.py`, vier testbestanden, `alert_defaults.json`, `docs/STATUS.md` en `docs/wp/WP-07/*`. Niets daarbuiten.
- `cli.py`-diff: PASS, precies één docstring-regel (`contracts_export`).

## Tijdsemantiek (eigen probes)
- Eerste meetellend uur = floor(now)+1h: now 08:00:00, 08:00:00.000001 en 08:59:59 geven alle drie start 09:00 UTC; now 07:59:59.999999 geeft 08:00. PASS.
- `now` in een andere tijdzone (Europe/Amsterdam 10:30) wordt naar UTC omgezet: eerste uur 09:00 UTC. Naive `now`, dubbele `valid_at` en gemengde `spot_id` geven `ValueError`; ongesorteerde invoer geeft hetzelfde resultaat.
- Halfopen window: 3 uren 08-10 UTC geeft start 08:00, end 11:00. PASS.
- `earliest_local=17:00, latest_local=19:00`: window 17:00-19:00 lokaal zowel op 2027-04-06 (zomer) als 2026-12-01 (winter). PASS.
- Zomertijd 2027-03-28 (01:00 lokaal volgt direct op 03:00): één doorlopend window over de overgang; filter zondag geeft vanaf 00:00 lokaal, filter zaterdag stopt om 00:00; `earliest_local=03:00` begint 03:00; niet-bestaand 02:00 begint op 03:00. PASS.
- Wintertijd 2026-10-25 (02:00 komt twee keer voor): één doorlopend window van 12 uur; `[02:00, 03:00)` pakt beide 02:00-uren; zondagsfilter correct. PASS.
- `days_ahead=1` met now 23:30 lokaal (21:30 UTC) loopt t/m einde lokale morgen; met now 00:30 lokaal een dag later. `days_ahead=0` stopt aan het einde van de lokale dag. PASS (lokale datum, niet UTC).
- `latest_local` `"24:00"` en `"24:00:00"` geven `None` (avonduren tellen mee, window 20:00-02:00 lokaal); `earliest_local` `"24:00"`/`"24:00:00"` geeft `ValueError`; `23:59:59` blijft een gewone tijd. PASS.

## Afwijkingen
`deviations.md` (N-1, N-3, testindeling, `dict(self)` in `model_copy`, `Any` voor `last_day`, `test_no_bypass_parameters` in twee stappen) is gedocumenteerd en geraakt geen contract of criterium. Geen ongedocumenteerde afwijkingen gevonden.

## Nodig van Lars
De defaults `min_go_hours=2` en `days_ahead=3` zijn een voorstel van de planner en wachten op bevestiging van Lars (geen fail).

## Problemen
Geen.
