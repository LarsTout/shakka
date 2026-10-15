## WP-13: PWA-basis

- SvelteKit 3 SPA in `/web` (adapter-static met fallback), magic-link-login via Supabase (`shouldCreateUser: false`), bronvermelding in de footer en op `/over`.
- Service worker die alleen de app-shell cachet; manifest met placeholder-iconen; `verify-build` en de Open-Meteo-guard in CI.
- CI-job `web`; `supabase/config.toml` auth-URL's; RUNBOOK §11.
- 87 web-tests, build en guards groen; CI `web` + `ingest` + `db` groen.

**Verificatie:** AC-1..6 PASS en alle harde regels (geen Open-Meteo in `web/`, geen tracking, geen secret in de build). AC-7 (Cloudflare Pages, Supabase Auth-URLs, handmatige login) doet Lars; stappen in RUNBOOK §11 en `docs/wp/WP-13/verification.md`.

**Beslispunten voor Lars:** SvelteKit 3 i.p.v. 2 (daarna regels 891/899/1101 in WORK_PACKAGES bijwerken), Node 24.22.0 op Cloudflare, placeholder-icoon, `shouldCreateUser: false` tot WP-22.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
