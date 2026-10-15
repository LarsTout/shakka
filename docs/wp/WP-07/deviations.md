# Afwijkingen WP-07

Allemaal klein; geen contract, schema of acceptatiecriterium geraakt.

- **N-1 (review ronde 2):** `telegram_chat_id` komt niet voor in het voorbeeld of de tests. `test_profile_from_row` gebruikt een profielrij met `weight_kg`, `level` en `quiver_m2`; Telegram is inmiddels geschrapt uit het project.
- **N-3 (review ronde 2):** pydantic zet "Value error, " voor de melding van een `ValueError` uit een validator. `test_end_of_day_time` toetst daarom op een deel van de melding (`earliest_local 24:00 matches no hour`, via `match=`), niet op de volledige tekst.
- **Tests (naamgeving/indeling):** `test_other_ranges` uit het testplan is gesplitst in `test_other_ranges_override` (geparametriseerd) en `test_other_ranges_rule_and_bounds`; `test_priority` heeft een extra test `test_priority_spot_level_derived_max` en `test_edge_cases_resolution` (E3, E6) erbij. `alert_fixtures.py` importeert `evaluation_fixtures` zonder `tests.`-prefix, zoals de bestaande tests (geen `tests/__init__.py`).
- **`alerts.py` intern:** `_RevalidatingModel.model_copy` gebruikt `dict(self)` (veldwaarden) in plaats van `model_dump()`, zodat frozensets en `HourEvaluation`-instanties intact blijven; de kopie wordt alsnog volledig via `model_validate` gevalideerd. `_qualifies` heeft `last_day` getypt als `Any` (geen `date`-import, conform de importlijst in de blueprint).
- **`test_no_bypass_parameters`:** in stap 1 (commit 1) nog zonder de `find_windows`-regels, omdat die functie pas in stap 2 bestaat; in commit 2 toegevoegd.
