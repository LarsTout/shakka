## WP-05: Evaluatie-engine (puur)

- `shakka.domain.{defaults,direction,consensus,daylight,season,evaluation}` plus `relative_tide_position` in `tide.py`. Alle redenen verzameld; oordeel is het zwaarste effect; `HourEvaluation` met vijf invarianten, `model_copy` hervalideert, `model_construct` verboden in `src`.
- **Harde regel geborgd:** `SIDESHORE_MAX_DEG = 90.0` inclusief, niet configureerbaar; classificatie op de onafgeronde consensusrichting (`dir_mean_deg`, 6 decimalen tegen rekenruis). Verifier: 148.086 evaluaties, 0 afwijkingen.
- Consensus: mediaan wind/vlaag, circulair gemiddelde richting, betrouwbaarheid uit spreiding; ontbrekende vlaag is onbekend, nooit 0; getijvoorkeur op geschat niveau (dubbel laagwater werkt).
- `shakka contracts export [--check]` → `data/contracts/{reason_codes,dir_classes,confidence}.json` met NL-labels, deterministisch.
- `docs/SPOT_DATA.md` §4/§7 bijgewerkt; nieuwe dependency `astral` (in plan).
- 788 tests groen; CI groen.

**Verificatie:** AC-1..11 PASS.

**Voor Lars (M1-testweek):** drempelwaarden in `defaults.py` (wind 12–30 kn, randmarge 2; vlaagratio 1,6/1,9 en ≥ 8 kn; richtingsklassen 22,5/67,5/90/157,5; daglicht ±15 min; betrouwbaarheid ≤4 kn/≤20° high, >8 kn/>45° low; getijbanden 0,3/0,7). Open punt O1: één aflandig model bij sideshore-consensus geeft nu alleen lagere confidence.

**Gevolg voor WP-08:** `WindowSnapshot.gust_max_kn` moet `float | None` worden (een `go`-uur kan geen vlaag hebben).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
