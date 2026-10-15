# Verificatie WP-05, ronde 1
Resultaat: PASS

Branch `wp/WP-05`, diff `origin/develop...HEAD` (29 bestanden, allemaal binnen de scope van de WP: `ingest/src/shakka/domain`, `contracts.py`, `cli.py`, tests, `data/contracts/`, `docs/SPOT_DATA.md`, `docs/STATUS.md`, `docs/wp/WP-05/`, `pyproject.toml` en `uv.lock` voor `astral`).

Suite: `uv run pytest` geeft 788 passed, 24 skipped (de skips zijn bestaande tests die een lokale Supabase nodig hebben: `test_fake_parity.py`, `test_spots_sync_local.py`; niet van deze WP). `uv run ruff check .` en `uv run ruff format --check .` zijn groen. CI-run 38720319643 op `wp/WP-05`: completed, success.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | Eigen run: voor normaal 270 geeft wind 270/225/315/180/0/135/45/90 de klassen onshore/side_onshore/side_onshore/sideshore/sideshore/side_offshore/side_offshore/offshore. Normaal 10, wind 350: onshore. `tests/test_direction.py` (symmetrie en monotoniteit over normalen 0/45/270/359 en alle gehele richtingen) groen. |
| AC-2 | PASS | Zie "Harde regels". `tests/test_evaluation_safety.py` groen; eigen run met 148.086 evaluaties zonder één afwijking. Signatures gecontroleerd: `evaluate_hour(spot, valid_at, hours, tides, limits)`, `evaluate_spot(spot, forecasts, tides, limits)`, `classify_direction(wind_from_deg, shore_normal_deg)`, `in_ranges(deg, ranges)`, `compute_consensus(hours)`; geen enkele parameter schakelt de regel uit. |
| AC-3 | PASS | `test_no_shore_normal_every_hour`, `test_ridable_dirs_restricts`, `test_ridable_dirs_cannot_allow_offshore` groen. |
| AC-4 | PASS | `test_wind_thresholds`, `test_gust_thresholds` (beide kanten van elke drempel), `test_narrow_limits_single_borderline` groen. Drempels staan in `defaults.py` (WIND_BORDERLINE_KN 2,0; GUSTY_RATIO 1,6; TOO_GUSTY_RATIO 1,9; GUST_MIN_DELTA_KN 8,0). |
| AC-5 | PASS | Eigen run met 52,47 N / 4,57 O: 21-06 03:00Z False (dark), 21-06 12:00Z True, 21-12 17:00Z False (dark). `tests/test_daylight.py` groen. |
| AC-6 | PASS | Eigen run met sluiting 05-01..09-30 10:00-18:00: 15-07 12:00 lokaal gesloten, 15-07 19:00 niet, 15-10 12:00 niet; 11-15..02-15 geldt op 10-01-2027. `test_dst` (29-03 en 25-10) en `test_status_reasons` groen. |
| AC-7 | PASS | `test_tide_none_has_level_but_no_reason`, `test_tide_too_low`, `test_tide_preference` (per variant), `test_tide_unknown_cases` groen; `tide_level_cm` komt uit `estimate_tide_level`. |
| AC-8 | PASS | Eigen run: vier vrijwel gelijke modellen geven `high`; winden 10/20/30/20 geven `low`; één model geeft `low` (gedocumenteerd; `test_single_model_marginal`); richtingen 350/10/350/10 geven `dir_deg` 0 (`dir_mean_deg` 0,0), niet 180. `test_low_confidence_makes_go_marginal`, `test_no_go_keeps_low_confidence_reason`, `test_no_data` groen. |
| AC-9 | PASS | `HourEvaluation` valideert zelf: verdict gelijk aan zwaarste effect, uniek en in vaste volgorde. `tests/test_evaluation_properties.py` en `test_evaluate_spot_sorted_unique` groen. |
| AC-10 | PASS | `uv run shakka contracts export --check` geeft exit 0 ("ok" voor drie bestanden). Twee keer `export` achter elkaar geeft identieke md5's en `git status` blijft schoon (deterministisch). `reason_codes.json` bevat 19 codes met `label_nl`; `dir_classes.json` 5 en `confidence.json` 3, allemaal niet leeg. `tests/test_contracts.py` groen. |
| AC-11 | PASS | `tests/test_domain_purity.py` groen. Geen netwerk-imports in `domain/*.py`. |

## Harde regels
- Offshore en side-offshore altijd `no_go`: PASS.
  - `SIDESHORE_MAX_DEG` is 90.0 (inclusief). Grens: 89,9 en 90,0 geven sideshore; 90,4, 91 en 100 geven side_offshore; 180 geeft offshore. Dit geldt aan beide kanten van de normaal.
  - Eigen exhaustieve run: normaal 0 t/m 345 in stappen van 15 en elke gehele windrichting 0 t/m 359 (alle vier de modellen gelijk), met drie RiderLimits (0..1000, 1..2, 12..30). Daarbij ook `ridable_dirs` die het hele bereik toestaan (normalen 0, 45 en 270). Daarnaast 20.000 willekeurige modelsets en 20.000 sets rond 88 tot 92 graden vanaf de normaal, met rekenruis. Totaal 148.086 evaluaties, 0 afwijkingen: elk uur met een gemiddelde afwijking groter dan 90 graden geeft `no_go` met `offshore` of `side_offshore`; geen enkele `go` of `marginal`.
  - Rekenruis-gevallen bij normaal 0: 4x180 geeft `dir_mean_deg` 180,0, offshore, `no_go`. (88, 91, 91, 90) geeft `dir_mean_deg` 90,000076, `dir_deg` 90, klasse `side_offshore`, `no_go`. De klasse is bepaald op het onafgeronde gemiddelde.
  - `model_copy`: `update={"verdict": go}`, `{"verdict": go, "reasons": ()}`, `{"dir_class": sideshore}` en `{"reasons": ()}` op een offshore-uur worden allemaal geweigerd (ValidationError). Toewijzen van een attribuut (frozen), de constructor en `model_validate` met `marginal` plus `offshore` worden ook geweigerd.
- Geen secrets in de diff: PASS (grep op secret/token/key/password/sk- levert niets).
- Geen client-side Open-Meteo: PASS (alleen Python in `/ingest`, geen `/web`-wijzigingen).
- Geen scraping, geen nieuwe betaalde dienst: PASS. Enige nieuwe dependency is `astral>=3.2,<4` (gratis, offline, in blueprint A11 en in het plan genoemd).
- Bronvermelding: ongewijzigd.
- Geen feitelijke spotdata verzonnen: PASS. De testcoördinaten staan alleen in tests (`evaluation_fixtures.py`).

## Afwijkingen van de blueprint
`deviations.md` bevat alleen kleine afwijkingen (helper-import, private `_evaluate`, extra tests) en de overgenomen N-1/N-2/N-3. Geen ongedocumenteerde afwijking gevonden. Wijzigingen aan `docs/SPOT_DATA.md` staan in de blueprint (Bestanden, stap 9).

## Opmerkingen (geen fail)
- Drempelwaarden in `defaults.py` zijn een voorstel voor Lars (testweek). `SIDESHORE_MAX_DEG = 90` is daarvan uitgezonderd (volgt uit de harde regel).
- `HourEvaluation` kent de kustnormaal niet. Een bewust opgebouwde kopie met consistente `dir_class` en `reasons` (bijv. `{"reasons": (), "verdict": go, "dir_class": onshore}`) wordt dus geaccepteerd. Dat is geen route vanuit `evaluate_hour`; de engine zelf kan zo'n uitkomst niet maken. `model_construct` omzeilt validatie, zoals bij elk pydantic-model.
- Open punt O1 uit de blueprint: de richting is de consensus; als één model aflandig voorspelt terwijl het gemiddelde sideshore is, volgt alleen een lagere `confidence` via de spreiding. Bewust niet ingebouwd, beleidskeuze voor Lars.

## Problemen
Geen.
