# Verificatie WP-18, ronde 1
Resultaat: NEEDS_LARS

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | `cd web && npm ci && npm run check` 0 errors/0 warnings (incl. SW-tsconfig); `npm test` 53 bestanden / 617 tests groen; `npm run build` en `npm run verify:build` ok, ook met `PUBLIC_VAPID_PUBLIC_KEY=` leeg. Ingest: 1550 passed, 24 skipped (lokale Supabase), ruff check en format ok. `bash scripts/check-no-client-openmeteo.sh` ok. CI op wp/WP-18: success. |
| AC-2 | PASS | `push.test.ts`: `getPushStatus` vraagt nooit toestemming (geen `requestPermission`); `enablePush` roept `requestPermission`, dan `subscribe({userVisibleOnly:true, applicationServerKey: Uint8Array})`, dan insert `{endpoint,p256dh,auth}`; `disablePush` verwijdert de rij vóór `unsubscribe()`. `push-settings.test.ts`: "turns notifications on after a tap, never before". Code gelezen: `requestPermission` is de eerste await in `enablePush`; `updatePending`-guard (`reg.waiting \|\| reg.installing`) aanwezig. |
| AC-3 | PASS | `sw-push.test.ts`: push met WP-17-payload `{title,body,url,tag}` geeft `showNotification(title,{body,icon,tag,data:{url}})`; `notificationclick` focust een venster op exact die URL, anders `openWindow`; fallback en sanering (`javascript:` wordt start-URL). Payloadvelden komen overeen met `ingest/src/shakka/domain/push.py` (`title, body, url, tag`). |
| AC-4 | PASS | `push-settings.test.ts` AC-4 (`it.each` iOS-UA's buiten standalone toont `installFirst`, geen knop; in standalone wel knop); `platform.test.ts`. |
| AC-5 | NEEDS_LARS | Echte test op iPhone en Android: `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare Pages, aanzetten, `uv run shakka alerts test-push --user-id <id>`, tik opent juiste pagina, meten hoeveel van titel (50) en body (150) zichtbaar is. Daarbij ook B-1/R1 (werkt "Verberg linkvoorvertoningen" ook als er geen andere mail met een link is, bijv. via Notities of Safari; deviations N-5). Procedure: blueprint Testplan en RUNBOOK §14 punt 12 t/m 15. |

## Harde regels
- Geen secrets: `git grep` en grep in `web/src`, `web/static`, `web/build`, `docs`, `.github` op `sb_(secret|publishable)_<20+ tekens>` en `eyJhbGciOi` vindt in de diff niets. In `web/build` staan alleen de publishable key en de publieke VAPID-key uit het lokale gitignored `web/.env` (publiek by design). De letterlijke string `sb_secret_` komt alleen voor in de bestaande weigercontrole in `env-schema.ts` en in de foutmelding.
- VAPID-validatie: een willekeurige 43-tekens base64url-waarde (32 bytes) laat `npm run build` falen (exit 1, `env_invalid: ... looks like a private key`). De waarde komt niet in de uitvoer (grep op de waarde: 0 treffers). Een geldige 65-byte key (0x04-prefix) laat build en `verify:build` slagen. Leeg = push uit, build slaagt.
- Geen tracking: geen nieuwe dependencies (`package.json` en lockfile ongewijzigd), geen analytics/tracker-code; alleen de bestaande "geen trackers"-tekst.
- Service worker: `classifyRequest` laat alles van een andere origin door (Supabase wordt nooit gecachet); `sw/push.ts` bevat geen `fetch`. `notificationclick` gebruikt `resolveTargetUrl` (alleen http/https) en focust/opent de juiste URL.
- Endpoint nooit in een request-URL: in `user-data.ts` staat `endpoint` alleen in de insert-body; select zonder filter, delete via `.eq('id', id)`; de koppeling endpoint-naar-rij gebeurt client-side. Test "never logs endpoints or keys" aanwezig.
- `user-data.ts` blijft de enige schrijfmodule voor vier tabellen (profiles, favorites, alert_rules, push_subscriptions); insert alleen `endpoint, p256dh, auth`; `user_id` via column default.
- Uitloggen: `signOut()` roept eerst `releasePushForSignOut()` (disablePush: eigen rij verwijderen, dan unsubscribe; time-out 5 s, blokkeert nooit) en daarna `supabase.auth.signOut({scope:'local'})`. Uitlogknop is `disabled` en toont "Uitloggen…" tijdens uitloggen (`layout.test.ts`).
- B-1: op `/login` in standalone staat de in-app waarschuwing over de iOS-linkvoorvertoning bij "Inloglink plakken" (gekoppeld met `aria-describedby`); `otp_expired` geeft `pastedLinkUsed`; "Check je mail" toont in standalone de kopieer-en-plak-tekst; `parseMagicLink` accepteert alleen de eigen Supabase-origin, pad `/auth/v1/verify` en type `magiclink`/`signup`/`invite` (recovery/email_change geweigerd). Link wordt niet gelogd. Gedekt door `login.test.ts` en `auth.test.ts`.
- Geen client-side Open-Meteo (script ok), geen scraping, geen nieuwe betaalde dienst, bronvermelding niet geraakt, offshore-regels niet geraakt (geen wijziging in ingest).
- Scope: alle wijzigingen liggen in `web/` en `docs/` (WP-18, RUNBOOK, STATUS); niets buiten de scope.
- Diff versus blueprint: afwijkingen staan in `deviations.md` (samengevoegde commit stap 7+8, niet strikt rood-eerst, `abc` geeft de P-256-melding); geen raakt een contract of acceptatiecriterium.

## Problemen
Geen. Alleen AC-5 wacht op Lars (zie boven).
