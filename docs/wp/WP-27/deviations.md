# Afwijkingen WP-27

Beide afwijkingen van de WP-tekst zijn vooraf in de blueprint (A2, A7) vastgelegd en in review N-1 genoteerd. Geen contract, schema, externe API of acceptatiecriterium raakt eraan.

1. **Eén boeking per run (A2).** De WP zegt "per request één boeking". De job boekt na de stationslus één keer de som (`calls = requests = n`). Impact: dezelfde totalen in `api_usage` als bij AC-1, met één database-roundtrip in plaats van n.
2. **`set`/`unset` in `doctor` (A7).** De WP noemt "gezet" en "niet gezet". De uitvoer van `doctor` is Engels en de bestaande regel heette al `unset   SUPABASE_PUBLISHABLE_KEY (optional)`; daarom `set`/`unset` met suffix `(optional)`. De blueprint noemt een bevestiging van Lars; die is niet in de repo na te lezen. Impact: alleen de gekozen woorden; de tests toetsen ze exact.

Kleine toevoegingen in de bouw (geen afwijking van het contract): extra tests (`test_parse_fetched_at`, `test_rws_usage_nothing_for_invalid_code_only`, `test_rws_usage_nothing_when_budget_gone_before_first`, `test_doctor_blank_optional_is_unset`); `test_pipeline_usage.py` en `test_marine_step_ok_counts` bleven ongewijzigd groen.
