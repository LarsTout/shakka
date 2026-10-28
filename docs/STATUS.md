# Status

Opdeling v2: goedgekeurd (Lars, 15 oktober 2026; scopewijzigingen WP-30 en WP-31 vragen nog expliciet akkoord vóór de start, WP-24 is op verzoek van Lars).

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
| WP-12 | Marine-ingest (golven) en golven op de spotpagina | done | |
| WP-13 | PWA-basis | done | AC-7 open: Cloudflare Pages + Supabase Auth-URLs door Lars (RUNBOOK §11) |
| WP-14 | Spotlijst en spotpagina | done | AC-7 open: Cloudflare Pages, APP_BASE_URL, terugknop-test (RUNBOOK §11.3, §13.2) |
| WP-15 | Kaart | done | AC-6 open: MapTiler-keys + check op de gedeployde site (RUNBOOK §11.9) |
| WP-16 | Profiel, favorieten en alertinstellingen | done | AC-7 open: rooktest in de app door Lars (verification.md O-1) |
| WP-17 | Web Push: backend (enige meldingskanaal) | done | supabase db push (push_subscriptions) door Lars; echte test-push na WP-18 |
| WP-18 | Web Push: PWA | done | AC-5 open: echte push-test op iPhone/Android, meten 50/150 (RUNBOOK §14.12-15) |
| WP-19 | Sessies: datamodel, RLS en RPC's | done | bewaartermijn 7 dagen bevestigen (A1) |
| WP-20 | Sessie aanmaken en delen | done | AC-6 open: telefoontest (push → ik ga → WhatsApp) door Lars |
| WP-21 | Publieke sessiepagina en RSVP zonder account | done | AC-7 open: RSVP-test op telefoon zonder account + noindex in preview (RUNBOOK §16.9) |
| WP-22 | Hardening backend en kostenbewaking | done | AC-6 open: SMTP-keuze, Open-Meteo-mail, OPERATOR_USER_ID (RUNBOOK §18) |
| WP-23 | Privacy, toegankelijkheid en performance | done | AC-6 + privacytekst + Supabase-instellingen (audit logs uit, EU) open voor Lars (RUNBOOK §17) |
| WP-24 | E-mail als tweede meldingskanaal | todo | M5; scopewijziging, akkoord Lars nodig; niet parallel met WP-30 |
| WP-25 | Moderatie voor organisatoren | in_review | M5 |
| WP-26 | Forecast-horizon 8 dagen (`days_ahead` 7 werkt) | done | AC-6 open: query op forecast_hours na promotie naar main en één uurlijkse run (verification.md) |
| WP-27 | Ingest-hygiëne: RWS-verbruik, stationvolgorde, `doctor`, puurheidscheck | todo | M5 |
| WP-28 | Dependabot | done | AC-3 open: Dependabot aanzetten en Insights-controle per ecosysteem door Lars (RUNBOOK §18.10) |
| WP-29 | Inloggen met een code | todo | M5; na eigen SMTP (WP-22) |
| WP-30 | Stille uren voor meldingen | todo | M5; scopewijziging, akkoord Lars nodig; niet parallel met WP-24 |
| WP-31 | Open aanmelden: crew organiseert zelf | todo | M5; scopewijziging, akkoord Lars nodig |
| WP-32 | `cell_selection` per spot | todo | M5; voorwaardelijk: Lars wijst een spot aan |
| WP-33 | Eigen app-icoon en installeerbaarheid | todo | M5; voorwaardelijk: icoon of bevindingen WP-23 AC-6 |

Statussen: `todo`, `blueprint`, `in_review`, `approved`, `building`, `verifying`, `done`, `blocked`, `dropped` (vervallen door een scopebesluit van Lars; wordt niet gebouwd).

Aanbevolen volgorde M2 (zie `docs/WORK_PACKAGES.md`, A-16 en A-17): WP-14 → WP-16 → WP-17 → WP-18 → WP-12 → WP-15.

Aanbevolen volgorde M5 (zie `docs/WORK_PACKAGES_V2.md`). Alles start pas na WP-22 en WP-23.
- Golf 1, parallel: WP-25, WP-26, WP-27 en WP-28.
- Golf 2: WP-29 en WP-30.
- Golf 3: WP-31 (na WP-25 en WP-29) en WP-24 (na WP-30).
- Voorwaardelijk: WP-32 (na WP-26) en WP-33.
