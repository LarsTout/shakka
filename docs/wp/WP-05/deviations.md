# Afwijkingen WP-05

Geen afwijkingen die een contract, schema, externe API, dependency of acceptatiecriterium raken. Alles hieronder is klein; de bouw ging door.

## Uit review ronde 2 (door de orchestrator meegegeven)
- **N-2, `Consensus`-validator.** `Consensus` heeft een `model_validator(mode="after")` die eist: `(dir_deg is None) == (dir_mean_deg is None)`, `0 <= dir_mean_deg < 360` en `dir_deg == int(round(dir_mean_deg)) % 360`. Stap 5 van `evaluate_hour` controleert daarom consistent op `c.dir_mean_deg is None` en gebruikt daarna alleen `dir_mean_deg` voor de klasse en de `ridable_dirs`-controle. Test: `test_consensus_dir_coupling_validator`. Impact: geen; via `compute_consensus` waren beide al samen gezet.
- **N-3, afrondingstest.** `test_rounding_never_makes_offshore_ridable` controleert `dir_mean_deg` via `compute_consensus` op dezelfde uren, en `dir_class`, `verdict` en `reasons` via `evaluate_hour` (`dir_mean_deg` is geen veld van `HourEvaluation`). Extra geval (88, 91, 91, 90) bij normaal 0: circulair gemiddelde groter dan 90, dus `side_offshore` en `no_go`.
- **N-1, formulering.** In de code staat nergens de zin dat afronden een aflandig uur "nooit" rijdbaar maakt. Het commentaar in `evaluation._direction` zegt alleen dat de klasse op de onafgeronde gemiddelde richting wordt bepaald (A15); de afronding (`DIR_MEAN_DECIMALS = 6`) verschuift de richting hooguit 5e-7 graden. De blueprint is niet aangepast (de zin staat al in A15).

## Kleine afwijkingen
- Testmodules importeren de helpers als `from evaluation_fixtures import ...` (zoals `spot_fixtures` bij de bestaande tests), niet als `tests.evaluation_fixtures`.
- `evaluation.py` heeft een private `_evaluate` die de al gefilterde getij-extremen krijgt; `evaluate_hour` en `evaluate_spot` zijn dunne wrappers. Gedrag gelijk aan de blueprint.
- Extra tests boven de lijst in het Testplan: `test_ridable_dirs_use_unrounded_direction`, `test_tide_min_level_boundary`, `test_tide_station_is_stripped`, `test_only_lows_gives_unknown_but_checks_level`, `test_narrow_limits_single_borderline`, `test_model_other_invariants`, `test_sun_times_is_cached`.
- `test_winter_daylight_hours`: de echte astral-uitkomst klopt met de blueprint (uurstarts 08:00 t/m 14:00 UTC); geen aanpassing nodig.
- `defaults.py` bevat exact de constanten uit de blueprint; verder niets aangeraakt.
