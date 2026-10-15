# Blueprint WP-18: Web Push: PWA
Status: DRAFT
Revisie: 1

## Doel
Ingelogde gebruikers zetten op hun telefoon (of computer) met één tik pushmeldingen aan op `/alerts`. De service worker toont binnenkomende alerts uit WP-17, en een tik op een melding opent de juiste pagina. Concreet:
1. `PUBLIC_VAPID_PUBLIC_KEY` als publieke build-variabele, met validatie die de private key weigert.
2. `#lib/push.ts` met `isPushSupported`, `needsInstallFirst`, `enablePush`, `disablePush` (contract), plus `getPushStatus` en `releasePushForSignOut`.
3. Schrijven naar `push_subscriptions` via `#lib/user-data.ts` (blijft de enige schrijfmodule).
4. `push`- en `notificationclick`-handlers in `src/service-worker/index.ts`, met de logica in `#lib/sw/push.ts` (te testen in vitest).
5. Op `/alerts` een sectie "Meldingen op dit apparaat"; op iOS buiten de beginschermapp een installatie-uitleg in plaats van de knop.
6. Bij uitloggen eerst het abonnement van dit apparaat opruimen (WP-17, "Gevolgen").
7. Voorstel (A3): op iOS in de beginschermapp inloggen door de inloglink te plakken, omdat de magic link in Safari opent en push daar niet kan.

## Aannames
Voorstellen waar Lars op kan reageren staan als **Voorstel**.

- **A1. Databasetoegang voor `push_subscriptions` komt in `user-data.ts`, niet in `push.ts`.** WP-16 maakte `user-data.ts` de enige module die gebruikersgegevens schrijft, bewaakt door `user-tables.test.ts`. Die regel blijft zo eenvoudig mogelijk: `push.ts` bevat alleen de browserkant (Notification, service worker, PushManager) en roept drie nieuwe functies in `user-data.ts` aan. `user-tables.test.ts` krijgt `push_subscriptions` erbij als vierde tabel, met insert toegestaan op `favorites` en `push_subscriptions`. Dit wijkt af van de suggestie in WP-16 ("`push.ts` schrijft `push_subscriptions`"); WP-16 liet de keuze aan WP-18.
- **A2. Geen user-id en geen endpoint in request-URL's.** De insert stuurt alleen `endpoint`, `p256dh` en `auth` in de body; `user_id` volgt uit de kolomdefault `auth.uid()` (WP-17). Het eigen abonnement zoeken gaat door de eigen rijen op te halen (`select id,endpoint,created_at`, RLS geeft alleen eigen rijen) en in de browser te vergelijken. Verwijderen gaat op `id`. Zo komt het endpoint (een capability-URL) nooit in een query-string en dus niet in de request-logs van Supabase. `push.ts` hoeft de sessie daardoor ook niet te kennen (geen import van `auth.ts`, geen kringverwijzing).
- **A3. Voorstel: inloggen met een geplakte inloglink in de beginschermapp.** Op iOS heeft een app op het beginscherm eigen opslag; de magic link uit de mail opent in Safari en logt dáár in (WP-13 R3). Push werkt op iOS alleen in de beginschermapp, dus zonder dit kan een iPhone-gebruiker geen meldingen aanzetten. Inloggen met een code vraagt een aangepast mailtemplate, en dat kan op het gratis plan pas met eigen SMTP (WP-13 A6, WP-22). De link zelf bevat al alles: `https://<ref>.supabase.co/auth/v1/verify?token=<token-hash>&type=magiclink&redirect_to=…` (gecontroleerd in de broncode van Supabase Auth, zie Externe afhankelijkheden). `supabase.auth.verifyOtp({ token_hash, type: 'magiclink' })` wisselt die hash in voor een sessie. Op `/login` komt daarom, alleen in standalone-modus, een veld "Inloglink plakken". Geen nieuwe dienst, geen wijziging aan Supabase. Wijst Lars dit af, dan vervallen stap 7 en 8 van het stappenplan; AC-5 kan dan alleen op Android of een computer.
- **A4. `PUBLIC_VAPID_PUBLIC_KEY` is optioneel.** Leeg of afwezig betekent: push is in deze build niet beschikbaar ("Meldingen zijn in deze versie van Shakka nog niet beschikbaar."). Zo faalt geen preview-build zolang de variabele nog niet in Cloudflare staat, en hebben CI en de tests hem niet nodig. Een ingevulde maar ongeldige waarde laat de build falen. Een waarde die op een private key lijkt (32 bytes) geeft een expliciete fout, net als `sb_secret_` bij de Supabase-sleutel. De SvelteKit-docs staan een schema toe dat `undefined` teruggeeft (zie Externe afhankelijkheden).
- **A5. Uitzetten en uitloggen: eerst de rij verwijderen, dan `subscription.unsubscribe()`.** Volgorde uit WP-17. Mislukt het verwijderen (offline, verlopen sessie), dan wordt toch afgemeld bij de browser: het endpoint is dan dood, de push-service geeft 404/410, en WP-17 ruimt de rij bij de volgende aflevering op. Voor de gebruiker staat push dus altijd uit na "Meldingen uitzetten" of "Uitloggen". `disablePush` gooit nooit.
- **A6. Uitloggen ruimt het abonnement van dit apparaat op** (WP-17, review N-7), met een tijdslimiet van 5 seconden zodat uitloggen nooit blijft hangen. Dit gebeurt in `signOut()` in `auth.ts`, zodat elk uitlogpad het doet.
- **A7. Endpoint van een ander account op hetzelfde apparaat.** Geeft de insert `23505` en staat het endpoint niet bij de eigen rijen, dan hoort het bij een ander account dat hier ooit meldingen aanzette en niet uitlogde (of waarvan de sessie verliep). Dan meldt `enablePush` dat abonnement af bij de browser, maakt een nieuw abonnement (nieuw endpoint) en voegt dat in. Het oude endpoint is daarmee dood en wordt door WP-17 opgeruimd (410). Zo komen de meldingen van het vorige account niet meer op dit apparaat. Geeft ook het nieuwe endpoint `23505`, dan volgt een melding.
- **A8. Hoogstens 10 abonnementen per gebruiker, ook in de app.** WP-17 bedient alleen de 10 nieuwste (`MAX_TARGETS_PER_USER`). Na een geslaagde aanmelding verwijdert de app de eigen rijen boven die 10 (oudste eerst, nooit het huidige endpoint). Zo klopt de status "aan" op elk apparaat met wat de backend werkelijk bedient: een weggevallen apparaat toont daarna "uit". Een grens in de database blijft WP-22.
- **A9. Uitleg "nieuwe windows" bij aanzetten** (WP-17 A1, "Gevolgen"). Bij de knop staat: meldingen gaan over nieuwe windows en wijzigingen; een window dat al liep, meldt Shakka pas bij een wijziging. De handmatige reset uit RUNBOOK §14 punt 9 blijft de enige ingreep.
- **A10. Geen `renotify`, geen acties, geen badge.** Een melding met dezelfde `tag` vervangt de vorige stil (standaardgedrag). `renotify` wordt niet door alle browsers ondersteund en valt buiten de payload uit WP-17. `icon` is het bestaande app-icoon `/icons/icon-192.png`.
- **A11. `notificationclick`: exact dezelfde URL focussen, anders `clients.openWindow(url)`.** Het patroon uit MDN. Geen `WindowClient.navigate()`: dat werkt alleen voor vensters die door de service worker worden beheerd, en zonder `clients.claim()` (WP-13 A7) is dat bij de eerste pagina niet zo. De URL uit de payload wordt opgelost ten opzichte van de origin van de service worker; alleen `http:` en `https:` zijn toegestaan, anders `/`. Een absolute `go_url` met een andere origin (bijv. productie-URL terwijl de app vanaf een preview draait) wordt wel geopend.
- **A12. Geen `pushsubscriptionchange`-handler.** Vernieuwt de browser een abonnement, dan geeft het oude endpoint 410 en ruimt WP-17 het op; `/alerts` toont dan "uit" en de gebruiker zet het opnieuw aan. Automatisch opnieuw registreren vanuit de service worker vraagt een sessie in de service worker; dat is meer dan deze WP nodig heeft.
- **A13. Geen wijziging aan `ingest/`, `supabase/`, `.github/`, `vite.config.ts` of `package.json`.** Geen nieuwe packages. De tabel en RLS komen uit WP-17.
- **A14. De service worker cachet niets nieuws.** De push-handlers doen geen enkele fetch. Supabase blijft `passthrough` (WP-13). Na een deploy wordt de nieuwe service worker pas actief als alle vensters van de app dicht zijn (geen `skipWaiting`, WP-13 A7). Tot dan heeft het apparaat de oude service worker zonder `push`-handler; de RUNBOOK zegt daarom: na de deploy de app volledig sluiten en opnieuw openen vóór het aanzetten.

## Ontwerp

**Lagen.**
```
routes/alerts/+page.svelte ──> components/PushSettings.svelte ──> #lib/push.ts
routes/login/+page.svelte  ──> #lib/platform.ts, #lib/auth.ts (signInWithPastedLink)
#lib/auth.ts (signOut) ──> #lib/push.ts (releasePushForSignOut)
#lib/push.ts ──> #lib/platform.ts, #lib/env-schema.ts (base64UrlToBytes), $app/env/public,
                 #lib/user-data.ts (push_subscriptions) ──> #lib/supabase.js
src/service-worker/index.ts ──> #lib/sw/shell.ts (WP-13), #lib/sw/push.ts (nieuw)
puur, zonder I/O: #lib/platform.ts (met injecteerbare PlatformInfo), #lib/sw/push.ts (met deps), env-schema
```

**Status van een apparaat.** `getPushStatus()` bepaalt zonder iets te vragen of te schrijven de toestand, in deze volgorde: iOS buiten de beginschermapp → `needs_install`; geen Push API → `unsupported`; geen VAPID-sleutel in de build → `unavailable`; toestemming geweigerd → `denied`; toestemming niet gegeven, geen browserabonnement of een abonnement met een andere sleutel → `off`; anders zoekt hij het endpoint in de eigen rijen: gevonden → `on`, niet gevonden → `off`. Een fout bij het laden → `error`. Pas de laatste stap raakt de database, dus de pagina vraagt nooit toestemming en schrijft nooit bij het laden (AC-2).

**Aanzetten.** `enablePush()` wordt synchroon vanuit de klik aangeroepen. De eerste `await` is `Notification.requestPermission()`, zodat iOS en Firefox de aanvraag als gebruikersgebaar zien. Daarna: `navigator.serviceWorker.ready` (met een tijdslimiet van 10 s; in `vite dev` wordt geen service worker geregistreerd), een bestaand abonnement hergebruiken als de sleutel klopt (anders eerst afmelden), anders `pushManager.subscribe({ userVisibleOnly: true, applicationServerKey })` met de sleutel als `Uint8Array`. Dan de insert, de afhandeling van `23505` (A7) en het opschonen boven 10 (A8).

**Service worker.** `#lib/sw/push.ts` parseert de payload van WP-17 zonder ooit te gooien: ongeldige JSON of een leeg veld valt terug op vaste waarden, zodat er altijd een melding verschijnt (`userVisibleOnly`; Chrome toont anders een eigen melding, en een stille push kan op iOS het abonnement kosten). `index.ts` is alleen bedrading, net als bij `shell.ts`.

**iOS.** De detectie staat in `#lib/platform.ts`: iPhone, iPad of iPod in de user-agent, of iPadOS met een desktop-user-agent (`Macintosh` plus `maxTouchPoints > 1`). Standalone is `navigator.standalone === true` of `matchMedia('(display-mode: standalone)')`. Alle functies krijgen optioneel een `PlatformInfo`, zodat ze puur te testen zijn.

**Waarom zo.** Elke regel die het contract bewaakt (geen toestemming bij laden, insert met precies drie velden, rij weg vóór afmelden, geen endpoint in URL's of logs, alleen `user-data.ts` schrijft) is een test. De browser-API's zitten achter kleine functies met structurele types, zodat vitest ze met nepobjecten kan aansturen.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `web/src/env.ts` | wijzigen | Derde variabele `PUBLIC_VAPID_PUBLIC_KEY` (zie Interfaces). |
| `web/src/lib/env-schema.ts` | wijzigen | `base64UrlToBytes`, `parseVapidPublicKey`. Bestaande functies ongewijzigd. |
| `web/.env.example` | wijzigen | Twee regels erbij (zie Interfaces). |
| `web/src/lib/platform.ts` | aanmaken | `PlatformInfo`, `readPlatform`, `isIos`, `isStandalone`, `needsInstallFirst`. |
| `web/src/lib/types.ts` | wijzigen | Aan het eind: `PUSH_SUBSCRIPTION_COLUMNS`, `OwnPushSubscription`, `PushSubscriptionKeys`. |
| `web/src/lib/user-data.ts` | wijzigen | Commentaarregel bovenaan (vier tabellen); aan het eind `listOwnPushSubscriptions`, `addPushSubscription`, `removePushSubscription`. |
| `web/src/lib/push.ts` | aanmaken | Constanten, `PUSH_MESSAGES`, `PushStatus`, `isPushSupported`, re-export `needsInstallFirst`, `vapidKeyBytes`, `withTimeout`, `subscriptionKeys`, `getPushStatus`, `enablePush`, `disablePush`, `releasePushForSignOut`. |
| `web/src/lib/sw/push.ts` | aanmaken | Payloadparser, URL-resolutie, `createPushHandlers`. |
| `web/src/service-worker/index.ts` | wijzigen | Push-handlers registreren (zie Interfaces); de commentaarregel over WP-18 vervalt. |
| `web/src/lib/components/PushSettings.svelte` | aanmaken | Sectie "Meldingen op dit apparaat". |
| `web/src/routes/alerts/+page.svelte` | wijzigen | Import en `<PushSettings>` direct onder `<h1>`. |
| `web/src/lib/supabase.ts` | wijzigen | Export `supabaseOrigin`. |
| `web/src/lib/auth.ts` | wijzigen | `signOut` roept eerst `releasePushForSignOut()` aan; `AUTH_MESSAGES.linkInvalid`; `parseMagicLink`, `pastedLinkErrorMessage`, `signInWithPastedLink`. |
| `web/src/routes/login/+page.svelte` | wijzigen | Installatiehint op iOS in Safari; sectie "Inloglink plakken" in standalone-modus. |
| `web/src/app.css` | wijzigen | Drie regels aan het eind (zie Interfaces). |
| `web/test/helpers/fake-push.ts` | aanmaken | `TEST_VAPID_PUBLIC_KEY`, user-agents, `publicEnv`, `fakeSubscription`, `installPushEnv`. |
| `web/test/env-schema.test.ts` | wijzigen | Tests voor de twee nieuwe functies. |
| `web/test/env-example.test.ts` | wijzigen | Drie sleutels verwacht. |
| `web/test/platform.test.ts` | aanmaken | Zie Testplan. |
| `web/test/user-data.test.ts` | wijzigen | `describe('push_subscriptions')`. |
| `web/test/user-tables.test.ts` | wijzigen | Vier tabellen, insert ook op `push_subscriptions`. |
| `web/test/push-schema.test.ts` | aanmaken | Kolommen en insert-grant tegen de WP-17-migratie. |
| `web/test/push.test.ts` | aanmaken | AC-2 op moduleniveau. |
| `web/test/sw-push.test.ts` | aanmaken | AC-3. |
| `web/test/push-settings.test.ts` | aanmaken | AC-2 en AC-4 op componentniveau. |
| `web/test/alerts-page.test.ts` | wijzigen | Mock van `$app/env/public`; één extra test (AC-4 op de pagina). |
| `web/test/auth.test.ts` | wijzigen | Mock van `#lib/push.js`, `verifyOtp` en `supabaseOrigin` in de supabase-mock; tests voor uitloggen en de geplakte link. |
| `web/test/login.test.ts` | wijzigen | Mock van `#lib/push.js`, `verifyOtp` en `supabaseOrigin`; tests voor hint en plakveld. |
| `docs/RUNBOOK.md` | wijzigen | §4, §11 en §14 (zie Interfaces). |

Geen andere bestanden. `docs/STATUS.md` en `WORK_PACKAGES.md` werkt de orchestrator bij.

## Interfaces en contracten

### `web/src/env.ts` (toevoegen, na `PUBLIC_SUPABASE_PUBLISHABLE_KEY`)
```ts
import { parsePublishableKey, parseSupabaseUrl, parseVapidPublicKey } from './lib/env-schema.js';
// ...
	PUBLIC_VAPID_PUBLIC_KEY: {
		public: true,
		static: true,
		schema: parseVapidPublicKey,
		description:
			'VAPID public key for Web Push (same value as VAPID_PUBLIC_KEY of the ingest). Empty = push disabled. Never the private key.'
	}
```

### `web/src/lib/env-schema.ts` (toevoegen)
```ts
/** Decodes base64url (with or without '=' padding) to bytes.
 *  Throws Error('invalid base64url') for other characters or a length that is 1 mod 4. */
export function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer>;

/** Validates PUBLIC_VAPID_PUBLIC_KEY. Empty or missing -> undefined (push disabled in this build).
 *  Returns the key without '=' padding. Never echoes the value. */
export function parseVapidPublicKey(value: string | undefined): string | undefined;
```
`base64UrlToBytes`: `/^[A-Za-z0-9_-]*={0,2}$/` anders fout; padding eraf; lengte `% 4 === 1` → fout; `-`→`+`, `_`→`/`, aanvullen met `=` tot een veelvoud van 4; `atob`; per teken `charCodeAt` in een `new Uint8Array(n)`.

`parseVapidPublicKey`, in deze volgorde:
1. `raw = value?.trim() ?? ''`; leeg → `undefined`.
2. `key = raw.replace(/=+$/, '')`; bevat `key` iets anders dan `[A-Za-z0-9_-]`, of gooit `base64UrlToBytes(key)` → `Error('PUBLIC_VAPID_PUBLIC_KEY must be base64url: use VAPID_PUBLIC_KEY from shakka alerts vapid-keys')`.
3. 32 bytes → `Error('PUBLIC_VAPID_PUBLIC_KEY looks like a private key: use VAPID_PUBLIC_KEY, never VAPID_PRIVATE_KEY')`.
4. Niet 65 bytes of eerste byte niet `0x04` → `Error('PUBLIC_VAPID_PUBLIC_KEY must be an uncompressed P-256 public key (65 bytes)')`.
5. Return `key`.

### `web/.env.example` (toevoegen aan het eind, exact)
```
# Web Push public key: the same value as VAPID_PUBLIC_KEY in the root .env. Never the private key. Empty = push disabled.
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
/** Reads navigator/window defensively: missing navigator -> '' / 0 / false; missing matchMedia -> false. */
export function readPlatform(): PlatformInfo;
/** /\b(iPhone|iPad|iPod)\b/ in the UA, or iPadOS with a desktop UA (/\bMacintosh\b/ and maxTouchPoints > 1). */
export function isIos(p: PlatformInfo = readPlatform()): boolean;
/** navigatorStandalone || displayModeStandalone */
export function isStandalone(p: PlatformInfo = readPlatform()): boolean;
/** isIos(p) && !isStandalone(p): Web Push on iOS/iPadOS only works in the Home Screen app (16.4+). */
export function needsInstallFirst(p: PlatformInfo = readPlatform()): boolean;
```
`readPlatform` leest `navigator.userAgent`, `navigator.maxTouchPoints ?? 0`, `(navigator as Navigator & { standalone?: boolean }).standalone === true` en, alleen als `typeof window.matchMedia === 'function'`, `window.matchMedia('(display-mode: standalone)').matches`.

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

/** 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window (false without window). */
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
/** withTimeout(disablePush(), SIGN_OUT_PUSH_TIMEOUT_MS, undefined) */
export function releasePushForSignOut(): Promise<void>;
```
`PUBLIC_VAPID_PUBLIC_KEY` wordt alleen binnen functies gelezen (via een interne `currentVapidKey()`), nooit op moduleniveau gekopieerd; zo werkt een testmock van `$app/env/public` per test.

Interne helpers (niet geëxporteerd):
- `sameKey(sub, key)`: `const k = sub.options?.applicationServerKey; return !k || bytesEqual(new Uint8Array(k), key);` (oudere Safari kent `options` niet; dan geldt hij als gelijk).
- `currentSubscription()`: `reg = await withTimeout(navigator.serviceWorker.getRegistration(), SW_READY_TIMEOUT_MS, undefined)`; `reg ? await reg.pushManager.getSubscription() : null`.
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
const reg = await withTimeout(navigator.serviceWorker.ready, SW_READY_TIMEOUT_MS, null);
if (!reg) return { ok: false, error: PUSH_MESSAGES.noServiceWorker };
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
		message = { kind: 'alert', text: r.error ?? PUSH_MESSAGES.subscribeFailed };
		if (r.error === PUSH_MESSAGES.denied) status = 'denied';
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
- Import `import { releasePushForSignOut } from '#lib/push.js';` en `supabaseOrigin` uit `#lib/supabase.js`.
- `AUTH_MESSAGES.linkInvalid = 'Dit is geen geldige inloglink. Kopieer de link uit de mail van Shakka opnieuw.'` (toevoegen; bestaande sleutels ongewijzigd).
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
  /** Token hash from a pasted magic link of this project:
   *  origin === supabaseOrigin, pathname '/auth/v1/verify', type 'magiclink', token non-empty,
   *  no whitespace, at most 256 chars. Anything else -> null. */
  export function parseMagicLink(text: string, origin: string): string | null;
  /** otp_expired -> linkExpired; AuthRetryableFetchError or status 0 -> network;
   *  status 429, over_request_rate_limit or over_email_send_rate_limit -> rateLimited; else linkFailed. */
  export function pastedLinkErrorMessage(error: unknown): string;
  /** parseMagicLink(text, supabaseOrigin); null -> { error: linkInvalid } without a call.
   *  supabase.auth.verifyOtp({ token_hash, type: 'magiclink' }); error -> pastedLinkErrorMessage;
   *  throw -> network. Success: {} (the session store updates via onAuthStateChange). Never logs the link. */
  export async function signInWithPastedLink(text: string): Promise<{ error?: string }>;
  ```

### `web/src/routes/login/+page.svelte` (wijzigen)
- Script: `import { isStandalone, needsInstallFirst } from '#lib/platform.js';` en `signInWithPastedLink` uit `#lib/auth.js`; `const standalone = isStandalone(); const installHint = needsInstallFirst();`; state `link = $state('')`, `linkBusy = $state(false)`, `linkError = $state<string | null>(null)`; `submitLink(e)`: `preventDefault`; als `linkBusy` return; `linkError = null; linkBusy = true; r = await signInWithPastedLink(link); linkBusy = false; if (r.error) linkError = r.error; else link = '';`.
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
  {#if !$session && standalone}
  	<section class="paste-link" aria-labelledby="paste-link-title">
  		<h2 id="paste-link-title">Inloglink plakken</h2>
  		<p class="hint">
  			Op iPhone en iPad opent de link uit de mail in Safari, niet in deze app. Tik de link daarom niet aan:
  			houd hem ingedrukt, kies ‘Kopieer link’ en plak hem hier.
  		</p>
  		<form novalidate onsubmit={submitLink}>
  			<label for="magic-link">Inloglink</label>
  			<input id="magic-link" name="magic-link" type="url" inputmode="url" autocomplete="off" bind:value={link} />
  			<button type="submit" disabled={linkBusy}>Inloggen met link</button>
  			{#if linkError}<p role="alert" class="error">{linkError}</p>{/if}
  		</form>
  	</section>
  {/if}
  ```

### `web/src/app.css` (toevoegen aan het eind)
```css
/* Push settings and pasted login link (WP-18) */
.push-settings { padding: 0.75rem 0; border-bottom: 1px solid #ddd; }
.push-settings h2 { font-size: 1.1rem; margin: 0 0 0.25rem; }
.paste-link { margin-top: 1.5rem; padding-top: 0.75rem; border-top: 1px solid #ddd; }
```

### Payload (consistent met WP-17)
De service worker leest JSON `{ "title": str, "body": str, "url": str, "tag": str }` (hoogstens 3.000 bytes). `url` is absoluut (`go_url`) of relatief (`/spot/{id}`, `/` bij de test-push); `tag` is `alert-{alert_state.id}` of `shakka-test`. `showNotification(title, { body, icon, tag, data: { url } })` met `data.url` als absolute URL.

### `docs/RUNBOOK.md`
- **§4**, tabel: nieuwe rij `| \`PUBLIC_VAPID_PUBLIC_KEY\` | \`web/.env\`, Cloudflare Pages | web: Web Push aanzetten (zelfde waarde als \`VAPID_PUBLIC_KEY\`) | WP-18 |` na de rij `PUBLIC_SUPABASE_URL…`. Onder de tabel, na "…`sb_secret_` begint.": "Ook `PUBLIC_VAPID_PUBLIC_KEY` is publiek; de build weigert een waarde die op de private key lijkt."
- **§11 punt 1**, aanvullen: "Voor pushmeldingen lokaal: zet de publieke VAPID-sleutel in `web/.env` zonder hem te tonen: `grep '^VAPID_PUBLIC_KEY=' .env | sed 's/^/PUBLIC_/' >> web/.env` (vanuit de repo-root). In `npm run dev` werken meldingen niet (geen service worker); gebruik `npm run build && npm run preview`."
- **§11 punt 3**, de environment variables aanvullen met `PUBLIC_VAPID_PUBLIC_KEY` (Production en Preview).
- **§11 punt 5**, de laatste zin "(zie WP-18)" vervangen door: "In de beginschermapp log je daarom in met 'Inloglink plakken' op de inlogpagina: houd de link in de mail ingedrukt, kies 'Kopieer link' (niet openen: de link werkt één keer) en plak hem in de app. Laat de mail-app een voorvertoning van de link laden, dan kan de link al gebruikt zijn; zet de voorvertoning uit (in het menu bij ingedrukt houden) of kopieer de link op je Mac en plak hem via het gedeelde klembord op je iPhone."
- **§14 punt 4** vervangen door: "**Cloudflare Pages (WP-18).** Zet `PUBLIC_VAPID_PUBLIC_KEY` (Production en Preview) op exact dezelfde waarde als `VAPID_PUBLIC_KEY` en deploy opnieuw. Zonder deze variabele toont de app 'Meldingen zijn in deze versie van Shakka nog niet beschikbaar.' Een andere sleutel dan die van de ingest geeft bij elke aflevering 403 (punt 7 en 10)."
- **§14**, nieuwe punten na 11:
  12. **Meldingen aanzetten (vanaf WP-18).** Android en computer: open Shakka, log in, ga naar Alerts en tik "Meldingen aanzetten". iPhone en iPad (iOS 16.4 of nieuwer): eerst in Safari "Zet op beginscherm", dan Shakka vanaf het beginscherm openen, daar inloggen (inloglink plakken, §11 punt 5) en op Alerts aanzetten. Installeer de productie-URL, want de "ik ga"-links in meldingen wijzen daarheen (`APP_BASE_URL`).
  13. **Na een deploy.** Een nieuwe versie van de service worker wordt pas actief als alle vensters van Shakka dicht zijn. Sluit de app na de deploy van WP-18 dus één keer helemaal (op iOS: wegvegen in de appkiezer) en open hem opnieuw, vóór je meldingen aanzet of test.
  14. **Uitloggen en gedeelde apparaten.** Uitloggen verwijdert het abonnement van dit apparaat; daarna krijgt het apparaat geen meldingen meer. Zet iemand anders op hetzelfde apparaat meldingen aan, dan krijgt het apparaat een nieuw abonnement en gaan de meldingen van het vorige account er niet meer heen. Per account gelden hoogstens 10 apparaten; bij een elfde verdwijnt het oudste.
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
| E7 | Toestemming geweigerd in de prompt | `denied`-melding; status wordt `denied`; geen subscribe, geen DB-call. |
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
| E21 | Uitloggen terwijl `getRegistration` of de DB hangt | Na 5 s gaat het uitloggen door. |
| E22 | Uitloggen in een ander tabblad terwijl `/alerts` open is | `signedIn` wordt `false`: de sectie verdwijnt (behalve de iOS-uitleg); een lopende statusaanvraag wordt genegeerd (token). |
| E23 | Push zonder data, met ongeldige JSON of met `text()` die gooit | Melding "Shakka" met `FALLBACK_BODY`, `data.url` = `<origin>/`, geen `tag`. |
| E24 | Payload met lege titel of zonder `tag` | Titel "Shakka"; geen `tag`-sleutel in de opties. |
| E25 | Payload-`url` `javascript:…` of `data:…` | `data.url` = `<origin>/`. |
| E26 | Payload-`url` absoluut op een andere origin (productie vs. preview) | Wordt geopend met `openWindow` (A11). |
| E27 | Tik terwijl de app al op exact die URL open staat | Dat venster krijgt focus; geen nieuw venster. |
| E28 | Tik terwijl de app op een andere pagina open staat | `openWindow(url)`. Op Android kan dat in het bestaande PWA-venster openen (MDN). |
| E29 | `matchAll` of `openWindow` faalt | Geen onafgevangen fout; de melding is gesloten. |
| E30 | Update met dezelfde `tag` | Vervangt de oude melding stil (A10). |
| E31 | Oude service worker nog actief na de deploy | Geen `push`-handler: Chrome toont een eigen melding, iOS kan het abonnement intrekken. RUNBOOK §14 punt 13. |
| E32 | Geplakte link van een ander project, een Outlook-safelink, tekst zonder URL, of `type` ≠ `magiclink` | `linkInvalid`, geen `verifyOtp`-call. |
| E33 | Geplakte link al gebruikt of verlopen | `linkExpired` (`otp_expired`). |
| E34 | Plakveld buiten standalone-modus | Niet zichtbaar. |
| E35 | Logs | `console.warn` alleen met de vaste teksten (`push enable failed`, `push status failed`, `push prune failed`, `push subscription delete failed`, `push unsubscribe failed`); nooit endpoint, sleutels, user-id, link of foutmelding. |

## Testplan
Alle tests staan in `web/test/` en draaien met `npm test`. Pure logica eerst: `env-schema`, `platform`, `sw/push` en de `user-data`-functies vóór de implementatie. Mocks volgen het `vi.hoisted`-patroon; elk bestand met mocks heeft `beforeEach(() => vi.clearAllMocks())`. Testwaarden zijn nooit echte sleutels; `TEST_VAPID_PUBLIC_KEY` is `'B' + 'A'.repeat(86)` (base64url van `0x04` plus 64 nulbytes).

### Helper `web/test/helpers/fake-push.ts`
- `TEST_VAPID_PUBLIC_KEY`, `OTHER_VAPID_PUBLIC_KEY = 'B' + 'Q'.repeat(86)`.
- `IPHONE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1'`, `IPAD_DESKTOP_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15'`, `ANDROID_UA = 'Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36'`.
- `publicEnv = { PUBLIC_VAPID_PUBLIC_KEY: TEST_VAPID_PUBLIC_KEY as string | undefined, PUBLIC_SUPABASE_URL: 'http://127.0.0.1:54321', PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test' }` (muteerbaar object; gebruik: `vi.mock('$app/env/public', async () => (await import('./helpers/fake-push.js')).publicEnv)`; `beforeEach` zet de sleutel terug).
- `fakeSubscription(endpoint = 'https://push.example.test/sub-1', key = TEST_VAPID_PUBLIC_KEY)`: `{ endpoint, options: { applicationServerKey: base64UrlToBytes(key).buffer }, toJSON: () => ({ endpoint, expirationTime: null, keys: { p256dh: 'p256dh-test', auth: 'auth-test' } }), unsubscribe: vi.fn(async () => true) }`.
- `installPushEnv(opts)` met `opts`: `userAgent` (default `ANDROID_UA`), `maxTouchPoints` (0), `navigatorStandalone` (false), `displayModeStandalone` (false), `supported` (true), `permission` (`'default'`), `requestResult` (`'granted'`), `subscription` (`null`), `newSubscriptions` (`[fakeSubscription()]`, `subscribe` geeft ze op volgorde), `ready` (`'resolve'` of `'never'`). Zet via `vi.spyOn(navigator, 'userAgent', 'get')` en `Object.defineProperty(…, { configurable: true })`: `navigator.maxTouchPoints`, `navigator.standalone`, `window.matchMedia` (`vi.fn((q) => ({ matches: q === '(display-mode: standalone)' && displayModeStandalone, media: q }))`), en bij `supported`: `window.PushManager` (lege klasse), `window.Notification` (`{ permission, requestPermission: vi.fn(async () => { N.permission = requestResult; return requestResult; }) }`) en `navigator.serviceWorker` (`{ ready, getRegistration: vi.fn(async () => registration) }`). `registration.pushManager = { getSubscription: vi.fn(async () => current), subscribe: vi.fn(...) }`, waarbij `subscribe` het volgende abonnement teruggeeft en `current` bijwerkt, en `unsubscribe` van een abonnement `current` op `null` zet. Geeft `{ requestPermission, subscribe, getSubscription, registration, uninstall }`; `uninstall` verwijdert alle gezette eigenschappen (`afterEach`).

### Testbestanden

| Bestand | Tests |
|---|---|
| `env-schema.test.ts` (node, uitbreiden) | `base64UrlToBytes('AQID')` → `[1, 2, 3]`; voor `'_-8'`, `'-_'` en `TEST_VAPID_PUBLIC_KEY` dezelfde bytes als `Buffer.from(x, 'base64url')`; `'AQ=='` gelijk aan `'AQ'`; `'a'` (lengte 1 mod 4) en `'a b'` gooien. `parseVapidPublicKey`: `undefined`, `''`, `'  '` → `undefined`; `TEST_VAPID_PUBLIC_KEY` (ook met spaties eromheen en met `=`) → de sleutel zonder `=`; een 43-tekens waarde (`'A'.repeat(43)`, 32 bytes) → melding met "private key"; `'abc!'` → "base64url"; `'B' + 'A'.repeat(42)` (32 bytes, eerste byte 4) → "private key"; base64url van 65 bytes met eerste byte `0x02` → "uncompressed P-256"; `sb_publishable_test` → fout. Geen melding bevat de invoer. |
| `env-example.test.ts` (wijzigen) | Verwacht `['PUBLIC_SUPABASE_URL=', 'PUBLIC_SUPABASE_PUBLISHABLE_KEY=', 'PUBLIC_VAPID_PUBLIC_KEY=']`; de testnaam wordt `declares exactly the public variables, empty`. |
| `platform.test.ts` (node) | Met expliciete `PlatformInfo`: iPhone-UA → `isIos` true; `IPAD_DESKTOP_UA` met `maxTouchPoints` 5 → true, met 0 → false; `ANDROID_UA` → false; `isStandalone` true bij `navigatorStandalone` of `displayModeStandalone`; `needsInstallFirst`: iPhone niet-standalone true, iPhone standalone false, Android false. `readPlatform()` zonder `navigator` (node) geeft `{ userAgent: '', maxTouchPoints: 0, navigatorStandalone: false, displayModeStandalone: false }`. |
| `user-data.test.ts` (uitbreiden) | `listOwnPushSubscriptions`: één call op `push_subscriptions` met ops `[['select', 'id,endpoint,created_at'], ['order', 'created_at', { ascending: false }]]`; geeft `data`; fout `{ code: '42501' }` → `DataError` met operatie `listOwnPushSubscriptions` en code. `addPushSubscription`: ops exact `[['insert', { endpoint, p256dh, auth }]]` (de payload heeft precies die drie sleutels, geen `user_id`) → `'added'`; `23505` → `'exists'`; `'08006'` → `DataError('addPushSubscription', '08006')`. `removePushSubscription('id-1')`: ops `[['delete'], ['eq', 'id', 'id-1']]`; fout → `DataError`. In geen enkele call staat een `eq` op `user_id` of `endpoint`. |
| `user-tables.test.ts` (wijzigen) | Test 2: namen ⊆ `['profiles', 'favorites', 'alert_rules', 'push_subscriptions']` en elk minstens één keer; testnaam `user-data.ts names only the four user tables, each at least once`. Test 4: elke `.insert(` wordt voorafgegaan door `.from('favorites')` of `.from('push_subscriptions')` (regex `/\.from\('(favorites|push_subscriptions)'\)\s*\.insert\($/`). Test 1 blijft: alleen `lib/data.ts` en `lib/user-data.ts` bevatten `.from('`, dus `push.ts` en `sw/push.ts` niet. |
| `push-schema.test.ts` (node) | Leest `supabase/migrations/20261015150000_push_subscriptions.sql`. Kolommen (parser zoals in `schema-columns.test.ts`, regels met twee spaties inspringing): `PUSH_SUBSCRIPTION_COLUMNS` ⊆ kolommen. De grant `grant insert (…) on table public.push_subscriptions to authenticated` bevat `endpoint`, `p256dh` en `auth`; de sleutels van `PushSubscriptionKeys` (als constante lijst in de test: `['endpoint', 'p256dh', 'auth']`) zijn een deelverzameling van die grant; `user_id` heeft `default auth.uid()`. |
| `push.test.ts` (jsdom) | Mocks: `#lib/supabase.js` met de fake supabase (patroon uit `user-data.test.ts`), `$app/env/public` met `publicEnv`. `afterEach(uninstall)`. Zie de lijst hieronder. |
| `sw-push.test.ts` (node) | Zie de lijst hieronder. **(AC-3)** |
| `push-settings.test.ts` (jsdom) | Rendert `PushSettings.svelte` met de echte `push.ts`; mocks zoals in `push.test.ts`. Zie de lijst hieronder. **(AC-2, AC-4)** |
| `alerts-page.test.ts` (wijzigen) | `vi.mock('$app/env/public', …publicEnv)` toevoegen. Bestaande tests ongewijzigd groen (in jsdom zonder Push API toont de sectie bij een sessie de `unsupported`-tekst en doet hij geen query). Nieuw: `installPushEnv({ userAgent: IPHONE_UA, supported: false })`, `sessionStore.set(null)` → de tekst `PUSH_MESSAGES.installFirst` en de loginprompt staan er, geen knop "Meldingen aanzetten", 0 calls. **(AC-4)** |
| `auth.test.ts` (wijzigen) | `vi.mock('#lib/push.js', () => ({ releasePushForSignOut: push.release }))` met `push = vi.hoisted(() => ({ release: vi.fn(async () => {}) }))`; supabase-mock krijgt `verifyOtp: vi.fn()` en `supabaseOrigin: 'https://abc.supabase.co'`. Nieuw: `signOut()` roept `releasePushForSignOut` aan vóór `auth.signOut` (volgorde via `mock.invocationCallOrder`); rejectt `release`, dan wordt `auth.signOut` toch aangeroepen en gooit `signOut()` niet. `parseMagicLink`: `https://abc.supabase.co/auth/v1/verify?token=abc123&type=magiclink&redirect_to=https%3A%2F%2Fapp.test` → `'abc123'`; met spaties eromheen ook; andere origin, ander pad, `type=signup`, lege `token`, token met spatie, 257 tekens, `'geen link'` → `null`. `signInWithPastedLink`: geldig → `verifyOtp` exact `{ token_hash: 'abc123', type: 'magiclink' }`, resultaat `{}`; ongeldig → `{ error: linkInvalid }` en 0 calls; `{ error: { code: 'otp_expired', status: 403 } }` → `linkExpired`; `{ name: 'AuthRetryableFetchError', status: 0 }` → `network`; rejected → `network`; status 500 → `linkFailed`. |
| `login.test.ts` (wijzigen) | Mock van `#lib/push.js` zoals in `auth.test.ts`; supabase-mock krijgt `verifyOtp` en `supabaseOrigin: 'http://127.0.0.1:54321'`. Bestaande tests ongewijzigd groen (geen plakveld, geen hint in jsdom). Nieuw: met `installPushEnv({ displayModeStandalone: true, supported: false })` staat de sectie "Inloglink plakken" er; een geldige link plakken en "Inloggen met link" klikken roept `verifyOtp` aan met de token-hash; `'geen link'` geeft `AUTH_MESSAGES.linkInvalid` (`role="alert"`) en 0 calls. Zonder standalone geen sectie. Met `IPHONE_UA` niet-standalone staat de installatiehint ("Op iPhone of iPad en wil je meldingen?") er. |

**`push.test.ts`, gevallen:**
1. `isPushSupported()`: false zonder `installPushEnv`; true met. `vapidKeyBytes(undefined)` en `vapidKeyBytes('')` → `null`; `vapidKeyBytes(TEST_VAPID_PUBLIC_KEY)` → 65 bytes, eerste `4`. `subscriptionKeys(fakeSubscription())` → `{ endpoint, p256dh: 'p256dh-test', auth: 'auth-test' }`; zonder `keys.auth` → `null`; endpoint `http://…` → `null`.
2. `getPushStatus()`: iPhone-UA niet-standalone → `needs_install`; zonder support → `unsupported`; `publicEnv.PUBLIC_VAPID_PUBLIC_KEY = undefined` → `unavailable`; `permission: 'denied'` → `denied`; `permission: 'default'` → `off` en 0 DB-calls; `granted` zonder abonnement → `off`, 0 DB-calls; `granted` met abonnement en een eigen rij met dat endpoint → `on`; zonder die rij → `off`; abonnement met `OTHER_VAPID_PUBLIC_KEY` → `off` zonder DB-call; select-fout → `error`. In alle gevallen: `requestPermission` en `subscribe` 0 keer aangeroepen. **(AC-2: geen toestemming bij laden)**
3. `enablePush()` (`permission: 'default'`, `requestResult: 'granted'`, geen abonnement): `requestPermission` 1 keer; `subscribe` 1 keer met `{ userVisibleOnly: true, applicationServerKey }`, waarbij `applicationServerKey` een `Uint8Array` is met dezelfde bytes als `base64UrlToBytes(TEST_VAPID_PUBLIC_KEY)`; de `subscribe`-mock controleert dat er op dat moment 0 DB-calls zijn (dus subscribe vóór insert); daarna een call op `push_subscriptions` met ops `[['insert', { endpoint: 'https://push.example.test/sub-1', p256dh: 'p256dh-test', auth: 'auth-test' }]]`; resultaat `{ ok: true }`. **(AC-2)**
4. `requestResult: 'denied'` → `{ ok: false, error: denied }`, `subscribe` 0, DB 0. `'default'` → `dismissed`. `requestPermission` rejectt → `dismissed`.
5. Bestaand abonnement met dezelfde sleutel → `subscribe` 0, insert 1, `ok`. Met `OTHER_VAPID_PUBLIC_KEY` → `unsubscribe` van het oude, dan `subscribe` 1.
6. Insert `23505` en de select geeft een rij met hetzelfde endpoint → `ok`, geen `unsubscribe`.
7. Insert `23505`, select zonder dat endpoint → `unsubscribe` van `sub-1`, `subscribe` levert `sub-2`, tweede insert met `sub-2` → `ok`. Tweemaal `23505` zonder eigen rij → `{ ok: false, error: otherAccount }`.
8. Insert-fout `'08006'` → `saveFailed`; `unsubscribe` 0 keer.
9. `subscribe` rejectt → `subscribeFailed`, 0 DB-calls. Abonnement zonder sleutels in `toJSON` → `subscribeFailed`, 0 DB-calls.
10. `ready: 'never'` met `vi.useFakeTimers()`: na `vi.advanceTimersByTimeAsync(SW_READY_TIMEOUT_MS)` → `noServiceWorker`.
11. Opschonen (A8): na de insert geeft de select 11 eigen rijen (de huidige plus 10 oudere, nieuwste eerst) → precies één delete op de oudste `id`; nooit op de `id` van het huidige endpoint. Een fout bij de delete → toch `{ ok: true }`.
12. iPhone niet-standalone → `installFirst`, `requestPermission` 0. Zonder support → `unsupported`. Zonder sleutel → `unavailable`, `requestPermission` 0.
13. `disablePush()` met abonnement en eigen rij: ops `[['delete'], ['eq', 'id', <id>]]`, en de `unsubscribe`-mock controleert dat die delete-call dan al bestaat (rij weg vóór afmelden); `unsubscribe` 1 keer. Zonder eigen rij: geen delete, wel `unsubscribe`. Select-fout: geen throw, wel `unsubscribe`. Zonder abonnement of zonder support: 0 DB-calls, geen throw. **(AC-2)**
14. `releasePushForSignOut()` met een `getRegistration` die nooit resolvet: met fake timers resolvet hij na `SIGN_OUT_PUSH_TIMEOUT_MS`.
15. `console.warn` (gespyd) is in geen enkel geval aangeroepen met een argument dat `push.example.test`, `p256dh-test` of `auth-test` bevat.

**`sw-push.test.ts`, gevallen** (origin `https://app.test`; `deps` met `vi.fn`; een `event` met `waitUntil: vi.fn()` en `data: { text: () => JSON.stringify(payload) }`; na elke handler `await` op de promise uit `waitUntil`):
1. Alertpayload `{ title: 'Brouwersdam: go za 14–17', body: 'ZW 18–22 kn\nIk ga: …', url: '/spot/brouwersdam', tag: 'alert-11111111-2222-4333-8444-555555555555' }` → `showNotification('Brouwersdam: go za 14–17', { body: 'ZW 18–22 kn\nIk ga: …', icon: '/icons/icon-192.png', tag: 'alert-11111111-2222-4333-8444-555555555555', data: { url: 'https://app.test/spot/brouwersdam' } })` (`toHaveBeenCalledWith`, exact); `waitUntil` 1 keer.
2. Absolute `go_url` `https://app.test/go?spot=brouwersdam&from=2026-10-17T12:00:00Z` → `data.url` ongewijzigd. Andere origin `https://shakka.pages.dev/go?x=1` → ongewijzigd.
3. Test-push `{ title: 'Shakka: testmelding', body: 'Meldingen werken op dit apparaat.', url: '/', tag: 'shakka-test' }` → `tag: 'shakka-test'`, `data.url: 'https://app.test/'`.
4. `data: null`, `'not json'`, `'[]'`, `'null'` en een `text()` die gooit → titel `FALLBACK_TITLE`, body `FALLBACK_BODY`, `data.url` `https://app.test/`, en de opties hebben geen eigenschap `tag` (`not.toHaveProperty('tag')`).
5. `{ title: '  ', body: 5, url: 'javascript:alert(1)' }` → titel `'Shakka'`, body `''`, `data.url` `https://app.test/`, geen `tag`.
6. `onNotificationClick` met `data: { url: 'https://app.test/spot/x' }`: `close` 1 keer; `matchAll` geeft `[{ url: 'https://app.test/spot/x', focus }]` → `focus` 1 keer, `openWindow` 0. Met `[{ url: 'https://app.test/', focus }]` → `openWindow('https://app.test/spot/x')`, `focus` 0. Met `[]` → `openWindow`. **(AC-3: opent of focust `data.url`)**
7. `data: null` → `openWindow('https://app.test/')`. `matchAll` rejectt → de promise uit `waitUntil` resolvet (geen reject).
8. `parsePushPayload` en `resolveTargetUrl` los: `resolveTargetUrl('/a?b=1#c', 'https://app.test')` → `'https://app.test/a?b=1#c'`; `resolveTargetUrl('data:text/html,x', …)` → `'https://app.test/'`; `resolveTargetUrl(undefined, …)` → `'https://app.test/'`.

**`push-settings.test.ts`, gevallen:**
1. Android, ingelogd (`signedIn: true`), toestemming `default`, geen abonnement: na laden staat de knop "Meldingen aanzetten" er en de tekst `PUSH_MESSAGES.newWindowsOnly`; `requestPermission` en `subscribe` 0 keer. Klik → `requestPermission` 1, `subscribe` 1 met de sleutel als `Uint8Array`, daarna een insert met `endpoint`, `p256dh` en `auth`; dan `role="status"` met `PUSH_MESSAGES.enabled` en de knop "Meldingen uitzetten". **(AC-2)**
2. Toestand `on` (toestemming `granted`, abonnement, eigen rij): knop "Meldingen uitzetten"; klik → delete op `push_subscriptions` en `unsubscribe` 1 keer; dan `PUSH_MESSAGES.disabled` en de knop "Meldingen aanzetten". **(AC-2)**
3. **AC-4:** `IPHONE_UA`, niet standalone, `supported: false`: `PUSH_MESSAGES.installFirst` staat er en `queryByRole('button', { name: 'Meldingen aanzetten' })` is `null`, zowel met `signedIn: true` als `false`; 0 DB-calls. Hetzelfde met `IPAD_DESKTOP_UA` en `maxTouchPoints: 5`. Met `IPHONE_UA` en `navigatorStandalone: true` (push ondersteund) staat de knop er wel en geen installatie-uitleg.
4. `signedIn: false` op Android → de component rendert niets (geen `heading` "Meldingen op dit apparaat"), 0 DB-calls, `getRegistration` 0 keer.
5. Toestemming `denied` → `PUSH_MESSAGES.denied`, geen knop. Klik met `requestResult: 'denied'` vanuit `off` → `role="alert"` met de denied-tekst en de denied-toestand.
6. `publicEnv.PUBLIC_VAPID_PUBLIC_KEY = undefined` → `PUSH_MESSAGES.unavailable`, geen knop.
7. Select-fout bij laden → banner met `PUSH_MESSAGES.statusFailed` en "Opnieuw proberen"; klik → nieuwe select.
8. Tijdens een lopende `enablePush` (pending `requestPermission`) is de knop `disabled`.

### Per acceptatiecriterium
- **AC-1:** `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`, en vanuit de repo-root `bash scripts/check-no-client-openmeteo.sh`. `npm run check` dekt ook de typecheck van de service worker met de nieuwe handlers. Lokaal extra (stap 1): zonder de variabele slaagt de build; met een ongeldige waarde of een private key faalt hij met de vaste melding.
- **AC-2:** `push.test.ts` gevallen 2, 3, 13 en `push-settings.test.ts` gevallen 1 en 2 (gemockte `Notification`, `PushManager` en supabase).
- **AC-3:** `sw-push.test.ts` gevallen 1 t/m 7.
- **AC-4:** `push-settings.test.ts` geval 3, `alerts-page.test.ts` (nieuwe test) en `platform.test.ts`.
- **AC-5 (`NEEDS_LARS`):** na de merge en de deploy, met `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare:
  1. app één keer volledig sluiten en openen (RUNBOOK §14 punt 13);
  2. Android: inloggen, Alerts, "Meldingen aanzetten", toestaan. iPhone: Zet op beginscherm, app openen, inloglink plakken, Alerts, aanzetten, toestaan;
  3. `cd ingest && uv run shakka alerts test-push --user-id <id>` → `device 1: ok`, de melding "Shakka: testmelding" verschijnt; een tik opent de startpagina;
  4. een echte alert (RUNBOOK §14 punt 9 en `uv run shakka alerts run`): een tik opent de "ik ga"-link of de spotpagina;
  5. noteren in `verification.md`: hoeveel van titel (≤ 50) en body (≤ 150) zichtbaar is op het vergrendelscherm en uitgeklapt, op welk toestel en OS;
  6. "Meldingen uitzetten" en daarna `test-push` → `no push subscriptions for this user`.

`cd ingest && uv run pytest` blijft groen (geen wijziging in `ingest/`).

## Externe afhankelijkheden
Geen nieuwe packages. Geen nieuwe dienst: de push-services (FCM, Apple, Mozilla, WNS) zijn gratis en worden door de browser gekozen. Gecontroleerd op 15 oktober 2026.

| API | Gebruik | Bron |
|---|---|---|
| `PushManager.subscribe({ userVisibleOnly, applicationServerKey })`; `applicationServerKey` als base64-string of `ArrayBuffer`/`BufferSource`; Chrome en Edge eisen `userVisibleOnly: true`; aanroepen na een gebruikersgebaar | `enablePush` | https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe, https://w3c.github.io/push-api/ |
| `PushManager.getSubscription()`, `PushSubscription.toJSON()` (`endpoint`, `keys.p256dh`, `keys.auth`, base64url zonder padding), `PushSubscription.options.applicationServerKey`, `unsubscribe()` | Status, hergebruik, uitzetten | https://developer.mozilla.org/en-US/docs/Web/API/PushSubscription, https://w3c.github.io/push-api/ |
| `Notification.permission`, `Notification.requestPermission()` (promise) | Toestemming | https://developer.mozilla.org/en-US/docs/Web/API/Notification/requestPermission_static |
| `navigator.serviceWorker.ready`, `getRegistration()` | Registratie ophalen (WP-13 "Gevolgen") | https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerContainer/ready |
| `ServiceWorkerRegistration.showNotification(title, { body, icon, tag, data })`; `PushEvent.data.text()` | `push`-handler | https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration/showNotification, https://developer.mozilla.org/en-US/docs/Web/API/PushEvent |
| `Clients.matchAll({ type: 'window', includeUncontrolled: true })`, `WindowClient.focus()`, `Clients.openWindow(url)` (patroon "zelfde URL focussen, anders openen"; vereist een notificatieklik) | `notificationclick` | https://developer.mozilla.org/en-US/docs/Web/API/Clients/openWindow |
| Web Push op iOS/iPadOS 16.4+: alleen als beginschermapp, manifest `display: standalone`, toestemming alleen na een directe gebruikersactie, feature detection | iOS-uitleg, volgorde in `enablePush` | https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ |
| iOS-detectie: `'PushManager' in window` pas in de beginschermapp, `navigator.standalone`, `matchMedia('(display-mode: standalone)')` (bronnen van derden; Apple documenteert de detectie niet) | `platform.ts` | https://documentation.onesignal.com/docs/en/web-push-for-ios, https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide |
| SvelteKit 3 `defineEnvVars`: een `schema`-functie mag `undefined` teruggeven (variabele optioneel); `public`, `static` | `PUBLIC_VAPID_PUBLIC_KEY` | https://svelte.dev/docs/kit/@sveltejs-kit-env |
| SvelteKit 3 service worker (`src/service-worker/index.ts`, `self` uit `$app/service-worker`, aparte tsconfig) | Bedrading | https://svelte.dev/docs/kit/service-workers (via WP-13) |
| Supabase Auth: de magic-link-URL is `…/verify?token=<TokenHash>&type=magiclink&redirect_to=…` | A3, `parseMagicLink` | https://raw.githubusercontent.com/supabase/auth/master/internal/mailer/templatemailer/templatemailer.go |
| Supabase Auth: `POST /verify` met `token_hash` en type `magiclink` zoekt de gebruiker op het recovery-token (dezelfde hash) | A3 | https://raw.githubusercontent.com/supabase/auth/master/internal/api/verify.go |
| supabase-js `verifyOtp({ token_hash, type })`, `EmailOtpType` bevat `'magiclink'` | `signInWithPastedLink` | https://supabase.com/docs/reference/javascript/auth-verifyotp, https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/auth-js/src/lib/types.ts |
| Standaard magic-link-mail bevat geen code; een code vraagt een aangepast template | A3 (waarom geen code) | https://supabase.com/docs/guides/auth/auth-email-passwordless |
| `push_subscriptions` (kolommen, insert-grant, `user_id default auth.uid()`, `endpoint unique`, RLS) | Contract | `supabase/migrations/20261015150000_push_subscriptions.sql` (WP-17) |

## Risico's
- **R1. Geplakte link op iOS.** De mail-app kan bij ingedrukt houden een voorvertoning laden en zo de eenmalige link verbruiken; Outlook kan links herschrijven (safelinks). Dan volgt "verlopen" of "geen geldige inloglink". Mitigatie: uitleg in de RUNBOOK (voorvertoning uit, of kopiëren op de Mac en plakken via het gedeelde klembord). De structurele oplossing is inloggen met een code zodra er eigen SMTP is (WP-22).
- **R2. Mock van `$app/env/public` in vitest.** Dit mechanisme werkt al voor `$app/navigation`. Wordt een mutatie van `publicEnv` niet gezien door `push.ts` (geen live binding), dan toetst de builder `unavailable` alleen via `vapidKeyBytes(undefined)` en via `push-settings.test.ts` met een aparte testfile die de mock zonder sleutel zet, en noteert dat in `deviations.md`.
- **R3. Optionele variabele in kit 3.** Volgens de docs mag een schema `undefined` teruggeven. Faalt de build toch als de variabele helemaal ontbreekt, dan zet de builder `PUBLIC_VAPID_PUBLIC_KEY: ''` in de `env` van CI-job `web` en in `TEST_ENV` van `vite.config.ts`, en noteert dat in `deviations.md`.
- **R4. Verkeerde publieke sleutel in Cloudflare.** Elk abonnement krijgt dan 403 bij aflevering (WP-17 R1); de app kan dat niet zien. RUNBOOK §14 punt 4, 7 en 10.
- **R5. Oude service worker na de deploy** (E31). Mitigatie: RUNBOOK §14 punt 13. Geen `skipWaiting` (WP-13 A7 blijft).
- **R6. Gedrag van `tag`, `openWindow` en de lengte van de tekst op iOS en Android is niet gemeten.** AC-5 laat het zien; de bevindingen gaan naar `verification.md`.
- **R7. Merge met WP-12 en WP-15.** Beide raken `web/`. Overlap die te verwachten is: `src/env.ts`, `.env.example`, `env-example.test.ts` en `env-schema.ts` (WP-15: `PUBLIC_MAPTILER_KEY`), `app.css` en de RUNBOOK. Alle wijzigingen hier zijn toevoegingen aan het eind van een lijst of bestand; een conflict is mechanisch op te lossen (beide regels houden).
- **R8. Gedeelde iPad of telefoon.** A7 maakt de meldingen van het vorige account op dit apparaat dood zodra een ander account hier aanzet. Dat is bedoeld, maar betekent dat dat account op dit apparaat "uit" ziet als het later terugkomt.
- **R9. Privacy.** De push-services van Google, Apple en Mozilla zien het endpoint en versleutelde payloads; dat hoort bij Web Push. Geen tracking, geen derde-partijscripts. WP-23 neemt het op in de privacypagina.

## Buiten scope
- De verzendkant, de payload en de inkorting (WP-17).
- Meldingsvoorkeuren, stille uren, acties in meldingen, badges, `renotify`.
- Een testmeldingsknop in de app (`shakka alerts test-push` bestaat).
- `pushsubscriptionchange`-afhandeling (A12).
- Inloggen met een code, eigen SMTP, een databasegrens op abonnementen (WP-22).
- `skipWaiting` of een melding "nieuwe versie beschikbaar".
- Privacypagina en CSP (WP-23; push heeft geen extra `connect-src` nodig).
- Wijzigingen in `ingest/`, `supabase/`, `.github/`, `vite.config.ts` en `package.json` (behalve de terugvaloptie uit R3).

## Gevolgen voor latere WP's
- **WP-22:** met eigen SMTP kan inloggen met een code het plakveld (A3) vervangen; dan `signInWithPastedLink` en de sectie op `/login` verwijderen. Een databasegrens op abonnementen per gebruiker kan `pruneOld` (A8) aanvullen.
- **WP-23:** `/privacy` noemt push-abonnementen (endpoint en sleutels per apparaat, verwijderd bij uitzetten, uitloggen of een dood abonnement) en dat de push-service van de browser (Google, Apple, Mozilla) de meldingen bezorgt. `delete_my_account()` verwijdert ze via de cascade. Axe-tests op `/alerts` dekken `PushSettings`. Geen extra origin in `connect-src`.
- **WP-20:** de geplakte link landt niet op een `redirect_to`-pagina; terugkeren naar een `/go`-URL na het inloggen geldt daar ook niet.

## Stappenplan voor de builder
Werk op branch `wp/WP-18` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-18`. Lees of print `.env` en `web/.env` nooit. Draai na elke stap vanuit `web/`: `npm run check && npm test`; na stap 5 en aan het eind ook `npm run build && npm run verify:build`. Eén commit per stap, commitberichten in het Engels.

1. **Env.** Tests eerst in `env-schema.test.ts` (rood), dan `base64UrlToBytes` en `parseVapidPublicKey` in `env-schema.ts`; `env.ts`; `.env.example` en `env-example.test.ts`. Controleer: `npm run build` zonder de variabele slaagt; `PUBLIC_VAPID_PUBLIC_KEY=abc npm run build` faalt met de base64url-melding (zonder de waarde); `PUBLIC_VAPID_PUBLIC_KEY=$(node -e "console.log('A'.repeat(43))") npm run build` faalt met "private key". Werkt het optioneel zijn niet: R3. Commit: `feat(WP-18): PUBLIC_VAPID_PUBLIC_KEY with validation`.
2. **Platform.** `platform.test.ts` (rood), dan `platform.ts`. Commit: `feat(WP-18): iOS and standalone detection`.
3. **Data.** `types.ts` (aan het eind), tests in `user-data.test.ts`, `user-tables.test.ts` aanpassen, `push-schema.test.ts`; dan de drie functies in `user-data.ts` en de commentaarregel. Commit: `feat(WP-18): push_subscriptions in user-data`.
4. **`push.ts`.** `test/helpers/fake-push.ts` en `push.test.ts` (rood), dan `push.ts` exact volgens Interfaces. Commit: `feat(WP-18): subscribe, status and unsubscribe for Web Push`.
5. **Service worker.** `sw-push.test.ts` (rood), dan `sw/push.ts` en de bedrading in `service-worker/index.ts`. `npm run check` (ook de tsc-run voor de service worker) en `npm run build && npm run verify:build`. Controleer met `grep -c notificationclick build/service-worker.js` dat de handler in de build zit (≥ 1). Commit: `feat(WP-18): push and notificationclick handlers in the service worker`.
6. **UI op `/alerts`.** `push-settings.test.ts` (rood), dan `PushSettings.svelte`, de wijziging in `alerts/+page.svelte`, `app.css`; `alerts-page.test.ts` (mock en nieuwe test). Commit: `feat(WP-18): notifications section on /alerts`.
7. **Uitloggen en geplakte link (auth).** `supabaseOrigin` in `supabase.ts`; tests in `auth.test.ts` (rood); dan `signOut`, `AUTH_MESSAGES.linkInvalid`, `parseMagicLink`, `pastedLinkErrorMessage`, `signInWithPastedLink` in `auth.ts`. Voeg de mock van `#lib/push.js` ook toe aan `login.test.ts`, zodat die groen blijft. Commit: `feat(WP-18): release the push subscription on sign-out; sign in with a pasted link`.
8. **`/login`.** Tests in `login.test.ts` (rood), dan de hint en de sectie "Inloglink plakken". Commit: `feat(WP-18): install hint and pasted-link login on /login`.
9. **RUNBOOK.** §4, §11 en §14 zoals in Interfaces. Commit: `docs(WP-18): runbook for push in the PWA`.
10. **Eindcontrole.** Vanuit `web/`: `npm ci && npm run check && npm test && npm run build && npm run verify:build`; vanuit de root `bash scripts/check-no-client-openmeteo.sh`; `cd ingest && uv run pytest`. `git grep -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'` geeft niets. `grep -rn "console\." web/src/lib/push.ts web/src/lib/sw/push.ts` toont alleen de vaste teksten uit E35. Schrijf afwijkingen in `docs/wp/WP-18/deviations.md` en zet AC-5 als `NEEDS_LARS` (procedure in het Testplan).
