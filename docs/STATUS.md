# Status

Opdeling: goedgekeurd.

| WP | Naam | Status | Notitie |
|---|---|---|---|
| WP-00 | Repo, tooling, CI en Supabase-koppeling | done | |
| WP-01 | Datamodel M1, RLS en database-client | done | AC-7: `supabase db push` door Lars na merge |
| WP-02 | Spotprofielen: schema, validatie, sync en startset | done | |
| WP-03 | Forecast-ingest wind (Open-Meteo multi-model) met call-budget | done | |
| WP-04 | Getij-ingest (Rijkswaterstaat) | done | |
| WP-05 | Evaluatie-engine (puur) | done | drempelwaarden toetsen in M1-testweek (blueprint 'Drempelwaarden', open punt O1) |
| WP-06 | Kite-advies (puur) | done | AC-2 open: Lars toetst kite_examples.yaml en zet checked_by_lars: true |
| WP-07 | Alertregels en windows (puur) | done | defaults min_go_hours=2, days_ahead=3 toetsen in M1-testweek |
| WP-08 | Alert-deduplicatie en berichtopbouw (puur) | done | drempels 2 uur / 4 kn toetsen in M1-testweek |
| WP-09 | Telegram-kanaal | dropped | Telegram vervallen, zie WP-17 (besluit Lars, 15 oktober 2026) |
| WP-10 | Evaluatie- en alertjobs plus beheer-CLI | done | AC-11 open: M1-check door Lars (RUNBOOK §12, verification.md) |
| WP-11 | Orkestratie: uurlijkse workflow, logging, foutmeldingen | done | AC-6 open: eerste echte run na promotie naar main (RUNBOOK §13) |
| WP-12 | Marine-ingest (golven) en golven op de spotpagina | building | weergave verhuisd uit WP-14 (A-17) |
| WP-13 | PWA-basis | done | AC-7 open: Cloudflare Pages + Supabase Auth-URLs door Lars (RUNBOOK §11) |
| WP-14 | Spotlijst en spotpagina | done | AC-7 open: Cloudflare Pages, APP_BASE_URL, terugknop-test (RUNBOOK §11.3, §13.2) |
| WP-15 | Kaart | todo | |
| WP-16 | Profiel, favorieten en alertinstellingen | done | AC-7 open: rooktest in de app door Lars (verification.md O-1) |
| WP-17 | Web Push: backend (enige meldingskanaal) | done | supabase db push (push_subscriptions) door Lars; echte test-push na WP-18 |
| WP-18 | Web Push: PWA | todo | |
| WP-19 | Sessies: datamodel, RLS en RPC's | todo | |
| WP-20 | Sessie aanmaken en delen | todo | |
| WP-21 | Publieke sessiepagina en RSVP zonder account | todo | |
| WP-22 | Hardening backend en kostenbewaking | todo | |
| WP-23 | Privacy, toegankelijkheid en performance | todo | |

Statussen: `todo`, `blueprint`, `in_review`, `approved`, `building`, `verifying`, `done`, `blocked`, `dropped` (vervallen door een scopebesluit van Lars; wordt niet gebouwd).

Aanbevolen volgorde M2 (zie `docs/WORK_PACKAGES.md`, A-16 en A-17): WP-14 → WP-16 → WP-17 → WP-18 → WP-12 → WP-15.
