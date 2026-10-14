# Afwijkingen WP-02

## D1. AC-6 niet lokaal aangetoond (geen Docker-toegang)
- Wat: stap 8 (lokale stack) is niet uitgevoerd. De Docker-daemon is vanuit de builder-omgeving niet bereikbaar (`permission denied` op de socket), dus `supabase start`, `supabase db reset` en de sync tegen echt Postgres zijn niet gedraaid.
- Waarom: omgevingsbeperking, zie blueprint A11 en R2.
- Impact: alleen bewijs, geen ontwerpwijziging. `tests/test_spots_sync_local.py` staat klaar (wordt zonder env overgeslagen). De verifier toont AC-6 met de commando's uit Testplan AC-6, of markeert het als `NEEDS_LARS`.

## D2. Kleine afwijkingen (genoteerd)
- `_LocalTime`-regex in code met een gewone `|` (de `\|` in de blueprint-tabel was markdown-escape), zoals de orchestrator aangaf.
- Extra tests naast het plan: `test_exception_message`, `test_empty_spots_list_is_valid`, `test_validate_missing_file`, `test_validate_needs_no_env`, `test_e15_label_without_id`, `test_e17_format`, `test_e39_single_error`.
- `season` in `FULL_SPOT_YAML` staat over twee regels (flow-sequence, semantisch identiek) vanwege de regellengte-lint (E501).
