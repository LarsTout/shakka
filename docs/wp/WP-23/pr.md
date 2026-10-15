## WP-23: Privacy, toegankelijkheid en performance

- `/privacy` (tekst ter goedkeuring door Lars) + `docs/PRIVACY.md` (inventaris van tabellen en opslagsleutels); tests lezen bewaartermijnen uit code en migratie. Account verwijderen via `delete_my_account()` (security definer, alleen eigen `auth.uid()`, cascades) met bevestiging op `/profiel`.
- `_headers` gegenereerd bij build: CSP met hash van het SvelteKit-startscript, `Referrer-Policy`, `X-Robots-Tag: noindex` op `/s/*`, caching; niet in de precache.
- Toegankelijkheid: axe-core op alle routes, compilercheck op a11y-waarschuwingen, contrasttest, skiplink.
- Performance: `check-bundle-size.mjs` in CI; initiële JS 102,4 kB (budget 150), precache 595,1 kB (budget 900) gzip. Bronvermelding noemt nu ook DWD/ECMWF-golfmodellen.
- 1092 web-tests; CI `web`/`ingest`/`db` groen (pgTAP 448).

**Verificatie:** AC-1..5 PASS. AC-6 (Lighthouse, installeerbaarheid, testaccount verwijderen op de preview) en de privacytekst doet Lars. `supabase db push` doet de orchestrator.

**Voor Lars:** privacytekst + `PRIVACY_CONTACT_EMAIL`; Supabase: "Write audit logs to the database" uit, EU-regio bevestigen; Cloudflare Web Analytics uit.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
