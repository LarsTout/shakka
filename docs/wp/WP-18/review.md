# Review WP-18, ronde 2
Oordeel: APPROVED

Ronde 2 (revisie 2). Getoetst: de verwerking van B-1 en N-1 t/m N-11, de afwijking bij N-4, `signup`/`invite` tegen de broncode van Supabase Auth, en de nieuwe onderdelen (`updatePending`-guard, uitlogknop met busy-state, wijziging in `+layout.svelte`, `parseVapidPublicKey` die `''` teruggeeft). Bestaande code gelezen op `develop` (stand na WP-12/15, zoals de blueprint aanneemt).

**B-1 is opgelost, en eerlijk.**
- De waarschuwing staat nu in de app, bij het plakveld (`.notice` met `id="paste-link-preview"`, gekoppeld via `aria-describedby`). De volgorde klopt: eerst de voorvertoningen verbergen bij een link in een andere mail, dan de inloglink kopiëren. Het alternatief (computer, gedeeld klembord, niet via WhatsApp of Berichten) staat er ook.
- `otp_expired` geeft in de plak-context `pastedLinkUsed`, en die tekst noemt de voorvertoning. `parseAuthRedirectError` blijft `linkExpired` geven; daar is een test voor.
- In standalone-modus spreekt "Check je mail" het plakveld niet meer tegen.
- `login.test.ts` heeft 9 gevallen. Gevallen 2, 5 en 7 leggen B-1 vast.
- De onzekerheid is eerlijk benoemd: Apple documenteert niet of "Verberg linkvoorvertoningen" in Mail werkt en onthouden wordt. Daarom staat het als R1, met een controle in AC-5 en een notitie in `verification.md`. De menutekst "Verberg linkvoorvertoningen" / "Toon linkvoorvertoningen" heb ik bij appletips.nl gecontroleerd. Die bron gaat over Safari, en dat zegt de blueprint ook.

**De afwijking bij N-4 is terecht.**
- `docs/wp/WP-15/deviations.md` (N-7) bevestigt het: `$app/env/public` resolvet in vitest niet zonder mock (`globalThis.__sveltekit_dev`). `spot-list.test.ts` en `home-no-map.test.ts` laten zien dat `vi.mock('$app/env/public', factory)` wel werkt.
- Een waarde in `TEST_ENV` bereikt `push.ts` dus nooit. Mijn voorstel uit ronde 1 zou niets hebben opgelost.
- De twee terugvalopties werken allebei in vitest: (a) `vi.resetModules` + `vi.doMock` + dynamische import, en (b) een apart testbestand met een statische mock.
- Ik heb nagelopen welke tests de echte `push.ts` laden. Via de echte `auth.ts` gebeurt dat alleen in `auth.test.ts` en `login.test.ts`, en die mocken `#lib/push.js`. Alle andere tests mocken `#lib/auth.js`. Via de pagina laadt alleen `alerts-page.test.ts` de echte `push.ts`, en die krijgt de mock.
- Er ontstaat geen kringverwijzing: `user-data.ts` importeert `auth.ts` niet.

**`signup`/`invite` accepteren is veilig.**
- `templatemailer.go`: de bevestigingsmail en de uitnodiging gebruiken `token=<ConfirmationToken>` met `type=signup` of `type=invite`. De magic link gebruikt `RecoveryToken` met `type=magiclink`.
- `verify.go`: bij POST met `token_hash` controleert `signup`/`invite` tegen `ConfirmationToken` en gaat via `signupVerify`, die de gebruiker bevestigt. `magiclink` gaat via `recoverVerify`. Daarna wordt voor elk type een sessie uitgegeven.
- Het token is net zo eenmalig en geheim als bij de magic link, dus het beveiligingsmodel verandert niet.
- Een al bevestigd adres heeft geen `ConfirmationToken` meer. Dat levert `otp_expired` op, en de gebruiker ziet dan `pastedLinkUsed`.
- `recovery` en `email_change` blijven geweigerd. Dat is terecht.
- `EmailOtpType` in auth-js bevat `signup`, `invite` en `magiclink`.

**De revisie introduceert geen nieuwe blokkerende punten.**
- `updatePending` komt pas na `requestPermission`, dus het gebruikersgebaar blijft de eerste `await`. Na `ready` (er is een actieve worker) zijn `waiting` en `installing` alleen gezet als er echt een update is. De guard is strenger dan nodig, en R5 erkent dat. Hij is wel veilig.
- `+layout.svelte`: `handleSignOut` met `signingOut` en `finally`. `signOut()` gooit nooit. De bestaande layout-tests blijven geldig.
- `parseVapidPublicKey` geeft `''` terug, consistent met `parseMaptilerKey`. `vapidKeyBytes('')` geeft dan `null`, en de status wordt `unavailable`.
- `supabaseOrigin = PUBLIC_SUPABASE_URL` is een origin, want `parseSupabaseUrl` geeft `url.origin` terug. De origin-vergelijking in `parseMagicLink` klopt dus.
- `ssr = false` in `+layout.ts`, dus `isStandalone()` en `needsInstallFirst()` bij de init van de component kunnen geen hydration-verschil geven.

## Blokkerend
Geen.

## Niet-blokkerend
**N-1: `login.test.ts` geval 7 kan op twee elementen struikelen.**
- **Waarom:** de standalone-tekst van "Check je mail" bevat "kopieer hem en plak hem hieronder". De hint in de sectie "Inloglink plakken" bevat die zin ook ("maar kopieer hem en plak hem hieronder"). `getByText(/kopieer hem en plak hem hieronder/)` gooit dan omdat er meerdere treffers zijn.
- **Voorstel:** zoek op een tekst die alleen in de alinea van "Check je mail" staat, zoals "bij ‘Inloglink plakken’" of het e-mailadres in `sentTo`, of zoek binnen die alinea.

**N-2: de `mockReturnValue` in de nieuwe `layout.test.ts`-test lekt naar volgende tests.**
- **Waarom:** `vi.clearAllMocks()` wist alleen de calls, niet de geïmplementeerde returnwaarde. Na `resolve()` is dat onschuldig, want de promise is dan opgelost.
- **Voorstel:** gebruik `mockReturnValueOnce`.

**N-3: `disablePush` en narrowing in de closure.**
- **Waar:** `.find((r) => r.endpoint === sub.endpoint)` gebruikt een `let sub` die in een `try` wordt toegewezen.
- **Waarom:** TS 5.4+ behoudt de narrowing na de laatste toewijzing, dus dit compileert naar verwachting. Klaagt `npm run check` toch, dan lost een `const s = sub` na de `if (!sub) return;` het op.

**N-4: login-CSRF met een geplakte link.**
- **Wat:** iemand kan een ander overhalen om zijn eigen link (magiclink, signup of invite) van dit project te plakken. Het slachtoffer zit dan in het account van de aanvaller.
- **Waarom niet-blokkerend:** dit risico bestaat al bij elke magic link. Het plakveld voegt geen nieuw type toe.
- **Voorstel:** geen actie, hoogstens noemen bij WP-23.

**N-5: de waarschuwing gaat uit van een andere mail met een link.**
- Heeft de gebruiker die niet, dan werkt een link in een andere app (bijv. Notities of Safari) waarschijnlijk ook, want de keuze geldt systeembreed volgens bronnen van derden.
- **Voorstel:** laat de builder dit bij AC-5 meenemen in de notitie over R1. Een tekstwijziging is niet nodig.

## Gecontroleerde bronnen
- https://raw.githubusercontent.com/supabase/auth/master/internal/api/verify.go (POST `token_hash`: `signup`/`invite` tegen `ConfirmationToken` via `signupVerify`, `magiclink`/`recovery` tegen `RecoveryToken` via `recoverVerify`; daarna `issueRefreshToken` voor alle types; GET zet `token` om naar `TokenHash`)
- https://raw.githubusercontent.com/supabase/auth/master/internal/mailer/templatemailer/templatemailer.go (invite: `ConfirmationToken` met `type=invite`; confirmation: `ConfirmationToken` met `type=signup`; magic link: `RecoveryToken` met `type=magiclink`)
- https://raw.githubusercontent.com/supabase/supabase-js/master/packages/core/auth-js/src/lib/types.ts (`EmailOtpType` met `signup`, `invite`, `magiclink`; `VerifyTokenHashParams`)
- https://www.appletips.nl/voorvertoningen-links-verbergen-ios/ ("Verberg linkvoorvertoningen" / "Toon linkvoorvertoningen", keuze wordt onthouden; artikel over Safari)
- Lokaal (develop): `docs/wp/WP-15/deviations.md` (N-7), `web/vite.config.ts`, `web/src/lib/{auth,supabase,env-schema,user-data,favorites}.ts`, `web/src/routes/{+layout.svelte,+layout.ts,login/+page.svelte,alerts/+page.svelte}`, `web/src/service-worker/index.ts`, `web/src/lib/sw/shell.ts`, `web/test/{layout,home-no-map,alerts-page}.test.ts` en een inventaris van de `vi.mock`-aanroepen in `web/test/`, `docs/WORK_PACKAGES.md` (WP-18)
- Vorige review: `docs/wp/WP-18/review.md` (ronde 1)
