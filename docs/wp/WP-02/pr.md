## WP-02: Spotprofielen: schema, validatie, sync en startset

- `shakka.domain.spot`: bevroren pydantic-modellen en enums voor spotprofielen.
- `shakka spots validate` en `shakka spots sync` (upsert zonder delete, wezen alleen gemeld).
- `data/spots.yaml`: startset van 25 spots met alleen `id`, `name`, `verified: false`.
- `docs/SPOT_DATA.md`: invulinstructies per veld.
- 324 tests groen; CI `ingest` + `db` groen.

**Verificatie:** AC-1..5 en AC-7 PASS. AC-6 (sync tegen lokale stack) wordt na de merge op `develop` door Lars gedraaid; stappen in `docs/wp/WP-02/verification.md`.

**Beslispunten voor Lars:** zie "Aannames" in de blueprint (PyYAML, extra validatieregels, YAML wint van dashboard, wezen = waarschuwing).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
