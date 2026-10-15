# Review WP-22, ronde 1
Oordeel: CHANGES_REQUIRED

De blueprint is grondig en dekt AC-1 t/m AC-7. De belangrijkste gecontroleerde punten kloppen:
- `with_retries` geeft voor Open-Meteo exact dezelfde wachttijden en teksten als de huidige `request_json`.
- De retry's op `upsert`, `update` en `delete` zijn in alle huidige aanroepen idempotent:
  - `api_usage` krijgt een absolute waarde;
  - `store_plan` werkt bij op `id` en houdt `count == 1` ook na een herhaling;
  - `_close_abandoned`, de voortgang en het einde van een run zijn idempotent.
- Een spot met alleen verouderde data valt in alerts in de bestaande `ineligible`-tak, die niets naar `alert_state` schrijft. Er ontstaat dus geen valse `cancelled`.
- De plan-aantallen van `01`, `02` en `04` kloppen: 71→70, 55→54, 42→40.
- De goldenteksten en tijdhelpers heb ik nagerekend; ze kloppen. 20 juli 2026 is een maandag, en de zomertijd eindigt op 25 oktober 2026.
- De twee actions-SHA's kloppen met de GitHub-API.
- Het GoTrue-gedrag rond `shouldCreateUser` en `signup_disabled` klopt met de broncode.

Er zijn zes blokkerende punten.

## Blokkerend

B-1: `supabase/tests/07_sessions.test.sql` wordt niet aangepast, terwijl `db_usage()` twee bestaande asserts breekt. Waar: Bestanden (Database), Testplan AC-7, stap 8. Waarom:
- Regel 68 eist dat `service_role` precies `purge_expired_sessions` mag uitvoeren. Na `grant execute on function public.db_usage() to service_role` is die set `{purge_expired_sessions, db_usage}`.
- Regel 69 noemt alle security-definer-functies in `public`, en `db_usage` is security definer.
- Daardoor faalt `supabase test db`, en daarmee AC-4 en AC-7.
- WP-23 (R8 en "Gevolgen") rekent er ook expliciet op dat WP-22 deze regels bijwerkt.

Voorstel:
- `07_sessions.test.sql` toevoegen aan Bestanden, met de exacte nieuwe regels 68 (`('purge_expired_sessions'), ('db_usage')`) en 69 (`…, ('db_usage')`). Het plan-aantal blijft gelijk.
- Een coördinatieregel opnemen: merget WP-23 eerst, dan komt `delete_my_account` er ook in, in regel 67 en 69.
- Ook vastleggen dat `push_subscriptions_limit` (security invoker, geen EXECUTE) bewust in geen van de vier sets staat.

B-2: Met A8 worden 401/403-fouten stil. Waar: A8, Interfaces `deliver_event`, `step_alerts`, RUNBOOK §14.7. Waarom:
- WP-17 R1 noemt het scenario "verkeerde `PUBLIC_VAPID_PUBLIC_KEY` in de PWA": elke aflevering geeft 403. Dat werd zichtbaar via `deferred`, een `partial` stap en de `::warning::alerts: … deferred`-annotatie in elke run.
- Na A8 tellen die fouten als `failed` zonder herhaling. `partial` hangt alleen af van `skipped`, `write_errors` en `deferred`, dus de stap wordt `ok`, zonder warning.
- Alle alerts van alle gebruikers gaan dan verloren. Het enige signaal is de regel "Push: x verstuurd, y mislukt" in het weekrapport. Voor een WP die betrouwbaarheid als doel heeft, is dat een regressie in de zichtbaarheid.

Voorstel:
- Een stapwarning toevoegen als er niet-herhaalbare afleverfouten zijn, bijvoorbeeld `f"{n} push delivery(ies) failed without retry (see push_failures in ingest_runs)"`. Een aparte teller `failed_final` of `dropped` in `AlertJobResult`/`alert_counts` is een optie. Overweeg de stap dan `partial` te maken.
- RUNBOOK §14.7 en WP-17 R1 (diagnose via 403) daarop aanpassen.
- Testen met `test_non_retryable_4xx_is_stored`, uitgebreid met de annotatie.

B-3: Brevo kan de eis "open- en kliktracking uit" niet waarmaken. Waar: A15, Externe afhankelijkheden (Brevo), RUNBOOK §17.6. Waarom:
- Volgens Brevo-medewerkers op het eigen communityforum kan tracking bij transactionele e-mail (SMTP/API) niet uit. Dat kan alleen op aanvraag en voor Enterprise-plannen.
- Brevo herschrijft elke link via een klikredirect. De magic link, een eenmalig bearer-token, loopt dan via het trackingdomein van een derde partij.
- Dat botst met de eigen eis in A15 en met de harde regel "geen tracking". Bovendien kan een redirect of prefetch het token verbruiken.

Voorstel:
- Brevo niet als voorstel opnemen, of alleen met de expliciete waarschuwing dat hij niet aan de eisen voldoet.
- In plaats daarvan een dienst voorstellen waarvan aantoonbaar is dat tracking op de gratis tier uit kan, met bronvermelding. Laat de planner het verifiëren, bijvoorbeeld voor Resend of SMTP2GO.
- In de RUNBOOK een test toevoegen: de ontvangen magic link moet direct naar `<project>.supabase.co/auth/v1/verify…` wijzen, zonder redirectdomein.

B-4: De push-allowlist mist `jmt17.google.com`. Waar: A9, `PUSH_SERVICE_HOSTS`, `test_push_allowlist.py`. Waarom:
- Chrome Beta, Dev en Canary, en Chromium-builds, abonneren via `https://jmt17.google.com/fcm/send/…`. Dat is het FCM-stagingendpoint uit de Chromium-broncode (`push_messaging_utils.cc`).
- Meerdere projecten hebben die host deze maand (oktober 2026) aan hun allowlist toegevoegd.
- Met deze blueprint zien zulke gebruikers "push aan" in de app, maar ze krijgen nooit een alert.

Voorstel:
- `jmt17.google.com` als exacte host opnemen in `PUSH_SERVICE_HOSTS`, met een rij in de allowlisttest.
- De bron vermelden in Externe afhankelijkheden.
- Controleer meteen of er nog meer Google-hosts zijn. `android.googleapis.com` (legacy GCM) kan buiten de lijst blijven.

B-5: De CHECK `sessions_starts_at_horizon` botst met het bewerken van een sessie, terwijl A13 zegt dat de grens "de UI niet raakt". Waar: A13, migratie `…_hardening.sql`, E47. Waarom:
- `/mijn-sessies` laat een bestaande sessie bewerken (`updateSession`) met dezelfde datumgrenzen als bij aanmaken (`SessionForm`: `sessionDateBounds(new Date())`, dus tot vandaag + 365 dagen).
- Voorbeeld: een sessie die op dag 0 is aangemaakt, wordt op dag 10 verzet naar dag 375. Dat is toegestaan in de UI, maar overschrijdt `created_at + 370 dagen` en geeft dus `23514`. De gebruiker ziet dan "een van de velden is ongeldig".

Voorstel: kies één van deze en leg het vast.
- (a) Een `BEFORE INSERT OR UPDATE OF starts_at`-trigger met `starts_at <= now() + interval '370 days'`. Een CHECK kan geen `now()` gebruiken. Dit sluit aan op de UI.
- (b) Bewust accepteren: A13 corrigeren, en de bewerkgrens in de UI beperken tot `created_at + 365`. Dat is wel extra webwerk.

In beide gevallen een pgTAP-assert toevoegen voor het bewerkgeval.

B-6: De maandcheck mist de MapTiler-sessies. Waar: stap 13, RUNBOOK §17.8 (tabel). Waarom:
- In scope staat letterlijk "de handmatige maandcheck van MapTiler-sessies".
- Volgens het plan (sectie 2) is de bindende gratis grens 5.000 map sessions per maand.
- De tabel noemt alleen "100.000 requests, actie > 70.000". Daarmee bewaakt de €0-check de grens die het eerst geraakt wordt niet.

Voorstel: een rij "MapTiler map sessions | Cloud, Analytics | 5.000 per maand | > 3.500" toevoegen, naast of in plaats van de rij voor requests.

## Niet-blokkerend

N-1: A11 noemt de versheidsindicator van de app daarna "eerlijk". Dat klopt maar half.
- Een spot wordt nog geëvalueerd zolang de rijen ≤ 3 uur oud zijn. Het laatste `evaluated_at` kan dus tot 3 uur na de laatste fetch liggen, en de app (WP-14 A5) waarschuwt pas 3 uur daarna.
- De forecast kan dus tot ongeveer 6 uur oud zijn voordat de banner verschijnt. Dat is wel begrensd, waar het eerst onbegrensd was.
- Voorstel: formuleer het zo, of laat de builder het in R-sectie/RUNBOOK zetten.

N-2: Over `shouldCreateUser: true` (aandachtspunt 2): het ontwerp is veilig genoeg.
- De vlag in de client was nooit een beveiligingsgrens. Met de publieke anon-sleutel kan iedereen `/auth/v1/otp` met `create_user: true` aanroepen. De echte controle is altijd "Allow new users to sign up" geweest, en "uit" is de veilige stand.
- Een extra guard in de app voegt dus geen veiligheid toe. Twee aanvullingen:
  - (a) Laat het RUNBOOK zeggen dat Lars de instelling nú controleert, los van de merge. Staat hij aan, dan is aanmelden via de API vandaag al open.
  - (b) Bij de test van AC-6: maak de gebruiker aan via Add user mét "Auto Confirm User". Een onbevestigde gebruiker gaat in GoTrue opnieuw door `Signup()` en krijgt `signup_disabled` zolang aanmelden uit staat.
- De orchestrator moet "Nodig van Lars" punt 1 als harde poort vóór de merge behandelen.

N-3: Coördinatie met WP-23.
- Beide WP's voegen een pgTAP-bestand met prefix `09_` toe. Dat werkt (verschillende namen, elk in een eigen transactie), maar `10_hardening.test.sql` houdt de volgorde eenduidig.
- Beide maken een nieuwe RUNBOOK-sectie; afspreken wie §17 wordt.
- De migratie van WP-23 (`20261016090000`) heeft een latere tijdstempel. Wordt die eerst gepusht, dan heeft de push van WP-22 `supabase db push --include-all` nodig. Zet dat in §17.5.
- WP-23 vraagt WP-22 om de telegram-regel in `docs/PRIVACY.md` en de regel "De maildienst" op `/privacy` bij te werken. Die bestanden bestaan pas na WP-23. Neem dat op als voorwaardelijke stap, of laat de orchestrator het als vervolgactie vastleggen.

N-4: Na een herhaling van een doorgevoerde `delete` of `update` is het teruggegeven aantal 0. Een `removed` uit `update_subscriptions`, `deleted` van de retentiejobs en `admin favorites remove` (`count > 0`) kunnen dan te laag of als "niet verwijderd" uitkomen. De state wordt niet fout. Noem het in R1 of A6, zodat niemand op die tellers gaat sturen.

N-5: `DB_RETRY_STATUSES` bevat 502, 503 en 504. Tijdens storingen geeft Supabase via Cloudflare ook 520–524 terug. Die zijn transient en geen SQL-fouten. Overweeg ze toe te voegen; 500 blijft terecht uitgesloten.

N-6: De grens van 20 abonnementen vuurt als BEFORE INSERT-trigger, dus vóór de unieke check. Bij precies 20 rijen geeft het opnieuw aanmelden van een bestaand endpoint `PT400` in plaats van `23505`. `addPushSubscription` maakt daar dan een generieke fout van in plaats van `'exists'`. Dat is zeldzaam, want de app snoeit naar 10. Noem het in RUNBOOK §14.14.

N-7: E50 zegt dat de drie waarschuwingen samen passen ("hoogstens 3 × 55 tekens"). 3 × 55 + 2 = 167 > 150. Bij de testwaarden (10¹² bytes, 10⁷ calls) is het 135, en het algoritme begrenst het hoe dan ook. Pas de tekst aan.

N-8: `secret_values` neemt de ruwe gestripte `OPERATOR_USER_ID` op. `resolve_operator` canonicaliseert naar kleine letters. Neem ook de canonieke vorm op in `secret_values`, voor het geval de waarde in hoofdletters of met accolades is gezet.

N-9: In `09_hardening` geven asserts 19–21 niet alle verplichte kolommen van de sessie-insert. Verwijs naar het insertpatroon van `07_sessions.test.sql` (slug, spot `pgtap-spot`, `organizer_name`), zodat de builder niets hoeft te raden.

N-10: WP-23 zet de moderatie-RPC voor organisatoren onder "WP-22", en WP-22 zet hem buiten scope. Daardoor valt hij tussen wal en schip. De orchestrator moet hem als open punt vastleggen.

N-11: Het runbudget slaat bij een trage ingest juist `alerts` over, de belangrijkste stap. Dat is acceptabel en zichtbaar (exitcode 1), maar noem de afweging expliciet in A12 of R1.

## Gecontroleerde bronnen
- https://api.github.com/repos/actions/checkout/git/ref/tags/v7.0.1 (commit `3d3c42e5aac5ba805825da76410c181273ba90b1`, type `commit`)
- https://api.github.com/repos/actions/setup-node/git/ref/tags/v7.1.0 (commit `949feb2413d6458794dcd2491c4babbbce0c15c1`, type `commit`)
- https://raw.githubusercontent.com/supabase/auth/master/internal/api/magic_link.go
- https://raw.githubusercontent.com/supabase/auth/master/internal/api/signup.go
- https://raw.githubusercontent.com/supabase/auth/master/internal/api/otp.go
- https://supabase.com/docs/guides/auth/rate-limits
- https://supabase.com/docs/guides/platform/database-size
- https://raw.githubusercontent.com/pypa/pip-audit/main/README.md
- https://community.brevo.com/t/no-way-to-disable-by-option-tracking-in-transactional-e-mail/201
- https://github.com/elan-registry/registry/issues/2151
- https://github.com/Significant-Gravitas/AutoGPT/pull/15356 (`jmt17.google.com`)
- https://github.com/natemsz/evesynapse/pull/121
- Eigen code en documenten: `ingest/src/shakka/{db,http,budget,pipeline}.py`, `jobs/{alerts,push,inputs,evaluate,forecast}.py`, `notify/{base,webpush}.py`, `openmeteo/client.py`, `supabase/migrations/*`, `supabase/tests/0{1,2,4,5,7}_*.sql`, `web/src/lib/{auth,sessions,user-data}.ts`, `web/test/{schema-columns,rsvp-contract,no-telegram}.test.ts`, `ingest/tests/test_migrations.py`, en de blueprints van WP-14, WP-17, WP-18 en WP-23
