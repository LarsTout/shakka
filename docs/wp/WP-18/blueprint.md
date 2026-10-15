# Blueprint WP-18: Web Push: PWA
Status: APPROVED
Revisie: 2

## Verwerking review
Ronde 1 (`docs/wp/WP-18/review.md`, CHANGES_REQUIRED). De bestandsverwijzingen en sectienummers gaan nu uit van `develop` na de rebase, dus met WP-12 en WP-15 erin: `env.ts` heeft al `PUBLIC_MAPTILER_KEY`, `.env.example` en `env-example.test.ts` hebben drie sleutels, RUNBOOK §11 punt 9 (Kaart) en §15 (Golven) bestaan.

| Punt | Verwerking |
|---|---|
| **B-1** (instructie bij "Inloglink plakken" verbruikt de link in iOS Mail) | Overgenomen. (1) De sectie "Inloglink plakken" op `/login` heeft een eigen waarschuwing (`.notice`). Daarin staat: de link werkt één keer en een voorvertoning gebruikt hem op. Eerst bij een link in een *andere* mail "Verberg linkvoorvertoningen" kiezen, dan de inloglink ingedrukt houden en "Kopieer link" kiezen. Alternatief: kopiëren op een computer en plakken via het gedeelde klembord, niet via WhatsApp of Berichten. (2) `otp_expired` geeft in de plak-context een eigen tekst `AUTH_MESSAGES.pastedLinkUsed`, die de voorvertoning noemt. (3) "Check je mail" zegt in standalone-modus niet meer "Open de link op dit apparaat", maar "Tik de link niet aan: kopieer hem en plak hem hieronder". (4) `login.test.ts` heeft tests voor de waarschuwing, de tekst bij `otp_expired` en de tekst van "Check je mail" in en buiten standalone. Volgens de bronnen (zie Externe afhankelijkheden) laadt de voorvertoning de pagina, en onthoudt iOS de keuze "Verberg linkvoorvertoningen" voor volgende links. Dat het in Mail werkt zoals in Safari, is niet door Apple gedocumenteerd. Daarom staat het als risico R1 vast, en controleert AC-5 het op een iPhone. RUNBOOK §11 punt 5 zegt hetzelfde. |
| **N-1** (`readPlatform` in Node) | Overgenomen. `readPlatform` controleert `typeof navigator !== 'undefined'` en `typeof window !== 'undefined' && typeof window.matchMedia === 'function'`. In `platform.test.ts` staat `vi.stubGlobal('navigator', undefined)` met `afterEach(vi.unstubAllGlobals)`. Een tweede test, zonder stub, eist alleen "gooit niet, geen iOS, niet standalone", want Node 24 heeft een globale `navigator`. |
| **N-2** (typering `withTimeout`) | Overgenomen. Alle drie aanroepen hebben een expliciet typeargument (`<ServiceWorkerRegistration \| null>`, `<ServiceWorkerRegistration \| undefined>`, `<void>`). |
| **N-3** (nieuwe service worker wacht) | Overgenomen. `enablePush` geeft na `ready` de melding `PUSH_MESSAGES.updatePending` als `reg.waiting` of `reg.installing` gezet is, en abonneert dan niet (E36, `push.test.ts` geval 10b). RUNBOOK §14 punt 13 zegt nu: sluit en open opnieuw tot de knop werkt, soms twee keer. |
| **N-4** (terugvaloptie als de mock van `$app/env/public` niet werkt) | Overgenomen, maar met een andere terugvaloptie dan `TEST_ENV`. WP-15 heeft vastgesteld (`docs/wp/WP-15/deviations.md`, N-7): `$app/env/public` resolvet in vitest *alleen* met een mock (`globalThis.__sveltekit_dev` ontbreekt). Een waarde in `TEST_ENV` komt dus nooit bij `push.ts`. Dat `vi.mock('$app/env/public', factory)` werkt, laten `spot-list.test.ts` en `home-no-map.test.ts` zien. R2 heeft nu twee terugvalopties voor het enige open punt, een mutatie van `publicEnv` die niet zichtbaar is: (a) per test `vi.resetModules()` + `vi.doMock('$app/env/public', …)` + dynamische `import('#lib/push.js')`; (b) een apart testbestand per sleutelwaarde, zoals WP-15 deed. `vite.config.ts` blijft ongewijzigd. |
| **N-5** (`type=signup`/`invite`) | Overgenomen. `parseMagicLink` accepteert `magiclink`, `signup` en `invite`, en geeft het type door aan `verifyOtp`. In de broncode van Supabase Auth gecontroleerd: `signup` en `invite` gebruiken `ConfirmationToken`, `magiclink` het `RecoveryToken`, en POST `/verify` met `token_hash` geeft voor alle drie een sessie. `recovery` en `email_change` blijven geweigerd. |
| **N-6** (toestemmingsfout dubbel in beeld) | Overgenomen. Bij `denied` na een klik wordt `message = null` en `status = 'denied'`. De tekst staat dan één keer in beeld. Test 5 eist `getAllByText(PUSH_MESSAGES.denied)` met lengte 1. |
| **N-7** (plakveld flitst) | Overgenomen: `{#if $session === null && standalone}`. De tests in `login.test.ts` zetten de sessie expliciet op `null` via `initAuth()` met een `onAuthStateChange`-mock. |
| **N-8** (uitloggen zonder feedback) | Overgenomen. In `+layout.svelte` is de knop tijdens het uitloggen `disabled`, met de tekst "Uitloggen…". Test in `layout.test.ts`. |
| **N-9** (dubbele regel in `web/.env`) | Overgenomen. RUNBOOK §11 punt 1 zegt eerst de lege regel `PUBLIC_VAPID_PUBLIC_KEY=` te verwijderen. |
| **N-10** (merge met WP-15) | Overgenomen. De blueprint beschrijft de toestand na de rebase: de importregel in `env.ts` met vier parsers, vier sleutels in `env-example.test.ts`, de nieuwe regel in `.env.example` na `PUBLIC_MAPTILER_KEY=`, en de rij in RUNBOOK §4 na `PUBLIC_MAPTILER_KEY`. R7 en stap 0 van het stappenplan controleren de rebase. |
| **N-11** (`OTHER_VAPID_PUBLIC_KEY` ongeldig) | Overgenomen. `OTHER_VAPID_PUBLIC_KEY = 'B' + 'A'.repeat(42) + 'Q' + 'A'.repeat(43)` is nu een geldige vorm (65 bytes, eerste byte `0x04`), en `env-schema.test.ts` controleert dat. |
| Extra (geen reviewpunt) | `parseVapidPublicKey` geeft nu `''` in plaats van `undefined` terug als de variabele leeg is, net als `parseMaptilerKey` (WP-15). WP-15 heeft bevestigd dat een build met een lege of ontbrekende optionele variabele slaagt; daarmee vervalt het grootste deel van R3. |

## Doel
Ingelogde gebruikers zetten op hun telefoon (of computer) met één tik pushmeldingen aan op `/alerts`. De service worker toont binnenkomende alerts uit WP-17, en een tik op een melding opent de juiste pagina. Concreet:
1. `PUBLIC_VAPID_PUBLIC_KEY` als publieke build-variabele, met validatie die de private key weigert.
2. `#lib/push.ts` met `isPushSupported`, `needsInstallFirst`, `enablePush`, `disablePush` (contract), plus `getPushStatus` en `releasePushForSignOut`.
3. Schrijven naar `push_subscriptions` via `#lib/user-data.ts` (blijft de enige schrijfmodule).
4. `push`- en `notificationclick`-handlers in `src/service-worker/index.ts`, met de logica in `#lib/sw/push.ts` (te testen in vitest).
5. Op `/alerts` een sectie "Meldingen op dit apparaat"; op iOS buiten de beginschermapp een installatie-uitleg in plaats van de knop.
6. Bij uitloggen eerst het abonnement van dit apparaat opruimen (WP-17, "Gevolgen"), met zichtbare feedback.
7. Voorstel (A3): op iOS in de beginschermapp inloggen door de inloglink te plakken, omdat de magic link in Safari opent en push daar niet kan. De app waarschuwt zelf voor de linkvoorvertoning die de link verbruikt.

## Aannames
Voorstellen waar Lars op kan reageren staan als **Voorstel**.

- **A1. Databasetoegang voor `push_subscriptions` komt in `user-data.ts`, niet in `push.ts`.** WP-16 maakte `user-data.ts` de enige module die gebruikersgegevens schrijft, bewaakt door `user-tables.test.ts`. Die regel blijft zo eenvoudig mogelijk: `push.ts` bevat alleen de browserkant (Notification, service worker, PushManager) en roept drie nieuwe functies in `user-data.ts` aan. `user-tables.test.ts` krijgt `push_subscriptions` erbij als vierde tabel, met insert toegestaan op `favorites` en `push_subscriptions`. Dit wijkt af van de suggestie in WP-16 ("`push.ts` schrijft `push_subscriptions`"); WP-16 liet de keuze aan WP-18.
- **A2. Geen user-id en geen endpoint in request-URL's.** De insert stuurt alleen `endpoint`, `p256dh` en `auth` in de body; `user_id` volgt uit de kolomdefault `auth.uid()` (WP-17). Het eigen abonnement zoeken gaat door de eigen rijen op te halen (`select id,endpoint,created_at`, RLS geeft alleen eigen rijen) en in de browser te vergelijken. Verwijderen gaat op `id`. Zo komt het endpoint (een capability-URL) nooit in een query-string en dus niet in de request-logs van Supabase. `push.ts` hoeft de sessie daardoor ook niet te kennen (geen import van `auth.ts`, geen kringverwijzing).
- **A3. Voorstel: inloggen met een geplakte inloglink in de beginschermapp.** Op iOS heeft een app op het beginscherm eigen opslag; de magic link uit de mail opent in Safari en logt dáár in (WP-13 R3). Push werkt op iOS alleen in de beginschermapp, dus zonder dit kan een iPhone-gebruiker geen meldingen aanzetten. Inloggen met een code vraagt een aangepast mailtemplate, en dat kan op het gratis plan pas met eigen SMTP (WP-13 A6, WP-22). De link zelf bevat al alles: `https://<ref>.supabase.co/auth/v1/verify?token=<token-hash>&type=magiclink&redirect_to=…` (gecontroleerd in de broncode van Supabase Auth, zie Externe afhankelijkheden). `supabase.auth.verifyOtp({ token_hash, type })` wisselt die hash in voor een sessie. Een gebruiker met een nog niet bevestigd adres krijgt een link met `type=signup` of `type=invite`; die worden ook geaccepteerd (zelfde mechanisme, `ConfirmationToken`). Op `/login` komt daarom, alleen in standalone-modus en alleen als de gebruiker zeker uitgelogd is, een sectie "Inloglink plakken". **De link is eenmalig, en een linkvoorvertoning (ingedrukt houden in iOS Mail) laadt hem en verbruikt hem.** Daarom staat de waarschuwing met de werkwijze in de app zelf, bij het plakveld, en noemt de foutmelding bij een verbruikte link de oorzaak. Geen nieuwe dienst, geen wijziging aan Supabase. Wijst Lars dit af, dan vervallen stap 7 (deel geplakte link) en 8 van het stappenplan; AC-5 kan dan alleen op Android of een computer.
- **A4. `PUBLIC_VAPID_PUBLIC_KEY` is optioneel.** Leeg of afwezig betekent: push is in deze build niet beschikbaar ("Meldingen zijn in deze versie van Shakka nog niet beschikbaar."). Het schema geeft dan `''` terug, net als `parseMaptilerKey` (WP-15). Zo faalt geen preview-build zolang de variabele nog niet in Cloudflare staat, en hebben CI en de tests hem niet nodig. Een ingevulde maar ongeldige waarde laat de build falen. Een waarde die op een private key lijkt (32 bytes) geeft een expliciete fout, net als `sb_secret_` bij de Supabase-sleutel.
- **A5. Uitzetten en uitloggen: eerst de rij verwijderen, dan `subscription.unsubscribe()`.** Volgorde uit WP-17. Mislukt het verwijderen (offline, verlopen sessie), dan wordt toch afgemeld bij de browser: het endpoint is dan dood, de push-service geeft 404/410, en WP-17 ruimt de rij bij de volgende aflevering op. Voor de gebruiker staat push dus altijd uit na "Meldingen uitzetten" of "Uitloggen". `disablePush` gooit nooit.
- **A6. Uitloggen ruimt het abonnement van dit apparaat op** (WP-17, review N-7), met een tijdslimiet van 5 seconden zodat uitloggen nooit blijft hangen. Dit gebeurt in `signOut()` in `auth.ts`, zodat elk uitlogpad het doet. De knop "Uitloggen" in de layout is in die tijd uitgeschakeld en toont "Uitloggen…".
- **A7. Endpoint van een ander account op hetzelfde apparaat.** Geeft de insert `23505` en staat het endpoint niet bij de eigen rijen, dan hoort het bij een ander account dat hier ooit meldingen aanzette en niet uitlogde (of waarvan de sessie verliep). Dan meldt `enablePush` dat abonnement af bij de browser, maakt een nieuw abonnement (nieuw endpoint) en voegt dat in. Het oude endpoint is daarmee dood en wordt door WP-17 opgeruimd (410). Zo komen de meldingen van het vorige account niet meer op dit apparaat. Geeft ook het nieuwe endpoint `23505`, dan volgt een melding.
- **A8. Hoogstens 10 abonnementen per gebruiker, ook in de app.** WP-17 bedient alleen de 10 nieuwste (`MAX_TARGETS_PER_USER`). Na een geslaagde aanmelding verwijdert de app de eigen rijen boven die 10 (oudste eerst, nooit het huidige endpoint). Zo klopt de status "aan" op elk apparaat met wat de backend werkelijk bedient: een weggevallen apparaat toont daarna "uit". Een grens in de database blijft WP-22.
- **A9. Uitleg "nieuwe windows" bij aanzetten** (WP-17 A1, "Gevolgen"). Bij de knop staat: meldingen gaan over nieuwe windows en wijzigingen; een window dat al liep, meldt Shakka pas bij een wijziging. De handmatige reset uit RUNBOOK §14 punt 9 blijft de enige ingreep.
- **A10. Geen `renotify`, geen acties, geen badge.** Een melding met dezelfde `tag` vervangt de vorige stil (standaardgedrag). `renotify` wordt niet door alle browsers ondersteund en valt buiten de payload uit WP-17. `icon` is het bestaande app-icoon `/icons/icon-192.png`.
- **A11. `notificationclick`: exact dezelfde URL focussen, anders `clients.openWindow(url)`.** Het patroon uit MDN. Geen `WindowClient.navigate()`: dat werkt alleen voor vensters die door de service worker worden beheerd, en zonder `clients.claim()` (WP-13 A7) is dat bij de eerste pagina niet zo. De URL uit de payload wordt opgelost ten opzichte van de origin van de service worker; alleen `http:` en `https:` zijn toegestaan, anders `/`. Een absolute `go_url` met een andere origin (bijv. productie-URL terwijl de app vanaf een preview draait) wordt wel geopend.
- **A12. Geen `pushsubscriptionchange`-handler.** Vernieuwt de browser een abonnement, dan geeft het oude endpoint 410 en ruimt WP-17 het op; `/alerts` toont dan "uit" en de gebruiker zet het opnieuw aan. Automatisch opnieuw registreren vanuit de service worker vraagt een sessie in de service worker; dat is meer dan deze WP nodig heeft.
- **A13. Geen wijziging aan `ingest/`, `supabase/`, `.github/`, `vite.config.ts` of `package.json`.** Geen nieuwe packages. De tabel en RLS komen uit WP-17.
- **A14. De service worker cachet niets nieuws.** De push-handlers doen geen enkele fetch. Supabase blijft `passthrough` (WP-13). Na een deploy wordt de nieuwe service worker pas actief als alle vensters van de app dicht zijn (geen `skipWaiting`, WP-13 A7). Tot dan kan het apparaat de oude service worker zonder `push`-handler hebben, terwijl de pagina (netwerk-eerst) al de nieuwe UI toont. Daarom weigert `enablePush` te abonneren zolang er een nieuwe service worker wacht of installeert (`reg.waiting || reg.installing`), met de vaste melding "Er staat een nieuwe versie van Shakka klaar…". De RUNBOOK zegt: na de deploy de app sluiten en opnieuw openen tot de knop werkt.

## Ontwerp

**Lagen.**
```
routes/alerts/+page.svelte ──> components/PushSettings.svelte ──> #lib/push.ts
routes/login/+page.svelte  ──> #lib/platform.ts, #lib/auth.ts (signInWithPastedLink)
routes/+layout.svelte      ──> #lib/auth.ts (signOut, met busy-state)
#lib/auth.ts (signOut) ──> #lib/push.ts (releasePushForSignOut)
#lib/push.ts ──> #lib/platform.ts, #lib/env-schema.ts (base64UrlToBytes), $app/env/public,
                 #lib/user-data.ts (push_subscriptions) ──> #lib/supabase.js
src/service-worker/index.ts ──> #lib/sw/shell.ts (WP-13), #lib/sw/push.ts (nieuw)
puur, zonder I/O: #lib/platform.ts (met injecteerbare PlatformInfo), #lib/sw/push.ts (met deps), env-schema
```

**Status van een apparaat.** `getPushStatus()` bepaalt zonder iets te vragen of te schrijven de toestand, in deze volgorde: iOS buiten de beginschermapp → `needs_install`; geen Push API → `unsupported`; geen VAPID-sleutel in de build → `unavailable`; toestemming geweigerd → `denied`; toestemming niet gegeven, geen browserabonnement of een abonnement met een andere sleutel → `off`; anders zoekt hij het endpoint in de eigen rijen: gevonden → `on`, niet gevonden → `off`. Een fout bij het laden → `error`. Pas de laatste stap raakt de database, dus de pagina vraagt nooit toestemming en schrijft nooit bij het laden (AC-2).

**Aanzetten.** `enablePush()` wordt synchroon vanuit de klik aangeroepen. De eerste `await` is `Notification.requestPermission()`, zodat iOS en Firefox de aanvraag als gebruikersgebaar zien. Daarna: `navigator.serviceWorker.ready` (met een tijdslimiet van 10 s; in `vite dev` wordt geen service worker geregistreerd), weigeren als er een nieuwe service worker wacht of installeert (A14), een bestaand abonnement hergebruiken als de sleutel klopt (anders eerst afmelden), anders `pushManager.subscribe({ userVisibleOnly: true, applicationServerKey })` met de sleutel als `Uint8Array`. Dan de insert, de afhandeling van `23505` (A7) en het opschonen boven 10 (A8).

**Service worker.** `#lib/sw/push.ts` parseert de payload van WP-17 zonder ooit te gooien: ongeldige JSON of een leeg veld valt terug op vaste waarden, zodat er altijd een melding verschijnt (`userVisibleOnly`; Chrome toont anders een eigen melding, en een stille push kan op iOS het abonnement kosten). `index.ts` is alleen bedrading, net als bij `shell.ts`.

**iOS.** De detectie staat in `#lib/platform.ts`: iPhone, iPad of iPod in de user-agent, of iPadOS met een desktop-user-agent (`Macintosh` plus `maxTouchPoints > 1`). Standalone is `navigator.standalone === true` of `matchMedia('(display-mode: standalone)')`. Alle functies krijgen optioneel een `PlatformInfo`, zodat ze puur te testen zijn.

**Geplakte link en de voorvertoning.** In iOS opent ingedrukt houden van een link standaard een live voorvertoning die de pagina laadt; voor de magic link is dat een `GET /auth/v1/verify`, en dan is het eenmalige token op. De gebruiker moet de voorvertoning dus uitzetten vóórdat hij de inloglink ingedrukt houdt. iOS biedt daarvoor in hetzelfde menu "Verberg linkvoorvertoningen" en onthoudt die keuze. De app legt dat uit bij het plakveld, in deze volgorde: eerst bij een link in een andere mail de voorvertoningen verbergen, dan de inloglink kopiëren. Als alternatief: kopiëren op een computer en plakken via het gedeelde klembord. Wordt de link toch verbruikt, dan noemt de foutmelding de voorvertoning als waarschijnlijke oorzaak.

**Waarom zo.** Elke regel die het contract bewaakt is een test: geen toestemming bij laden, insert met precies drie velden, rij weg vóór afmelden, geen endpoint in URL's of logs, alleen `user-data.ts` schrijft, en de waarschuwing over de voorvertoning staat in beeld. De browser-API's zitten achter kleine functies met structurele types, zodat vitest ze met nepobjecten kan aansturen.

## Bestanden
Alle paden gaan uit van `develop` na de rebase (WP-12 en WP-15 erin).

| Pad | Actie | Inhoud |
|---|---|---|
| `web/src/env.ts` | wijzigen | Vierde variabele `PUBLIC_VAPID_PUBLIC_KEY` na `PUBLIC_MAPTILER_KEY`; importregel uitgebreid (zie Interfaces). |
| `web/src/lib/env-schema.ts` | wijzigen | Aan het eind `base64UrlToBytes`, `parseVapidPublicKey`. Bestaande functies (ook `parseMaptilerKey`) ongewijzigd. |
| `web/.env.example` | wijzigen | Twee regels na `PUBLIC_MAPTILER_KEY=` (zie Interfaces). |
| `web/src/lib/platform.ts` | aanmaken | `PlatformInfo`, `readPlatform`, `isIos`, `isStandalone`, `needsInstallFirst`. Los van `web/src/lib/map/platform.ts` (WP-15). |
| `web/src/lib/types.ts` | wijzigen | Aan het eind: `PUSH_SUBSCRIPTION_COLUMNS`, `OwnPushSubscription`, `PushSubscriptionKeys`. |
| `web/src/lib/user-data.ts` | wijzigen | Commentaarregel bovenaan (vier tabellen); aan het eind `listOwnPushSubscriptions`, `addPushSubscription`, `removePushSubscription`. |
| `web/src/lib/push.ts` | aanmaken | Constanten, `PUSH_MESSAGES`, `PushStatus`, `isPushSupported`, re-export `needsInstallFirst`, `vapidKeyBytes`, `withTimeout`, `subscriptionKeys`, `getPushStatus`, `enablePush`, `disablePush`, `releasePushForSignOut`. |
| `web/src/lib/sw/push.ts` | aanmaken | Payloadparser, URL-resolutie, `createPushHandlers`. |
| `web/src/service-worker/index.ts` | wijzigen | Push-handlers registreren (zie Interfaces); de commentaarregel over WP-18 vervalt. |
| `web/src/lib/components/PushSettings.svelte` | aanmaken | Sectie "Meldingen op dit apparaat". |
| `web/src/routes/alerts/+page.svelte` | wijzigen | Import en `<PushSettings>` direct onder `<h1>`. |
| `web/src/lib/supabase.ts` | wijzigen | Export `supabaseOrigin`. |
| `web/src/lib/auth.ts` | wijzigen | `signOut` roept eerst `releasePushForSignOut()` aan; `AUTH_MESSAGES.linkInvalid` en `pastedLinkUsed`; `PastedLinkType`, `parseMagicLink`, `pastedLinkErrorMessage`, `signInWithPastedLink`. |
| `web/src/routes/login/+page.svelte` | wijzigen | Installatiehint op iOS in Safari; tekst van "Check je mail" in standalone; sectie "Inloglink plakken" met waarschuwing over de voorvertoning. |
| `web/src/routes/+layout.svelte` | wijzigen | Knop "Uitloggen" uitgeschakeld tijdens het uitloggen (N-8). |
| `web/src/app.css` | wijzigen | Drie regels aan het eind (zie Interfaces). |
| `web/test/helpers/fake-push.ts` | aanmaken | `TEST_VAPID_PUBLIC_KEY`, `OTHER_VAPID_PUBLIC_KEY`, user-agents, `publicEnv`, `fakeSubscription`, `installPushEnv`. |
| `web/test/env-schema.test.ts` | wijzigen | Tests voor de twee nieuwe functies. |
| `web/test/env-example.test.ts` | wijzigen | Vier sleutels verwacht. |
| `web/test/platform.test.ts` | aanmaken | Zie Testplan. |
| `web/test/user-data.test.ts` | wijzigen | `describe('push_subscriptions')`. |
| `web/test/user-tables.test.ts` | wijzigen | Vier tabellen, insert ook op `push_subscriptions`. |
| `web/test/push-schema.test.ts` | aanmaken | Kolommen en insert-grant tegen de WP-17-migratie. |
| `web/test/push.test.ts` | aanmaken | AC-2 op moduleniveau. |
| `web/test/sw-push.test.ts` | aanmaken | AC-3. |
| `web/test/push-settings.test.ts` | aanmaken | AC-2 en AC-4 op componentniveau. |
| `web/test/alerts-page.test.ts` | wijzigen | Mock van `$app/env/public` (verplicht, zie R2); één extra test (AC-4 op de pagina). |
| `web/test/auth.test.ts` | wijzigen | Mock van `#lib/push.js`, `verifyOtp` en `supabaseOrigin` in de supabase-mock; tests voor uitloggen en de geplakte link. |
| `web/test/login.test.ts` | wijzigen | Mock van `#lib/push.js`, `verifyOtp` en `supabaseOrigin`; tests voor hint, plakveld, waarschuwing over de voorvertoning en "Check je mail". |
| `web/test/layout.test.ts` | wijzigen | Eén test: knop uitgeschakeld tijdens het uitloggen. |
| `docs/RUNBOOK.md` | wijzigen | §4, §11 en §14 (zie Interfaces). §15 (Golven) blijft ongewijzigd. |

Geen andere bestanden. `docs/STATUS.md` en `WORK_PACKAGES.md` werkt de orchestrator bij.

## Interfaces en contracten

### `web/src/env.ts` (na de rebase: importregel vervangen, variabele toevoegen na `PUBLIC_MAPTILER_KEY`)
```ts
import {
	parseMaptilerKey,
	parsePublishableKey,
	parseSupabaseUrl,
	parseVapidPublicKey
} from './lib/env-schema.js';
// ...
	PUBLIC_VAPID_PUBLIC_KEY: {
		public: true,
		static: true,
		schema: parseVapidPublicKey,
		description:
			'VAPID public key for Web Push (same value as VAPID_PUBLIC_KEY of the ingest). Optional: empty = push disabled. Never the private key.'
	}
```

### `web/src/lib/env-schema.ts` (toevoegen aan het eind)
```ts
/** Decodes base64url (with or without '=' padding) to bytes.
 *  Throws Error('invalid base64url') for other characters or a length that is 1 mod 4. */
export function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer>;

/** Validates PUBLIC_VAPID_PUBLIC_KEY. Missing or blank -> '' (push disabled in this build).
 *  Returns the key without '=' padding. Never echoes the value. */
export function parseVapidPublicKey(value: string | undefined): string;
```
`base64UrlToBytes`: `/^[A-Za-z0-9_-]*={0,2}$/` anders fout; padding eraf; lengte `% 4 === 1` → fout; `-`→`+`, `_`→`/`, aanvullen met `=` tot een veelvoud van 4; `atob`; per teken `charCodeAt` in een `new Uint8Array(n)`.

`parseVapidPublicKey`, in deze volgorde:
1. `raw = value?.trim() ?? ''`; leeg → `''`.
2. `key = raw.replace(/=+$/, '')`; bevat `key` iets anders dan `[A-Za-z0-9_-]`, of gooit `base64UrlToBytes(key)` → `Error('PUBLIC_VAPID_PUBLIC_KEY must be base64url: use VAPID_PUBLIC_KEY from shakka alerts vapid-keys')`.
3. 32 bytes → `Error('PUBLIC_VAPID_PUBLIC_KEY looks like a private key: use VAPID_PUBLIC_KEY, never VAPID_PRIVATE_KEY')`.
4. Niet 65 bytes of eerste byte niet `0x04` → `Error('PUBLIC_VAPID_PUBLIC_KEY must be an uncompressed P-256 public key (65 bytes)')`.
5. Return `key`.

### `web/.env.example` (toevoegen direct na `PUBLIC_MAPTILER_KEY=`, exact)
```
# Web Push public key: the same value as VAPID_PUBLIC_KEY in the root .env. Never the private key. Optional: empty = push disabled.
PUBLIC_VAPID_PUBLIC_KEY=
```

### `web/src/lib/platform.ts`
```ts
export interface PlatformInfo {
	userAgent: string;
	maxTouchPoints: number;
	navigatorStandalone: boolean;   // iOS Safari: navigator.standalone === true
	displayModeStandalone: boolean; // matchMedia('(display-mode: standalone)').matches
}
/** Reads navigator/window defensively; never throws (also in Node without window). */
export function readPlatform(): PlatformInfo;
/** /\b(iPhone|iPad|iPod)\b/ in the UA, or iPadOS with a desktop UA (/\bMacintosh\b/ and maxTouchPoints > 1). */
export function isIos(p: PlatformInfo = readPlatform()): boolean;
/** navigatorStandalone || displayModeStandalone */
export function isStandalone(p: PlatformInfo = readPlatform()): boolean;
/** isIos(p) && !isStandalone(p): Web Push on iOS/iPadOS only works in the Home Screen app (16.4+). */
export function needsInstallFirst(p: PlatformInfo = readPlatform()): boolean;
```
`readPlatform`, letterlijk:
```ts
const nav = typeof navigator !== 'undefined' ? navigator : undefined;
const hasMatchMedia = typeof window !== 'undefined' && typeof window.matchMedia === 'function';
return {
	userAgent: typeof nav?.userAgent === 'string' ? nav.userAgent : '',
	maxTouchPoints: typeof nav?.maxTouchPoints === 'number' ? nav.maxTouchPoints : 0,
	navigatorStandalone: (nav as (Navigator & { standalone?: boolean }) | undefined)?.standalone === true,
	displayModeStandalone: hasMatchMedia && window.matchMedia('(display-mode: standalone)').matches
};
```

### `web/src/lib/types.ts` (toevoegen aan het eind)
```ts
/** Columns of push_subscriptions the PWA reads (own rows only, RLS). */
export const PUSH_SUBSCRIPTION_COLUMNS = ['id', 'endpoint', 'created_at'] as const;
export interface OwnPushSubscription { id: string; endpoint: string; created_at: string }
/** Exactly the columns the PWA inserts; user_id comes from the column default auth.uid() (WP-17). */
export interface PushSubscriptionKeys { endpoint: string; p256dh: string; auth: string }
```

### `web/src/lib/user-data.ts` (wijzigen)
De commentaarregel wordt `// The only module that reads or writes profiles, favorites, alert_rules and push_subscriptions.`

| Functie | Query | Resultaat / fout |
|---|---|---|
| `listOwnPushSubscriptions(): Promise<OwnPushSubscription[]>` | `supabase.from('push_subscriptions').select(PUSH_SUBSCRIPTION_COLUMNS.join(',')).order('created_at', { ascending: false })` | `data ?? []`; fout → `DataError('listOwnPushSubscriptions', code)` |
| `addPushSubscription(keys: PushSubscriptionKeys): Promise<'added' \| 'exists'>` | `supabase.from('push_subscriptions').insert({ endpoint: keys.endpoint, p256dh: keys.p256dh, auth: keys.auth })` | geen fout → `'added'`; code `23505` → `'exists'`; anders `DataError('addPushSubscription', code)` |
| `removePushSubscription(id: string): Promise<void>` | `supabase.from('push_subscriptions').delete().eq('id', id)` | fout → `DataError('removePushSubscription', code)` |

Geen `user_id` in de payload of als filter (A2). De insert-payload is letterlijk uitgeschreven met deze drie sleutels.

### `web/src/lib/push.ts`
```ts
import { PUBLIC_VAPID_PUBLIC_KEY } from '$app/env/public';
import { DataError } from './data.js';
import { base64UrlToBytes } from './env-schema.js';
import { needsInstallFirst } from './platform.js';
import { addPushSubscription, listOwnPushSubscriptions, removePushSubscription } from './user-data.js';
import type { PushSubscriptionKeys } from './types.js';

export { needsInstallFirst } from './platform.js';

export const MAX_PUSH_SUBSCRIPTIONS = 10;      // = MAX_TARGETS_PER_USER in shakka.jobs.push (WP-17)
export const SW_READY_TIMEOUT_MS = 10_000;
export const SIGN_OUT_PUSH_TIMEOUT_MS = 5_000;

export const PUSH_MESSAGES = {
	installFirst:
		'Meldingen op iPhone en iPad werken alleen in de app op je beginscherm (iOS 16.4 of nieuwer). Tik op de deelknop en kies ‘Zet op beginscherm’. Open Shakka daarna vanaf je beginscherm, log daar in en zet hier meldingen aan.',
	unsupported:
		'Deze browser ondersteunt geen pushmeldingen. Op iPhone en iPad werkt het vanaf iOS 16.4, in de app op je beginscherm.',
	unavailable: 'Meldingen zijn in deze versie van Shakka nog niet beschikbaar.',
	denied:
		'Meldingen zijn geblokkeerd voor Shakka. Sta ze toe in de instellingen van je browser of telefoon en herlaad deze pagina.',
	dismissed: 'Meldingen staan nog uit: je hebt geen toestemming gegeven.',
	noServiceWorker: 'Meldingen zijn nu niet beschikbaar. Herlaad de pagina en probeer het opnieuw.',
	updatePending:
		'Er staat een nieuwe versie van Shakka klaar. Sluit de app helemaal af (op iPhone en iPad: veeg hem weg in de appkiezer), open hem opnieuw en zet dan meldingen aan.',
	subscribeFailed: 'Aanzetten is niet gelukt. Probeer het opnieuw.',
	saveFailed: 'Aanzetten is niet gelukt: geen verbinding met de server. Probeer het opnieuw.',
	otherAccount:
		'Aanzetten is niet gelukt: dit apparaat is nog gekoppeld aan een ander account. Probeer het opnieuw.',
	statusFailed: 'De status van meldingen kon niet worden geladen.',
	intro:
		'Krijg een melding op dit apparaat als er voor een van je favoriete spots een kitebaar window aankomt.',
	newWindowsOnly:
		'Je krijgt meldingen over nieuwe windows en over wijzigingen. Een window dat al liep voordat je meldingen aanzette, meldt Shakka pas bij een wijziging.',
	on: 'Je krijgt meldingen op dit apparaat.',
	enabled: 'Meldingen staan aan op dit apparaat.',
	disabled: 'Meldingen staan uit op dit apparaat.'
} as const;

export type PushStatus = 'needs_install' | 'unsupported' | 'unavailable' | 'denied' | 'off' | 'on' | 'error';

/** typeof navigator/window guarded; 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window. */
export function isPushSupported(): boolean;
/** Key bytes for applicationServerKey, or null for an empty/undefined key. */
export function vapidKeyBytes(key: string | undefined): Uint8Array<ArrayBuffer> | null;
/** Resolves with the promise's value, or with fallback after ms. Clears its timer. Never rejects on timeout. */
export function withTimeout<T>(promise: Promise<T>, ms: number, fallback: T): Promise<T>;
/** endpoint, keys.p256dh and keys.auth from sub.toJSON() (endpoint falls back to sub.endpoint);
 *  null if any is missing/empty or the endpoint does not start with 'https://' (DB CHECK, WP-17). */
export function subscriptionKeys(sub: Pick<PushSubscription, 'endpoint' | 'toJSON'>): PushSubscriptionKeys | null;
export function getPushStatus(): Promise<PushStatus>;
export function enablePush(): Promise<{ ok: boolean; error?: string }>;
export function disablePush(): Promise<void>;
/** withTimeout<void>(disablePush(), SIGN_OUT_PUSH_TIMEOUT_MS, undefined) */
export function releasePushForSignOut(): Promise<void>;
```
`PUBLIC_VAPID_PUBLIC_KEY` wordt alleen binnen functies gelezen (via een interne `currentVapidKey()`), nooit op moduleniveau gekopieerd; zo werkt een testmock van `$app/env/public` per test.

Interne helpers (niet geëxporteerd):
- `sameKey(sub, key)`: `const k = sub.options?.applicationServerKey; return !k || bytesEqual(new Uint8Array(k), key);` (oudere Safari kent `options` niet; dan geldt hij als gelijk).
- `currentSubscription()`: `const reg = await withTimeout<ServiceWorkerRegistration | undefined>(navigator.serviceWorker.getRegistration(), SW_READY_TIMEOUT_MS, undefined); return reg ? await reg.pushManager.getSubscription() : null;`
- `register(sub)`: `keys = subscriptionKeys(sub)`; `null` → `throw new Error('push keys missing')`; `await addPushSubscription(keys) === 'added'` → `'ok'`; anders `(await listOwnPushSubscriptions()).some((r) => r.endpoint === keys.endpoint) ? 'ok' : 'other_account'`.
- `pruneOld(endpoint)`: in `try`: `rows = await listOwnPushSubscriptions()` (nieuwste eerst); `extra = rows.filter((r) => r.endpoint !== endpoint).slice(MAX_PUSH_SUBSCRIPTIONS - 1)`; per rij `await removePushSubscription(r.id)`. `catch` → `console.warn('push prune failed')`.

**`getPushStatus()`**, exact in deze volgorde:
```
if (needsInstallFirst()) return 'needs_install';
if (!isPushSupported()) return 'unsupported';
const key = vapidKeyBytes(currentVapidKey()); if (!key) return 'unavailable';
if (Notification.permission === 'denied') return 'denied';
if (Notification.permission !== 'granted') return 'off';                 // no DB call
try {
  const sub = await currentSubscription();
  if (!sub || !sameKey(sub, key)) return 'off';
  const keys = subscriptionKeys(sub); if (!keys) return 'off';
  return (await listOwnPushSubscriptions()).some((r) => r.endpoint === keys.endpoint) ? 'on' : 'off';
} catch { console.warn('push status failed'); return 'error'; }
```

**`enablePush()`**, exact in deze volgorde:
```
if (needsInstallFirst()) return { ok: false, error: PUSH_MESSAGES.installFirst };
if (!isPushSupported()) return { ok: false, error: PUSH_MESSAGES.unsupported };
const key = vapidKeyBytes(currentVapidKey());
if (!key) return { ok: false, error: PUSH_MESSAGES.unavailable };
let permission: NotificationPermission;
try { permission = await Notification.requestPermission(); }   // first await: still inside the tap (iOS)
catch { return { ok: false, error: PUSH_MESSAGES.dismissed }; }
if (permission === 'denied') return { ok: false, error: PUSH_MESSAGES.denied };
if (permission !== 'granted') return { ok: false, error: PUSH_MESSAGES.dismissed };
const reg = await withTimeout<ServiceWorkerRegistration | null>(navigator.serviceWorker.ready, SW_READY_TIMEOUT_MS, null);
if (!reg) return { ok: false, error: PUSH_MESSAGES.noServiceWorker };
if (reg.waiting || reg.installing) return { ok: false, error: PUSH_MESSAGES.updatePending };   // A14
const options = { userVisibleOnly: true, applicationServerKey: key };
try {
  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(sub, key)) { await sub.unsubscribe(); sub = null; }
  sub ??= await reg.pushManager.subscribe(options);
  let outcome = await register(sub);
  if (outcome === 'other_account') {                                       // A7
    await sub.unsubscribe();
    sub = await reg.pushManager.subscribe(options);
    outcome = await register(sub);
    if (outcome === 'other_account') return { ok: false, error: PUSH_MESSAGES.otherAccount };
  }
  await pruneOld(sub.endpoint);                                             // A8, never throws
  return { ok: true };
} catch (e) {
  console.warn('push enable failed');
  return { ok: false, error: e instanceof DataError ? PUSH_MESSAGES.saveFailed : PUSH_MESSAGES.subscribeFailed };
}
```
Bij een fout na `subscribe` (bijv. de insert faalt) blijft het browserabonnement bestaan; een nieuwe tik hergebruikt het en probeert de insert opnieuw.

**`disablePush()`**:
```
if (!isPushSupported()) return;
let sub: PushSubscription | null = null;
try { sub = await currentSubscription(); } catch { console.warn('push status failed'); return; }
if (!sub) return;
try {
  const own = (await listOwnPushSubscriptions()).find((r) => r.endpoint === sub.endpoint);
  if (own) await removePushSubscription(own.id);
} catch { console.warn('push subscription delete failed'); }               // A5: unsubscribe anyway
try { await sub.unsubscribe(); } catch { console.warn('push unsubscribe failed'); }
```
Geen `console`-regel bevat een endpoint, sleutel, user-id of foutmelding; alleen de vaste teksten hierboven.

### `web/src/lib/sw/push.ts`
```ts
import type { WaitUntilEvent } from './shell.js';

export const FALLBACK_TITLE = 'Shakka';
export const FALLBACK_BODY = 'Er is een nieuwe melding. Open Shakka voor de details.';
export const NOTIFICATION_ICON = '/icons/icon-192.png';

export interface ParsedPush { title: string; body: string; url: string; tag: string | undefined }

/** Never throws. Invalid JSON, null or a non-object -> { FALLBACK_TITLE, FALLBACK_BODY, '/', undefined }.
 *  Object: title = non-empty-after-trim string or FALLBACK_TITLE; body = string or '';
 *  url = non-empty string or '/'; tag = non-empty string or undefined. */
export function parsePushPayload(text: string | null): ParsedPush;
/** new URL(String(raw ?? '/'), origin); protocol http: or https: -> href; otherwise or on error -> `${origin}/`. */
export function resolveTargetUrl(raw: unknown, origin: string): string;

export interface PushMessageDataLike { text(): string }
export interface PushEventLike extends WaitUntilEvent { readonly data: PushMessageDataLike | null }
export interface NotificationLike { readonly data: unknown; close(): void }
export interface NotificationClickEventLike extends WaitUntilEvent { readonly notification: NotificationLike }
export interface WindowClientLike { readonly url: string; focus(): Promise<unknown> }
export interface PushDeps {
	origin: string;                                                    // self.location.origin
	showNotification(title: string, options: NotificationOptions): Promise<void>;
	matchAll(): Promise<readonly WindowClientLike[]>;                  // window clients, incl. uncontrolled
	openWindow(url: string): Promise<unknown>;
}
export function createPushHandlers(deps: PushDeps): {
	onPush(event: PushEventLike): void;
	onNotificationClick(event: NotificationClickEventLike): void;
};
```
- `onPush`: `text = event.data ? safeText(event.data) : null` (`safeText` vangt een exceptie van `text()` af en geeft dan `null`); `p = parsePushPayload(text)`; `options: NotificationOptions = { body: p.body, icon: NOTIFICATION_ICON, data: { url: resolveTargetUrl(p.url, deps.origin) } }`; alleen als `p.tag !== undefined` ook `options.tag = p.tag`; `event.waitUntil(deps.showNotification(p.title, options))`.
- `onNotificationClick`: `event.notification.close()`; `url = resolveTargetUrl((event.notification.data as { url?: unknown } | null)?.url, deps.origin)`; `event.waitUntil((async () => { const hit = (await deps.matchAll()).find((c) => c.url === url); if (hit) { await hit.focus(); return; } await deps.openWindow(url); })().catch(() => undefined))`.
- Het bestand gebruikt alleen types die zowel in de DOM- als in de WebWorker-lib bestaan (`NotificationOptions`), zodat `npm run check` (svelte-check plus de tsc-run voor de service worker) slaagt.

### `web/src/service-worker/index.ts` (de laatste regel `// WP-18 adds …` vervangen door)
```ts
const push = createPushHandlers({
	origin: self.location.origin,
	showNotification: (title, options) => self.registration.showNotification(title, options),
	matchAll: () => self.clients.matchAll({ type: 'window', includeUncontrolled: true }),
	openWindow: (url) => self.clients.openWindow(url)
});

self.addEventListener('push', push.onPush);
self.addEventListener('notificationclick', push.onNotificationClick);
```
Met de import `import { createPushHandlers } from '#lib/sw/push.js';` bij de andere imports. De bestaande `install`-, `activate`- en `fetch`-registratie blijft exact gelijk.

### `web/src/lib/components/PushSettings.svelte`
Props `{ signedIn: boolean }`. Importeert alleen `#lib/push.js` en `svelte`.
```ts
const installFirst = needsInstallFirst();            // once, at init (CSR only)
let status = $state<PushStatus | 'loading'>('loading');
let busy = $state(false);
let message = $state<{ kind: 'status' | 'alert'; text: string } | null>(null);
let token = 0;
async function refresh() { const t = ++token; status = 'loading'; const s = await getPushStatus(); if (t === token) status = s; }
$effect(() => {
	if (signedIn && !installFirst) void refresh();
	else { token++; status = 'loading'; message = null; }
});
function turnOn() {                                  // enablePush is called synchronously from the click
	if (busy) return;
	busy = true; message = null;
	void enablePush().then((r) => {
		busy = false;
		if (r.ok) { status = 'on'; message = { kind: 'status', text: PUSH_MESSAGES.enabled }; return; }
		if (r.error === PUSH_MESSAGES.denied) { status = 'denied'; message = null; return; }   // shown once, by the status branch (N-6)
		message = { kind: 'alert', text: r.error ?? PUSH_MESSAGES.subscribeFailed };
	});
}
async function turnOff() {
	if (busy) return;
	busy = true; message = null;
	await disablePush();
	busy = false; status = 'off'; message = { kind: 'status', text: PUSH_MESSAGES.disabled };
}
```
Markup:
```svelte
{#if installFirst || signedIn}
	<section class="push-settings" aria-labelledby="push-title">
		<h2 id="push-title">Meldingen op dit apparaat</h2>
		{#if installFirst}
			<p class="notice">{PUSH_MESSAGES.installFirst}</p>
		{:else if status === 'loading'}
			<p class="muted">Meldingen controleren…</p>
		{:else if status === 'unsupported' || status === 'unavailable' || status === 'denied' || status === 'needs_install'}
			<p class="notice">{PUSH_MESSAGES[status === 'needs_install' ? 'installFirst' : status]}</p>
		{:else if status === 'error'}
			<div class="banner" role="alert">
				<p>{PUSH_MESSAGES.statusFailed}</p>
				<button type="button" onclick={refresh}>Opnieuw proberen</button>
			</div>
		{:else if status === 'off'}
			<p>{PUSH_MESSAGES.intro}</p>
			<p class="hint">{PUSH_MESSAGES.newWindowsOnly}</p>
			<button type="button" disabled={busy} onclick={turnOn}>Meldingen aanzetten</button>
		{:else}
			<p>{PUSH_MESSAGES.on}</p>
			<button type="button" disabled={busy} onclick={turnOff}>Meldingen uitzetten</button>
		{/if}
		{#if message}
			<p role={message.kind} class:error={message.kind === 'alert'}>{message.text}</p>
		{/if}
	</section>
{/if}
```

### `web/src/routes/alerts/+page.svelte` (wijzigen)
Import `import PushSettings from '#lib/components/PushSettings.svelte';`. Direct na `<h1>Alerts</h1>`:
```svelte
{#if $session !== undefined}
	<PushSettings signedIn={$session !== null} />
{/if}
```
De rest van de pagina blijft gelijk. Uitgelogd op iOS in Safari zie je dus de installatie-uitleg boven de loginprompt: daar moet je eerst installeren en dan in de app inloggen.

### `web/src/lib/supabase.ts` (toevoegen, na `supabase`)
```ts
/** Origin of the Supabase project (validated by env-schema); used to recognise pasted login links. */
export const supabaseOrigin: string = PUBLIC_SUPABASE_URL;
```

### `web/src/lib/auth.ts` (wijzigen)
- Import `import { releasePushForSignOut } from '#lib/push.js';` en `supabaseOrigin` uit `#lib/supabase.js` (naast `initialUrlHash`, `supabase`).
- `AUTH_MESSAGES` krijgt twee sleutels (bestaande sleutels ongewijzigd):
  ```ts
  linkInvalid: 'Dit is geen geldige inloglink. Kopieer de link uit de mail van Shakka opnieuw.',
  pastedLinkUsed:
  	'Deze inloglink is al gebruikt of verlopen. Een voorvertoning van de link in je mail-app telt ook als gebruik. Zet de linkvoorvertoningen uit (zie hierboven) en vraag een nieuwe link aan.'
  ```
- `signOut()`:
  ```ts
  export async function signOut(): Promise<void> {
  	// Remove this device's push subscription while the session is still valid (WP-17, WP-18).
  	try { await releasePushForSignOut(); } catch { /* never blocks sign-out */ }
  	// ... existing body unchanged (signOut({ scope: 'local' }), warnings) ...
  }
  ```
- Nieuw:
  ```ts
  /** Link types that sign a user in via verifyOtp({ token_hash, type }). recovery and email_change are refused. */
  export type PastedLinkType = 'magiclink' | 'signup' | 'invite';
  /** Token hash and type from a pasted Supabase Auth link of this project (text is trimmed first):
   *  new URL succeeds, origin === origin argument, pathname '/auth/v1/verify',
   *  type in PastedLinkType, token non-empty, no whitespace, at most 256 chars. Anything else -> null. */
  export function parseMagicLink(text: string, origin: string): { tokenHash: string; type: PastedLinkType } | null;
  /** otp_expired -> pastedLinkUsed; AuthRetryableFetchError or status 0 -> network;
   *  status 429, over_request_rate_limit or over_email_send_rate_limit -> rateLimited; else linkFailed. */
  export function pastedLinkErrorMessage(error: unknown): string;
  /** parseMagicLink(text, supabaseOrigin); null -> { error: linkInvalid } without a call.
   *  supabase.auth.verifyOtp({ token_hash: tokenHash, type }); error -> pastedLinkErrorMessage;
   *  throw -> network. Success: {} (the session store updates via onAuthStateChange). Never logs the link. */
  export async function signInWithPastedLink(text: string): Promise<{ error?: string }>;
  ```
  `parseAuthRedirectError` (redirect-fragment, buiten de plak-context) blijft `linkExpired` geven.

### `web/src/routes/login/+page.svelte` (wijzigen)
- Script: `import { isStandalone, needsInstallFirst } from '#lib/platform.js';` en `signInWithPastedLink` uit `#lib/auth.js`; `const standalone = isStandalone(); const installHint = needsInstallFirst();`; state `link = $state('')`, `linkBusy = $state(false)`, `linkError = $state<string | null>(null)`; `submitLink(e: SubmitEvent)`: `e.preventDefault()`; als `linkBusy` return; `linkError = null; linkBusy = true; const r = await signInWithPastedLink(link); linkBusy = false; if (r.error) linkError = r.error; else link = '';`.
- In de `sent`-tak de bestaande `<p>` vervangen door:
  ```svelte
  <p>
  	We hebben een inloglink gestuurd naar {sentTo}.
  	{#if standalone}
  		Tik de link in de mail niet aan, maar kopieer hem en plak hem hieronder bij ‘Inloglink plakken’.
  	{:else}
  		Open de link op dit apparaat om in te loggen.
  	{/if}
  </p>
  ```
- In de idle-tak, direct na `<p>Je krijgt een link per mail. Een wachtwoord is niet nodig.</p>`:
  ```svelte
  {#if installHint}
  	<p class="notice">
  		Op iPhone of iPad en wil je meldingen? Zet Shakka dan eerst op je beginscherm (deelknop, ‘Zet op
  		beginscherm’) en log in vanuit die app. Inloggen hier in Safari geldt niet voor de app op je beginscherm.
  	</p>
  {/if}
  ```
- Na het hele bestaande `{#if $session} … {/if}`-blok:
  ```svelte
  {#if $session === null && standalone}
  	<section class="paste-link" aria-labelledby="paste-link-title">
  		<h2 id="paste-link-title">Inloglink plakken</h2>
  		<p class="hint">
  			De link uit de mail opent in Safari, niet in deze app. Tik hem daarom niet aan, maar kopieer hem en
  			plak hem hieronder.
  		</p>
  		<p class="notice" id="paste-link-preview">
  			Let op: de link werkt maar één keer, en een voorvertoning van de link gebruikt hem al op. Zet daarom
  			eerst de linkvoorvertoningen uit: houd in je mail-app een link in een ándere mail ingedrukt en kies
  			‘Verberg linkvoorvertoningen’. Houd daarna de inloglink ingedrukt en kies ‘Kopieer link’. Zie je
  			toch een voorbeeld van de pagina, dan is de link gebruikt; vraag dan een nieuwe aan. Of kopieer de
  			link op je computer en plak hem hier via het gedeelde klembord (niet via WhatsApp of Berichten: die
  			laden ook een voorvertoning).
  		</p>
  		<form novalidate onsubmit={submitLink}>
  			<label for="magic-link">Inloglink</label>
  			<input
  				id="magic-link"
  				name="magic-link"
  				type="url"
  				inputmode="url"
  				autocomplete="off"
  				aria-describedby="paste-link-preview"
  				bind:value={link}
  			/>
  			<button type="submit" disabled={linkBusy}>Inloggen met link</button>
  			{#if linkError}<p role="alert" class="error">{linkError}</p>{/if}
  		</form>
  	</section>
  {/if}
  ```
  De sectie staat zowel onder de idle-tak als onder "Check je mail", nooit tijdens het laden van de sessie (`undefined`) en nooit als iemand is ingelogd.

### `web/src/routes/+layout.svelte` (wijzigen, N-8)
Script, toevoegen:
```ts
let signingOut = $state(false);
async function handleSignOut() {
	if (signingOut) return;
	signingOut = true;
	try { await signOut(); } finally { signingOut = false; }
}
```
De knop wordt:
```svelte
<button type="button" disabled={signingOut} onclick={handleSignOut}>{signingOut ? 'Uitloggen…' : 'Uitloggen'}</button>
```
Verder ongewijzigd.

### `web/src/app.css` (toevoegen aan het eind)
```css
/* Push settings and pasted login link (WP-18) */
.push-settings { padding: 0.75rem 0; border-bottom: 1px solid #ddd; }
.push-settings h2 { font-size: 1.1rem; margin: 0 0 0.25rem; }
.paste-link { margin-top: 1.5rem; padding-top: 0.75rem; border-top: 1px solid #ddd; }
```

### Payload (consistent met WP-17)
De service worker leest JSON `{ "title": str, "body": str, "url": str, "tag": str }` (hoogstens 3.000 bytes). `url` is absoluut (`go_url`) of relatief (`/spot/{id}`, `/` bij de test-push); `tag` is `alert-{alert_state.id}` of `shakka-test`. `showNotification(title, { body, icon, tag, data: { url } })` met `data.url` als absolute URL.

### `docs/RUNBOOK.md` (na de rebase)
- **§4**, tabel: nieuwe rij `| \`PUBLIC_VAPID_PUBLIC_KEY\` | \`web/.env\`, Cloudflare Pages | web: Web Push aanzetten (optioneel, publiek; zelfde waarde als \`VAPID_PUBLIC_KEY\`) | WP-18 |` direct na de rij `PUBLIC_MAPTILER_KEY`. Onder de tabel, na "…`sb_secret_` begint.": "Ook `PUBLIC_VAPID_PUBLIC_KEY` is publiek; de build weigert een waarde die op de private key lijkt."
- **§11 punt 1**, aanvullen: "Voor pushmeldingen lokaal: verwijder eerst de lege regel `PUBLIC_VAPID_PUBLIC_KEY=` uit `web/.env` (die komt mee uit `.env.example`). Zet dan de publieke VAPID-sleutel erin zonder hem te tonen, vanuit de repo-root: `grep '^VAPID_PUBLIC_KEY=' .env | sed 's/^/PUBLIC_/' >> web/.env`. In `npm run dev` werken meldingen niet (geen service worker); gebruik `npm run build && npm run preview`."
- **§11 punt 3**, de environment variables aanvullen met `PUBLIC_VAPID_PUBLIC_KEY` (Production en Preview; zie §14 punt 4).
- **§11 punt 5**, de laatste zin "(zie WP-18)" vervangen door: "In de beginschermapp log je daarom in met 'Inloglink plakken' op de inlogpagina. De link werkt één keer, en een linkvoorvertoning (ingedrukt houden in Mail) laadt de link en gebruikt hem op. Zet daarom eerst de voorvertoningen uit: houd in Mail een link in een ándere mail ingedrukt en kies 'Verberg linkvoorvertoningen' (iOS onthoudt die keuze). Houd daarna de inloglink ingedrukt, kies 'Kopieer link' en plak hem in de app. Alternatief: kopieer de link op je Mac (rechtermuisknop, 'Kopieer link') en plak hem via het gedeelde klembord; niet via WhatsApp of Berichten, want die laden ook een voorvertoning. Met de standaard-SMTP kun je hoogstens 2 links per uur aanvragen, dus wees zuinig met pogingen."
- **§14 punt 4** vervangen door: "**Cloudflare Pages (WP-18).** Zet `PUBLIC_VAPID_PUBLIC_KEY` (Production en Preview) op exact dezelfde waarde als `VAPID_PUBLIC_KEY` en deploy opnieuw. Zonder deze variabele toont de app 'Meldingen zijn in deze versie van Shakka nog niet beschikbaar.' Een andere sleutel dan die van de ingest geeft bij elke aflevering 403 (punt 7 en 10)."
- **§14**, nieuwe punten na 11 (vóór §15):
  12. **Meldingen aanzetten (vanaf WP-18).** Android en computer: open Shakka, log in, ga naar Alerts en tik "Meldingen aanzetten". iPhone en iPad (iOS 16.4 of nieuwer): eerst in Safari "Zet op beginscherm", dan Shakka vanaf het beginscherm openen, daar inloggen (inloglink plakken, §11 punt 5) en op Alerts aanzetten. Installeer de productie-URL, want de "ik ga"-links in meldingen wijzen daarheen (`APP_BASE_URL`).
  13. **Na een deploy.** Een nieuwe versie van de service worker wordt pas actief als alle vensters van Shakka dicht zijn. Sluit de app na een deploy helemaal (op iOS: wegvegen in de appkiezer; op Android: uit de recente apps vegen; op een computer: alle tabbladen van Shakka sluiten) en open hem opnieuw. Herhaal dat tot "Meldingen aanzetten" werkt; soms is het twee keer nodig (de eerste keer haalt de browser de nieuwe versie op, de tweede keer wordt die actief). Zegt de app "Er staat een nieuwe versie van Shakka klaar", sluit en open dan nog een keer.
  14. **Uitloggen en gedeelde apparaten.** Uitloggen verwijdert het abonnement van dit apparaat (dat kan tot 5 seconden duren; de knop toont dan "Uitloggen…"); daarna krijgt het apparaat geen meldingen meer. Zet iemand anders op hetzelfde apparaat meldingen aan, dan krijgt het apparaat een nieuw abonnement en gaan de meldingen van het vorige account er niet meer heen. Per account gelden hoogstens 10 apparaten; bij een elfde verdwijnt het oudste.
  15. **Controle (WP-18 AC-5).** Zie punt 6 voor `test-push`. Een tik op de testmelding opent de startpagina. Voor een echte alert: punt 9 (actieve rijen verwijderen) en `uv run shakka alerts run`; tik op de melding, die opent de "ik ga"-link of de spotpagina. Noteer hoeveel van de titel (max. 50 tekens) en de body (max. 150 tekens) zichtbaar is op het vergrendelscherm en in de uitgeklapte melding.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `/alerts` laden (welke toestand ook) | Geen `requestPermission`, geen `subscribe`, geen insert. Hoogstens één select op `push_subscriptions`, alleen bij toestemming `granted` én een browserabonnement. |
| E2 | iOS in Safari (niet op beginscherm), in- of uitgelogd | Installatie-uitleg, geen knop. Op `/login` de installatiehint. |
| E3 | iPadOS met desktop-user-agent (`Macintosh`, `maxTouchPoints` 5) | Telt als iOS: installatie-uitleg buiten standalone. Een Mac (`maxTouchPoints` 0) niet. |
| E4 | iOS-beginschermapp onder 16.4 (geen `PushManager`) | `unsupported`-tekst (noemt iOS 16.4). |
| E5 | Build zonder `PUBLIC_VAPID_PUBLIC_KEY` | `unavailable`-tekst; `enablePush` vraagt geen toestemming. |
| E6 | `PUBLIC_VAPID_PUBLIC_KEY` = de private key, `abc`, of base64url van iets anders dan 65 bytes met `0x04` | Build faalt met de vaste melding, zonder de waarde. |
| E7 | Toestemming geweigerd in de prompt | Status wordt `denied`; de denied-tekst staat één keer in beeld; geen subscribe, geen DB-call. |
| E8 | Prompt weggeklikt (`default`) | `dismissed`-melding; status blijft `off`; opnieuw tikken mag. |
| E9 | Toestemming eerder geblokkeerd (`Notification.permission === 'denied'`) | `denied`-tekst bij laden, geen knop. |
| E10 | Geen actieve service worker (bijv. `npm run dev`) | Na 10 s `noServiceWorker`. |
| E11 | Bestaand browserabonnement met dezelfde sleutel (insert faalde eerder, of rij door WP-17 opgeruimd) | Hergebruik, insert; status `on`. |
| E12 | Bestaand browserabonnement met een andere sleutel (sleutelwissel) | Eerst `unsubscribe`, dan `subscribe` met de nieuwe sleutel. Bij laden: `off`. |
| E13 | Insert geeft `23505` en het endpoint staat bij de eigen rijen (dubbel tikken, ander tabblad) | Geldt als gelukt. |
| E14 | Insert geeft `23505`, endpoint niet bij de eigen rijen (ander account op dit apparaat) | `unsubscribe`, nieuw abonnement, nieuwe insert (A7). Lukt dat ook niet: `otherAccount`-melding. |
| E15 | Insert faalt anders (netwerk, `42501`) | `saveFailed`-melding; browserabonnement blijft; status `off`; opnieuw tikken probeert opnieuw. |
| E16 | `subscribe` faalt (`AbortError`, `NotAllowedError`) of `toJSON()` zonder sleutels | `subscribeFailed`-melding, geen DB-call. |
| E17 | Elfde apparaat | Na de insert worden eigen rijen boven 10 verwijderd, oudste eerst, nooit het huidige endpoint (A8). Een fout daarbij wordt genegeerd (warn). |
| E18 | Uitzetten, rij verwijderen faalt | Toch `unsubscribe` (A5); status `off`. WP-17 ruimt de rij op bij 410. |
| E19 | Uitzetten zonder browserabonnement | Geen DB-call, status `off`. |
| E20 | Uitloggen, apparaat zonder push of zonder support | `releasePushForSignOut` doet niets; uitloggen gaat gewoon door. |
| E21 | Uitloggen terwijl `getRegistration` of de DB hangt | Knop "Uitloggen…" uitgeschakeld; na 5 s gaat het uitloggen door. |
| E22 | Uitloggen in een ander tabblad terwijl `/alerts` open is | `signedIn` wordt `false`: de sectie verdwijnt (behalve de iOS-uitleg); een lopende statusaanvraag wordt genegeerd (token). |
| E23 | Push zonder data, met ongeldige JSON of met `text()` die gooit | Melding "Shakka" met `FALLBACK_BODY`, `data.url` = `<origin>/`, geen `tag`. |
| E24 | Payload met lege titel of zonder `tag` | Titel "Shakka"; geen `tag`-sleutel in de opties. |
| E25 | Payload-`url` `javascript:…` of `data:…` | `data.url` = `<origin>/`. |
| E26 | Payload-`url` absoluut op een andere origin (productie vs. preview) | Wordt geopend met `openWindow` (A11). |
| E27 | Tik terwijl de app al op exact die URL open staat | Dat venster krijgt focus; geen nieuw venster. |
| E28 | Tik terwijl de app op een andere pagina open staat | `openWindow(url)`. Op Android kan dat in het bestaande PWA-venster openen (MDN). |
| E29 | `matchAll` of `openWindow` faalt | Geen onafgevangen fout; de melding is gesloten. |
| E30 | Update met dezelfde `tag` | Vervangt de oude melding stil (A10). |
| E31 | Oude service worker nog actief na de deploy, nieuwe wacht of installeert | `enablePush` abonneert niet en toont `updatePending` (E36). Was er al een abonnement (latere deploys), dan heeft de oude worker vanaf WP-18 al een `push`-handler. RUNBOOK §14 punt 13. |
| E32 | Geplakte link van een ander project, een Outlook-safelink, tekst zonder URL, of `type` `recovery`/`email_change`/onbekend | `linkInvalid`, geen `verifyOtp`-call. |
| E33 | Geplakte link al gebruikt (ook door een voorvertoning) of verlopen | `pastedLinkUsed` (`otp_expired`), met de verwijzing naar de voorvertoning. |
| E34 | Plakveld buiten standalone-modus, tijdens het laden van de sessie, of ingelogd | Niet zichtbaar. |
| E35 | Logs | `console.warn` alleen met de vaste teksten (`push enable failed`, `push status failed`, `push prune failed`, `push subscription delete failed`, `push unsubscribe failed`); nooit endpoint, sleutels, user-id, link of foutmelding. |
| E36 | Tik op "Meldingen aanzetten" terwijl `reg.waiting` of `reg.installing` gezet is | Na de toestemming: `updatePending`-melding (`role="alert"`), geen `getSubscription`, geen `subscribe`, geen DB-call; status blijft `off`. |
| E37 | Geplakte link met `type=signup` of `type=invite` (adres nog niet bevestigd) | `verifyOtp({ token_hash, type: 'signup' \| 'invite' })`; bij succes ingelogd. |
| E38 | "Check je mail" in standalone-modus | Tekst zegt: link niet aantikken, kopiëren en hieronder plakken; de sectie "Inloglink plakken" staat eronder. Buiten standalone ongewijzigd ("Open de link op dit apparaat"). |
| E39 | Dubbelklik op "Uitloggen" | Eén `signOut`-call; de knop is uitgeschakeld tot die klaar is. |

## Testplan
Alle tests staan in `web/test/` en draaien met `npm test`. Pure logica eerst: `env-schema`, `platform`, `sw/push` en de `user-data`-functies vóór de implementatie. Mocks volgen het `vi.hoisted`-patroon; elk bestand met mocks heeft `beforeEach(() => vi.clearAllMocks())`. Testwaarden zijn nooit echte sleutels.

**Verplicht:** elk testbestand waarvan de modulegraaf de echte `push.ts` laadt (`push.test.ts`, `push-settings.test.ts`, `alerts-page.test.ts`), mockt `$app/env/public`. Zonder mock resolvet die module in vitest niet (WP-15 deviations, N-7). `auth.test.ts` en `login.test.ts` mocken `#lib/push.js` en laden `push.ts` dus niet. Faalt na de wijziging een ander bestaand testbestand op `$app/env/public` of op een ontbrekende export van die mock (bijv. `spot-list.test.ts` of `home-no-map.test.ts`, die alleen `PUBLIC_MAPTILER_KEY` mocken), voeg dan `PUBLIC_VAPID_PUBLIC_KEY: ''` aan die mock toe en noteer het in `deviations.md`.

### Helper `web/test/helpers/fake-push.ts`
- `TEST_VAPID_PUBLIC_KEY = 'B' + 'A'.repeat(86)` (base64url van `0x04` plus 64 nulbytes). `OTHER_VAPID_PUBLIC_KEY = 'B' + 'A'.repeat(42) + 'Q' + 'A'.repeat(43)` (87 tekens, 65 bytes, eerste byte `0x04`, andere bytes dan de testsleutel).
- `IPHONE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1'`, `IPAD_DESKTOP_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15'`, `ANDROID_UA = 'Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36'`.
- `publicEnv = { PUBLIC_VAPID_PUBLIC_KEY: TEST_VAPID_PUBLIC_KEY as string, PUBLIC_SUPABASE_URL: 'http://127.0.0.1:54321', PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test', PUBLIC_MAPTILER_KEY: '' }`. Het object is muteerbaar. Gebruik: `vi.mock('$app/env/public', async () => (await import('./helpers/fake-push.js')).publicEnv)`; `beforeEach` zet de sleutel terug op `TEST_VAPID_PUBLIC_KEY`. "Zonder sleutel" = `publicEnv.PUBLIC_VAPID_PUBLIC_KEY = ''`.
- `fakeSubscription(endpoint = 'https://push.example.test/sub-1', key = TEST_VAPID_PUBLIC_KEY)`: `{ endpoint, options: { applicationServerKey: base64UrlToBytes(key).buffer }, toJSON: () => ({ endpoint, expirationTime: null, keys: { p256dh: 'p256dh-test', auth: 'auth-test' } }), unsubscribe: vi.fn(async () => true) }`.
- `installPushEnv(opts)` met deze `opts` (default tussen haakjes): `userAgent` (`ANDROID_UA`), `maxTouchPoints` (0), `navigatorStandalone` (false), `displayModeStandalone` (false), `supported` (true), `permission` (`'default'`), `requestResult` (`'granted'`), `subscription` (`null`), `newSubscriptions` (`[fakeSubscription()]`, `subscribe` geeft ze op volgorde), `ready` (`'resolve'` of `'never'`) en `updateState` (`'none'`; `'waiting'` of `'installing'` zet die eigenschap van de registratie op `{}`).
  - Wat het zet, via `vi.spyOn(navigator, 'userAgent', 'get')` en `Object.defineProperty(…, { configurable: true })`: `navigator.maxTouchPoints`, `navigator.standalone` en `window.matchMedia` (`vi.fn((q) => ({ matches: q === '(display-mode: standalone)' && displayModeStandalone, media: q }))`).
  - Alleen bij `supported`:
    - `window.PushManager` (lege klasse);
    - `window.Notification` (`{ permission, requestPermission: vi.fn(async () => { N.permission = requestResult; return requestResult; }) }`);
    - `navigator.serviceWorker` (`{ ready, getRegistration: vi.fn(async () => registration) }`).
  - `registration = { waiting: null | {}, installing: null | {}, pushManager: { getSubscription: vi.fn(async () => current), subscribe: vi.fn(...) } }`. `subscribe` geeft het volgende abonnement terug en werkt `current` bij. `unsubscribe` van een abonnement zet `current` op `null`.
  - Geeft `{ requestPermission, subscribe, getSubscription, registration, uninstall }` terug. `uninstall` verwijdert alle gezette eigenschappen (`afterEach`).

### Testbestanden

| Bestand | Tests |
|---|---|
| `env-schema.test.ts` (node, uitbreiden) | **`base64UrlToBytes`:** `'AQID'` → `[1, 2, 3]`. Voor `'_-8'`, `'-_'`, `TEST_VAPID_PUBLIC_KEY` en `OTHER_VAPID_PUBLIC_KEY` dezelfde bytes als `Buffer.from(x, 'base64url')`. `OTHER_VAPID_PUBLIC_KEY` geeft 65 bytes met eerste byte 4. `'AQ=='` geeft hetzelfde als `'AQ'`. `'a'` (lengte 1 mod 4) en `'a b'` gooien. **`parseVapidPublicKey`:** `undefined`, `''` en `'  '` → `''`. `TEST_VAPID_PUBLIC_KEY` en `OTHER_VAPID_PUBLIC_KEY`, ook met spaties eromheen en met `=` erachter, → de sleutel zonder `=`. `'A'.repeat(43)` (43 tekens, 32 bytes) → melding met "private key". `'abc!'` → "base64url". `'B' + 'A'.repeat(42)` (32 bytes, eerste byte 4) → "private key". Base64url van 65 bytes met eerste byte `0x02` → "uncompressed P-256". `sb_publishable_test` → fout. Geen enkele melding bevat de invoer. |
| `env-example.test.ts` (wijzigen) | Verwacht `['PUBLIC_SUPABASE_URL=', 'PUBLIC_SUPABASE_PUBLISHABLE_KEY=', 'PUBLIC_MAPTILER_KEY=', 'PUBLIC_VAPID_PUBLIC_KEY=']`; testnaam blijft `declares exactly the public variables, empty`. |
| `platform.test.ts` (node) | **Met expliciete `PlatformInfo`:** iPhone-UA → `isIos` true. `IPAD_DESKTOP_UA` → true met `maxTouchPoints` 5, false met 0. `ANDROID_UA` → false. `isStandalone` is true bij `navigatorStandalone` of `displayModeStandalone`. `needsInstallFirst`: iPhone niet-standalone true, iPhone standalone false, Android false. **`readPlatform()`:** met `vi.stubGlobal('navigator', undefined)` (en `afterEach(() => vi.unstubAllGlobals())`) geeft hij `{ userAgent: '', maxTouchPoints: 0, navigatorStandalone: false, displayModeStandalone: false }`, zonder te gooien (er is geen `window` in node). Zonder stub gooit hij niet, en zijn `isIos(readPlatform())` en `isStandalone(readPlatform())` false. Node 24 heeft een eigen `navigator` met een Node-user-agent, dus geen verwachting op `userAgent`. |
| `user-data.test.ts` (uitbreiden) | **`listOwnPushSubscriptions`:** één call op `push_subscriptions` met ops `[['select', 'id,endpoint,created_at'], ['order', 'created_at', { ascending: false }]]`; geeft `data` terug. Fout `{ code: '42501' }` → `DataError` met operatie `listOwnPushSubscriptions` en die code. **`addPushSubscription`:** ops exact `[['insert', { endpoint, p256dh, auth }]]` → `'added'`. De payload heeft precies die drie sleutels, geen `user_id`. `23505` → `'exists'`; `'08006'` → `DataError('addPushSubscription', '08006')`. **`removePushSubscription('id-1')`:** ops `[['delete'], ['eq', 'id', 'id-1']]`; fout → `DataError`. In geen enkele call staat een `eq` op `user_id` of `endpoint`. |
| `user-tables.test.ts` (wijzigen) | Test 2: namen ⊆ `['profiles', 'favorites', 'alert_rules', 'push_subscriptions']` en elk minstens één keer; testnaam `user-data.ts names only the four user tables, each at least once`. Test 4: elke `.insert(` wordt voorafgegaan door `.from('favorites')` of `.from('push_subscriptions')` (regex `/\.from\('(favorites|push_subscriptions)'\)\s*\.insert\($/`). Test 1 blijft: alleen `lib/data.ts` en `lib/user-data.ts` bevatten `.from('`, dus `push.ts` en `sw/push.ts` niet. |
| `push-schema.test.ts` (node) | Leest `supabase/migrations/20261015150000_push_subscriptions.sql`. **Kolommen:** parser zoals in `schema-columns.test.ts` (regels met twee spaties inspringing); `PUSH_SUBSCRIPTION_COLUMNS` ⊆ kolommen. **Grant:** `grant insert (…) on table public.push_subscriptions to authenticated` bevat `endpoint`, `p256dh` en `auth`. De sleutels van `PushSubscriptionKeys` (in de test als constante lijst `['endpoint', 'p256dh', 'auth']`) zijn een deelverzameling van die grant. **Default:** `user_id` heeft `default auth.uid()`. |
| `push.test.ts` (jsdom) | Mocks: `#lib/supabase.js` met de fake supabase (patroon uit `user-data.test.ts`), `$app/env/public` met `publicEnv`. `afterEach(uninstall)`. Zie de lijst hieronder. |
| `sw-push.test.ts` (node) | Zie de lijst hieronder. **(AC-3)** |
| `push-settings.test.ts` (jsdom) | Rendert `PushSettings.svelte` met de echte `push.ts`; mocks zoals in `push.test.ts`. Zie de lijst hieronder. **(AC-2, AC-4)** |
| `alerts-page.test.ts` (wijzigen) | Toevoegen: `vi.mock('$app/env/public', …publicEnv)`. De bestaande tests blijven ongewijzigd groen: in jsdom zonder Push API toont de sectie bij een sessie de `unsupported`-tekst, zonder query. Nieuwe test: `installPushEnv({ userAgent: IPHONE_UA, supported: false })` en `sessionStore.set(null)` → de tekst `PUSH_MESSAGES.installFirst` en de loginprompt staan er, er is geen knop "Meldingen aanzetten" en er zijn 0 calls. **(AC-4)** |
| `auth.test.ts` (wijzigen) | **Mocks:** `vi.mock('#lib/push.js', () => ({ releasePushForSignOut: push.release }))` met `push = vi.hoisted(() => ({ release: vi.fn(async () => {}) }))`. De supabase-mock krijgt `verifyOtp: vi.fn()` en `supabaseOrigin: 'https://abc.supabase.co'`. **`signOut()`:** roept `releasePushForSignOut` aan vóór `auth.signOut` (volgorde via `mock.invocationCallOrder`). Rejectt `release`, dan wordt `auth.signOut` toch aangeroepen en gooit `signOut()` niet. **`parseMagicLink`:** `https://abc.supabase.co/auth/v1/verify?token=abc123&type=magiclink&redirect_to=https%3A%2F%2Fapp.test` → `{ tokenHash: 'abc123', type: 'magiclink' }`, ook met spaties eromheen. `type=signup` → `{ …, type: 'signup' }`, `type=invite` → `{ …, type: 'invite' }`. `null` bij: andere origin, ander pad, `type=recovery`, `type=email_change`, geen `type`, lege `token`, token met spatie, token van 257 tekens, `'geen link'`. **`signInWithPastedLink`:** geldige link → `verifyOtp` exact `{ token_hash: 'abc123', type: 'magiclink' }`, resultaat `{}`. Een signup-link → `verifyOtp` met `type: 'signup'`. Ongeldige link → `{ error: linkInvalid }` en 0 calls. `{ error: { code: 'otp_expired', status: 403 } }` → `pastedLinkUsed`. `{ name: 'AuthRetryableFetchError', status: 0 }` → `network`. Rejected → `network`. Status 500 → `linkFailed`. **`parseAuthRedirectError`** met `otp_expired` geeft nog steeds `linkExpired` (ongewijzigd). |
| `login.test.ts` (wijzigen) | Zie de lijst hieronder. **(B-1)** |
| `layout.test.ts` (wijzigen) | Nieuw: `store().set({ user: { email: 'lars@example.com' } })`; `mocks.signOut.mockReturnValue(new Promise((r) => (resolve = r)))`. Klik "Uitloggen": daarna is de knop `{ name: 'Uitloggen…' }` disabled. Een tweede klik geeft geen tweede call (`signOut` 1 keer). `resolve()`, daarna staat de knop `{ name: 'Uitloggen' }` er weer, enabled. De bestaande test "shows email and Uitloggen when signed in" blijft groen. |

**`push.test.ts`, gevallen:**
1. `isPushSupported()`: false zonder `installPushEnv`; true met. `vapidKeyBytes(undefined)` en `vapidKeyBytes('')` → `null`; `vapidKeyBytes(TEST_VAPID_PUBLIC_KEY)` → 65 bytes, eerste `4`. `subscriptionKeys(fakeSubscription())` → `{ endpoint, p256dh: 'p256dh-test', auth: 'auth-test' }`; zonder `keys.auth` → `null`; endpoint `http://…` → `null`. `withTimeout`: resolvet met de waarde als de promise eerder klaar is; met fake timers en een promise die nooit resolvet de fallback na `ms`.
2. `getPushStatus()`:
   - iPhone-UA niet-standalone → `needs_install`;
   - zonder support → `unsupported`;
   - `publicEnv.PUBLIC_VAPID_PUBLIC_KEY = ''` → `unavailable`;
   - `permission: 'denied'` → `denied`;
   - `permission: 'default'` → `off`, 0 DB-calls;
   - `granted` zonder abonnement → `off`, 0 DB-calls;
   - `granted` met abonnement en een eigen rij met dat endpoint → `on`; zonder die rij → `off`;
   - abonnement met `OTHER_VAPID_PUBLIC_KEY` → `off`, zonder DB-call;
   - select-fout → `error`.

   In alle gevallen zijn `requestPermission` en `subscribe` 0 keer aangeroepen. **(AC-2: geen toestemming bij laden)**
3. `enablePush()` met `permission: 'default'`, `requestResult: 'granted'` en geen abonnement:
   - `requestPermission` 1 keer;
   - `subscribe` 1 keer met `{ userVisibleOnly: true, applicationServerKey }`, waarbij `applicationServerKey` een `Uint8Array` is met dezelfde bytes als `base64UrlToBytes(TEST_VAPID_PUBLIC_KEY)`;
   - de `subscribe`-mock controleert dat er op dat moment 0 DB-calls zijn, dus subscribe vóór insert;
   - daarna een call op `push_subscriptions` met ops `[['insert', { endpoint: 'https://push.example.test/sub-1', p256dh: 'p256dh-test', auth: 'auth-test' }]]`;
   - resultaat `{ ok: true }`.

   **(AC-2)**
4. `requestResult: 'denied'` → `{ ok: false, error: denied }`, `subscribe` 0, DB 0. `'default'` → `dismissed`. `requestPermission` rejectt → `dismissed`.
5. Bestaand abonnement met dezelfde sleutel → `subscribe` 0, insert 1, `ok`. Met `OTHER_VAPID_PUBLIC_KEY` → `unsubscribe` van het oude, dan `subscribe` 1.
6. Insert `23505` en de select geeft een rij met hetzelfde endpoint → `ok`, geen `unsubscribe`.
7. Insert `23505` en een select zonder dat endpoint:
   - `unsubscribe` van `sub-1`;
   - `subscribe` levert `sub-2`;
   - tweede insert met `sub-2` → `ok`.

   Twee keer `23505` zonder eigen rij → `{ ok: false, error: otherAccount }`.
8. Insert-fout `'08006'` → `saveFailed`; `unsubscribe` 0 keer.
9. `subscribe` rejectt → `subscribeFailed`, 0 DB-calls. Abonnement zonder sleutels in `toJSON` → `subscribeFailed`, 0 DB-calls.
10. `ready: 'never'` met `vi.useFakeTimers()`: na `vi.advanceTimersByTimeAsync(SW_READY_TIMEOUT_MS)` → `noServiceWorker`.
10b. **(N-3)** Geldt voor zowel `updateState: 'waiting'` als `'installing'`: resultaat `{ ok: false, error: PUSH_MESSAGES.updatePending }`. `requestPermission` is 1 keer aangeroepen (nog steeds als eerste); `getSubscription` en `subscribe` 0 keer; 0 DB-calls.
11. Opschonen (A8): na de insert geeft de select 11 eigen rijen (de huidige plus 10 oudere, nieuwste eerst) → precies één delete op de oudste `id`; nooit op de `id` van het huidige endpoint. Een fout bij de delete → toch `{ ok: true }`.
12. iPhone niet-standalone → `installFirst`, `requestPermission` 0. Zonder support → `unsupported`. Zonder sleutel (`''`) → `unavailable`, `requestPermission` 0.
13. `disablePush()`:
    - met abonnement en eigen rij: ops `[['delete'], ['eq', 'id', <id>]]`; de `unsubscribe`-mock controleert dat die delete-call dan al bestaat (rij weg vóór afmelden); `unsubscribe` 1 keer;
    - zonder eigen rij: geen delete, wel `unsubscribe`;
    - select-fout: geen throw, wel `unsubscribe`;
    - zonder abonnement of zonder support: 0 DB-calls, geen throw.

    **(AC-2)**
14. `releasePushForSignOut()` met een `getRegistration` die nooit resolvet: met fake timers resolvet hij na `SIGN_OUT_PUSH_TIMEOUT_MS`.
15. `console.warn` (gespyd) is in geen enkel geval aangeroepen met een argument dat `push.example.test`, `p256dh-test` of `auth-test` bevat.

**`sw-push.test.ts`, gevallen.** Opzet: origin `https://app.test`; `deps` met `vi.fn`; een `event` met `waitUntil: vi.fn()` en `data: { text: () => JSON.stringify(payload) }`. Na elke handler `await` op de promise uit `waitUntil`.
1. Alertpayload:
   - invoer: `{ title: 'Brouwersdam: go za 14–17', body: 'ZW 18–22 kn\nIk ga: …', url: '/spot/brouwersdam', tag: 'alert-11111111-2222-4333-8444-555555555555' }`;
   - verwacht, exact met `toHaveBeenCalledWith`: `showNotification('Brouwersdam: go za 14–17', { body: 'ZW 18–22 kn\nIk ga: …', icon: '/icons/icon-192.png', tag: 'alert-11111111-2222-4333-8444-555555555555', data: { url: 'https://app.test/spot/brouwersdam' } })`;
   - `waitUntil` 1 keer.
2. Absolute `go_url` `https://app.test/go?spot=brouwersdam&from=2026-10-17T12:00:00Z` → `data.url` ongewijzigd. Andere origin `https://shakka.pages.dev/go?x=1` → ongewijzigd.
3. Test-push `{ title: 'Shakka: testmelding', body: 'Meldingen werken op dit apparaat.', url: '/', tag: 'shakka-test' }` → `tag: 'shakka-test'`, `data.url: 'https://app.test/'`.
4. `data: null`, `'not json'`, `'[]'`, `'null'` en een `text()` die gooit → titel `FALLBACK_TITLE`, body `FALLBACK_BODY`, `data.url` `https://app.test/`, en de opties hebben geen eigenschap `tag` (`not.toHaveProperty('tag')`).
5. `{ title: '  ', body: 5, url: 'javascript:alert(1)' }` → titel `'Shakka'`, body `''`, `data.url` `https://app.test/`, geen `tag`.
6. `onNotificationClick` met `data: { url: 'https://app.test/spot/x' }`; steeds `close` 1 keer:
   - `matchAll` geeft `[{ url: 'https://app.test/spot/x', focus }]` → `focus` 1 keer, `openWindow` 0;
   - `matchAll` geeft `[{ url: 'https://app.test/', focus }]` → `openWindow('https://app.test/spot/x')`, `focus` 0;
   - `matchAll` geeft `[]` → `openWindow`.

   **(AC-3: opent of focust `data.url`)**
7. `data: null` → `openWindow('https://app.test/')`. `matchAll` rejectt → de promise uit `waitUntil` resolvet (geen reject).
8. `parsePushPayload` en `resolveTargetUrl` los: `resolveTargetUrl('/a?b=1#c', 'https://app.test')` → `'https://app.test/a?b=1#c'`; `resolveTargetUrl('data:text/html,x', …)` → `'https://app.test/'`; `resolveTargetUrl(undefined, …)` → `'https://app.test/'`.

**`push-settings.test.ts`, gevallen:**
1. Android, ingelogd (`signedIn: true`), toestemming `default`, geen abonnement:
   - na laden staan de knop "Meldingen aanzetten" en de tekst `PUSH_MESSAGES.newWindowsOnly` er; `requestPermission` en `subscribe` 0 keer;
   - klik → `requestPermission` 1, `subscribe` 1 met de sleutel als `Uint8Array`, daarna een insert met `endpoint`, `p256dh` en `auth`;
   - dan `role="status"` met `PUSH_MESSAGES.enabled` en de knop "Meldingen uitzetten".

   **(AC-2)**
2. Toestand `on` (toestemming `granted`, abonnement, eigen rij): knop "Meldingen uitzetten". Klik → delete op `push_subscriptions` en `unsubscribe` 1 keer; dan `PUSH_MESSAGES.disabled` en de knop "Meldingen aanzetten". **(AC-2)**
3. **AC-4:**
   - `IPHONE_UA`, niet standalone, `supported: false`: `PUSH_MESSAGES.installFirst` staat er en `queryByRole('button', { name: 'Meldingen aanzetten' })` is `null`, zowel met `signedIn: true` als `false`; 0 DB-calls;
   - hetzelfde met `IPAD_DESKTOP_UA` en `maxTouchPoints: 5`;
   - met `IPHONE_UA` en `navigatorStandalone: true` (push ondersteund) staat de knop er wel en geen installatie-uitleg.
4. `signedIn: false` op Android → de component rendert niets (geen `heading` "Meldingen op dit apparaat"), 0 DB-calls, `getRegistration` 0 keer.
5. Toestemming `denied` bij laden → `PUSH_MESSAGES.denied`, geen knop. **(N-6)** Klik met `requestResult: 'denied'` vanuit `off`: daarna geeft `getAllByText(PUSH_MESSAGES.denied)` precies 1 element, is er geen knop "Meldingen aanzetten" en geen `role="alert"`.
6. `publicEnv.PUBLIC_VAPID_PUBLIC_KEY = ''` → `PUSH_MESSAGES.unavailable`, geen knop.
7. Select-fout bij laden → banner met `PUSH_MESSAGES.statusFailed` en "Opnieuw proberen"; klik → nieuwe select.
8. Tijdens een lopende `enablePush` (pending `requestPermission`) is de knop `disabled`.
9. `updateState: 'waiting'`, klik → `role="alert"` met `PUSH_MESSAGES.updatePending`, de knop "Meldingen aanzetten" staat er weer (enabled), 0 DB-calls.

**`login.test.ts`, gevallen.**

Opzet:
- Mock van `#lib/push.js` zoals in `auth.test.ts`. De supabase-mock krijgt `verifyOtp: vi.fn()` en `supabaseOrigin: 'http://127.0.0.1:54321'`.
- Helper `signedOut()`: `auth.onAuthStateChange.mockImplementation((cb) => { cb('INITIAL_SESSION', null); return { data: { subscription: { unsubscribe: vi.fn() } } }; })` en `stop = initAuth()` (import uit `#lib/auth.js`). `afterEach` roept `stop?.()` en `uninstall?.()` aan.
- `LINK = 'http://127.0.0.1:54321/auth/v1/verify?token=abc123&type=magiclink&redirect_to=http%3A%2F%2Flocalhost'`.

Gevallen:
1. De bestaande tests blijven ongewijzigd groen. Zonder standalone en zonder iOS staan er geen plakveld en geen hint. De tekst van "Check je mail" bevat nog "Open de link op dit apparaat".
2. **Standalone, uitgelogd:** `installPushEnv({ displayModeStandalone: true, supported: false })` en `signedOut()`. De heading "Inloglink plakken" staat er. De waarschuwing (`getByText(/Verberg linkvoorvertoningen/)`) staat er en noemt ook "Kopieer link" en "maar één keer". Het veld `getByLabelText('Inloglink')` heeft `aria-describedby="paste-link-preview"`. **(B-1)**
3. **Standalone, sessie nog onbekend** (geen `signedOut()`, store `undefined`) → geen sectie "Inloglink plakken" (N-7).
4. **Standalone, geldige link:** `LINK` plakken (`userEvent.type` of `fireEvent.input`) en "Inloggen met link" klikken. `verifyOtp` is aangeroepen met `{ token_hash: 'abc123', type: 'magiclink' }`.
5. **Standalone, verbruikte link:** `verifyOtp` geeft `{ data: { user: null, session: null }, error: { name: 'AuthApiError', status: 403, code: 'otp_expired', message: 'x' } }`. Dan heeft `findByRole('alert')` de tekst `AUTH_MESSAGES.pastedLinkUsed`, die "voorvertoning" bevat, en staat `'x'` nergens in beeld. **(B-1)**
6. **Standalone, geen geldige link:** `'geen link'` → `role="alert"` met `AUTH_MESSAGES.linkInvalid`, 0 `verifyOtp`-calls.
7. **Standalone, "Check je mail":** `signInWithOtp` slaagt. Daarna bevat de alinea "kopieer hem en plak hem hieronder" en niet "Open de link op dit apparaat", en staat de sectie "Inloglink plakken" eronder. **(B-1)**
8. **Niet standalone, uitgelogd** (`signedOut()`, Android-UA) → geen sectie "Inloglink plakken".
9. **iPhone in Safari:** `IPHONE_UA`, niet standalone → de installatiehint ("Op iPhone of iPad en wil je meldingen?") staat er.

### Per acceptatiecriterium
- **AC-1:** `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`, en vanuit de repo-root `bash scripts/check-no-client-openmeteo.sh`. `npm run check` dekt ook de typecheck van de service worker met de nieuwe handlers, en de typeargumenten van `withTimeout`. Lokaal extra (stap 1): zonder de variabele slaagt de build; met een ongeldige waarde of een private key faalt hij met de vaste melding.
- **AC-2:** `push.test.ts` gevallen 2, 3, 13 en `push-settings.test.ts` gevallen 1 en 2 (gemockte `Notification`, `PushManager` en supabase).
- **AC-3:** `sw-push.test.ts` gevallen 1 t/m 7.
- **AC-4:** `push-settings.test.ts` geval 3, `alerts-page.test.ts` (nieuwe test) en `platform.test.ts`.
- **AC-5 (`NEEDS_LARS`):** na de merge en de deploy, met `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare:
  1. app sluiten en opnieuw openen tot "Meldingen aanzetten" werkt (RUNBOOK §14 punt 13);
  2. Android: inloggen, Alerts, "Meldingen aanzetten", toestaan.

     iPhone:
     - Zet op beginscherm en open de app;
     - inloglink aanvragen, en in Mail eerst bij een link in een andere mail "Verberg linkvoorvertoningen" kiezen;
     - noteer of daarna ingedrukt houden van de inloglink géén voorbeeld meer toont;
     - "Kopieer link", plakken, inloggen;
     - Alerts, aanzetten, toestaan;
  3. `cd ingest && uv run shakka alerts test-push --user-id <id>` → `device 1: ok`, de melding "Shakka: testmelding" verschijnt; een tik opent de startpagina;
  4. een echte alert (RUNBOOK §14 punt 9 en `uv run shakka alerts run`): een tik opent de "ik ga"-link of de spotpagina;
  5. noteren in `verification.md`:
     - hoeveel van de titel (≤ 50) en de body (≤ 150) zichtbaar is op het vergrendelscherm en uitgeklapt, op welk toestel en OS;
     - of de werkwijze tegen de voorvertoning op de iPhone werkte (R1);
  6. "Meldingen uitzetten" en daarna `test-push` → `no push subscriptions for this user`.

`cd ingest && uv run pytest` blijft groen (geen wijziging in `ingest/`).

## Externe afhankelijkheden
Geen nieuwe packages. Geen nieuwe dienst: de push-services (FCM, Apple, Mozilla, WNS) zijn gratis en worden door de browser gekozen. Gecontroleerd op 15 oktober 2026.

| API | Gebruik | Bron |
|---|---|---|
| `PushManager.subscribe({ userVisibleOnly, applicationServerKey })`; `applicationServerKey` als base64-string of `ArrayBuffer`/`BufferSource`; Chrome en Edge eisen `userVisibleOnly: true`; aanroepen na een gebruikersgebaar | `enablePush` | https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe, https://w3c.github.io/push-api/ |
| `PushManager.getSubscription()`, `PushSubscription.toJSON()` (`endpoint`, `keys.p256dh`, `keys.auth`, base64url zonder padding), `PushSubscription.options.applicationServerKey`, `unsubscribe()` | Status, hergebruik, uitzetten | https://developer.mozilla.org/en-US/docs/Web/API/PushSubscription, https://w3c.github.io/push-api/ |
| `Notification.permission`, `Notification.requestPermission()` (promise) | Toestemming | https://developer.mozilla.org/en-US/docs/Web/API/Notification/requestPermission_static |
| `navigator.serviceWorker.ready`, `getRegistration()`, `ServiceWorkerRegistration.waiting` / `.installing` | Registratie ophalen (WP-13 "Gevolgen"); wachtende update herkennen (A14) | https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerContainer/ready, https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration |
| `ServiceWorkerRegistration.showNotification(title, { body, icon, tag, data })`; `PushEvent.data.text()` | `push`-handler | https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration/showNotification, https://developer.mozilla.org/en-US/docs/Web/API/PushEvent |
| `Clients.matchAll({ type: 'window', includeUncontrolled: true })`, `WindowClient.focus()`, `Clients.openWindow(url)` (patroon "zelfde URL focussen, anders openen"; vereist een notificatieklik) | `notificationclick` | https://developer.mozilla.org/en-US/docs/Web/API/Clients/openWindow |
| Web Push op iOS/iPadOS 16.4+: alleen als beginschermapp, manifest `display: standalone`, toestemming alleen na een directe gebruikersactie, feature detection | iOS-uitleg, volgorde in `enablePush` | https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ |
| iOS-detectie: `'PushManager' in window` pas in de beginschermapp, `navigator.standalone`, `matchMedia('(display-mode: standalone)')` (bronnen van derden; Apple documenteert de detectie niet) | `platform.ts` | https://documentation.onesignal.com/docs/en/web-push-for-ios, https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide |
| iOS-linkvoorvertoning bij ingedrukt houden: laadt de pagina; menu-optie "Hide Link Previews" / NL "Verberg linkvoorvertoningen" (terug: "Toon linkvoorvertoningen"), keuze wordt onthouden. Bronnen van derden; Apple documenteert niet of de keuze voor Mail en Safari gedeeld is. | B-1, waarschuwing bij het plakveld, R1 | https://www.cultofmac.com/how-to/how-to-disable-link-previews-ios-13, https://www.appletips.nl/voorvertoningen-links-verbergen-ios/ |
| SvelteKit 3 `defineEnvVars`: `public`, `static`; een optionele variabele met schema dat een lege waarde accepteert (zoals `PUBLIC_MAPTILER_KEY`, WP-15) | `PUBLIC_VAPID_PUBLIC_KEY` | https://svelte.dev/docs/kit/@sveltejs-kit-env, `docs/wp/WP-15/deviations.md` |
| `$app/env/public` in vitest alleen met `vi.mock` | Testopzet | `docs/wp/WP-15/deviations.md` (N-7), `web/test/spot-list.test.ts`, `web/test/home-no-map.test.ts` |
| SvelteKit 3 service worker (`src/service-worker/index.ts`, `self` uit `$app/service-worker`, aparte tsconfig) | Bedrading | https://svelte.dev/docs/kit/service-workers (via WP-13) |
| Supabase Auth: magic-link-URL `…/verify?token=<RecoveryToken>&type=magiclink&redirect_to=…`; bevestiging `type=signup` en uitnodiging `type=invite` met `ConfirmationToken` | A3, `parseMagicLink` | https://raw.githubusercontent.com/supabase/auth/master/internal/mailer/templatemailer/templatemailer.go |
| Supabase Auth: `POST /verify` met `token_hash`: `signup`/`invite` zoeken op `ConfirmationToken`, `magiclink` op `RecoveryToken`, alle drie geven een sessie; `GET /verify` zet `token` om naar `TokenHash` en verbruikt het token ook (daarom verbruikt een voorvertoning de link) | A3, B-1 | https://raw.githubusercontent.com/supabase/auth/master/internal/api/verify.go |
| supabase-js `verifyOtp({ token_hash, type })`, `EmailOtpType` bevat `'signup'`, `'invite'` en `'magiclink'` | `signInWithPastedLink` | https://supabase.com/docs/reference/javascript/auth-verifyotp, https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/auth-js/src/lib/types.ts |
| Standaard magic-link-mail bevat geen code; een code vraagt een aangepast template | A3 (waarom geen code) | https://supabase.com/docs/guides/auth/auth-email-passwordless |
| `push_subscriptions` (kolommen, insert-grant, `user_id default auth.uid()`, `endpoint unique`, RLS) | Contract | `supabase/migrations/20261015150000_push_subscriptions.sql` (WP-17) |

## Risico's
- **R1. Geplakte link op iOS en de voorvertoning.** Ingedrukt houden in iOS Mail laadt standaard een voorvertoning. Die doet een GET op `/auth/v1/verify`, en dan is het eenmalige token op.
  - **Mitigatie in de app:** de waarschuwing bij het plakveld, en `pastedLinkUsed` bij `otp_expired`. Daarnaast de RUNBOOK.
  - **Niet zeker:**
    - Volgens bronnen van derden onthoudt iOS de keuze "Verberg linkvoorvertoningen" voor volgende links en tussen apps. Apple documenteert dat niet voor Mail.
    - Andere mail-apps (Gmail, Outlook) gedragen zich mogelijk anders.
    - Outlook kan links herschrijven (safelinks; dan `linkInvalid`) of vooraf openen.
    - De menuteksten kunnen per iOS-versie iets verschillen.
  - **Controle:** AC-5 controleert de werkwijze op een iPhone, en de uitkomst gaat naar `verification.md`.
  - **Terugval:** werkt het niet, dan blijft de route via een computer en het gedeelde klembord. De standaard-SMTP stuurt hoogstens 2 mails per uur, dus een mislukte poging kost tijd.
  - **Structurele oplossing:** inloggen met een code zodra er eigen SMTP is (WP-22).
- **R2. Mock van `$app/env/public` in vitest.**
  - Wat vaststaat: de mock is verplicht en werkt (WP-15). Open is alleen of `push.ts` een mutatie van `publicEnv` ná de import ziet.
  - Ziet `push.ts` die mutatie niet, dan gebruikt de builder terugvaloptie (a): voor de gevallen "zonder sleutel" `vi.resetModules()`, `vi.doMock('$app/env/public', () => ({ ...publicEnv, PUBLIC_VAPID_PUBLIC_KEY: '' }))` en daarna `await import('#lib/push.js')` (en voor de component `await import('../src/lib/components/PushSettings.svelte')`).
  - Werkt dat ook niet, dan terugvaloptie (b): een apart testbestand `push-no-key.test.ts` met een statische mock zonder sleutel (zoals `home-no-map.test.ts` in WP-15). Daarnaast toetst `vapidKeyBytes('')` de logica.
  - In beide gevallen een notitie in `deviations.md`. `TEST_ENV` in `vite.config.ts` is géén terugvaloptie, want `$app/env/public` resolvet zonder mock niet.
- **R3. Optionele variabele in kit 3.** WP-15 heeft bevestigd dat een schema dat een lege waarde accepteert ook bouwt als de variabele ontbreekt (`PUBLIC_MAPTILER_KEY`). `parseVapidPublicKey` volgt hetzelfde patroon. Faalt de build toch zonder de variabele, dan zet de builder `PUBLIC_VAPID_PUBLIC_KEY: ''` in de `env` van CI-job `web` en noteert dat in `deviations.md`.
- **R4. Verkeerde publieke sleutel in Cloudflare.** Elk abonnement krijgt dan 403 bij aflevering (WP-17 R1); de app kan dat niet zien. RUNBOOK §14 punt 4, 7 en 10.
- **R5. Oude service worker na de deploy** (E31, E36). Mitigatie: `updatePending` in `enablePush` en RUNBOOK §14 punt 13. Geen `skipWaiting` (WP-13 A7 blijft). Ook bij latere deploys toont de knop `updatePending` zolang een nieuwe worker wacht. Dat is strenger dan nodig: de oude worker heeft dan al een `push`-handler. Maar het is eenvoudig en altijd veilig.
- **R6. Gedrag van `tag`, `openWindow` en de lengte van de tekst op iOS en Android is niet gemeten.** AC-5 laat het zien; de bevindingen gaan naar `verification.md`.
- **R7. Rebase op `develop` (WP-12, WP-15).** De orchestrator rebased vóór de bouw. De blueprint beschrijft de toestand daarna:
  - `env.ts` importeert vier parsers en heeft vier variabelen;
  - `.env.example` en `env-example.test.ts` hebben vier sleutels;
  - RUNBOOK §4 krijgt een rij na `PUBLIC_MAPTILER_KEY`;
  - §11 punt 9 (Kaart) en §15 (Golven) blijven ongewijzigd;
  - WP-15 raakt `app.css` niet;
  - `lib/platform.ts` (WP-18) en `lib/map/platform.ts` (WP-15) zijn verschillende bestanden.

  Stap 0 controleert de rebase.
- **R8. Gedeelde iPad of telefoon.** A7 maakt de meldingen van het vorige account op dit apparaat dood zodra een ander account hier aanzet. Dat is bedoeld, maar betekent dat dat account op dit apparaat "uit" ziet als het later terugkomt.
- **R9. Privacy.** De push-services van Google, Apple en Mozilla zien het endpoint en versleutelde payloads; dat hoort bij Web Push. Geen tracking, geen derde-partijscripts. WP-23 neemt het op in de privacypagina.

## Buiten scope
- De verzendkant, de payload en de inkorting (WP-17).
- Meldingsvoorkeuren, stille uren, acties in meldingen, badges, `renotify`.
- Een testmeldingsknop in de app (`shakka alerts test-push` bestaat).
- `pushsubscriptionchange`-afhandeling (A12).
- Inloggen met een code, eigen SMTP, een databasegrens op abonnementen (WP-22).
- `skipWaiting` of een knop "nieuwe versie laden"; alleen de vaste melding `updatePending` in `enablePush`.
- Privacypagina en CSP (WP-23; push heeft geen extra `connect-src` nodig).
- Wijzigingen in `ingest/`, `supabase/`, `.github/`, `vite.config.ts` en `package.json` (behalve de terugvaloptie uit R3 in `.github/`).

## Gevolgen voor latere WP's
- **WP-22:** met eigen SMTP kan inloggen met een code het plakveld (A3) vervangen; dan `signInWithPastedLink`, `pastedLinkUsed` en de sectie op `/login` verwijderen. Een databasegrens op abonnementen per gebruiker kan `pruneOld` (A8) aanvullen.
- **WP-23:** `/privacy` noemt push-abonnementen (endpoint en sleutels per apparaat, verwijderd bij uitzetten, uitloggen of een dood abonnement) en dat de push-service van de browser (Google, Apple, Mozilla) de meldingen bezorgt. `delete_my_account()` verwijdert ze via de cascade. Axe-tests op `/alerts` dekken `PushSettings`, op `/login` de sectie "Inloglink plakken". Geen extra origin in `connect-src`.
- **WP-20:** de geplakte link landt niet op een `redirect_to`-pagina; terugkeren naar een `/go`-URL na het inloggen geldt daar ook niet.

## Stappenplan voor de builder
Werk op branch `wp/WP-18` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-18`. Lees of print `.env` en `web/.env` nooit. Draai na elke stap vanuit `web/`: `npm run check && npm test`; na stap 5 en aan het eind ook `npm run build && npm run verify:build`. Eén commit per stap, commitberichten in het Engels.

0. **Rebase controleren.** `git merge-base --is-ancestor develop HEAD` slaagt (exitcode 0), `grep -c PUBLIC_MAPTILER_KEY web/src/env.ts` ≥ 1 en `docs/RUNBOOK.md` heeft `## 15.`. Zo niet: stop en meld het aan de orchestrator (niet zelf rebasen). Geen commit.
1. **Env.** Tests eerst in `env-schema.test.ts` (rood), dan `base64UrlToBytes` en `parseVapidPublicKey` aan het eind van `env-schema.ts`; `env.ts` (importregel en vierde variabele); `.env.example` en `env-example.test.ts` (vier sleutels). Controleer:
   - `npm run build` zonder de variabele slaagt;
   - `PUBLIC_VAPID_PUBLIC_KEY=abc npm run build` faalt met de base64url-melding, zonder de waarde;
   - `PUBLIC_VAPID_PUBLIC_KEY=$(node -e "console.log('A'.repeat(43))") npm run build` faalt met "private key".

   Lukt de build zonder de variabele niet: R3. Commit: `feat(WP-18): PUBLIC_VAPID_PUBLIC_KEY with validation`.
2. **Platform.** `platform.test.ts` (rood), dan `platform.ts` met `readPlatform` letterlijk zoals in Interfaces. Commit: `feat(WP-18): iOS and standalone detection`.
3. **Data.** `types.ts` (aan het eind), tests in `user-data.test.ts`, `user-tables.test.ts` aanpassen, `push-schema.test.ts`; dan de drie functies in `user-data.ts` en de commentaarregel. Commit: `feat(WP-18): push_subscriptions in user-data`.
4. **`push.ts`.** `test/helpers/fake-push.ts` en `push.test.ts` (rood, inclusief geval 10b), dan `push.ts` exact volgens Interfaces, inclusief de typeargumenten van `withTimeout`. Werkt de mutatie van `publicEnv` niet: R2. Commit: `feat(WP-18): subscribe, status and unsubscribe for Web Push`.
5. **Service worker.** `sw-push.test.ts` (rood), dan `sw/push.ts` en de bedrading in `service-worker/index.ts`. `npm run check` (ook de tsc-run voor de service worker) en `npm run build && npm run verify:build`. Controleer met `grep -c notificationclick build/service-worker.js` dat de handler in de build zit (≥ 1). Commit: `feat(WP-18): push and notificationclick handlers in the service worker`.
6. **UI op `/alerts`.** `push-settings.test.ts` (rood), dan `PushSettings.svelte`, de wijziging in `alerts/+page.svelte`, `app.css`; `alerts-page.test.ts` (mock en nieuwe test). Commit: `feat(WP-18): notifications section on /alerts`.
7. **Uitloggen en geplakte link (auth, layout).**
   - Tests eerst: `supabaseOrigin` in `supabase.ts`; tests in `auth.test.ts` en de nieuwe test in `layout.test.ts` (rood).
   - Dan in `auth.ts`: `signOut`, `AUTH_MESSAGES.linkInvalid` en `pastedLinkUsed`, `PastedLinkType`, `parseMagicLink`, `pastedLinkErrorMessage` en `signInWithPastedLink`.
   - Dan de busy-state in `+layout.svelte`.
   - Voeg de mock van `#lib/push.js` en `supabaseOrigin`/`verifyOtp` ook toe aan `login.test.ts`, zodat die groen blijft.

   Commit: `feat(WP-18): release the push subscription on sign-out; sign in with a pasted link`.
8. **`/login`.** Tests in `login.test.ts` (rood, gevallen 1 t/m 9), dan de installatiehint, de tekst van "Check je mail" en de sectie "Inloglink plakken" met de waarschuwing, exact zoals in Interfaces. Commit: `feat(WP-18): install hint and pasted-link login with preview warning on /login`.
9. **RUNBOOK.** §4, §11 (punt 1, 3, 5) en §14 (punt 4, nieuwe punten 12 t/m 15) zoals in Interfaces; §11 punt 9 en §15 niet aanraken. Commit: `docs(WP-18): runbook for push in the PWA`.
10. **Eindcontrole.**
    - Vanuit `web/`: `npm ci && npm run check && npm test && npm run build && npm run verify:build`.
    - Vanuit de root: `bash scripts/check-no-client-openmeteo.sh`.
    - `cd ingest && uv run pytest`.
    - `git grep -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'` geeft niets.
    - `grep -rn "console\." web/src/lib/push.ts web/src/lib/sw/push.ts` toont alleen de vaste teksten uit E35.

    Schrijf afwijkingen in `docs/wp/WP-18/deviations.md` en zet AC-5 als `NEEDS_LARS` (procedure in het Testplan, inclusief de controle van R1).
