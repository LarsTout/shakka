## WP-06: Kite-advies (puur)

- `shakka.domain.kite`: `ideal_kite_size` (factor × gewicht / wind; 1,8 beginner, 2,2 intermediate/advanced), `pick_from_quiver` (dichtstbijzijnde maat naar verhouding), `classify_fit` (band 1,25), `recommend_kite`, `recommend_for_window` (bovenste mediaan).
- Voorbeeldtabel `ingest/tests/fixtures/kite_examples.yaml` met 26 gevallen, `checked_by_lars: false`.
- 150 tests in `test_kite.py`; monotonie (AC-4/5) door de verifier exhaustief gecontroleerd (0 schendingen). Suite 745 groen; CI groen.

**Verificatie:** AC-1, AC-3..6 PASS. AC-2 open: Lars toetst de 26 gevallen en zet `checked_by_lars: true` (let op review N-1: één bron geeft beginners onder ~18 kn een iets grotere kite).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
