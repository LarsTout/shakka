## WP-18: Web Push: PWA

- `PushSettings` op `/alerts`: meldingen aan/uit; toestemming pas na een tik; iOS-uitleg (alleen vanaf beginscherm); `updatePending`-guard bij een wachtende service worker.
- `#lib/push.ts` + `user-data.ts` (vier tabellen; insert alleen `endpoint,p256dh,auth`, select zonder filter, delete op `id`: endpoint nooit in een URL; hooguit 10 rijen). Uitloggen verwijdert eerst de eigen rij.
- Service worker: `push`- en `notificationclick`-handlers (`sw/push.ts`, testbaar), payload `{title,body,url,tag}` conform WP-17; cachet nog steeds nooit Supabase.
- `/login`: installatiehint en "Inloglink plakken" (`verifyOtp` met `token_hash`, alleen eigen origin, `magiclink`/`signup`/`invite`) zodat een iPhone in de beginscherm-app kan inloggen; in-app waarschuwing over de iOS Mail-linkvoorvertoning die het eenmalige token verbruikt (R1: door Apple niet gedocumenteerd, te toetsen in AC-5).
- `PUBLIC_VAPID_PUBLIC_KEY` optioneel; build faalt op een waarde die op een private key lijkt. RUNBOOK §4, §11, §14.
- 617 web-tests, check 0 fouten, build/verify/guard groen; CI groen.

**Verificatie:** AC-1..4 PASS. AC-5 (echte test op iPhone en Android, meten titel 50/body 150, voorvertoning-werkwijze) doet Lars.

**Hiermee is M2 compleet.** Voor Lars: `PUBLIC_VAPID_PUBLIC_KEY` (= `VAPID_PUBLIC_KEY`) als Pages-variabele; A3 (plakveld) bevestigen.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
