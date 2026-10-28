# Privacy-inventaris Shakka

Bijgewerkt in WP-23; wijzig dit bestand samen met `/privacy` en `#lib/privacy.ts`.

## 1. Database (Supabase)

| Gegeven | Tabel en kolommen | Doel | Zichtbaar voor | Bewaartermijn | Verwijderd door |
|---|---|---|---|---|---|
| Account | `auth.users` (o.a. `email`, `created_at`, `last_sign_in_at`), `auth.identities` | Inloggen | Gebruiker zelf, beheerder | Tot het account wordt verwijderd | `delete_my_account()`, of Lars in het dashboard |
| Inlogsessies | `auth.sessions` (o.a. tijdstip, IP-adres, user agent), `auth.refresh_tokens` | Ingelogd blijven | Beheerder | Tot uitloggen of verlopen; met het account | Supabase Auth; cascade |
| Auth-auditlog | `auth.audit_log_entries` | Beveiliging | Beheerder | Leeg als "Write audit logs to the database" uit staat (A13); anders onbeperkt | n.v.t. bij uit |
| Profiel | `public.profiles` (`weight_kg`, `level`, `quiver_m2`, `default_min_kn`, `default_max_kn`); plus een ongebruikte, altijd lege legacy-kolom die WP-22 verwijdert | Kite-advies, alerts | Gebruiker (RLS), ingest | Tot het account wordt verwijderd | cascade |
| Favorieten | `public.favorites` | Alerts, ster | Gebruiker (RLS), ingest | Tot ontfavorieten of het account wordt verwijderd | gebruiker; cascade |
| Alertregels | `public.alert_rules` | Alerts | Gebruiker (RLS), ingest | Idem | gebruiker; cascade via `favorites` |
| Alertstatus | `public.alert_state` (`window_*`, `status`, `snapshot`, `last_*`) | Deduplicatie | Gebruiker (lezen), ingest | 48 uur na `window_end` | `jobs/alerts.py` (`ALERT_STATE_RETENTION`); cascade |
| Push-abonnementen | `public.push_subscriptions` (`endpoint`, `p256dh`, `auth`, `created_at`, `last_success_at`) | Meldingen bezorgen | Gebruiker (RLS), ingest | Tot uitzetten, uitloggen, 404/410 van de pushdienst, of verwijdering van het account | `disablePush`, `jobs/push.py`; cascade |
| Georganiseerde sessies | `public.sessions` (`organizer_id`, `organizer_name`, `note`, `departure_point`, `tikkie_url`, `seats_free`, spot en tijden, `recent_rsvp_creates`, `rsvps_closed_at`) | "Ik ga" | Organisator (RLS); publiek via `get_public_session` (zonder `organizer_id`) | 7 dagen na `ends_at` | `purge_expired_sessions` (`sessions_cleanup`); cascade |
| Aanmeldingen | `public.rsvps` (`first_name`, `ride`, `seats_offered`, `rides_with`, `edit_token_hash`, `created_at`) | "Ik ook" | Publiek via `get_public_session` (zonder hash) | Tot afmelden of verwijdering door de organisator; 7 dagen na `ends_at` | `rsvp_delete`, `organizer_delete_rsvp`; cascade via `sessions` |
| Geen persoonsgegevens | `spots`, `forecast_hours`, `marine_hours`, `tide_extremes`, `evaluations`, `api_usage`, `ingest_runs` | — | — | Forecast-, golf-, getij- en evaluatiedata 48 uur | `jobs/*` |

In de database staat nergens een IP-adres in een `public`-tabel. Er wordt geen locatie opgeslagen.

## 2. Browser

| Opslag | Sleutel | Inhoud | Bewaard tot |
|---|---|---|---|
| `localStorage` | `sb-<project-ref>-auth-token` | supabase-js-sessie | Uitloggen of account verwijderen |
| `localStorage` | `shakka:organizer_name` | voornaam van de organisator | Account verwijderen (`clearAccountLocalData`), of browsergegevens wissen |
| `localStorage` | `shakka:return_to` | `{path, saved_at}` van een `/go`-link | Gewist bij inloggen (`takeReturnTo`). Zonder inloggen: na 60 minuten niet meer gebruikt, en gewist bij de eerstvolgende app-start (`pruneReturnTo`). Ook gewist bij account verwijderen |
| `localStorage` | `shakka:rsvp:{slug}` | `{rsvp_id, edit_token}` | Afmelden, of het openen van de sessiepagina nadat de sessie weg is; anders tot browsergegevens wissen (A9) |
| `sessionStorage` (SvelteKit) | `sveltekit:history-info`, `sveltekit:snapshot`, `sveltekit:navigation-snapshot` | scrollpositie per history-item; snapshots (leeg, Shakka gebruikt ze niet) | Tabblad sluiten |
| Cache API (service worker) | `shakka-shell-<versie>` | alleen app-bestanden | Volgende app-versie (`onActivate`) |
| HTTP-cache van de browser | — | o.a. kaarttegels, fonts en sprites van MapTiler, volgens hun `Cache-Control` | Beheerd door de browser; geen opslag door de app |

MapLibre GL JS 6.14.0 heeft geen eigen tegelcache in de Cache API (gecontroleerd in WP-23: geen `caches.open` in `maplibre-gl/dist`). SvelteKit schrijft alleen de drie genoemde sleutels naar `sessionStorage` (`storage.set(` in `@sveltejs/kit/src/runtime/client`). Er zijn geen cookies van Shakka.

## 3. Logs en derden

- Supabase: API-logs 1 dag, auth-auditlogs 1 uur (gratis plan), regio EU (A13).
- Cloudflare Pages: hosting; Web Analytics uit.
- GitHub Actions: de uurlijkse job leest profielen, favorieten, alertregels, push-abonnementen en `alert_state` (de laatst gemelde windows). Hij schrijft `alert_state`, en werkt `push_subscriptions` bij (`last_success_at`; verwijderen bij 404/410). De logs bevatten geen persoonsgegevens (tests in WP-10, WP-11 en WP-17). De repo is publiek, dus de logs ook.
- Pushdiensten (Apple, Google, Mozilla, Microsoft): endpoint plus versleutelde payload.
- MapTiler: alleen na een klik op "Kaart"; IP, origin, user agent; Referer alleen de origin (`Referrer-Policy`).
- Maildienst: Supabase (tot WP-22).
- Open-Meteo en Rijkswaterstaat: alleen de server, zonder gebruikersgegevens.

## 4. Afdwinging

Waar dit getest wordt:

- `supabase/tests/09_delete_my_account.test.sql`: account verwijderen en de cascade.
- `web/test/retention-consistency.test.ts`: bewaartermijnen in de tekst tegenover de ingest en de migratie.
- `web/test/headers.test.ts` en `verify-build`: de CSP.
- `web/test/no-third-party.test.ts` en `verify-build`: geen trackers.
- `scripts/check-no-client-openmeteo.sh`: Open-Meteo nooit vanuit de browser.

## 5. Checklist bij wijzigingen

Een nieuwe tabel of kolom met persoonsgegevens, een nieuwe `localStorage`-sleutel, een nieuwe externe origin, of een nieuwe kolom die de uurlijkse job leest: werk dit bestand, `/privacy` en zo nodig `web/static/_headers` bij.
