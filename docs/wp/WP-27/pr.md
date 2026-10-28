## WP-27: Ingest-hygiëne

**Wat er nu werkt**
- Getijjob boekt het RWS-verbruik in `api_usage` (bron `rws`): één boeking per run met het aantal requests, mislukte meegeteld. Een run die alles overslaat boekt niets.
- Stations worden opgehaald in volgorde: nooit opgehaald eerst, dan oudste `fetched_at`, bij gelijke stand alfabetisch. Zo ververst het budget van 240 s de oudste data eerst.
- Gebruiksrapport heeft de regel `Rijkswaterstaat (7 dagen): <n> requests` (of `onbekend`).
- `shakka doctor` toont per optionele variabele (`APP_BASE_URL`, `VAPID_*`, `OPERATOR_USER_ID`) `set` of `unset (optional)`, zonder waarden. Een ongeldige `SUPABASE_URL` of sleutel geeft één foutregel en exitcode 1, zonder traceback.
- `test_domain_purity.py` vangt ook `datetime.now`, `date.today` enz. zonder aanroep (bijv. `default_factory=datetime.now`).

**Zelf proberen** (vanaf `develop` na de merge)
```bash
cd ingest && uv run shakka doctor
```

**Niet-blokkerende punten**
- Afwijking A7: `doctor` gebruikt `set`/`unset` i.p.v. "gezet"/"niet gezet", omdat de doctor-uitvoer Engels is. Lars: bevestig of zeg het als je toch Nederlands wilt.
- Afwijking A2: één boeking per run met de som i.p.v. per request; de totalen zijn gelijk.
- Raakpunt met WP-26: alleen `docs/RUNBOOK.md` (andere secties).

Tests: 1789 passed, 24 skipped (live-Supabase); ruff groen. Verificatie: PASS (`docs/wp/WP-27/verification.md`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
