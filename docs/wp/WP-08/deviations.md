# Afwijkingen WP-08

Geen afwijkingen die een contract, schema, externe API, dependency of acceptatiecriterium raken.

## Klein (genoteerd, doorgegaan)
- **N-1 uit review ronde 2 (R7 algemener).** In de docstring van `_repair_overlaps` (`dedup.py`) staat R7 als "een dubbele melding" (elke dubbele melding die het herstel kan geven), niet alleen een dubbele `new`. Geen gedragswijziging.
- **Commentaar zonder het woord `urllib`.** Docstrings in `messages.py` verwijzen naar "de standaardbibliotheek-quote", zodat `grep -n "urllib" ingest/src/shakka/domain/*.py` (stap 4) niets vindt. De vergelijkingstest in `test_messages.py` gebruikt `urllib` wel (tests zijn geen domein).
- **Testopzet.** `windows_from_pattern` is in stap 2 toegevoegd, zoals het stappenplan zegt. `test_no_bypass_parameters` is gesplitst: `test_dedup.py` dekt `diff_windows`, `classify_change` en `snapshot_window`; `test_messages.py` dekt `render_alert` en `build_go_url` (anders zou stap 2 afhangen van `messages.py`).
- **Testwinden AC-4.** Voor de AC-4-tests gebruikt `test_dedup.py` een hulpfunctie `mw(start, eind, min, max)` met `wind_min` op het eerste en `wind_max` op het tweede uur. De basislijn `B` is 10:00Z-16:00Z met wind 16-22 kn (de blueprint noemt een andere windlijst, `[16, 18, 20, 22, 20, 18]`), omdat vensters van andere lengte dan dezelfde min en max moeten houden. De beoordeelde uitkomsten zijn gelijk.
- **Tests eerst.** Stap 1 en 2 zijn in dezelfde ronde als de implementatie geschreven en gedraaid; de rode fase is alleen bij stap 3 expliciet doorlopen (collection-error vóór `messages.py`).
- **Looptijd.** `test_dedup_invariants.py` draait in ongeveer 1 seconde (ruim onder 30 s).
