# Review WP-18, ronde 1
Oordeel: CHANGES_REQUIRED

Samenvatting: de blueprint is grondig en klopt op bijna alle punten met WP-13, WP-16, WP-17 en de bestaande code. Wat ik heb nagelopen:

- **Harde regels.** Geen tracking. `PUBLIC_VAPID_PUBLIC_KEY` is publiek, en de build weigert een waarde van 32 bytes. De service worker doet geen fetch en cachet niets nieuws. Het endpoint komt nooit in een URL: select zonder filter, delete op `id`, insert met de waarden in de body.
- **WP-17-contract.** De payload is `{title, body, url, tag}`, met test-push `url "/"` en `tag "shakka-test"`. De insert stuurt precies `endpoint`, `p256dh` en `auth`; dat is een deelverzameling van de grant `(user_id, endpoint, p256dh, auth)`, en `user_id` komt uit de default `auth.uid()`. Verder: `23505` op het unieke `endpoint`, hoogstens 10 abonnementen, en bij uitloggen gaat eerst de rij weg.
- **WP-16.** `user-data.ts` blijft de enige module die schrijft. `user-tables.test.ts` gaat naar vier tabellen, met een kloppende insert-regex.
- **iOS.** Toestemming wordt synchroon in de tik gevraagd, en het plakveld is er alleen in standalone-modus.

A3 is technisch juist. Ik heb het in de broncode van Supabase Auth gecontroleerd:
- De magic link is `…/auth/v1/verify?token=<RecoveryToken-hash>&type=magiclink&redirect_to=…`.
- `POST /verify` met `token_hash` en `magiclink` zoekt op hetzelfde recovery-token.
- `EmailOtpType` bevat `'magiclink'`.

Eén blokkerend punt zit in de gebruikersinstructie rond die link.

## Blokkerend

B-1: **De in-app-instructie voor "Inloglink plakken" leidt in de standaard Mail-app van iOS tot een verbruikte link.**
- **Waar:** `routes/login/+page.svelte`, sectie "Inloglink plakken" (tekst: "houd hem ingedrukt, kies 'Kopieer link' en plak hem hier"). Verder A3, R1 en RUNBOOK §11 punt 5.
- **Waarom:**
  - In iOS Mail opent ingedrukt houden van een link standaard een live voorvertoning van de pagina. Die doet een `GET /auth/v1/verify?token=…`. In `verify.go` behandelt GET de `token` als `token_hash`, via hetzelfde verificatiepad als POST, dus het eenmalige token is dan op.
  - De gebruiker volgt de instructie letterlijk. Het plakken geeft dan `linkExpired` ("vraag een nieuwe aan"). Bij de volgende mail gebeurt precies hetzelfde.
  - De mitigatie (voorvertoning uitzetten, of via de Mac kopiëren) staat alleen in de RUNBOOK, dus alleen Lars kent haar.
  - De standaard-SMTP stuurt hoogstens 2 mails per uur (RUNBOOK §11 punt 5). Na één mislukte poging zit een iPhone-gebruiker dus vast. Dit is het enige pad naar push op iOS, en AC-5 op een iPhone hangt ervan af.
  - Daarnaast zegt het scherm "Check je mail" in standalone-modus "Open de link op dit apparaat om in te loggen". Dat spreekt het plakveld eronder tegen: daar staat "Tik de link daarom niet aan".
- **Voorstel:**
  - Zet de waarschuwing in de app zelf, in de hint van het plakveld. Bijvoorbeeld: "Zie je bij ingedrukt houden een voorbeeld van de pagina? Kies dan eerst 'Verberg voorvertoning': het voorbeeld gebruikt de link al op. Of kopieer de link op een ander apparaat."
  - Geef bij `otp_expired` in de plak-context dezelfde hint mee: een eigen tekst of een extra regel onder `linkExpired`.
  - Pas in standalone-modus de tekst "Open de link op dit apparaat" aan, of laat die zin weg.
  - Leg in `login.test.ts` met een test vast dat de hint over de voorvertoning er in standalone-modus staat.

## Niet-blokkerend

**N-1: De test van `readPlatform()` in Node faalt zoals hij er nu staat.**
- **Waar:** Testplan, `platform.test.ts` ("`readPlatform()` zonder `navigator` (node) geeft `{ userAgent: '' … }`").
- **Waarom:**
  - Node 21+ heeft een globale `navigator` met `userAgent` `"Node.js/24…"`, en het project eist Node ^24.15. De verwachte `''` klopt dus niet.
  - Verder bestaat `window` niet in Node. `typeof window.matchMedia` gooit daar een ReferenceError, tenzij `readPlatform` eerst op `typeof window !== 'undefined'` controleert.
- **Voorstel:** in de test `vi.stubGlobal('navigator', undefined)` gebruiken, of de verwachting omzetten naar "geen iOS, niet standalone". Schrijf in de interface expliciet `typeof window !== 'undefined' && typeof window.matchMedia === 'function'`.

**N-2: De typering van `withTimeout(navigator.serviceWorker.ready, SW_READY_TIMEOUT_MS, null)` compileert niet.**
- **Waar:** `enablePush`.
- **Waarom:** TS leidt `T = ServiceWorkerRegistration` af, en `null` past daar niet in. `npm run check` faalt dan.
- **Voorstel:** schrijf `withTimeout<ServiceWorkerRegistration | null>(…)` letterlijk zo in de blueprint.

**N-3: De nieuwe service worker na de deploy (R5, E31, RUNBOOK §14 punt 13).**
- `skipWaiting` terecht buiten scope laten: het zou de garantie uit WP-13 A7 breken dat oude shell en oude chunks bij elkaar passen.
- Eén keer sluiten en openen is alleen niet altijd genoeg:
  - Opent Lars de app na de deploy voor het eerst opnieuw, dan ziet de browser de update pas bij die navigatie.
  - De nieuwe worker wacht dan, omdat die pagina nog door de oude wordt beheerd.
  - Ondertussen laadt de pagina de nieuwe UI wel van het netwerk (navigatie gaat netwerk-eerst), dus "Meldingen aanzetten" werkt al. Pushes gaan dan nog naar de oude worker zonder `push`-handler: Chrome toont een eigen melding, en op iOS telt het als stille push.
- **Voorstel (goedkoop, binnen WP-13):**
  - In `enablePush`: na `ready`, als `reg.waiting || reg.installing` gezet is, een vaste melding tonen ("Er staat een nieuwe versie van Shakka klaar. Sluit de app helemaal en open hem opnieuw.") en niet abonneren.
  - In de RUNBOOK: "sluit en open opnieuw tot de knop werkt", of "twee keer".

**N-4: De terugvaloptie in R2 dekt niet het geval dat `vi.mock('$app/env/public')` helemaal niet werkt.**
- **Waarom:** de docs zeggen dat statische variabelen "inlined into the bundle" worden. Over vitest en mocken zeggen ze niets. R2 dekt alleen het geval waarin een mutatie van `publicEnv` niet wordt gezien.
- **Voorstel:** als tweede terugvaloptie in `vite.config.ts` `TEST_ENV.PUBLIC_VAPID_PUBLIC_KEY = TEST_VAPID_PUBLIC_KEY` zetten (alleen `mode === 'test'`). "Zonder sleutel" toets je dan via `vapidKeyBytes(undefined)`, en de afwijking komt in `deviations.md`. R3 (optionele variabele) is volgens de docs in orde: "Returning `undefined` is valid, so a function can describe an optional variable."

**N-5: Links met `type=signup` of `type=invite` worden geweigerd.**
- **Waar:** `parseMagicLink`.
- **Waarom:** heeft een gebruiker zijn e-mailadres nog niet bevestigd (bijv. via Invite aangemaakt), dan stuurt Supabase een link van dat type. `verifyOtp` met `token_hash` accepteert die types ook.
- **Voorstel:** `magiclink`, `signup` en `invite` toestaan en dat type doorgeven aan `verifyOtp`. Of in de RUNBOOK expliciet zeggen: gebruikers aanmaken met "Auto confirm".

**N-6: De toestemmingsfout staat twee keer in beeld.**
- **Waar:** `PushSettings`, bij `requestResult: 'denied'`.
- **Waarom:** de status-tak toont `PUSH_MESSAGES.denied`, en `message` (role="alert") toont dezelfde tekst nog een keer.
- **Voorstel:** `message` op `null` laten als de status `denied` wordt, of in de denied-tak alleen de alert tonen. Test 5 moet dan op `getByRole('alert')` zoeken, zodat hij niet op twee gelijke teksten struikelt.

**N-7: Het plakveld flitst kort op tijdens het laden van de sessie.**
- **Waar:** `/login`, `{#if !$session && standalone}`.
- **Waarom:** het veld staat er ook zolang `$session === undefined` (auth nog niet geladen).
- **Voorstel:** `$session === null && standalone`.

**N-8: Uitloggen kan tot 5 s hangen zonder zichtbare feedback.**
- **Waar:** de knop "Uitloggen" in de layout.
- **Waarom:** `releasePushForSignOut` kan tot 5 s duren, en in die tijd gebeurt er op het scherm niets.
- **Voorstel:** acceptabel als de builder het noteert. Anders de knop disabled maken tijdens het uitloggen.

**N-9: De `grep … | sed … >> web/.env`-regel voegt een tweede regel toe.**
- **Waar:** RUNBOOK §11 punt 1.
- **Waarom:** als `web/.env` al `PUBLIC_VAPID_PUBLIC_KEY=` uit `.env.example` bevat, komt de sleutel er twee keer in. Dotenv neemt de laatste waarde, dus het werkt wel, maar het is verwarrend.
- **Voorstel:** noem het in de tekst ("verwijder eerst de lege regel"), of laat de lege regel weg uit de kopie.

**N-10: Het merge-risico met WP-15 is klein en additief.**
- Conflicten die je kunt verwachten:
  - de importregel in `env.ts`;
  - de verwachte lijst in `env-example.test.ts` (WP-15 voorziet `PUBLIC_VAPID_PUBLIC_KEY` al als vierde regel);
  - het eind van `.env.example`, `env-schema.ts` en `env-schema.test.ts`;
  - een rij in RUNBOOK §4, en §11 (WP-15 voegt punt 9 toe, WP-18 past punt 1, 3 en 5 aan).
- WP-15 raakt `app.css` niet. `lib/platform.ts` (WP-18) en `lib/map/platform.ts` (WP-15) hebben verschillende paden.
- **Voorstel:** schrijf in R7 dat de tweede merge `env-example.test.ts` op vier sleutels zet.

**N-11: `OTHER_VAPID_PUBLIC_KEY = 'B' + 'Q'.repeat(86)` is geen geldige sleutel.**
- Na decoderen begint hij met `0x05`. Voor `sameKey` maakt dat niet uit, maar gebruik hem nooit in `publicEnv` of in de tests van `parseVapidPublicKey`.

## Gecontroleerde bronnen
- https://svelte.dev/docs/kit/@sveltejs-kit-env (`schema` mag `undefined` teruggeven; `static` wordt ingelined)
- https://svelte.dev/docs/kit/$app-env-public
- https://raw.githubusercontent.com/supabase/auth/master/internal/mailer/templatemailer/templatemailer.go (magic link = `token=<RecoveryToken>&type=magiclink&redirect_to=…`)
- https://raw.githubusercontent.com/supabase/auth/master/internal/api/verify.go (POST `token_hash` met magiclink, `FindUserByOneTimeToken(…, RecoveryToken)`; GET zet `token` om naar `TokenHash`, zelfde pad)
- https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/auth-js/src/lib/types.ts (`EmailOtpType` met `'magiclink'`, `VerifyTokenHashParams`)
- https://supabase.com/docs/reference/javascript/auth-verifyotp
- https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ (alleen als beginschermapp; toestemming als reactie op een directe gebruikersactie)
- https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe (`applicationServerKey`, `userVisibleOnly`, gebruikersgebaar)
- https://github.com/andreinwald/webpush-ios-example (`subscribe` na een `await` werkt op iOS)
- Lokaal: `supabase/migrations/20261015150000_push_subscriptions.sql`, `docs/wp/WP-17/blueprint.md`, `docs/wp/WP-16/blueprint.md`, `docs/wp/WP-13/blueprint.md`, `.claude/worktrees/WP-15/docs/wp/WP-15/blueprint.md`, `web/src/**` (`env.ts`, `env-schema.ts`, `auth.ts`, `supabase.ts`, `user-data.ts`, `service-worker/index.ts`, `sw/shell.ts`, `sw-register.ts`, `routes/alerts`, `routes/login`, `+layout.*`), `web/test/**` (`user-tables`, `schema-columns`, `env-example`, `alerts-page`, `login`, `auth`, `fake-supabase`, `fake-session`), `web/vite.config.ts`, `web/package.json`, `web/scripts/verify-build.mjs`, `docs/RUNBOOK.md`.
