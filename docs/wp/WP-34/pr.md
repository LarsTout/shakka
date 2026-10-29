## WP-34: Visueel ontwerp: strak, licht en donker (ontwerp B)

**Wat er nu werkt**
- Nieuwe tokens in `web/src/app.css`: één lichte en één donkere set (`prefers-color-scheme`), contrast AA getoetst vanuit de tokens (`contrast.test.ts`, `tokens.test.ts`).
- Rustig ontwerp zonder kaarten en schaduwen: lichte header, spots als rijen met een stip-oordeel en een tijdlijnbalk voor vandaag en morgen.
- `DayTimeline` op vier plekken: spotlijst, spotpagina (per dag, met LW/HW en "nu"), `/s/[slug]` (tijdvak omkaderd) en Stille uren (24 uur).
- Spotpagina met dagtabs; "Toon ook donkere uren" staat na de tabs.
- Tabbalk onderin als je bent ingelogd; formulieren met labels boven de velden.
- Twee `theme-color`-tags; manifest volgt de lichte kleur. Geen externe fonts of CSS.
- Gedrag blijft gelijk, op de dagtabs na. `lib/timeline.ts` is nieuw; `types.ts` en `view.ts` zijn alleen additief (`SpotSummary.hours`, geen extra query).

**Afwijkingen van de WP-tekst** (ontwerp B, verwerkt in `WORK_PACKAGES_V2.md`): AC-2, AC-3 en AC-8 aangepast; AC-10 en AC-11 nieuw.

**Zelf proberen (na merge, vanaf `develop`)**
1. `cd web && npm run dev`
2. Open de app in licht en donker (systeeminstelling) op je telefoon.

**Verificatie:** automatisch PASS, AC-9 goedgekeurd door Lars op 29 oktober 2026 (`docs/wp/WP-34/verification.md`). Web 1248 tests groen.

**Vervolg:** donkere kaartstijl, kitemaat per uur op de spotpagina, tijdlijn op `/sessie/nieuw`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
