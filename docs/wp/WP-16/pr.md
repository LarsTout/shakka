## WP-16: Profiel, favorieten en alertinstellingen

- Routes `/profiel` en `/alerts`, favorietenster op `/` en `/spot/[id]`, `LoginPrompt`; alles reageert op `$session` zonder route-load (0 queries uitgelogd).
- `#lib/user-data.ts` is het enige schrijfbestand: profiel via `update` met de vijf toegestane kolommen, favorieten en `alert_rules` alleen eigen rijen. Offshore/side-offshore nergens instelbaar (parser weigert).
- `#lib/rules.ts` `effectiveRule()` spiegelt `resolve_rule` (WP-07); 20 gedeelde gevallen in `data/contracts/rule_resolution_cases.json`, getoetst door `ingest/tests/test_rule_resolution_cases.py` (echte domeincode) én `web/test/rules.test.ts`.
- UI biedt alleen hele uren 01:00–23:00 en `days_ahead` 0–6; schrijft nooit 00:00/24:00. `ruleHints` kan niet gooien. Guards: user-tables, no-telegram, schema-columns, form-ranges.
- 408 web-tests, check 0 fouten, build/verify/guard groen; ingest 1349 groen; CI groen.

**Verificatie:** AC-1..6, AC-8 PASS. AC-7 (rooktest in de app tegen de lokale stack) doet Lars; stappen in `verification.md` O-1.

**Voor Lars:** A9 (niveaulabels Beginner/Gemiddeld/Gevorderd), A10 (bronlabels), A13 (profielconflict als waarschuwing op `/alerts`), A14 (ontfavorieten wist de regel via cascade).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
