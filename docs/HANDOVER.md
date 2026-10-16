# Overdracht na v1 (16 oktober 2026)

Dit bestand is de start voor een nieuwe sessie. Lees daarna `docs/STATUS.md`, `CLAUDE.md` en `.claude/skills/ship/SKILL.md`.

## Stand

- **v1 is compleet:** WP-00 t/m WP-23 staan op `done` (WP-09 `dropped`). Alles is gemerged op `develop` (`097ff95` + docs). Migraties t/m `20261015220100_hardening.sql` staan in het remote Supabase-project.
- **`main`** staat nog op M1 + WP-13/14 (`959bfcb`); de uurlijkse workflow draait daarop (`HOURLY_ENABLED=true`). De promotie `develop` → `main` wacht op één handeling van Lars (zie hieronder).
- **v2 is gepland en goedgekeurd** (`docs/WORK_PACKAGES_V2.md`, WP-24 t/m WP-33, mijlpaal M5) maar **gepauzeerd op verzoek van Lars**: eerst een ander project. De branches `wp/WP-25..28` bestaan met alleen een STATUS-commit; bij hervatten opnieuw aftakken van `develop`.
- **Proces:** sinds PR #31 "lean review" (compacte blueprints, `reviewer-light` voor ronde 2 en S-WP's). Tokenverbruik per rol bewaken is een vaste orchestratortaak (zie geheugen `feedback-token-efficiency`).

## Vóór de promotie naar `main` (Lars)

1. Supabase → Authentication → Sign In / Providers → Email → **"Allow new users to sign up" UIT** (WP-22 zet `shouldCreateUser: true`; deze instelling is het slot). Check: `curl -s -H "apikey: <publishable>" https://tjvfviaopfndfzodhlic.supabase.co/auth/v1/settings` → `disable_signup: true`.
2. Daarna: `git checkout main && git pull && git merge --ff-only origin/develop && git push && git checkout develop`.

## Open voor Lars (niet-technisch, in volgorde van nut)

| # | Wat | Waar |
|---|---|---|
| 1 | Supabase-user voor jezelf (Dashboard → Authentication → Users → Add user, Auto Confirm aan) → uuid in `.env` als `OPERATOR_USER_ID` en als GitHub Secret | WP-10 AC-11, WP-22 |
| 2 | Minstens één spot invullen met `verified: true` in `data/spots.yaml` (lat/lon, `shore_normal_deg`, `status`, `rws_station`); `docs/SPOT_DATA.md` | WP-02 |
| 3 | Cloudflare Pages: root leeg, build `cd web && npm ci && npm run build`, output `web/build`, vars `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NODE_VERSION=24.22.0`, `PUBLIC_VAPID_PUBLIC_KEY` (= `VAPID_PUBLIC_KEY` uit `.env`), `PUBLIC_MAPTILER_KEY`; Actions-variable `APP_BASE_URL` | RUNBOOK §11.3, §13.2 |
| 4 | Supabase Auth URL Configuration (Site URL + Redirect URLs) | RUNBOOK §11.4 |
| 5 | MapTiler: twee keys (productie alleen Pages-domein; lokaal apart) | RUNBOOK §11.9 |
| 6 | Supabase: "Write audit logs to the database" uit; EU-regio bevestigen; Cloudflare Web Analytics uit | WP-23 A13 |
| 7 | Privacytekst goedkeuren + `PRIVACY_CONTACT_EMAIL` | `web/src/routes/privacy`, RUNBOOK §17 |
| 8 | SMTP-keuze: Resend (eigen domein, ±€10/jaar) of Gmail met app-wachtwoord; instellen in Supabase Auth; magic-link-test naar een niet-teamlid | RUNBOOK §18.6 |
| 9 | Mail aan Open-Meteo (niet-commercieel gebruik bevestigen) | RUNBOOK §18.9 |
| 10 | GitHub: e-mailmeldingen voor Actions aan | RUNBOOK §13.2 |
| 11 | Telefoontests: installeren, inloglink plakken (iOS), push aan, `shakka alerts test-push`, "Ik ga" → sessie → WhatsApp, RSVP zonder account | WP-13/18/20/21 AC's |
| 12 | Toetsen in de testweek: `kite_examples.yaml` (`checked_by_lars`), drempelwaarden `defaults.py`, dedup-drempels 2 u/4 kn, `min_go_hours=2`, `days_ahead=3` | WP-05/06/07/08 |

## Beslissingen die nog hangen

- WP-30 (stille uren) en WP-31 (open aanmelden): expliciet akkoord van Lars vóór de start.
- WP-24 (e-mailkanaal): door Lars gevraagd; hangt aan de SMTP-keuze (punt 8).
- `docs/PROJECT_PLAN.md` en RUNBOOK §18.8: MapTiler rekent met MapLibre in requests (100.000/maand), niet in sessions; het plan is daarop gelijkgetrokken in deze PR.

## v2 hervatten

In een verse sessie in `~/Dev/Shakka`: "Lees docs/HANDOVER.md en start v2 golf 1 (WP-25, 26, 27, 28 parallel; merge-volgorde 28, 26, 27, 25)". Per WP: worktree van `origin/develop`, `.env` symlinken, `/ship`-stappen met planner → reviewer(-light) → builder → verifier → PR. Golf 2: WP-29, WP-30; golf 3: WP-31, WP-24. Niet tegelijk: WP-24+WP-30, WP-26+WP-32.

## Opruimen (optioneel)

`git worktree list` toont de v1-worktrees onder `.claude/worktrees/`; `git worktree remove .claude/worktrees/WP-XX` per stuk. Branches `wp/*` blijven bewust staan.
