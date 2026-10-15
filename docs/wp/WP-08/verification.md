# Verificatie WP-08, ronde 1
Resultaat: PASS

Basis: `git merge-base origin/develop HEAD` ... `HEAD` (branch `wp/WP-08`, commit `d721e75`).

## Suite
- `cd ingest && uv run pytest`: 1169 passed, 24 skipped. De skips zijn de Supabase-tests (`SHAKKA_TEST_SUPABASE_URL` ontbreekt), niet WP-08.
- `uv run ruff check . && uv run ruff format --check .`: groen (88 files already formatted).
- `uv run pytest tests/test_dedup.py tests/test_dedup_invariants.py tests/test_messages.py tests/test_domain_purity.py`: 139 passed.
- CI `wp/WP-08` (run 38729807727): jobs `ingest` en `web` success; job `db` liep nog bij afronding. Er is geen migratie of SQL gewijzigd.

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `test_idempotent` (4 scenario's, ook `new_state == stored`) en `test_running_window_hourly_sequence` groen. Eigen toets: 3000 willekeurige reeksen van 6 runs met wisselende windows en voortschrijdende `now`. Na `persist` gaf de tweede `diff_windows` steeds 0 events (0 fouten). |
| AC-2 | PASS | `test_new_window`: precies 1 `new` en 1 entry `active`. Eigen reeksen: elk huidig window overlapt na elke run precies 1 actieve entry. |
| AC-3 | PASS | `test_cancel_before_start`, `test_expired_no_event`, `test_cancelled_comes_back`, `test_begun_not_cancelled`, `test_active_beats_cancelled` groen. |
| AC-4 | PASS | `test_small_changes_no_event` (11 gevallen, rand ±1 uur en wind ±2 en 3,9 kn) en `test_threshold_events` (8 gevallen: begin, eind, min en max, elk in beide richtingen) groen. Ze toetsen via `diff_windows` en `classify_change`. |
| AC-5 | PASS | `test_split_equal`, `test_split_unequal`, `test_merge`, `test_split_begun`, `test_deterministic_order`, `test_overlap_repair` en de invarianten in `test_dedup_invariants.py` groen. Eigen toets: de uitkomst voor omgekeerde invoervolgorde van `previous` (met ids) gaf dezelfde events. Er waren geen overlappende events voor dezelfde uren, geen overlappende actieve entries, en elk window overlapt precies 1 actieve entry. |
| AC-6 | PASS | `test_snapshot_json_roundtrip`, `test_snapshot_json_details`, `test_entry_row_roundtrip` groen. De `gust_max_kn=None`-variant zit erin. |
| AC-7 | PASS | `test_golden` voor `new`, `improved`, `worsened`, `cancelled` (6 cases). Zomertijd: 12:00Z wordt 14:00. Wintertijd: 11:00Z wordt 12:00. De getij-regel staat alleen bij een getijgevoelige spot met station en alleen voor extremen binnen het window of 3 uur ervoor of erna. Ik heb de tijden en filtering met de hand nagerekend. Kite staat alleen als `kite` is meegegeven. `go_url` is `None` bij `cancelled` en zonder `base_url`. De golden-tests vergelijken de volledige tekst. |
| AC-8 | PASS | `test_build_go_url_roundtrip` en `test_quote_matches_urllib` groen. Eigen toets: 20.000 willekeurige `spot_id`'s met speciale tekens, unicode, spaties, `?#&=%+` en emoji. `_quote(s) == urllib.parse.quote(s, safe="")` en `parse_qs` leest `spot`, `start` en `end` terug. Invoer in lokale tijd (Amsterdam) geeft UTC met `Z`. |
| AC-9 | PASS | `test_body_max_length` en `test_body_max_length_stress` groen. Eigen worst case (2,5 dagen window, vergelijking met `Was`, kite, 6 getij-extremen): 397 tekens. De structuur begrenst de body (de spotnaam staat alleen in de titel, getij maximaal 6 extremen). |
| AC-10 | PASS | `tests/test_domain_purity.py` groen. `grep -nE "urllib\|import (os\|time\|random\|sys)\|datetime\.now\|open\("` op `dedup.py` en `messages.py` vindt niets. |

## Extra scherpe controles
- **Begonnen windows nooit `cancelled`:** in 3000 reeksen met willekeurige `now` (ook niet-hele uren) had geen enkel `cancelled`-event een entry met `window_start <= now`. Dit gold ook voor de gesimuleerde gedeeltelijke schrijfstaten.
- **Overlapherstel:** ik heb crashstaten gesimuleerd (willekeurig 50% van de updates en inserts verloren, 3000 reeksen). Elke zo ontstane `previous` werd door `diff_windows` geaccepteerd, de tweede diff over de herstelde en gepersisteerde staat gaf 0 events (convergentie, idempotent), en omgekeerde invoervolgorde gaf dezelfde uitkomst. In totaal 41.667 `new`, 20.645 `cancelled`, 8.767 `worsened` en 7.547 `improved` events, dus de scenario's raken alle paden.
- **Puurheid:** geen `urllib`, I/O of klok in `shakka.domain.dedup` of `messages`. De URL-codering is eigen code (`_quote`) en gelijk aan de standaardbibliotheek.

## Harde regels
- Geen secrets in de diff (grep op key, secret, token en password: geen treffers).
- Geen client-side Open-Meteo en geen scraping. Geen nieuwe dienst of dependency.
- Offshore en side-offshore: `WindowSnapshot` weigert `offshore` en `side_offshore` (`test_snapshot_rejects_offshore`). Er zijn geen bypass-parameters (`test_no_bypass_parameters`, in `test_dedup.py` en `test_messages.py`).
- Bronvermelding: niet geraakt (geen UI in deze WP).
- Scope: alleen `ingest/src/shakka/domain/{dedup,messages}.py`, de bijbehorende tests en fixtures onder `ingest/tests/`, `docs/wp/WP-08/*` en `docs/STATUS.md` (todo naar verifying). Geen bestand buiten de scope.
- Blueprint: de afwijkingen staan in `deviations.md` (helper `mw`, gesplitste bypass-test, N-1). Er zijn geen ongedocumenteerde afwijkingen gevonden. De `gust_max_kn: float | None`-afwijking staat al op `develop` in `docs/WORK_PACKAGES.md`.

## Problemen
Geen blokkerende problemen.

Opmerking (geen fail): de drempels `EDGE_SHIFT_THRESHOLD` (2 uur) en `WIND_CHANGE_THRESHOLD_KN` (4 kn) zijn een voorstel dat Lars in de M1-testweek toetst.
