## WP-30: Stille uren voor meldingen

**Wat er nu werkt**
- Op `/alerts` stel je stille uren in (bijv. 22:00–07:00, hele uren, ook over middernacht). "Uit" zet ze weer uit.
- Tijdens de stille uren krijg je geen alerts. Na afloop komt de actuele stand als één melding binnen, zonder inhaalreeks (A1, bevestigd door Lars).
- `run_alerts` telt stille gebruikers als `quiet` (alleen een telling, zonder user-id). De admin-preview negeert stille uren (A7).
- Migratie `20261028120000_quiet_hours.sql`: `profiles.quiet_from` en `quiet_until`, met een CHECK en een kolomgrant voor de eigen rij. pgTAP `12_quiet_hours.test.sql`.
- Privacytekst, `docs/PRIVACY.md` en het RUNBOOK zijn bijgewerkt.

**Zelf proberen (na merge, vanaf `develop`)**
1. `supabase db push`
2. Zet in de app op `/alerts` stille uren die nu lopen, en draai `cd ingest && uv run shakka run-hourly`: de alerts-stap toont `quiet=1` en er komt geen push binnen.

**Verificatie:** PASS (`docs/wp/WP-30/verification.md`). Ingest 1821 passed, web 1159 passed. pgTAP komt uit CI.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
