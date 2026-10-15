# Afwijkingen WP-06

Geen afwijkingen die contract, schema, externe API, dependency of acceptatiecriterium raken.

## Uit de review overgenomen (niet-blokkerend)
- **N-2:** het fijne windraster in `test_ideal_monotone_in_wind_fine_grid` is opgebouwd als `i / 10` voor `i` van 10 t/m 1000 (niet cumulatief optellen), zodat de laatste waarde exact 100,0 is.
- **N-4:** `recommend_for_window` geeft de gevalideerde waarden (`[_check_wind(v) for v in ...]`) aan `statistics.median_high`, niet de ruwe invoer.
- **N-5:** extra test `test_window_upper_median_changes_size_too` met window `[12, 14, 17, 25]`: gewone mediaan 15,5 kn geeft 12 m², bovenste mediaan 17 kn geeft 9 m².

## Kleine afwijkingen
- Stappenvolgorde: `recommend_for_window` is al in stap 2 samen met `recommend_kite` geschreven; de AC-6-tests kwamen in stap 4/5 (één commit met de eigenschapstests). De inhoud is gelijk aan de blueprint.
- Extra tests: `test_ideal_rejects_unknown_level`, `test_ideal_wind_bounds_valid`, `test_heavier_never_smaller_size`.
- Constanten staan in `shakka.domain.kite` (A7), niet in `defaults.py`.

## Open voor Lars
- `checked_by_lars: false` blijft staan; AC-2 is `NEEDS_LARS` (verwacht).
