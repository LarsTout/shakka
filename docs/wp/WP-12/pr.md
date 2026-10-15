## WP-12: Marine-ingest (golven) en golven op de spotpagina

- `shakka.openmeteo.marine` (enige plek met de Marine-URL), `shakka.jobs.marine`, `shakka marine fetch`, pipelinestap `marine` na `forecast` (falen → `partial`, exit 0; stale-regel ongewijzigd). Modellen EWAM → ECMWF WAM, drietal uit één model per uur; gewicht 1/spot, geboekt onder `open_meteo_marine` in de gedeelde `BudgetGuard`.
- Migratie `marine_hours` met revoke, expliciete grants (`anon` select) en pgTAP; golven raken oordeel en alerts niet.
- Web: `getMarineHours`, `#lib/marine.ts`, golfregel per uur op `/spot/[id]` (komma-opmaak, rijen > 3 u verborgen, mislukte query → geen golven, geen foutpagina). RUNBOOK §15.
- Fixture: één echte Marine-respons (15 okt 2026), CC BY 4.0. 1529 ingest-tests, 221 web-tests; CI `ingest`/`db`/`web` groen.

**Verificatie:** AC-1..4, 6, 7 PASS. AC-5 (live `marine fetch`) doet de orchestrator na `supabase db push`.

**Voor Lars:** A1 (modelkeuze EWAM → ECMWF WAM), A9 (golven > 3 u oud verborgen), A14 (geen `--dry-run`), A15 (marinefout geen mail).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
