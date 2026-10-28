# Verificatie WP-25, ronde 1
Resultaat: PASS (AC-1, AC-2 en AC-3 afhankelijk van CI-job `db` op de PR)

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS (statisch), CI-afhankelijk | `supabase test db` niet gedraaid (Docker ontbreekt). `11_organizer_moderation.test.sql` gelezen: eigen verwijdering geeft `true` en de rij is weg, B op A's RSVP geeft `false` en de rij blijft, onbekend id en `null` geven `false`, `anon` krijgt 42501 en `function_privs_are` voor anon is leeg, `rides_with` wordt `null`. `plan(32)` klopt met 32 asserts. Migratie: `security definer`, `search_path = ''`, `grant execute` alleen aan `authenticated`. Er is nog geen PR, dus geen CI-uitkomst. |
| AC-2 | PASS (statisch), CI-afhankelijk | Zelfde bestand: A zet `rsvps_closed_at` (lives_ok, daarna isnt null), B's update raakt 0 rijen (kolom blijft null), insert met de kolom geeft 42501, `rsvp_create` geeft `session_closed` (PT400), `rsvp_update` en `rsvp_delete` met token werken nog, `rsvps_closed` is `true`, de sleutels bevatten geen `organizer_id`, `edit_token` of `email`. `08_session_rpcs.test.sql` en `01_schema.test.sql` zijn bijgewerkt. |
| AC-3 | PASS (statisch), CI-afhankelijk | `07_sessions.test.sql`: `organizer_delete_rsvp` staat in de `authenticated`-lijst en in de `prosecdef`-lijst, `rsvps_closed_at` staat in `columns_are`, `column_privs_are` erbij, `plan(113)`. Groen over alle pgTAP-bestanden is pas bevestigd door CI. |
| AC-4 | PASS | `cd web && npm run check` geeft 0 errors en 0 warnings. `npm test` geeft 95 bestanden en 1132 tests, allemaal groen. `npm run build` slaagt met de CI-placeholders voor `PUBLIC_SUPABASE_*` (zonder die variabelen faalt hij met `env_invalid`, zoals in `ci.yml`). `verify:build` is ok. `manage-page.test.ts` (a) tot (i) en `moderation.test.ts` (22 tests) zijn individueel gedraaid. (a) uitgelogd: loginprompt en 0 db- en rpc-calls. (b) onbekende slug: "Sessie niet gevonden" en 0 rpc-calls. (c) eerst bevestiging, dan precies één call met `{p_rsvp_id}`, rij weg. (g) update met alleen `{rsvps_closed_at}`. |

## Harde regels
- Geen secrets in de diff. De grep op secret, key en `service_role` in `web/src` en docs geeft geen treffers.
- Geen client-side Open-Meteo, geen scraping, geen nieuwe betaalde dienst.
- Bronvermelding niet aangeraakt. Offshore-logica niet aangeraakt.
- Privacy: `PRIVACY.md` bijgewerkt (kolom, RPC en verwijdering door de organisator). `get_public_session` geeft nog steeds geen `organizer_id`.

## Diff versus blueprint en scope
- Alle gewijzigde bestanden liggen binnen `web/`, `supabase/` en `docs/` en horen bij de WP-scope. Er is niets in `ingest`, `data` of `.github` gewijzigd.
- `deviations.md` documenteert N-1, N-3 en N-4 en twee kleine afwijkingen (pgTAP niet lokaal gedraaid, `rpc`-mock). De diff toont geen ongedocumenteerde afwijkingen.
- De migratie volgt de contracten uit de WP-sectie. Het tijdstempel `20261028090000` ligt na de laatste bestaande migratie.

## Problemen
Geen blokkerende problemen.
- NEEDS-CI (geen fail): de pgTAP-suite (`supabase test db`) moet groen zijn in de CI-job `db` zodra de PR er is. Dat is het bewijs voor AC-1, AC-2 en AC-3.
