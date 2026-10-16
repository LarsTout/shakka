# Blueprint WP-22: Hardening backend en kostenbewaking
Status: APPROVED
Revisie: 2

## Doel

De backend blijft werken als Open-Meteo, Rijkswaterstaat, Supabase of een push-service hapert, en het verbruik van alle gratis tiers is zichtbaar, zodat Shakka ook met meer gebruikers €0 per maand blijft. Concreet:

- één retry/backoff-helper voor alle externe HTTP-calls;
- een service-only RPC `db_usage()`;
- een wekelijks gebruiksrapport en drempelwaarschuwingen als pushmelding aan Lars;
- de kolom `profiles.telegram_chat_id` verwijderd;
- eigen SMTP en de Auth-rate-limits gedocumenteerd;
- een dependency-audit.

Daarnaast neemt deze WP de openstaande "Gevolgen → WP-22"-punten over die backend-hardening zijn: veroudering per spot, een tijdsbudget voor de run, en bij push een retry-limiet, een host-allowlist en een databasegrens. De punten die hier niet passen staan onder "Buiten scope", met reden.

## Aannames

Voorstellen waar nog geen besluit ligt. Lars kan ze bij de review omgooien.

- **A1. `OPERATOR_USER_ID` bevestigd.** Het is de Supabase-user-id (UUID) van Lars, als GitHub Secret en in `.env`, en komt dus niet in de repo. `Settings.operator_user_id: str | None` valideert niet. De stap `usage_report` controleert het formaat met `uuid.UUID`: een ongeldige waarde laat de run niet falen, maar geeft een waarschuwing en geen push. De waarde komt in `secret_values`, zowel ruw (gestript) als in de canonieke vorm (kleine letters, met streepjes, zonder accolades) als die afwijkt, zodat ze uit logs en `ingest_runs.error` wordt geredigeerd. Lars vindt zijn id in het Dashboard onder Authentication, Users (kolom UID).
- **A2. Drempels.**
  - Database: boven 300 MB, waarbij MB = 1024² bytes, zoals `pg_size_pretty` en het Supabase-dashboard tellen. "Boven" is strikt: precies 300 MB geeft geen waarschuwing.
  - Open-Meteo: boven 70% van de echte limieten (sectie 2 van het plan), dus meer dan 7.000 calls op de huidige UTC-dag of meer dan 210.000 in de huidige UTC-maand. Beide bronnen `open_meteo_*` tellen mee, zoals in `BudgetGuard`.
  - De bestaande guard (80% van de limiet, WP-03) en de forecast-warning (80% van de guard) blijven ongewijzigd.
- **A3. Pushvenster voor Lars: 08:00–22:00 lokale tijd** (`Europe/Amsterdam`).
  - Het weekrapport is "due" op maandag binnen dat venster, tot het één keer gelukt is. In de praktijk gaat het dus maandag om 08:17 de deur uit.
  - Een drempelwaarschuwing gaat hoogstens één keer per lokale kalenderdag uit, en alleen binnen het venster.
  - Beide worden gededupliceerd via eerdere `usage_report`-stappen in `ingest_runs` (`counts.report_done`, `counts.warning_notified`).
  - Valt het rapport op maandag weg, bijvoorbeeld omdat alle runs tussen 08:00 en 22:00 falen, dan komt het pas de volgende maandag. Inhalen op dinsdag zou elk uur een duurdere `ingest_runs`-query vergen (egress), dus dat doen we niet.
- **A4. De `::warning::`-annotaties voor drempels komen elk uur** zolang een drempel overschreden is, zoals de bestaande budgetwarning. De push gaat hoogstens één keer per dag (A3).
- **A5. Bewaartermijn `ingest_runs`: 90 dagen.** Het opruimen gebeurt alleen in de run die het weekrapport maakt (één DELETE per week). `ingest_runs` bevat geen persoonsgegevens.
- **A6. Retrybeleid per bron.** Overal via `shakka.http.with_retries`:

  | Bron | Opnieuw bij | Pogingen | Wachttijd (s) |
  |---|---|---|---|
  | Open-Meteo (`request_json`) | transportfout, 429, 5xx (ongewijzigd) | 3 | 1, 2; `Retry-After` bij 429 (1–30) |
  | Rijkswaterstaat (`_post_json`) | transportfout, 429, 5xx | 3 | 1, 2 |
  | Supabase REST (`SupabaseRest`) | transportfout, 429, 502, 503, 504 en de Cloudflare-statussen 520–524; alleen `select`, `upsert`, `update` en `delete` (idempotent) | 3 | 0,5, 1 |
  | Web Push | geen retry binnen de run; de deferral van WP-17 is de retry | – | – |

  `insert` en `rpc` krijgen bewust geen retry. Een insert die na een time-out toch is doorgevoerd, zou anders dubbel staan. Een HTTP 500 van PostgREST is meestal een SQL-fout en wordt dus niet herhaald.

  Gevolg voor tellers (review N-4): is een `update` of `delete` wél doorgevoerd maar ging het antwoord verloren, dan geeft de herhaling 0 rijen terug. Tellers die op het aantal teruggegeven rijen leunen (`removed` uit `update_subscriptions`, `deleted` van de retentiejobs, en `admin favorites remove`, dat dan "niet verwijderd" meldt) kunnen daardoor te laag uitvallen. De state zelf klopt wel. Stuur dus niet op die tellers; ze zijn indicatief.
- **A7. Stroomonderbreker in `SupabaseRest`.** Zodra één aanroep al zijn pogingen opmaakt met een herhaalbare fout, doet hetzelfde `SupabaseRest`-object de rest van zijn leven (één uurlijkse run) nog maar één poging per aanroep. Zo groeit een Supabase-storing niet uit tot een run van 15 minuten.
- **A8. Push-retrylimiet (WP-17 R1).**
  - HTTP 400, 401, 403, 413 en elke andere 4xx (behalve 404, 410 en 429) heten voortaan "mislukt, niet herhaalbaar" (`DeliveryResult.retryable = False`). Zo'n fout blokkeert de state van een favoriet niet meer: de state wordt opgeslagen en het event is voor dat apparaat verloren.
  - Het abonnement wordt níét verwijderd. Bij een VAPID-configuratiefout (de reden dat WP-17 403 niet-permanent hield) blijven alle abonnementen dus bestaan. Na herstel komen nieuwe events weer aan.
  - Herhaalbaar blijven: 429, 5xx, een `WebPushException` zonder status, en netwerkfouten (`OSError`; `requests.RequestException` erft van `IOError`).
  - Niet herhaalbaar: `ValueError` bij het bouwen van de payload, en elke andere exception, bijvoorbeeld `VapidException` of `TypeError`.
  - Zo is er geen nieuwe kolom of migratie nodig voor een teller.
  - **Zichtbaarheid (review B-2).** Elke mislukte aflevering die niet permanent en niet herhaalbaar is, telt in de stapteller `push_non_retryable` (stap `alerts`, in `ingest_runs`). Is die groter dan 0, dan:
    - krijgt de stap een warning `f"{n} push delivery(ies) failed without retry; the alert is lost for that device (see push_failures in ingest_runs)"`, die als `::warning::alerts: …` in de Actions-log staat;
    - wordt de stap `alerts` `partial`, net als bij `deferred` in WP-17. Een verkeerde `PUBLIC_VAPID_PUBLIC_KEY` (elke aflevering 403, WP-17 R1) is dus nog steeds in elke run zichtbaar: als warning, als `partial` stap, en in het weekrapport onder "Stappen niet ok".
    - Bewuste afweging: één abonnement dat altijd 400 geeft, maakt elke run `partial`. Dat was onder WP-17 ook zo (eindeloos `deferred`). De exitcode blijft 0; er komt geen mail.
- **A9. Host-allowlist voor push-endpoints (WP-17 N-10, review N-3), afgedwongen in de ingest, niet in de database.** Toegestaan is `https://` zonder poort en zonder userinfo, met als host exact `fcm.googleapis.com` of `jmt17.google.com`, of een subdomein van `push.services.mozilla.com`, `push.apple.com` of `notify.windows.com`.
  - `jmt17.google.com` (review B-4) is het FCM-stagingendpoint van Chromium: Chrome Beta, Dev en Canary en Chromium-builds abonneren op `https://jmt17.google.com/fcm/send/…` (bron in Externe afhankelijkheden).
  - `android.googleapis.com` (legacy GCM, `…/gcm/send/…`) blijft bewust buiten de lijst: GCM is uitgezet, zulke abonnementen kunnen geen push meer ontvangen. Er zijn geen andere Google-hosts bekend.
  - De check zit op twee plekken: bij het laden (een geblokkeerd abonnement telt mee in `blocked_targets` en wordt niet bediend) en in `WebPushNotifier.send_payload` (verdediging in de diepte: er gaat nooit een POST naar een andere host).
  - Waarom geen CHECK in de database:
    - Mozilla noemt de endpoint-URL "opaque" en kan hem wijzigen;
    - een nieuwe browserhost zou dan het aanzetten van push in de app breken;
    - de pgTAP-fixtures van WP-17 gebruiken `push.example.test`.
- **A10. Databasegrens: hoogstens 20 abonnementen per gebruiker** (trigger, `PT400 too_many_subscriptions`). De app houdt er 10 en ruimt na een nieuwe aanmelding op (WP-18 A8), dus 20 raakt een normale gebruiker nooit. Zonder deze grens kan één ingelogde gebruiker de database van 500 MB volschrijven.
- **A11. Veroudering per spot (WP-11 N-1, WP-14 R3).** De evaluatie- en de alertjob laten forecastrijen weg met `fetched_at < now − 3 h`. Dat is absoluut, bovenop de bestaande relatieve regel.
  - Een spot met alleen oude rijen krijgt geen nieuwe evaluaties. De oude rijen houden hun oude `evaluated_at`, dus de app toont 3 uur daarna zelf "verouderd" (WP-14 A5).
  - Wat dat begrenst (review N-1): een spot wordt nog geëvalueerd zolang zijn rijen hoogstens 3 uur oud zijn, dus het laatste `evaluated_at` ligt tot 3 uur na de laatste fetch. De banner van de app verschijnt 3 uur na dat `evaluated_at`. De forecast achter een oordeel kan dus tot ongeveer 6 uur oud zijn voordat de app "verouderd" toont. Dat is begrensd, waar het eerst onbegrensd was; "eerlijk tot op het uur" is het niet. Dit staat ook in RUNBOOK §17.3.
  - In de alertjob wordt de favoriet `ineligible`.
  - Precies 3 uur oud telt nog als vers, net als de globale stale-regel (WP-11 E4).
  - Hiermee vervalt het voorstel van WP-14 voor een extra kolom `fetched_at` in `evaluations`.
- **A12. Tijdsbudget voor de hele run: 600 s** (WP-11 N-5, WP-04 R5). Vóór elke stap kijkt de run of er al 600 s verstreken zijn sinds de start van de stappen. Zo ja, dan krijgen alle resterende stappen `skipped` met reden `run_time_budget`, een `::error::`-annotatie en exitcode 1 (mail van GitHub). De job-timeout is 900 s. Zo wordt een trage run netjes vastgelegd in plaats van halverwege `alerts` afgebroken. Het getijbudget van 240 s blijft bestaan.
  - Afweging (review N-11): omdat `alerts` na de ingeststappen komt, is het juist de belangrijkste stap die bij een trage ingest wordt overgeslagen. Dat accepteren we: zonder budget zou de job-timeout van 900 s de run halverwege `alerts` afbreken, zonder vastlegging. Met budget is het zichtbaar (`::error::`, exitcode 1, mail van GitHub) en draait `alerts` het volgende uur weer, met de dan aanwezige data.
- **A13. Bovengrens voor sessies (WP-19 N-4, review B-5).** Een trigger `sessions_starts_at_horizon` (`BEFORE INSERT OR UPDATE OF starts_at`) dwingt `starts_at <= now() + interval '370 days'` af. Een CHECK kan dat niet, want een CHECK mag geen `now()` gebruiken.
  - Bij een update geldt de grens alleen als `starts_at` echt verandert (`new.starts_at is distinct from old.starts_at`). Een bestaande rij die toevallig verder vooruit staat, blijft dus bewerkbaar zolang de begintijd gelijk blijft.
  - De app staat bij aanmaken én bewerken tot vandaag + 365 dagen toe (`SESSION_MAX_DAYS_AHEAD`, `sessionDateBounds(new Date())`). Dat valt altijd binnen `now() + 370 dagen`, ook rond middernacht en bij zomer-/wintertijd. De grens raakt de UI dus niet; er is geen webwijziging nodig.
  - Overtreding geeft SQLSTATE `23514` met de tekst `starts_at_too_far_ahead`. De app vertaalt `23514` al naar "een van de velden is ongeldig" (`sessionErrorMessage`).
  - RSVP's worden daardoor hoogstens ongeveer een jaar plus 7 dagen bewaard in plaats van onbeperkt.
- **A14. Open aanmelden (besluit WP-13: `shouldCreateUser: false` "tot WP-22").** De PWA stuurt voortaan `shouldCreateUser: true`. Of nieuwe gebruikers zich kunnen aanmelden, regelt Lars server-side met de Supabase-instelling "Allow new users to sign up".
  - Staat die uit, dan geeft GoTrue voor een onbekend adres `signup_disabled`, en de app toont de bestaande melding `notAuthorized`. Bestaande gebruikers loggen gewoon in.
  - **Harde poort vóór de merge (review N-2):** "Allow new users to sign up" staat uit. Lars controleert dat nú, los van deze WP: de vlag in de client was nooit een beveiligingsgrens (met de publieke anon-sleutel kan iedereen `/auth/v1/otp` met `create_user: true` aanroepen). Staat de instelling vandaag aan, dan is aanmelden via de API al open.
  - Lars zet de instelling pas weer aan nadat eigen SMTP werkt en de test van AC-6 geslaagd is (RUNBOOK §17.6).
  - Voor de test van AC-6 maakt Lars de testgebruiker aan via Add user mét "Auto Confirm User". Een onbevestigde gebruiker gaat in GoTrue opnieuw door `Signup()` en krijgt `signup_disabled` zolang aanmelden uit staat.
  - Zo is er geen nieuwe publieke env-variabele nodig.
- **A15. SMTP, provider-agnostisch (review B-3).** Er komt geen code: SMTP stelt Lars in het Supabase-dashboard in (Authentication, SMTP Settings: host, poort, gebruiker, wachtwoord/sleutel, afzenderadres, afzendernaam). Dat werkt met elke dienst. Eisen aan de dienst:
  - een gratis tier;
  - open- en kliktracking aantoonbaar uit: standaard uit, of per account/domein/bericht uit te zetten op de gratis tier (harde regel "geen tracking"; kliktracking leidt bovendien de eenmalige inloglink via een redirectdomein van een derde, en een redirect of prefetch kan het token verbruiken);
  - een geverifieerde afzender.

  Onderzochte diensten (bronnen in Externe afhankelijkheden, gecontroleerd op 15 oktober 2026):

  | Dienst | Gratis | Tracking | Eigen domein nodig | Oordeel |
  |---|---|---|---|---|
  | Resend | 3.000 per maand, 100 per dag | "disabled by default for all domains"; werkt alleen als je het per domein aanzet én een trackingsubdomein verifieert | Ja ("You must add and verify at least one domain") | **Voorkeur als er een domein is** |
  | Postmark | 100 per maand | open: `TrackOpens` standaard `false`; links: standaard `None` (per server en per bericht) | Ja: een sender signature moet op een privédomein liggen (geen Gmail e.d.), en het account moet handmatig worden goedgekeurd | Voldoet, maar 100 per maand is te weinig zodra aanmelden open is |
  | Gmail (apart Google-account voor Shakka, `smtp.gmail.com`, app-wachtwoord) | 500 per dag | Gmail heeft geen functie voor open- of kliktracking. Dat is niet als garantie gedocumenteerd; de test van AC-6 (link wijst direct naar Supabase) bevestigt het | Nee | **Voorkeur zonder domein**, met kanttekeningen (zie hieronder) |
  | Brevo | 300 per dag | Bij transactionele mail niet uit te zetten op de gratis tier | Nee | **Afgewezen** |
  | SMTP2GO | 1.000 per maand | Standaard niet te verifiëren in de eigen documentatie | Onduidelijk | Niet voorgesteld |

  Voorkeur, met de voorwaarde:
  - **Met een eigen domein: Resend.** Host `smtp.resend.com`, poort 465 (SMTPS) of 587 (STARTTLS), gebruiker `resend`, wachtwoord = een Resend-API-sleutel met permission `sending_access` ("Can only send emails"). Tracking niet aanzetten. Let op: een domein kost geld (registratie per jaar). Dat is een betaalde dienst en vergt volgens de harde regel het akkoord van Lars.
  - **Zonder domein: een apart Gmail-account voor Shakka** (niet het persoonlijke adres van Lars), met tweestapsverificatie en een app-wachtwoord. Host `smtp.gmail.com`, poort 465 (SSL) of 587 (TLS), gebruiker = het volledige Gmail-adres, wachtwoord = het app-wachtwoord. Kanttekeningen: Google raadt app-wachtwoorden af ("aren't recommended") en kan ze ooit intrekken; dan stoppen de inloglinks tot er een andere dienst is. De afzender is een `@gmail.com`-adres. Google verwerkt de adressen van de ontvangers.
  - De keuze is aan Lars. Alertkanalen (zoals het voorstel WP-24) blijven ongemoeid.
  - Na de keuze moeten "De maildienst" op `/privacy` en in `docs/PRIVACY.md` (WP-23) de gekozen dienst noemen. Dat is een vervolgactie (zie Stappenplan, stap 13, en "Nodig van Lars").
- **A16. Rate limits van Supabase Auth.** Het RUNBOOK zet de defaults op een rij (bron hieronder) met deze voorstellen:
  - "Emails sent per hour" op `floor(daglimiet van de dienst / 24)`, zodat de daglimiet nooit geraakt wordt: 4 bij Resend (100 per dag), 20 bij Gmail (500 per dag). Bij Postmark (100 per maand) is dat 0; daarom valt Postmark af zodra aanmelden open is. Lars mag hoger gaan als hij accepteert dat bij misbruik de daglimiet van de dienst bereikt wordt (dan werken inloglinks tot de volgende dag niet). Supabase begint na het instellen van eigen SMTP zelf met 30 per uur;
  - de andere limieten op de default (30 sign-ups/sign-ins per 5 minuten per IP, 60 s tussen OTP-aanvragen per gebruiker, 30 verificaties per 5 minuten, 150 tokenrefreshes per 5 minuten).

  Lars stelt ze in. Ze staan niet in `config.toml`, want lokaal gebruikt de stack Mailpit.
- **A17. Dependency-audit.**
  - Eenmalig in deze WP: `npm audit --omit=dev --audit-level=high` (AC-5) en `pip-audit` op de vergrendelde Python-dependencies. High- en critical-bevindingen worden opgelost met een minimale versie-update.
  - Daarna maandelijks met de hand (RUNBOOK).
  - Alle GitHub Actions worden op een commit-SHA vastgezet, met een test die dat bewaakt.
  - Geen `npm audit` als CI-stap: nieuwe advisories zouden dan willekeurige PR's rood maken, los van wat ze wijzigen.
  - Geen Dependabot.
- **A18. `db_usage()` meet `sum(pg_database_size)` over alle databases waarop de functie-eigenaar `CONNECT` heeft.** Dat is de query die Supabase zelf aanraadt voor de limiet van 500 MB. Rijen per tabel zijn exacte `count(*)`-waarden voor de 14 tabellen uit `TABLE_KEYS`. "Gebruikers" = rijen in `profiles` (1-op-1 met `auth.users` via de trigger van WP-01). "Abonnementen" = rijen in `push_subscriptions`.
- **A19. Pywebpush-timeout.** Al aanwezig sinds WP-17: `timeout=PUSH_TIMEOUT_S` (10 s) gaat via `webpush()` naar `requests.post` (geverifieerd in de pywebpush-bron) en wordt getest in `test_notify_webpush.py`. Er hoeft niets te veranderen.
- **A20. Geen nieuwe packages.** `pip-audit` draait ad hoc via `uvx` en wordt geen dependency.

## Ontwerp

**HTTP-hardening.** `shakka.http` krijgt de generieke `with_retries(fn, *, attempts=3, backoff=1.0, ...)` en de uitzondering `TransientError` (met optionele `retry_after`).
- Een bron vertaalt zelf zijn respons naar "herhaalbaar" (een `TransientError` of een herhaalbare `DatabaseError`) of "definitief" (de eigen foutklasse).
- `with_retries` wacht `backoff · 2^(n−2)` vóór poging n, of `retry_after` als die gezet is (hoogstens 30 s), en gooit na de laatste poging de laatste uitzondering ongewijzigd door, zonder exception-chaining.
- De wachtfunctie is een module-variabele `_sleep`. Een autouse-fixture in `conftest.py` zet die in tests op no-op.
- Open-Meteo (`request_json`) stapt intern over op `with_retries`. Signatuur, foutteksten, logregels en wachttijden blijven exact gelijk, dus de bestaande tests blijven ongewijzigd groen.
- RWS (`_post_json`) en `SupabaseRest._send` krijgen nieuw retries volgens A6, met de stroomonderbreker van A7.
- `httpx.Client(` blijft alleen in `shakka/http.py`. Een test bewaakt dat en ook dat de timeouts eindig zijn (AC-1).

**Push-hardening.**
- `DeliveryResult` krijgt een veld `retryable: bool = True`. `deliver_event` telt alleen herhaalbare fouten als "transient", waardoor 4xx-fouten een favoriet niet meer eindeloos uitstellen (A8). Niet-herhaalbare fouten tellen apart (`non_retryable`), lopen via `PlanDelivery` en `run_alerts` door naar `AlertJobResult.push_non_retryable`, en maken de stap `alerts` `partial` met een warning.
- `shakka.notify.base.endpoint_allowed` implementeert de allowlist (A9).
- `load_all_targets_checked` geeft de doelen en het aantal geblokkeerde abonnementen terug. `load_all_targets` en `load_targets` filteren ook.
- `run_alerts` telt `blocked_targets`; de stap `alerts` geeft daarbij een warning.
- Het `Notifier`-protocol krijgt `send_payload`, dat `WebPushNotifier` al had. Daarmee kan de gebruiksstap "via de Notifier uit WP-17" een eigen `PushPayload` sturen.
- In de database komt een trigger met hoogstens 20 abonnementen per gebruiker (A10). Die trigger is security invoker en heeft geen `EXECUTE`-rechten, dus hij komt in geen van de vier functiesets van `07_sessions.test.sql` voor (zie Database).

**Veroudering per spot en runbudget.**
- `load_inputs_checked` krijgt `max_fetch_age`. De evaluatie- en de alertjob geven `MAX_FETCH_AGE = 3 h` mee (A11), en `InputsLoad.stale` noemt de spots waarvan alle rijen te oud waren.
- `_run` in de pipeline controleert vóór elke stap het runbudget (A12).

**Gebruiksrapport.** Er zijn drie lagen:
1. `shakka.domain.usage` (puur): `UsageStats`, `usage_warnings`, `build_usage_report` (een tekst van meerdere regels), `usage_push_text`, `warning_push_text` en de tijdhelpers voor het pushvenster en de week- en dagstart.
2. `shakka.jobs.usage` (I/O):
   - `read_open_meteo_usage` (`api_usage`, UTC);
   - `read_db_usage` (RPC `db_usage`);
   - `read_run_history` (`ingest_runs` van de laatste 7 dagen: statussen, stappen die niet `ok` waren, en `sent` en `failed` van de stap `alerts`);
   - `deliver_operator_push` (`load_targets(db, operator)` → `send_payload` → `update_subscriptions`);
   - `delete_old_ingest_runs`;
   - de orkestratie `run_usage_report`.
3. De pipelinestap `usage_report`, als laatste in `STEPS`. Hij zet het resultaat om in `counts`, warnings en een status.

Elk uur leest de stap twee kleine dingen (`api_usage` van ruim een maand en één RPC) en berekent hij de waarschuwingen. Duurdere `ingest_runs`-queries draait hij alleen als er iets te versturen valt: op maandag binnen het venster, of bij een waarschuwing. De pushmelding is een korte samenvatting met de waarschuwingen eerst (hoogstens 50/150 tekens). Het volledige rapport staat in `counts.report` van de stap. `shakka usage show` toont het rapport lokaal zonder te versturen.

**Database.** Twee nieuwe migraties:
1. `…_drop_profiles_telegram_chat_id.sql`: verwijdert de kolom en zijn CHECK.
2. `…_hardening.sql`: `db_usage()`, de trigger `push_subscriptions_limit` en de trigger `sessions_starts_at_horizon` (A13).

pgTAP:
- `01`, `02` en `04` worden aangepast voor de verwijderde kolom.
- `07_sessions.test.sql` regels 68 en 69 krijgen `db_usage` erbij (review B-1): `service_role` mag daarna `purge_expired_sessions` én `db_usage` uitvoeren, en `db_usage` is security definer. De twee nieuwe triggerfuncties (`push_subscriptions_limit`, `sessions_starts_at_horizon`) zijn security invoker zonder `EXECUTE` voor wie dan ook; ze staan bewust in geen van de vier sets (regels 66–69).
- `10_hardening.test.sql` is nieuw. Prefix `10_`, omdat WP-23 `09_delete_my_account.test.sql` toevoegt (review N-3).
- De oude migraties blijven ongewijzigd.

**Web.** Alleen `auth.ts` verandert: `shouldCreateUser: true` en de mapping `signup_disabled` → `notAuthorized`. Verder komen er testaanpassingen (`auth`, `login`, de alter-guard in `schema-columns`).

**Belangrijkste keuzes en waarom:**
- Retries zitten in de bronmodules zelf, niet in de jobs. De jobs en hun tests blijven daardoor ongewijzigd, en de contracten (`request_json`, `fetch_tide_extremes`, `SupabaseRest`) houden dezelfde signatuur.
- Deduplicatie via `ingest_runs` (contract) in plaats van een nieuwe tabel. De query's zijn klein omdat ze alleen draaien als er iets te versturen valt.
- Veroudering wordt opgelost in de backend (A11) in plaats van met een nieuwe kolom en een UI-wijziging. Daarmee is de leeftijd van de forecast achter een oordeel begrensd (tot ongeveer 6 uur voordat de app "verouderd" toont), waar die eerst onbegrensd was.
- De sessiegrens is een trigger met `now()` in plaats van een CHECK op `created_at` (A13), zodat bewerken in de UI dezelfde grens houdt als aanmaken.

## Bestanden

### Ingest (`ingest/src/shakka/`)
| Bestand | Actie | Inhoud |
|---|---|---|
| `http.py` | wijzigen | `TransientError`, `is_transient`, `with_retries`, `RETRY_MAX_DELAY_S`, `_sleep`. `make_client` blijft ongewijzigd. |
| `openmeteo/client.py` | wijzigen | `request_json` via `with_retries`. Signatuur, teksten en wachttijden blijven gelijk. |
| `rws/tides.py` | wijzigen | `RWS_ATTEMPTS`, `RWS_BACKOFF_S`; retries in `_post_json`. |
| `db.py` | wijzigen | `DB_ATTEMPTS`, `DB_BACKOFF_S`, `DB_RETRY_STATUSES`, `RETRYING_OPS`, `is_retryable_db_error`; `SupabaseRest(..., attempts=DB_ATTEMPTS)`, de stroomonderbreker, de property `retries_disabled` en een logger `shakka.db`. |
| `notify/base.py` | wijzigen | `DeliveryResult.retryable`, `endpoint_allowed`, host-constanten, `BLOCKED_HOST_DETAIL`, `Notifier.send_payload`. |
| `notify/webpush.py` | wijzigen | De allowlist-guard en de classificatie `retryable` in `send_payload`; `send` geeft bij een `ValueError` `retryable=False`. |
| `jobs/push.py` | wijzigen | `TargetsLoad`, `load_all_targets_checked`; de allowlist in `load_all_targets` en `load_targets`; `deliver_event` telt alleen herhaalbare fouten als transient; `EventDelivery.non_retryable`. |
| `jobs/alerts.py` | wijzigen | `AlertJobResult.blocked_targets` en `push_non_retryable`; `PlanDelivery.non_retryable`; `load_all_targets_checked`; `max_fetch_age` in `load_alert_context`; logregel en CLI-uitvoer met `non_retryable`. |
| `jobs/inputs.py` | wijzigen | `MAX_FETCH_AGE`, `max_fetch_age`-parameter, `InputsLoad.stale`. |
| `jobs/evaluate.py` | wijzigen | `max_fetch_age=MAX_FETCH_AGE`; `EvaluationJobResult.stale`. |
| `jobs/usage.py` | aanmaken | De I/O en orkestratie van het gebruiksrapport, plus `run_usage_show_cli`. |
| `domain/usage.py` | aanmaken | Puur: `UsageStats`, waarschuwingen, rapporttekst, pushteksten, tijdhelpers. |
| `pipeline.py` | wijzigen | `step_usage_report`, `STEPS`/`STEP_NAMES`, `RUN_TIME_BUDGET_S`, `RUN_TIME_BUDGET`, `blocked_targets` en `push_non_retryable` in `alert_counts` met hun warnings (`non_retryable_warning`), `partial` bij `push_non_retryable`, `exit_code_for`, `build_annotations`, de docstring. |
| `config.py` | wijzigen | `operator_user_id: str \| None = None`. |
| `logsetup.py` | wijzigen | `secret_values` neemt de gestripte `operator_user_id` op, plus de canonieke UUID-vorm als die afwijkt. |
| `cli.py` | wijzigen | De groep `usage` met het commando `show`; de docstring van `run-hourly` noemt alle stappen. |

### Ingest-tests (`ingest/tests/`)
| Bestand | Actie | Inhoud |
|---|---|---|
| `conftest.py` | wijzigen | Autouse-fixture `_no_retry_sleep`: `monkeypatch.setattr(shakka.http, "_sleep", lambda s: None)`. |
| `test_http.py` | wijzigen | Tests voor `with_retries` en AC-1 (eindige timeouts, alleen `http.py` maakt clients). |
| `test_db.py` | wijzigen | Retry- en stroomonderbrekertests. |
| `test_rws_tides.py` | wijzigen | Retrytests. |
| `test_notify_webpush.py` | wijzigen | Classificatie `retryable`, de allowlist-guard. `test_payload_value_error_is_retryable` → `test_payload_value_error_is_not_retryable`. |
| `test_push_allowlist.py` | aanmaken | `endpoint_allowed` en het filteren bij het laden. |
| `test_job_push.py`, `test_job_alerts_push.py` | wijzigen | 4xx niet herhaalbaar en geteld in `non_retryable`/`push_non_retryable`; host `push.example.test` → `fcm.googleapis.com/fcm`. |
| `test_cli_push.py` | wijzigen | Push-regel met `non_retryable=`; exitcode 1 bij een niet-herhaalbare fout. |
| `push_fixtures.py` | wijzigen | `endpoint()` → `https://fcm.googleapis.com/fcm/send/{user_id[:8]}-{n}`; tekst van `FakeResponse` met dezelfde host; `FakeNotifier.send_payload` met lijst `payload_calls`. |
| `test_pipeline.py` | wijzigen | Stapvolgorde (8 stappen), `len(report.steps) == 8`, laatste stap `usage_report` in `test_all_steps_ok_records_run`, het endpoint op r. 772 naar het fcm-host, tests voor het runbudget, veroudering per spot in de pipeline, de warning `blocked_targets` en `test_non_retryable_push_is_partial_with_warning`. |
| `test_job_inputs.py`, `test_job_evaluate.py`, `test_job_alerts.py` | wijzigen | Tests voor `max_fetch_age`. |
| `test_usage.py` | aanmaken | AC-2: het domein (golden-tekst, waarschuwingen, pushteksten, tijdhelpers). |
| `test_job_usage.py` | aanmaken | De I/O-functies en `run_usage_report`. |
| `test_pipeline_usage.py` | aanmaken | AC-3. |
| `test_cli_usage.py` | aanmaken | `shakka usage show`. |
| `fakes.py` | wijzigen | Ingebouwde RPC `db_usage` en attribuut `database_bytes`. |
| `test_fakes.py` | wijzigen | De fake-`db_usage`. |
| `test_config.py`, `test_logsetup.py` | wijzigen | `operator_user_id`; in `test_logsetup.py` ook de canonieke vorm (hoofdletters/accolades). |
| `test_repo_hygiene.py` | wijzigen | `ENV_KEYS` + `OPERATOR_USER_ID`; `test_actions_pinned_to_commit_sha`. |
| `test_hourly_workflow.py` | wijzigen | Env en secrets met `OPERATOR_USER_ID`. |
| `test_migrations.py` | wijzigen | `test_db_usage_counts_every_table`. |
| `test_openmeteo_client.py` | ongewijzigd | Moet groen blijven (regressie). |

### Database (`supabase/`)
| Bestand | Actie | Inhoud |
|---|---|---|
| `migrations/20261015220000_drop_profiles_telegram_chat_id.sql` | aanmaken | De kolom en de CHECK verwijderen. |
| `migrations/20261015220100_hardening.sql` | aanmaken | `db_usage()`, de trigger `push_subscriptions_limit`, de trigger `sessions_starts_at_horizon`. |
| `tests/01_schema.test.sql` | wijzigen | `plan(70)`; `columns_are(profiles)` zonder de legacy-kolom; die rij uit de `set_eq` gehaald; de `throws_ok` voor het numerieke formaat verwijderd. |
| `tests/02_privileges.test.sql` | wijzigen | `plan(54)`; de `column_privs_are` voor de legacy-kolom verwijderd. |
| `tests/04_rls_users.test.sql` | wijzigen | `plan(40)`; de asserts op r. 80 en 86 verwijderd; de kopregel zonder legacy-kolom. |
| `tests/07_sessions.test.sql` | wijzigen | Alleen regels 68 en 69 (exacte tekst in Interfaces); `plan(112)` blijft. |
| `tests/10_hardening.test.sql` | aanmaken | AC-4 en de nieuwe grenzen, `plan(28)` (zie Testplan). |

### Web (`web/`)
| Bestand | Actie | Inhoud |
|---|---|---|
| `src/lib/auth.ts` | wijzigen | `shouldCreateUser: true`; docstring; `signup_disabled` → `notAuthorized`. |
| `test/auth.test.ts`, `test/login.test.ts` | wijzigen | Verwachte opties `shouldCreateUser: true`; een test voor `signup_disabled`. |
| `test/schema-columns.test.ts` | wijzigen | De alter-guard slaat `20261015220000_drop_profiles_telegram_chat_id.sql` over. Een nieuwe test eist dat dat bestand `drop column if exists` plus de legacy-naam bevat (zoals nu opgebouwd met `join`). |
| `package-lock.json` (eventueel `package.json`) | wijzigen indien nodig | Alleen als `npm audit --omit=dev --audit-level=high` faalt (AC-5). |

### Overig
| Bestand | Actie | Inhoud |
|---|---|---|
| `.env.example` | wijzigen | Regel `OPERATOR_USER_ID=` als laatste, met een commentaarregel erboven. |
| `.github/workflows/hourly.yml` | wijzigen | `OPERATOR_USER_ID: ${{ secrets.OPERATOR_USER_ID }}` in de env van de pipelinestap; `actions/checkout` op SHA. |
| `.github/workflows/ci.yml` | wijzigen | `actions/checkout` en `actions/setup-node` op SHA. |
| `docs/RUNBOOK.md` | wijzigen | §4, §11.2, §11.5, §13.1, §13.6, §14.7, §14.14 en de nieuwe sectie "Hardening en kostenbewaking" (in deze blueprint §17; zie Stappenplan stap 13 voor het nummer). |
| `docs/WORK_PACKAGES.md` | wijzigen | De env-rij `OPERATOR_USER_ID`: "(voorstel, de planner van WP-22 bevestigt)" → "(bevestigd in WP-22)". Verder niets. |
| `docs/PRIVACY.md` | wijzigen, **alleen na merge WP-23** | Bestaat pas na WP-23. Alleen als het bestand na het rebasen op `develop` bestaat: in de rij "Profiel" de bijzin "; plus een ongebruikte, altijd lege legacy-kolom die WP-22 verwijdert" weghalen. De regel "Maildienst" blijft ongewijzigd tot Lars een SMTP-dienst kiest (A15). Zie stap 13. |

## Interfaces en contracten

### `shakka.http`
```python
T = TypeVar("T")
RETRY_MAX_DELAY_S: Final = 30.0
_sleep: Callable[[float], None] = time.sleep  # module seam; looked up at call time

class TransientError(Exception):
    """A failure worth another attempt. `retry_after` (s) overrides the backoff when set."""
    def __init__(self, message: str, *, retry_after: float | None = None) -> None: ...
    retry_after: float | None

def is_transient(exc: BaseException) -> bool:
    """isinstance(exc, TransientError | httpx.TransportError)"""

def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    backoff: float = 1.0,
    retry_if: Callable[[BaseException], bool] = is_transient,
    sleep: Callable[[float], None] | None = None,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> T: ...
```
Gedrag van `with_retries`:
- `ValueError` als `attempts < 1`, of als `backoff` negatief of niet eindig is.
- Alleen `Exception`-subklassen worden opgevangen; een `BaseException` zoals `KeyboardInterrupt` gaat er direct doorheen.
- Is `retry_if(exc)` onwaar, of is het de laatste poging, dan volgt een kale `raise` (zelfde object, zelfde `__cause__`).
- Wachttijd vóór poging n (n ≥ 2): `exc.retry_after` als `exc` een `TransientError` met `retry_after` is, begrensd op `[0, RETRY_MAX_DELAY_S]`; anders `backoff * 2 ** (n - 2)`.
- `on_retry(n - 1, exc, delay)` wordt aangeroepen vóór de wachttijd. Daarna `(sleep or _sleep)(delay)`.
- Implementatie: de volgende poging start buiten het `except`-blok, zodat `__context__` van een latere fout `None` blijft. Skelet:
```python
for attempt in range(1, attempts + 1):
    try:
        return fn()
    except Exception as exc:
        if attempt == attempts or not retry_if(exc):
            raise
        failure = exc
    delay = ...  # from failure / attempt
    if on_retry is not None:
        on_retry(attempt, failure, delay)
    (sleep or _sleep)(delay)
raise AssertionError("unreachable")
```

### `shakka.openmeteo.client.request_json` (signatuur ongewijzigd)
- Binnen `attempt()`:
  - een `httpx.HTTPError` wordt `TransientError(type(exc).__name__)` (`from None`);
  - 2xx levert de JSON op; ongeldige JSON geeft `OpenMeteoRequestError("invalid JSON response", status=...)`;
  - een status ongelijk aan 429 en onder 500 geeft `OpenMeteoRequestError(...)` met dezelfde tekst als nu;
  - 429 en 5xx geven `TransientError(f"HTTP {status}", retry_after=_retry_after(response) if status == 429 else None)`.
- Aanroep: `with_retries(attempt, attempts=attempts, backoff=base_delay, retry_if=lambda e: isinstance(e, TransientError), sleep=sleep, on_retry=log)`. `log` schrijft exact de huidige warning `"open-meteo request attempt %d/%d failed: %s; retrying in %.1fs"`.
- Na uitputting: `except TransientError as exc: raise OpenMeteoRequestError(f"failed after {attempts} attempts: {exc}") from None`.
- `sleep` heeft standaard nog steeds `time.sleep`; de Open-Meteo-tests geven die zelf mee.

### `shakka.rws.tides`
```python
RWS_ATTEMPTS: Final = 3
RWS_BACKOFF_S: Final = 1.0
def _post_json(client: httpx.Client, url: str, body: dict[str, Any], *, label: str) -> Any
```
Per poging:
- een `httpx.HTTPError` wordt `TransientError(f"{label}: {type(exc).__name__}")`;
- 204 geeft direct `TideFetchError(f"{label}: no data (HTTP 204)")`;
- 429 en 5xx worden `TransientError(text)`, met `text` zoals nu (`f"{label}: HTTP {status}"` plus `: {Foutmelding[:200]}` als die er is);
- andere niet-2xx-statussen geven direct `TideFetchError(text)`;
- ongeldige JSON geeft direct `TideFetchError(f"{label}: invalid JSON")`.

Aanroep `with_retries(..., attempts=RWS_ATTEMPTS, backoff=RWS_BACKOFF_S, retry_if=lambda e: isinstance(e, TransientError))`. Na uitputting `raise TideFetchError(f"{exc} (after {RWS_ATTEMPTS} attempts)") from None`. Er wordt niets gelogd: de getijjob logt al per station.

### `shakka.db`
```python
DB_ATTEMPTS: Final = 3
DB_BACKOFF_S: Final = 0.5
DB_RETRY_STATUSES: Final = frozenset({429, 502, 503, 504, 520, 521, 522, 523, 524})  # 52x: Cloudflare
RETRYING_OPS: Final = frozenset({"select", "upsert", "update", "delete"})

def is_retryable_db_error(exc: BaseException) -> bool:
    """DatabaseError with status None (transport) or status in DB_RETRY_STATUSES."""

class SupabaseRest:
    def __init__(self, url: str, secret_key: str, *, client: httpx.Client | None = None,
                 attempts: int = DB_ATTEMPTS) -> None: ...
    @property
    def retries_disabled(self) -> bool: ...
```
- `_send` houdt een interne functie `attempt()` met de huidige code: een transportfout wordt `DatabaseError(f"{op} {label}: {ExcName}") from None`, en een niet-2xx-status wordt `self._http_error(...)`.
- Is `op` niet in `RETRYING_OPS`, staat de onderbreker aan of is `attempts == 1`, dan volgt `return attempt()`.
- Anders: `with_retries(attempt, attempts=self._attempts, backoff=DB_BACKOFF_S, retry_if=is_retryable_db_error, on_retry=...)`. Bij een `DatabaseError` waarvoor `is_retryable_db_error` waar is, gaat `self._retries_disabled = True` aan, volgt eenmalig de warning `"db: retries disabled for the rest of this run"` en wordt de fout doorgegooid.
- De retry-logregel (logger `shakka.db`, WARNING) is `"db: %s %s attempt %d/%d failed (%s); retrying in %.1fs"`, met `op`, tabelnaam, poging, `attempts` en `HTTP <status>` of `transport error`. Nooit URL, filters, body of sleutel.
- `__init__` geeft `ValueError` als `attempts < 1`.

### `shakka.notify.base`
```python
PUSH_SERVICE_HOSTS: Final = frozenset({"fcm.googleapis.com", "jmt17.google.com"})  # jmt17: Chromium FCM staging (Chrome Beta/Dev/Canary)
PUSH_SERVICE_HOST_SUFFIXES: Final = (".push.services.mozilla.com", ".push.apple.com", ".notify.windows.com")
BLOCKED_HOST_DETAIL: Final = "blocked host"

def endpoint_allowed(endpoint: str) -> bool:
    """https, no port, no userinfo, host in PUSH_SERVICE_HOSTS or a proper subdomain of a suffix."""
    # urlsplit; parts.port may raise ValueError -> False; hostname is lower-cased by urlsplit;
    # suffix match requires len(host) > len(suffix) and host.endswith(suffix)

@dataclass(frozen=True, slots=True)
class DeliveryResult:
    ok: bool
    permanent_failure: bool
    detail: str
    retryable: bool = True  # only meaningful when not ok and not permanent_failure

class Notifier(Protocol):
    channel: str
    def send(self, target: DeliveryTarget, message: AlertMessage, *, tag: str) -> DeliveryResult: ...
    def send_payload(self, target: DeliveryTarget, payload: PushPayload) -> DeliveryResult: ...
```
De bestaande `__post_init__`-regels van `DeliveryResult` blijven.

### `shakka.notify.webpush.WebPushNotifier`
- `send_payload`: eerst `if not endpoint_allowed(target.endpoint): return DeliveryResult(False, False, BLOCKED_HOST_DETAIL, retryable=False)`, zonder `webpush()` aan te roepen. Daarna:
  - `WebPushException` met status 404 of 410 → `(False, True, "HTTP n")`, permanent;
  - status `None` → `(False, False, "WebPushException")`, `retryable=True`;
  - status 429 of ≥ 500 → `retryable=True`;
  - elke andere status → `retryable=False`;
  - `except OSError as exc` → `(False, False, type(exc).__name__)`, `retryable=True`;
  - `except Exception as exc` → `(False, False, type(exc).__name__, retryable=False)`.
- `send`: een `ValueError` bij het bouwen van de payload geeft `DeliveryResult(False, False, "ValueError", retryable=False)`.

### `shakka.jobs.push`
```python
@dataclass(frozen=True, slots=True)
class TargetsLoad:
    targets: dict[str, list[DeliveryTarget]]  # by user_id, at most MAX_TARGETS_PER_USER each
    blocked: int  # valid rows skipped because endpoint_allowed() is False

def load_all_targets_checked(db: SupabaseRest) -> TargetsLoad
def load_all_targets(db: SupabaseRest) -> dict[str, list[DeliveryTarget]]  # = ...checked(db).targets
def load_targets(db: SupabaseRest, user_id: str) -> list[DeliveryTarget]  # same query; drops blocked hosts
```
- Volgorde in `load_all_targets_checked`: parsen (ongeldige rij → overslaan), dan de allowlist (→ `blocked += 1`), dan de grens van 10.
- Is `blocked > 0`, dan logt de functie WARNING `"push: %d subscription(s) skipped: push service host not allowed"`, met alleen het aantal.
- `EventDelivery` krijgt als laatste veld `non_retryable: int = 0` (aantal afleveringen met `not ok and not permanent_failure and not retryable`).
- `deliver_event`: na een mislukte, niet-permanente aflevering geldt `if result.retryable: transient += 1 else: non_retryable += 1`. `retryable=sent == 0 and transient > 0` blijft. De rest blijft gelijk.
- Een `DeliveryResult` uit de `except Exception`-tak van `deliver_event` (een notifier die toch gooit) houdt de default `retryable=True`, zoals nu.

### `shakka.jobs.inputs`
```python
MAX_FETCH_AGE: Final = timedelta(hours=3)

@dataclass(frozen=True, slots=True)
class InputsLoad:
    inputs: dict[str, SpotInputs]
    invalid: list[str]
    without_coords: list[str]
    errors: list[str]
    stale: list[str] = field(default_factory=list)  # spots whose rows were all older than max_fetch_age, sorted

def load_inputs_checked(db, *, now, spot_ids=None, max_fetch_age: timedelta | None = None) -> InputsLoad
def load_inputs(db, *, now, spot_ids=None, max_fetch_age: timedelta | None = None) -> dict[str, SpotInputs]
```
- Is `max_fetch_age` gezet, dan valt eerst elke rij weg met `fetched_at < now - max_fetch_age`; precies op de grens blijft de rij staan.
- Daarna geldt de bestaande relatieve regel ten opzichte van de nieuwste resterende rij.
- Had een spot rijen, maar blijft er na de absolute filter niets over, dan komt zijn id in `stale` en is `forecasts == []`.
- De logregel krijgt `stale=%d`, alleen het aantal.

### `shakka.jobs.evaluate`
- `run_evaluation` roept `load_inputs_checked(db, now=now, max_fetch_age=MAX_FETCH_AGE)` aan.
- `EvaluationJobResult` krijgt een laatste veld `stale: tuple[str, ...] = ()` met openbare spot-id's. De status hangt er niet van af.

### `shakka.jobs.alerts`
- `load_alert_context` roept `load_inputs(db, now=now, spot_ids=..., max_fetch_age=MAX_FETCH_AGE)` aan.
- `run_alerts` gebruikt `load_all_targets_checked`.
- `PlanDelivery` krijgt als laatste veld `non_retryable: int = 0`. `deliver_plan` telt `non_retryable += d.non_retryable` per event en geeft het in beide `PlanDelivery`-returns mee (ook bij `deferred=True`).
- `run_alerts`: direct na `failures.update(d.failures)` (dus vóór de `if d.deferred`-tak) `counts["push_non_retryable"] += d.non_retryable`.
- `AlertJobResult` krijgt twee laatste velden: `blocked_targets: int = 0` en `push_non_retryable: int = 0` (afleveringen die mislukten zonder herhaling; het event is voor dat apparaat verloren). De logregel van `run_alerts` krijgt `blocked=%d non_retryable=%d`.
- `run_alerts_cli`: de push-regel wordt `f"push: sent=… failed=… no_target=… deferred=… non_retryable={result.push_non_retryable} removed=…"`, en `failed` (exitcode 1) geldt ook bij `result.push_non_retryable > 0`, gelijk aan de status van de pipelinestap.

### `shakka.domain.usage` (puur)
```python
OPEN_METEO_DAILY_LIMIT: Final = 10_000
OPEN_METEO_MONTHLY_LIMIT: Final = 300_000
OPEN_METEO_WARN_FRACTION: Final = 0.7
DATABASE_LIMIT_MB: Final = 500
DATABASE_WARN_MB: Final = 300
BYTES_PER_MB: Final = 1024 * 1024
REPORT_DAYS: Final = 7
REPORT_WEEKDAY: Final = 0  # Monday (date.weekday())
OPERATOR_PUSH_FROM: Final = time(8, 0)
OPERATOR_PUSH_UNTIL: Final = time(22, 0)
REPORT_TITLE: Final = "Shakka weekrapport"
REPORT_TITLE_WARN: Final = "Shakka weekrapport: let op"
WARNING_TITLE: Final = "Shakka: gebruik boven drempel"
UNKNOWN: Final = "onbekend"

@dataclass(frozen=True, slots=True)
class UsageStats:
    now: datetime                          # aware; end of the report period
    open_meteo_today: float | None = None  # UTC day of now, all open_meteo_* sources
    open_meteo_max_day: float | None = None  # highest UTC day of the last 7 (incl. today)
    open_meteo_month: float | None = None  # UTC month of now
    database_bytes: int | None = None
    table_rows: Mapping[str, int] = field(default_factory=dict)  # {} = unknown
    runs_ok: int | None = None             # finished runs in [now - 7 d, now)
    runs_partial: int | None = None
    runs_failed: int | None = None
    step_issues: Mapping[str, int] = field(default_factory=dict)  # step -> runs not ok
    push_sent: int | None = None           # sum of alerts.counts.sent in 7 days
    push_failed: int | None = None

    @property
    def users(self) -> int | None: ...          # table_rows.get("profiles")
    @property
    def subscriptions(self) -> int | None: ...  # table_rows.get("push_subscriptions")
    @property
    def runs_total(self) -> int | None: ...     # None if runs_ok is None

def usage_warnings(stats: UsageStats) -> list[str]
def build_usage_report(stats: UsageStats) -> str
def usage_push_text(stats: UsageStats) -> PushText
def warning_push_text(warnings: Sequence[str]) -> PushText   # ValueError if empty
def local_day_start(now: datetime) -> datetime   # 00:00 Europe/Amsterdam of now's local date, as UTC
def week_start(now: datetime) -> datetime        # Monday 00:00 local of now's week, as UTC
def in_operator_window(now: datetime) -> bool    # OPERATOR_PUSH_FROM <= local time < OPERATOR_PUSH_UNTIL
def report_due_time(now: datetime) -> bool       # local weekday == REPORT_WEEKDAY and in_operator_window(now)
```
Validatie in `__post_init__` (`ValueError`):
- `now` moet aware zijn;
- floats moeten eindig en ≥ 0 zijn, ints ≥ 0 (geen `bool`);
- `runs_ok`, `runs_partial` en `runs_failed` zijn alle drie `None` of alle drie gezet;
- waarden in `table_rows` en `step_issues` zijn ints ≥ 0.

Hulpfuncties (privé):
- `_n(x)`: `int(math.floor(x + 0.5))` met `.` als duizendtalscheiding (`f"{v:,}".replace(",", ".")`);
- `_mb(b)`: `math.ceil(b / BYTES_PER_MB)`;
- `_pct(ok, total)`: `int(math.floor(100 * ok / total + 0.5))`.

`usage_warnings`, in deze volgorde:
1. als `database_bytes is not None and database_bytes > DATABASE_WARN_MB * BYTES_PER_MB`: `f"Database {_mb(b)} MB, boven {DATABASE_WARN_MB} MB"`;
2. als `open_meteo_today > 0.7 * 10_000`: `f"Open-Meteo vandaag {_n(today)} calls, boven {_n(7000)}"`;
3. als `open_meteo_month > 0.7 * 300_000`: `f"Open-Meteo deze maand {_n(month)} calls, boven {_n(210000)}"`.

`build_usage_report`: regels gescheiden door `"\n"`, zonder `\n` aan het eind.
1. `f"Shakka gebruiksrapport tot {local:%Y-%m-%d %H:%M} (Europe/Amsterdam)"` (`local = now.astimezone(LOCAL_TZ)`)
2. `"Waarschuwingen: geen"`, of `"Waarschuwingen:"` gevolgd door één regel `"- " + w` per waarschuwing
3. `f"Open-Meteo: vandaag {_n(today)} calls, hoogste dag (7 dagen) {_n(max_day)}, limiet 10.000 per dag; deze maand {_n(month)}, limiet 300.000"`, of `"Open-Meteo: onbekend"` als een van de drie `None` is
4. `f"Database: {_mb(b)} MB van 500 MB"` of `"Database: onbekend"`
5. `"Rijen: " + ", ".join(f"{t} {_n(c)}" for t, c in sorted(table_rows.items()))`, of `"Rijen: onbekend"`
6. `f"Runs (7 dagen): {_n(total)}, waarvan {ok} ok, {partial} partial, {failed} failed ({_pct}% ok)"`; bij `total == 0` alleen `"Runs (7 dagen): 0"`; onbekend: `"Runs (7 dagen): onbekend"`
7. `"Stappen niet ok (7 dagen): " +` per stap `f"{name} {count}"`, gesorteerd op aflopend aantal en dan op naam, gescheiden door `", "`; `"geen"` bij leeg; `"onbekend"` als de runs onbekend zijn
8. `f"Push (7 dagen): {sent} verstuurd, {failed} mislukt"` of `"Push (7 dagen): onbekend"`
9. `f"Gebruikers: {users or onbekend}, push-abonnementen: {subscriptions or onbekend}"` (elk afzonderlijk `UNKNOWN` als `None`; 0 is geen onbekend)

`usage_push_text`:
- Titel: `REPORT_TITLE_WARN` als er waarschuwingen zijn, anders `REPORT_TITLE`.
- Kandidaat-regels: eerst de waarschuwingen. Dan regel A: `f"Runs {pct}% ok · DB {mb} MB · Open-Meteo max {max_day}/dag"`, met `?` voor elk onbekend getal (pct onbekend of `total == 0` → `?`). Dan regel B: `f"{users} gebruikers, {subscriptions} abonnementen"`, met `?` voor onbekend.
- Body: zoveel mogelijk regels vanaf het begin, zolang `"\n".join(...)` hoogstens `PUSH_BODY_MAX` tekens heeft. Past de eerste regel al niet, dan `shorten_words(regel, PUSH_BODY_MAX)`. Dit is hetzelfde algoritme als `to_push_text`.

`warning_push_text`: titel `WARNING_TITLE`, body volgens hetzelfde algoritme over de waarschuwingen.

### `shakka.jobs.usage`
```python
USAGE_STEP: Final = "usage_report"
DB_USAGE_RPC: Final = "db_usage"
INGEST_RUNS_RETENTION: Final = timedelta(days=90)
REPORT_TAG: Final = "shakka-usage-report"
WARNING_TAG: Final = "shakka-usage-warning"
OPERATOR_PUSH_URL: Final = "/"
DeliveryStatus = Literal["sent", "failed", "no_operator", "invalid_operator", "push_disabled", "no_target"]

@dataclass(frozen=True, slots=True)
class OpenMeteoUsage:
    today: float
    max_day: float
    month: float

@dataclass(frozen=True, slots=True)
class DbUsage:
    database_bytes: int
    table_rows: dict[str, int]

@dataclass(frozen=True, slots=True)
class RunHistory:
    ok: int
    partial: int
    failed: int
    step_issues: dict[str, int]
    push_sent: int
    push_failed: int

@dataclass(frozen=True, slots=True)
class OperatorDelivery:
    status: DeliveryStatus
    sent: int = 0
    failed: int = 0
    removed: int = 0
    retryable: bool = False   # status == "failed" and a retry next run makes sense
    push_failures: dict[str, int] = field(default_factory=dict)  # detail -> count

@dataclass(frozen=True, slots=True)
class UsageReportResult:
    stats: UsageStats
    warnings: tuple[str, ...]          # usage_warnings(stats), Dutch
    report_due: bool
    report: str | None                 # build_usage_report(stats) when due
    report_done: bool
    warning_notified: bool
    delivery: OperatorDelivery | None  # None if no push was due
    runs_deleted: int
    errors: tuple[str, ...]            # "<source>: DatabaseError (HTTP n, code c)" | "db_usage: unexpected response"
    notes: tuple[str, ...]             # English, public, without values

    @property
    def status(self) -> Literal["ok", "partial"]:
        """partial if errors, or delivery.status in ("failed", "invalid_operator")."""

def read_open_meteo_usage(db: SupabaseRest, *, now: datetime) -> OpenMeteoUsage
def read_db_usage(db: SupabaseRest) -> DbUsage                      # ValueError on a bad shape
def read_run_history(db: SupabaseRest, *, now: datetime) -> RunHistory
def earlier_usage_counts(db: SupabaseRest, *, since: datetime, now: datetime) -> list[dict[str, Any]]
def resolve_operator(value: str | None) -> str | None                # canonical UUID; ValueError if invalid
def deliver_operator_push(db: SupabaseRest, notifier: Notifier | None, operator_id: str | None,
                          payload: PushPayload, *, now: datetime) -> OperatorDelivery
def delete_old_ingest_runs(db: SupabaseRest, *, now: datetime) -> int
def collect_usage_stats(db: SupabaseRest, *, now: datetime, with_history: bool) -> tuple[UsageStats, list[str]]
def usage_stats_json(stats: UsageStats) -> dict[str, Any]
def run_usage_report(db: SupabaseRest, *, now: datetime, operator_user_id: str | None,
                     notifier_factory: Callable[[], Notifier | None]) -> UsageReportResult
def run_usage_show_cli(*, echo: Callable[[str], None]) -> int
```

Details:
- **`read_open_meteo_usage`**
  - `today = now` als UTC-datum, `first = today.replace(day=1)`, `start = min(first, today - 6 dagen)`.
  - `db.select("api_usage", columns="day,source,calls", filters={"day": [f"gte.{start}", f"lte.{today}"]})`.
  - Alleen bronnen met prefix `OPEN_METEO_PREFIX` (uit `shakka.budget`) tellen mee.
  - `today` is de som van vandaag, `max_day` het maximum van de dagsommen in `[today − 6, today]` (0 als er niets is), `month` de som vanaf `first`.
- **`read_db_usage`**
  - `db.rpc(DB_USAGE_RPC)`. Verwacht een dict met `database_bytes` (een int ≥ 0, geen `bool`) en `tables` (een dict van str naar int ≥ 0).
  - Anders `ValueError("db_usage: unexpected response")`.
- **`read_run_history`**
  - `db.select("ingest_runs", columns="started_at,status,steps", filters={"started_at": [f"gte.{iso_utc(now - 7 d)}", f"lt.{iso_utc(now)}"]})`.
  - Telt `status` ok/partial/failed; `running` en andere statussen tellen niet mee.
  - Per stap-dict in `steps` met `status` in `partial`/`failed`/`skipped`: `step_issues[name] += 1`.
  - Voor de stap `alerts`: `push_sent += int(counts.get("sent", 0))`, idem voor `failed`.
  - Een rij of stap die geen dict of lijst is, wordt overgeslagen.
- **`earlier_usage_counts`**: `db.select("ingest_runs", columns="started_at,steps", filters={"started_at": [f"gte.{iso_utc(since)}", f"lt.{iso_utc(now)}"]})`. Geeft per run de `counts`-dict van de stap `USAGE_STEP`, als die er is.
- **`resolve_operator`**: `None` of leeg na `strip()` geeft `None`; anders `str(uuid.UUID(value.strip()))`. Een `ValueError` van `uuid` gaat door.
- **`deliver_operator_push`**
  - Bij `operator_id is None` → `no_operator`. Bij `notifier is None` → `push_disabled`.
  - `targets = load_targets(db, operator_id)`. Een `DatabaseError` geeft `failed` met `retryable=True` en `push_failures={"DatabaseError": 1}`.
  - Geen doelen → `no_target`.
  - Per doel `notifier.send_payload(target, payload)` in `try/except Exception` (→ `DeliveryResult(False, False, type(exc).__name__)`).
  - Daarna `update_subscriptions(db, gone=..., ok=..., now=now)` als er gone- of ok-id's zijn. Een fout daarbij komt in `push_failures` als `"update"` en verandert de status niet.
  - Status: `sent` bij ≥ 1 geslaagd. Anders `no_target` als alle fouten permanent waren (alle doelen weg). Anders `failed`, met `retryable = any(not r.ok and not r.permanent_failure and r.retryable)`.
  - Nooit een endpoint, user-id of tekst in een log of resultaat.
- **`delete_old_ingest_runs`**: `db.delete("ingest_runs", filters={"started_at": f"lt.{iso_utc(now - INGEST_RUNS_RETENTION)}"})`.
- **`collect_usage_stats`**: roept `read_open_meteo_usage` en `read_db_usage` aan, en bij `with_history` ook `read_run_history`. Elke bron afzonderlijk in `try`: een `DatabaseError` geeft een fout `f"{bron}: {db_error_summary(exc)}"` (bronnen `api_usage`, `db_usage`, `ingest_runs`), een `ValueError` van `read_db_usage` geeft `"db_usage: unexpected response"`. Het veld blijft dan `None` of `{}`.
- **`run_usage_report`**, de volgorde is bindend:
  1. `require_aware(now)`. `stats, errors = collect_usage_stats(db, now=now, with_history=False)`. `warnings = usage_warnings(stats)`.
  2. `report_due = False`. Als `report_due_time(now)`: `earlier_usage_counts(db, since=week_start(now), now=now)`. Een `DatabaseError` daarbij geeft een fout en het rapport is niet due. Anders `report_due = not any(c.get("report_done") is True for c in ...)`.
  3. Als `report_due`:
     - lees de geschiedenis (een fout in `errors`) en vul `stats` aan met `dataclasses.replace`;
     - `report = build_usage_report(stats)`;
     - `payload = PushPayload(**usage_push_text(stats).model_dump(), url=OPERATOR_PUSH_URL, tag=REPORT_TAG)`;
     - verstuur (stap 5);
     - `report_done = not (delivery.status == "failed" and delivery.retryable)`;
     - `warning_notified = bool(warnings) and report_done`;
     - `runs_deleted = delete_old_ingest_runs(...)` (een `DatabaseError` geeft een fout en 0).
  4. Anders als `warnings` en `in_operator_window(now)`:
     - `earlier_usage_counts(db, since=local_day_start(now), now=now)` (een `DatabaseError` geeft een fout en geen push);
     - als geen enkele eerdere stap vandaag `warning_notified is True` heeft: payload met `warning_push_text(warnings)`, `tag=WARNING_TAG`, versturen, en `warning_notified = not (failed and retryable)`.
  5. Versturen:
     - `operator = resolve_operator(operator_user_id)`; een `ValueError` geeft `OperatorDelivery("invalid_operator")`;
     - `notifier = notifier_factory()`; een `ValueError` geeft `notifier = None` met een aparte note;
     - daarna `deliver_operator_push(...)`.
  6. Notes, Engels en zonder waarden:
     - `no_operator`: `"OPERATOR_USER_ID not set: usage push not sent (report stored in ingest_runs)"`
     - `invalid_operator`: `"OPERATOR_USER_ID is not a valid UUID: usage push not sent"`
     - `push_disabled`: `"push disabled or misconfigured: usage push not sent"`
     - `no_target`: `"no push subscription for the operator: usage push not sent"`
     - `failed`: `f"usage push failed on all {n} device(s); see push_failures in ingest_runs"`, plus `"; retried next run"` als `retryable`
     - Elke note gaat ook via `logger.warning`.
  - In alle gevallen: `report_done` en `warning_notified` zijn `False` als er niets gebeurde. Bij `no_operator`, `push_disabled`, `no_target` en `invalid_operator` zijn ze waar, zodat niet elk uur opnieuw geprobeerd wordt.
- **`run_usage_show_cli`**: `get_settings()` (`ValidationError` → `"usage show: configuration incomplete; run shakka doctor"`, exit 1). Dan `open_db`, `collect_usage_stats(with_history=True)`, de regels van `build_usage_report` met `echo`, daarna per fout `"error   <tekst>"`. Exit 1 bij fouten, anders 0. De clock komt uit `runtime.utcnow` via de module. Er wordt nooit iets verstuurd of geschreven.

### Pipeline
```python
RUN_TIME_BUDGET_S: Final = 600.0      # read from the module at run time (tests monkeypatch it)
RUN_TIME_BUDGET: Final = "run_time_budget"
STEP_NAMES = (..., "sessions_cleanup", "usage_report")
STEPS = (..., ("sessions_cleanup", step_sessions_cleanup), ("usage_report", step_usage_report))
def step_usage_report(ctx: PipelineContext) -> StepOutcome
def usage_counts(result: UsageReportResult) -> dict[str, Any]
```
- **`step_usage_report`**
  - Bouwt `notifier_factory`: `(ctx.notifiers if ctx.notifiers is not None else notifiers_from_settings(ctx.settings)).get(WEBPUSH_CHANNEL)`.
  - Roept `run_usage_report(ctx.db, now=ctx.now, operator_user_id=ctx.settings.operator_user_id, notifier_factory=...)` aan.
  - Geeft `StepOutcome(result.status, usage_counts(result), warnings)` terug, met `warnings = tuple(f"usage threshold: {w}" for w in result.warnings) + result.notes`.
- **`usage_counts`** levert precies deze sleutels:
  - `due`, `report_done`, `warning_notified`;
  - `database_bytes` (int of None), `open_meteo_today` en `open_meteo_month` (afgerond op 2 decimalen, of None);
  - `warnings` (lijst), `delivery` (status of None), `sent`, `failed`, `removed`, `push_failures` (dict);
  - `runs_deleted`, `report` (str of None), `stats` (`usage_stats_json(stats)` als due, anders None), `errors` (lijst).
- **`step_alerts`**:
  - als `result.blocked_targets` groter dan 0 is, komt er een warning `f"{n} push subscription(s) skipped: push service host not allowed"`;
  - als `result.push_non_retryable` groter dan 0 is, komt er een warning `non_retryable_warning(n)`:
    ```python
    def non_retryable_warning(count: int) -> str:
        return (
            f"{count} push delivery(ies) failed without retry; the alert is lost for that "
            "device (see push_failures in ingest_runs)"
        )
    ```
  - volgorde van de warnings: `PUSH_DISABLED_WARNING`, deferred, non-retryable, blocked;
  - `partial = bool(result.skipped or result.write_errors or result.deferred or result.push_non_retryable)`;
  - `alert_counts` krijgt `"blocked_targets"` en `"push_non_retryable"` (direct na `"deferred"`).
- **`_run`**: in de lus `if _monotonic() - started >= RUN_TIME_BUDGET_S: report = StepReport(name, "skipped", 0, {}, reason=RUN_TIME_BUDGET) else: report = run_step(...)`. `started` wordt dan vóór de lus gezet; dat is het al. Het voortgangs-update blijft per stap.
- **`exit_code_for`**: ook 1 als een stap `skipped` is met reden `RUN_TIME_BUDGET`.
- **`build_annotations`**: zo'n stap geeft `::error::step {name} skipped: run time budget of {RUN_TIME_BUDGET_S:.0f} s reached`.

### Config en env
- `Settings.operator_user_id: str | None = None`. De env-naam is `OPERATOR_USER_ID`.
- `secret_values` voegt `v = operator_user_id.strip()` toe als die niet leeg is. Daarna `try: c = str(uuid.UUID(v))` en, als `c != v`, ook `c`; een `ValueError` wordt genegeerd (de stap meldt een ongeldige waarde al). Zo wordt ook de canonieke vorm geredigeerd als de secret in hoofdletters of met accolades is gezet (review N-8).
- `.env.example`, als laatste regels:
  ```
  # WP-22: your Supabase user id (Dashboard, Authentication, Users); weekly usage push
  OPERATOR_USER_ID=
  ```
- `hourly.yml`, env van "Hourly pipeline": `OPERATOR_USER_ID: ${{ secrets.OPERATOR_USER_ID }}`.

### SQL: `supabase/migrations/20261015220000_drop_profiles_telegram_chat_id.sql`
```sql
-- WP-22 (A-16): the notification channel of M1 was dropped; remove its unused column.
alter table public.profiles drop constraint if exists profiles_telegram_chat_id_format;
alter table public.profiles drop column if exists telegram_chat_id;
```

### SQL: `supabase/migrations/20261015220100_hardening.sql`
Let op, twee statische tests lezen alle latere migraties:
- zet het woord "grant" in dit bestand nergens vóór de body van `db_usage`: `test_no_grants_on_rsvps` matcht `grant … on … public.rsvps` tot de eerstvolgende `;`;
- noem in dit bestand (ook niet in commentaar) de namen `get_public_session`, `rsvp_create`, `rsvp_update`, `rsvp_delete` of `purge_expired_sessions`, en schrijf geen `alter table … public.rsvps`: `web/test/rsvp-contract.test.ts` ("migration drift") weert die in latere migraties.
```sql
-- WP-22: database usage for the weekly report (service role only), at most 20 push
-- subscriptions per user, and an upper bound on how far ahead a session can start.

create function public.db_usage()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select pg_catalog.jsonb_build_object(
    'database_bytes',
    (select coalesce(sum(pg_catalog.pg_database_size(d.oid)), 0)::bigint
       from pg_catalog.pg_database d
      where pg_catalog.has_database_privilege(d.oid, 'CONNECT')),
    'tables',
    pg_catalog.jsonb_build_object(
      'spots', (select count(*) from public.spots),
      'forecast_hours', (select count(*) from public.forecast_hours),
      'marine_hours', (select count(*) from public.marine_hours),
      'tide_extremes', (select count(*) from public.tide_extremes),
      'evaluations', (select count(*) from public.evaluations),
      'profiles', (select count(*) from public.profiles),
      'favorites', (select count(*) from public.favorites),
      'alert_rules', (select count(*) from public.alert_rules),
      'alert_state', (select count(*) from public.alert_state),
      'push_subscriptions', (select count(*) from public.push_subscriptions),
      'sessions', (select count(*) from public.sessions),
      'rsvps', (select count(*) from public.rsvps),
      'api_usage', (select count(*) from public.api_usage),
      'ingest_runs', (select count(*) from public.ingest_runs)
    )
  );
$$;

revoke all on function public.db_usage() from public, anon, authenticated, service_role;
grant execute on function public.db_usage() to service_role;

-- Security invoker on purpose: under RLS an authenticated caller only counts own rows.
create function public.push_subscriptions_limit()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('shakka.push_subscriptions:' || new.user_id::text, 0)
  );
  select count(*) into v_count from public.push_subscriptions p where p.user_id = new.user_id;
  if v_count >= 20 then
    raise sqlstate 'PT400' using message = 'too_many_subscriptions';
  end if;
  return new;
end;
$$;

create trigger push_subscriptions_limit before insert on public.push_subscriptions
  for each row execute function public.push_subscriptions_limit();

revoke all on function public.push_subscriptions_limit()
  from public, anon, authenticated, service_role;

-- Upper bound on how far ahead a session may start. A CHECK cannot use now(), so a trigger.
-- The app allows up to 365 days ahead, on create and on edit. On update the bound only applies
-- when starts_at actually changes, so an older row stays editable. Security invoker.
create function public.sessions_starts_at_horizon()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' then
    if new.starts_at is not distinct from old.starts_at then
      return new;
    end if;
  end if;
  if new.starts_at > now() + interval '370 days' then
    raise sqlstate '23514' using message = 'starts_at_too_far_ahead';
  end if;
  return new;
end;
$$;

create trigger sessions_starts_at_horizon before insert or update of starts_at on public.sessions
  for each row execute function public.sessions_starts_at_horizon();

revoke all on function public.sessions_starts_at_horizon()
  from public, anon, authenticated, service_role;
```

Opmerkingen:
- `old` wordt alleen gelezen binnen `if tg_op = 'UPDATE'` (geneste `if`, want SQL garandeert geen kortsluiting van `and`/`or`). De builder test beide takken (Testplan AC-4, 22–28).
- De trigger vuurt alleen als `starts_at` in de SET-lijst staat. Annuleren (`update … set cancelled_at`) raakt hem dus niet.
- Triggers op dezelfde tabel lopen op naamvolgorde: `sessions_prepare_insert`, `sessions_set_updated_at`, `sessions_starts_at_horizon`. De volgorde maakt hier niet uit.

### `supabase/tests/07_sessions.test.sql` (alleen regels 68 en 69)
Regel 68 wordt:
```sql
select set_eq($$select p.proname::text from pg_proc p where p.pronamespace = 'public'::regnamespace and has_function_privilege('service_role', p.oid, 'EXECUTE')$$, $$values ('purge_expired_sessions'), ('db_usage')$$, 'service_role can execute exactly purge_expired_sessions and db_usage');
```
Regel 69 wordt:
```sql
select set_eq($$select p.proname::text from pg_proc p where p.pronamespace = 'public'::regnamespace and p.prosecdef$$, $$values ('handle_new_user'), ('get_public_session'), ('rsvp_create'), ('rsvp_update'), ('rsvp_delete'), ('purge_expired_sessions'), ('db_usage')$$, 'security definer functions in public');
```
- `plan(112)` blijft gelijk. Regels 66, 67 en 70 blijven ongewijzigd.
- **Samenloop met WP-23** (die `delete_my_account` toevoegt, security definer, `EXECUTE` alleen voor `authenticated`): wie als tweede merget, voegt beide samen. Na beide merges luiden de regels:
  - regel 67: `… $$values ('get_public_session'), ('rsvp_create'), ('rsvp_update'), ('rsvp_delete'), ('delete_my_account')$$, 'authenticated can execute exactly the four public RPCs and delete_my_account');` (tekst van WP-23);
  - regel 68: zoals hierboven;
  - regel 69: `… $$values ('handle_new_user'), ('get_public_session'), ('rsvp_create'), ('rsvp_update'), ('rsvp_delete'), ('purge_expired_sessions'), ('delete_my_account'), ('db_usage')$$, 'security definer functions in public');`
  - Is WP-23 al gemerged als de builder van WP-22 rebaset, dan schrijft hij direct deze eindvorm.
- `push_subscriptions_limit` en `sessions_starts_at_horizon` staan bewust in geen van de sets van regels 66–69: ze zijn security invoker en niemand heeft `EXECUTE`. Regel 70 (`search_path` gepind) geldt alleen voor security-definerfuncties; beide hebben toch `set search_path = ''`.

### Web: `auth.ts`
- `signInWithOtp({ email, options: { emailRedirectTo: window.location.origin, shouldCreateUser: true } })`.
- Docstring: "New addresses get an account (WP-22). Whether sign-up is open is a server setting ("Allow new users to sign up"); when it is off, GoTrue answers signup_disabled."
- `authErrorMessage`: `code === 'email_address_not_authorized' || code === 'otp_disabled' || code === 'signup_disabled'` → `AUTH_MESSAGES.notAuthorized`, met het commentaar daarop bijgewerkt.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `with_retries` met `attempts=1` | Eén aanroep, geen wachttijd. |
| E2 | Niet-herhaalbare fout bij poging 1 | Direct doorgegooid, geen wachttijd, `on_retry` niet aangeroepen. |
| E3 | `TransientError(retry_after=100)` | Wachttijd 30. Bij `retry_after=-5` is de wachttijd 0. |
| E4 | `KeyboardInterrupt` in `fn` | Niet opgevangen. |
| E5 | Open-Meteo 3× 500 | `"failed after 3 attempts: HTTP 500"`, wachttijden [1, 2], 2 logregels (ongewijzigd). |
| E6 | RWS 500, 500, 200 | Resultaat geparsed, 3 POST's. |
| E7 | RWS 3× 500 | `TideFetchError("hoekvanholland: HTTP 500: … (after 3 attempts)")`, korter dan 260 tekens. |
| E8 | RWS 204, 302, 400 of ongeldige JSON | Eén request, direct `TideFetchError`. |
| E9 | DB-select 503, 503, 200 | Rijen, 3 requests, wachttijden [0,5; 1,0]. |
| E10 | DB-insert 503 | Eén request, `DatabaseError(status=503)`. |
| E11 | DB-rpc 503 | Eén request. |
| E12 | DB-select 500 of 409 | Eén request. |
| E13 | DB-select 3× `ConnectError`, daarna nog een select die faalt | 3 requests, dan 1; `retries_disabled is True`. |
| E14 | DB-retrylog met een user-id in een filter | De user-id staat niet in de logtekst. |
| E15 | Endpoint `https://fcm.googleapis.com@evil.test/x` | Niet toegestaan (userinfo). |
| E16 | Endpoint `https://fcm.googleapis.com:443/x` of `http://fcm.googleapis.com/x` | Niet toegestaan. |
| E17 | Endpoint `https://push.apple.com/x` (geen subdomein) | Niet toegestaan. `https://web.push.apple.com/x` wel. |
| E18 | Endpoint `https://evilnotify.windows.com/x` | Niet toegestaan: `.notify.windows.com` vereist een punt. |
| E19 | Endpoint `https://[::1]/x` of een ongeldige poort | Niet toegestaan, geen exception. |
| E20 | Gebruiker met alleen een geblokkeerd abonnement | `no_target`, state opgeslagen, `blocked_targets == 1`, warning-annotatie. |
| E21 | Aflevering HTTP 403 voor het enige abonnement | `failed`, niet `deferred`; `push_non_retryable == 1`; state opgeslagen; abonnement blijft staan; stap `alerts` `partial` met de warning `1 push delivery(ies) failed without retry; …`. |
| E22 | Aflevering HTTP 503 of `requests.ConnectTimeout` | Herhaalbaar: `deferred` zoals in WP-17. |
| E23 | `RuntimeError` of `VapidException` uit `webpush()` | Niet herhaalbaar. |
| E24 | Spot met alle rijen precies 3 uur oud | Vers: wordt geëvalueerd. |
| E25 | Spot met alle rijen 3 uur en 1 seconde oud | `stale`; geen evaluatierijen; favoriet `ineligible`; oude evaluaties blijven staan. |
| E26 | Twee modellen, één 1 uur en één 4 uur oud | Alleen het verse model, lagere betrouwbaarheid. |
| E27 | Twee spots, één vers en één oud (gefaalde chunk) | De globale stale-regel laat `alerts` draaien; de oude spot is `ineligible`. |
| E28 | Runbudget overschreden na `evaluate` | `alerts`, `sessions_cleanup` en `usage_report` `skipped` (`run_time_budget`); run `partial`; exitcode 1; `::error::` per overgeslagen stap. |
| E29 | Woensdag 08:17, geen waarschuwingen | Stap `ok`: geen push, geen `ingest_runs`-query, geen writes. Counts met `due: false`. |
| E30 | Maandag 07:17 lokaal | Niet due (buiten het venster). |
| E31 | Maandag 08:17, eerste keer | Rapport due; push naar de abonnementen van de operator; `report_done: true`; `counts.report` gevuld; oude `ingest_runs` opgeruimd. |
| E32 | Maandag 09:17, na een geslaagde run om 08:17 | Niet due, geen push. |
| E33 | Maandag 08:17 met een tijdelijke fout (503) op alle apparaten | `failed`, `retryable`, `report_done: false`, stap `partial`. Om 09:17 opnieuw. |
| E34 | Maandag met 410 op alle apparaten | Abonnementen verwijderd; `no_target`; `report_done: true`. |
| E35 | Geen `OPERATOR_USER_ID` | Rapport opgeslagen, `no_operator`, note-annotatie, stap `ok`; `report_done: true`. |
| E36 | `OPERATOR_USER_ID="abc"` | `invalid_operator`, stap `partial`, de waarde komt nergens in de uitvoer. |
| E37 | Operator zonder abonnementen | `no_target`, stap `ok`. |
| E38 | Woensdag 10:17, database 310 MB | Waarschuwingspush (titel `WARNING_TITLE`); `warning_notified: true`. Om 11:17: geen push, wel de annotatie. Donderdag 08:17: opnieuw een push. |
| E39 | Waarschuwing om 23:17 lokaal | Geen push (buiten het venster), wel een annotatie. De volgende ochtend om 08:17 een push als de drempel nog overschreden is. |
| E40 | Maandag 08:17 met waarschuwing | Eén push (het rapport, met de waarschuwingen eerst), geen aparte waarschuwingspush. |
| E41 | `db_usage` geeft `PGRST202` (migratie nog niet gepusht) | `database_bytes` en `tables` onbekend; fout `db_usage: DatabaseError (HTTP 404, code PGRST202)`; stap `partial`; geen crash. |
| E42 | `api_usage` niet leesbaar | Open-Meteo onbekend; geen Open-Meteo-waarschuwing; stap `partial`. |
| E43 | `ingest_runs` niet leesbaar op maandag (dedup-query) | Niet due, fout, `partial`; geen spam. |
| E44 | VAPID onvolledig, maar er is een push due | De factory geeft `ValueError` → `push_disabled` met note; de stap `alerts` faalt al (mail). |
| E45 | `db_usage()` als anon of authenticated | `42501`. |
| E46 | 21e abonnement van gebruiker A | `PT400 too_many_subscriptions`; B kan nog wel. |
| E47 | Sessie met `starts_at` 371 dagen vooruit, of een update naar 371 dagen | `23514 starts_at_too_far_ahead`. 365 dagen gaat goed. |
| E47a | Sessie 10 dagen geleden aangemaakt, nu verzet naar vandaag + 369 dagen (review B-5) | Gaat goed: de grens hangt aan `now()`, niet aan `created_at`. |
| E47b | Bestaande rij met `starts_at` verder dan 370 dagen vooruit (van vóór de migratie); update van `note` met dezelfde `starts_at` in de SET-lijst | Gaat goed (`starts_at` verandert niet). Een update die `starts_at` wél verandert naar > 370 dagen: `23514`. |
| E47c | Annuleren van een sessie (`set cancelled_at`) | De trigger vuurt niet. |
| E48 | Inloggen met een onbekend adres terwijl aanmelden uit staat | `signup_disabled` → melding "nog niet inloggen". |
| E49 | Rapport met alle velden onbekend | Elke regel toont "onbekend"; pushbody `Runs ?% ok · DB ? MB · Open-Meteo max ?/dag\n? gebruikers, ? abonnementen`. |
| E50 | Grote getallen (10¹² bytes, 10⁷ calls) | De titel blijft binnen 50 tekens en de body binnen 150. Met deze testwaarden passen de drie waarschuwingen samen (ongeveer 136 tekens inclusief de twee regeleinden, dus onder 150). Bij nog grotere getallen kan dat niet meer; dan valt een waarschuwing weg volgens het algoritme van `usage_push_text` (regels vanaf het begin zolang ze passen), maar de grenzen blijven gelden. |
| E51 | Week die over de maandgrens loopt (1 augustus) | `max_day` over 7 dagen die in juli beginnen; `month` alleen augustus. |
| E52 | Endpoint `https://jmt17.google.com/fcm/send/abc` (Chrome Beta/Dev/Canary) | Toegestaan. `https://x.jmt17.google.com/…` en `https://android.googleapis.com/gcm/send/…` niet. |
| E53 | Gebruiker met precies 20 abonnementen meldt een bestaand endpoint opnieuw aan (review N-6) | De trigger vuurt vóór de unieke check: `PT400 too_many_subscriptions` in plaats van `23505`. `addPushSubscription` geeft dan een generieke fout in plaats van `'exists'`. Zeldzaam, want de app snoeit naar 10. Geen codewijziging; staat in RUNBOOK §14.14. |
| E54 | Database-select geeft 522 (Cloudflare), dan 200 | Herhaald, rijen terug, 2 requests. |
| E55 | `OPERATOR_USER_ID` als `{AAAAAAAA-…}` (hoofdletters, accolades) | Push werkt (canoniek via `resolve_operator`); zowel de ruwe als de canonieke vorm worden geredigeerd. |

## Testplan

Tests eerst voor het domein (`test_usage.py`) en voor `with_retries`. Alle Python-tests draaien zonder netwerk; de autouse-fixture zet `_sleep` op no-op. Draai vanuit `ingest/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`. Vanuit de root: `supabase test db`. Vanuit `web/`: `npm run check && npm test && npm run build`.

### AC-1: alleen `make_client`, eindige timeouts, uniforme retries
- `test_http.py`:
  - `test_only_http_module_creates_clients`: loopt alle `.py`-bestanden onder `ingest/src/shakka` door; `"httpx.Client("` komt alleen voor in `http.py`.
  - `test_make_client_timeouts_are_finite`: voor `make_client()` en `make_client(timeout=5)` zijn alle vier de timeouts eindig en groter dan 0.
  - `test_with_retries_*`:
    - succes zonder retry;
    - retry, daarna succes: wachttijden [1, 2] met `backoff=1`, en [0,5; 1,0] met `backoff=0,5`;
    - uitgeput: zelfde exception-object en `__context__ is None`;
    - een niet-herhaalbare fout gaat direct door;
    - `retry_after` wordt toegepast en begrensd (E3);
    - `attempts=0` en `backoff=-1` geven `ValueError`;
    - `on_retry` krijgt de argumenten `(1, exc, 1.0)`;
    - `KeyboardInterrupt` wordt niet opgevangen;
    - zonder `sleep`-argument wordt `shakka.http._sleep` gebruikt (monkeypatch met een recorder).
- `test_openmeteo_client.py`: blijft ongewijzigd groen (regressie van E5).
- `test_rws_tides.py`: `test_fetch_retries_then_ok` (E6), `test_fetch_500_three_times` (E7), `test_fetch_no_retry_on_permanent` (E8, telt de requests), `test_fetch_transport_error_retried` (ConnectError, dan 200). De bestaande `test_fetch_errors` blijft groen (de fixture slaat het wachten over).
- `test_db.py`: E9–E14 en E54 met de bestaande `make_db`. Wachttijden via `monkeypatch.setattr(shakka.http, "_sleep", rec.append)`. Plus `test_retry_statuses`: `DB_RETRY_STATUSES == {429, 502, 503, 504, 520, 521, 522, 523, 524}` en 500 zit er niet in.
- `test_notify_webpush.py`: `test_webpush_called_with_timeout` bestaat al (r. 54) en blijft.

### AC-2: `tests/test_usage.py` (puur)
- Fixture `STATS_OK`:
  - `now = datetime(2026, 7, 20, 6, 17, tzinfo=UTC)` (maandag 08:17 CEST);
  - `open_meteo_today=1400.0`, `open_meteo_max_day=1420.5`, `open_meteo_month=26000.0`, `database_bytes=42 * BYTES_PER_MB`;
  - `table_rows={"spots": 25, "forecast_hours": 14500, "marine_hours": 4000, "tide_extremes": 300, "evaluations": 4800, "profiles": 2, "favorites": 3, "alert_rules": 3, "alert_state": 2, "push_subscriptions": 2, "sessions": 0, "rsvps": 0, "api_usage": 40, "ingest_runs": 1000}`;
  - `runs_ok=160, runs_partial=7, runs_failed=1`, `step_issues={"tides": 3, "marine": 5}`, `push_sent=12, push_failed=1`.
- `test_build_usage_report_golden`: `build_usage_report(STATS_OK)` is exact:
  ```
  Shakka gebruiksrapport tot 2026-07-20 08:17 (Europe/Amsterdam)
  Waarschuwingen: geen
  Open-Meteo: vandaag 1.400 calls, hoogste dag (7 dagen) 1.421, limiet 10.000 per dag; deze maand 26.000, limiet 300.000
  Database: 42 MB van 500 MB
  Rijen: alert_rules 3, alert_state 2, api_usage 40, evaluations 4.800, favorites 3, forecast_hours 14.500, ingest_runs 1.000, marine_hours 4.000, profiles 2, push_subscriptions 2, rsvps 0, sessions 0, spots 25, tide_extremes 300
  Runs (7 dagen): 168, waarvan 160 ok, 7 partial, 1 failed (95% ok)
  Stappen niet ok (7 dagen): marine 5, tides 3
  Push (7 dagen): 12 verstuurd, 1 mislukt
  Gebruikers: 2, push-abonnementen: 2
  ```
- `test_build_usage_report_with_warnings_golden`: `STATS_OK` met `database_bytes=310 * BYTES_PER_MB` en `open_meteo_today=7100.0`, `open_meteo_max_day=7100.0`. Regel 2 en 3 worden `Waarschuwingen:`, `- Database 310 MB, boven 300 MB`, `- Open-Meteo vandaag 7.100 calls, boven 7.000`, en de Open-Meteo-regel toont `vandaag 7.100 calls, hoogste dag (7 dagen) 7.100`.
- `test_build_usage_report_unknown`: `UsageStats(now=...)` met alleen `now` geeft voor elke regel de "onbekend"-vorm (E49). Runs `0/0/0` geeft `Runs (7 dagen): 0` en `Stappen niet ok (7 dagen): geen`.
- `test_usage_warnings`, geparametriseerd:
  - 310 MB → databasewaarschuwing;
  - precies 300 MB → geen; 300 MB + 1 byte → wel, als "Database 301 MB, boven 300 MB";
  - 7.100 vandaag → Open-Meteo-waarschuwing; 7.000 → geen;
  - maand 210.001 → maandwaarschuwing; 210.000 → geen;
  - alle drie samen in de vaste volgorde;
  - `STATS_OK` → `[]`;
  - onbekende waarden → geen waarschuwing.
- `test_usage_push_text_golden`:
  - `STATS_OK` → titel `"Shakka weekrapport"`, body `"Runs 95% ok · DB 42 MB · Open-Meteo max 1.421/dag\n2 gebruikers, 2 abonnementen"`;
  - met de waarschuwingen van hierboven → titel `"Shakka weekrapport: let op"`, body `"Database 310 MB, boven 300 MB\nOpen-Meteo vandaag 7.100 calls, boven 7.000\nRuns 95% ok · DB 310 MB · Open-Meteo max 7.100/dag"` (de laatste regel past niet meer).
- `test_push_text_bounds`: een raster van extreme stats (alles onbekend, alles 0, `database_bytes=10**12`, calls `10**7`, alle drie de waarschuwingen) geeft altijd `len(title) <= 50` en `len(body) <= 150`, en de waarschuwingen staan vooraan.
- `test_warning_push_text`: titel `WARNING_TITLE`, body = de waarschuwingen samengevoegd; `[]` geeft `ValueError`.
- `test_time_helpers`:
  - `week_start(2026-07-15T06:17Z) == 2026-07-12T22:00Z`;
  - `week_start(2026-10-26T07:17Z) == 2026-10-25T23:00Z` (de maandag na het einde van de zomertijd);
  - `local_day_start(2026-07-15T06:17Z) == 2026-07-14T22:00Z`;
  - `in_operator_window` op 05:59Z (07:59 CEST) onwaar, op 06:00Z waar, op 19:59Z waar en op 20:00Z onwaar;
  - `report_due_time` op maandag 2026-07-20T06:17Z waar, op maandag 05:17Z onwaar, op dinsdag onwaar.
- `test_usage_stats_validation`: een naïeve `now`, `-1`, `NaN`, `True` als int, en runs half gezet geven elk `ValueError`.
- `test_limits_match_budget`: `OPEN_METEO_DAILY_LIMIT` en `OPEN_METEO_MONTHLY_LIMIT` zijn gelijk aan die in `shakka.budget`.
- De puurheid wordt bewaakt door `test_domain_purity.py` (ongewijzigd).

### AC-3: `tests/test_pipeline_usage.py`
Fixture:
- `FakeSupabase` met `seed_user` en de pipeline-spot;
- 2 abonnementen voor `USER_A` (operator) en 1 voor `USER_B` (`seed_subs`);
- `settings = make_settings(spots_yaml, operator_user_id=USER_A)`;
- `notifier = FakeNotifier()`;
- `run_hourly(settings, now=MONDAY, db=db, http=blocked_http(), notifiers={"webpush": notifier}, forecast_fetch=fake_forecast_fetch, marine_fetch=fake_marine_fetch, tide_fetch=no_tides)`, met `MONDAY = datetime(2026, 7, 20, 6, 17, tzinfo=UTC)`.

Tests:
- `test_report_sent_on_monday_to_operator_only`:
  - `notifier.payload_calls` heeft 2 items, beide endpoints van `USER_A`, `tag == "shakka-usage-report"`, titel ≤ 50, body ≤ 150;
  - de stap `usage_report` is `ok`, met `counts.report_done is True`, `counts.report` die begint met `"Shakka gebruiksrapport tot 2026-07-20 08:17"`, en `counts.stats` niet `None`.
- `test_report_once_per_week`: een tweede `run_hourly` om MONDAY + 1 uur op dezelfde database geeft geen nieuwe `payload_calls` en `counts.due is False`.
- `test_no_report_on_tuesday`: om MONDAY + 1 dag geen `payload_calls` en `due is False`.
- `test_no_operator_still_stores_report`: zonder `operator_user_id` is de stap `ok`, `counts.report` is gevuld, `delivery == "no_operator"`, er is geen push, en er staat een annotatie `"::warning::usage_report: OPERATOR_USER_ID not set"`.
- `test_operator_without_subscription`: de operator is `USER_C` zonder abonnementen → `no_target`, rapport opgeslagen, geen crash.
- `test_invalid_operator_id_is_partial_and_not_leaked`: `operator_user_id="not-a-uuid-12345"` → stap `partial`; de waarde staat niet in `db.rows("ingest_runs")` en niet in de annotaties.
- `test_threshold_warning_pushed_once_a_day`:
  - `db.database_bytes = 310 * BYTES_PER_MB`, `now` op woensdag 2026-07-15T08:17Z (10:17 CEST): één `payload_call` met `tag == "shakka-usage-warning"`, en een annotatie die begint met `"::warning::usage_report: usage threshold: Database 310 MB"`;
  - een tweede run om +1 uur geeft geen nieuwe push, maar wel de annotatie.
- `test_retry_after_transient_failure`: `notifier.set_result(<beide endpoints>, DOWN)` → `report_done is False` en stap `partial`; daarna `OK` en een run om +1 uur → verstuurd.
- `test_old_ingest_runs_deleted_on_report`: een gezaaide rij met `started_at = MONDAY - 91 dagen` is weg na de rapportrun, met `counts.runs_deleted == 1`. Een rij van 89 dagen blijft staan.
- In `test_pipeline.py`:
  - `test_steps_contract_order` met 8 namen;
  - `test_all_steps_ok_records_run`: laatste stap `usage_report`, `ok`, `counts["due"] is False`;
  - `test_spots_sync_failure_continues`: `len(report.steps) == 8`.

### AC-4: `supabase/tests/10_hardening.test.sql`
Opbouw zoals `07_sessions.test.sql`: `begin; create extension if not exists pgtap with schema extensions; select plan(28); … select * from finish(); rollback;`.

Fixture (als postgres), letterlijk het patroon van `07_sessions.test.sql` regels 8–11:
```sql
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'a@example.test'),
  ('22222222-2222-2222-2222-222222222222', 'b@example.test');
insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot');
```
Elke sessie-insert geeft expliciet `id`, `slug` (≥ 10 tekens, uniek), `spot_id = 'pgtap-spot'`, `organizer_id`, `organizer_name`, `starts_at` en `ends_at` (ends_at = starts_at + 2 uur; hoogstens 16 uur en ná starts_at, anders faalt een andere CHECK).

Asserts, met `plan(28)`:
1. `has_function('public','db_usage', array[]::name[], …)`
2. `is_definer('public','db_usage', array[]::name[], …)`
3. `function_privs_are(… 'db_usage' … 'anon', '{}')`
4. idem voor `authenticated`, `'{}'`
5. idem voor `service_role`, `array['EXECUTE']`
6. als `anon`: `throws_ok('select public.db_usage()', '42501', …)`
7. als `authenticated` (claims A): `throws_ok(…, '42501', …)`
8. als `service_role`: `lives_ok('select public.db_usage()', …)`
9. `set_eq($$select k from jsonb_object_keys(public.db_usage()->'tables') k$$, <de 14 namen>, …)`
10. `ok((public.db_usage()->>'database_bytes')::bigint > 0, …)`
11. `is((public.db_usage()->'tables'->>'spots')::bigint, (select count(*) from public.spots), …)`
12. `has_trigger('public','push_subscriptions','push_subscriptions_limit', …)`
13. `function_privs_are(… 'push_subscriptions_limit' … 'authenticated', '{}')`
14. als A: `lives_ok` van een insert van 20 rijen (`'https://fcm.googleapis.com/fcm/send/a' || g` uit `generate_series(1,20)`, `p256dh 'AAAA'`, `auth 'aaaa'`)
15. als A: `throws_ok` van het 21e abonnement, met `'PT400', 'too_many_subscriptions'`
16. als A: `lives_ok` van het verwijderen van `…/a1`
17. als A: `lives_ok` van het 21e na dat verwijderen
18. als B: `lives_ok` van een insert (`…/b1`): de grens geldt per gebruiker
19. `has_trigger('public','sessions','sessions_starts_at_horizon', …)`
20. `function_privs_are('public','sessions_starts_at_horizon', array[]::name[], 'authenticated', '{}', …)`
21. `isnt_definer('public','sessions_starts_at_horizon', array[]::name[], …)`
22. als postgres: `throws_ok` van `insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('d0000000-0000-4000-8000-000000000009', 'pgtap-horizon-0009', 'pgtap-spot', '1111…', 'Anna', now() + interval '371 days', now() + interval '371 days 2 hours')`, met `'23514', 'starts_at_too_far_ahead'`
23. als postgres: `lives_ok` van een insert met `id 'd0000000-0000-4000-8000-000000000001'`, slug `'pgtap-horizon-0001'`, organizer A, `starts_at = now() + interval '365 days'`, `ends_at = … + 2 hours` en `created_at = now() - interval '10 days'` (het bewerkgeval van review B-5)
24. als A (`set local role authenticated`, claims A): `lives_ok` van `update public.sessions set starts_at = now() + interval '369 days', ends_at = now() + interval '369 days 2 hours' where id = 'd0000000-…-000000000001'`
25. als postgres: `ok((select starts_at > now() + interval '368 days' from public.sessions where id = 'd0000000-…-000000000001'), …)`: de update van 24 is echt doorgevoerd (met de oude CHECK op `created_at + 370` zou dit `23514` geven)
26. als A: `throws_ok` van `update … set starts_at = now() + interval '371 days', ends_at = now() + interval '371 days 2 hours' where id = 'd0000000-…-000000000001'`, met `'23514', 'starts_at_too_far_ahead'`
27. Vóór dit assert, als postgres (geen assert): `alter table public.sessions disable trigger sessions_starts_at_horizon;` dan een insert met `id 'd0000000-0000-4000-8000-000000000002'`, slug `'pgtap-horizon-0002'`, organizer A, `starts_at = now() + interval '400 days'`, `ends_at = … + 2 hours`; dan `alter table public.sessions enable trigger sessions_starts_at_horizon;`. Assert als A: `lives_ok` van `update public.sessions set note = 'pgtap-legacy', starts_at = starts_at where id = 'd0000000-…-000000000002'` (E47b: `starts_at` in de SET-lijst maar ongewijzigd)
28. als A: `throws_ok` van `update public.sessions set starts_at = starts_at + interval '1 day', ends_at = ends_at + interval '1 day' where id = 'd0000000-…-000000000002'`, met `'23514', 'starts_at_too_far_ahead'`

Schrijf de verkorte id's (`1111…`, `d0000000-…-000000000001`) in het bestand voluit. Wissel van rol zoals in `05`/`07` (`set local role …`, `select set_config('request.jwt.claims', …, true)`, `reset role`). Het `alter table … disable/enable trigger` werkt als postgres (eigenaar van de tabel) en wordt door de `rollback` aan het eind ook teruggedraaid.

### AC-5
De builder draait `cd web && npm audit --omit=dev --audit-level=high` (exitcode 0) en legt de uitvoer vast in de PR-beschrijving. De verifier herhaalt het.

### AC-6 (`NEEDS_LARS`)
RUNBOOK §17 bevat de velden "Open-Meteo-bevestiging: datum … / uitkomst …" en "Gekozen SMTP-dienst: …", ingevuld met "nog in te vullen door Lars". Lars vult ze in en test een magic link naar een adres dat geen teamlid is:
1. eigen SMTP ingesteld, "Allow new users to sign up" nog uit;
2. de testgebruiker aangemaakt via Authentication, Add user, mét "Auto Confirm User" (A14);
3. in de app een inloglink aangevraagd: de mail komt aan;
4. de link in de mail wijst direct naar `https://<project-ref>.supabase.co/auth/v1/verify?…` en niet naar een redirect- of trackingdomein van de maildienst (review B-3). Controleer dat door de link te kopiëren in plaats van erop te klikken;
5. inloggen met die link lukt;
6. pas daarna "Allow new users to sign up" aan.

### AC-7
- `supabase test db` is groen, inclusief `07_sessions.test.sql` met de nieuwe regels 68 en 69 (review B-1). `01_schema` noemt de legacy-kolom niet meer in `columns_are(profiles)` en in de `set_eq`.
- `grep -rni "telegram" ingest/src web/src` geeft niets (ook nu al niet).
- `git diff origin/develop -- supabase/migrations/2026101509* supabase/migrations/20261015150000* supabase/migrations/20261015180000* supabase/migrations/20261015200000*` is leeg.
- Web: `schema-columns.test.ts` is groen met de aangepaste guard.

### Gevolgen-punten (geen AC, wel getest)
- **Push:**
  - `test_push_allowlist.py`: tabel van `endpoint_allowed` (E15–E19 en E52, plus geldige endpoints voor FCM, Chrome-staging `jmt17.google.com/fcm/send/…`, Mozilla `updates.push.services.mozilla.com/wpush/v2/…`, Apple `web.push.apple.com/…` en WNS `wns2-par02p.notify.windows.com/w/?token=…`);
  - `load_all_targets_checked` met 1 geblokkeerde en 1 geldige rij geeft `blocked == 1`, en de logregel bevat geen endpoint;
  - `load_targets` filtert;
  - `test_notify_webpush.py`: geblokkeerde host geeft `DeliveryResult(False, False, "blocked host", retryable=False)` zonder aanroep van `webpush_fn`. Status 400, 403 en 413 → `retryable=False`; 429, 500 en 503 → `True`; `ConnectTimeout` → `True`; `RuntimeError` → `False`; `WebPushException` zonder response → `True`; `ValueError` uit de payload → `False`.
  - `test_job_push.py`: `deliver_event` met één 403 (`retryable=False`) geeft `retryable is False` en `non_retryable == 1`; met één 503 `retryable is True` en `non_retryable == 0`; met 403 + 503 op twee doelen `retryable is True` en `non_retryable == 1`.
  - `test_job_alerts.py` of `test_job_alerts_push.py`: `deliver_plan` geeft `non_retryable` door, ook bij `deferred=True`.
  - `test_job_alerts_push.py`: `test_non_retryable_4xx_is_stored` (E21: state opgeslagen, `deferred == 0`, `failed == 1`, `push_non_retryable == 1`, abonnement bestaat nog) en `test_blocked_host_is_no_target` (E20).
  - `test_pipeline.py::test_non_retryable_push_is_partial_with_warning` (review B-2): een pipeline-run waarin de `FakeNotifier` voor het enige abonnement een niet-herhaalbaar resultaat geeft (`DeliveryResult(False, False, "HTTP 403", retryable=False)`): stap `alerts` is `partial`, `counts["push_non_retryable"] == 1`, `counts["push_failures"] == {"HTTP 403": 1}`, `counts["deferred"] == 0`, en de annotaties bevatten `"::warning::alerts: 1 push delivery(ies) failed without retry; the alert is lost for that device (see push_failures in ingest_runs)"`. De exitcode is 0.
  - `test_cli_push.py`: de verwachte regels op r. 79 en 95 worden `"push: sent=1 failed=0 no_target=0 deferred=0 non_retryable=0 removed=0"` en `"push: sent=0 failed=1 no_target=0 deferred=1 non_retryable=0 removed=0"`. Nieuwe test: met een niet-herhaalbare fout `"push: sent=0 failed=1 no_target=0 deferred=0 non_retryable=1 removed=0"`, `alerts: failed` en exitcode 1.
- **Veroudering:**
  - `test_job_inputs.py`: E24–E26 en `stale`; zonder `max_fetch_age` blijft het gedrag gelijk;
  - `test_job_evaluate.py`: E25 (geen upsert voor die spot, `stale == ("test-strand",)`, oude evaluatierijen bestaan nog);
  - `test_job_alerts.py`: favoriet met rijen van 4 uur oud → `ineligible`, geen schrijfactie op `alert_state`;
  - `test_pipeline.py::test_per_spot_staleness_with_two_spots` (E27).
- **Runbudget:** `test_pipeline.py::test_run_time_budget_skips_remaining_steps` (E28). Monkeypatch `pipeline._monotonic` op een klok die een eigen stap na `evaluate` 601 s laat vooruitzetten; gebruik `steps=` met een eigen lijst.
- **Jobs-usage** (`test_job_usage.py`):
  - `read_open_meteo_usage` over de bronnen en de maandgrens (E51), zonder `rws`;
  - `read_db_usage` met een ongeldige vorm geeft `ValueError`;
  - `read_run_history` (statussen, `step_issues`, `push_sent` en `push_failed`, kapotte stappen overgeslagen);
  - `resolve_operator` (hoofdletters, accolades, leeg, ongeldig);
  - `deliver_operator_push` voor alle zes de statussen, plus de `DatabaseError` bij het laden;
  - `run_usage_report` voor E29–E43, met een recorder op `db.writes` voor E29 (geen writes);
  - `earlier_usage_counts` slaat de huidige run over (`lt.now`).
- **Overig:**
  - `test_fakes.py`: de fake-`db_usage` geeft de tabellen van `TABLE_KEYS` met hun aantallen en `database_bytes`;
  - `test_migrations.py::test_db_usage_counts_every_table`: in `20261015220100_hardening.sql` levert de regex `'(\w+)', \(select count\(\*\) from public\.(\w+)\)` paren met naam == tabel, en de set is gelijk aan `set(TABLE_KEYS)`;
  - `test_cli_usage.py`: met `runtime.open_db` gepatcht naar een `FakeSupabase` toont `usage show` de rapportregels met exit 0; `db_usage` met een fout geeft een regel `error   db_usage: …` en exit 1; zonder configuratie exit 1;
  - `test_config.py` en `test_logsetup.py`: `OPERATOR_USER_ID` wordt gelezen; `secret_values` bevat de gestripte waarde; met `"{AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA}"` bevat hij ook `"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"`; met een canonieke waarde staat die er één keer in; met `"not-a-uuid-12345"` alleen de ruwe waarde, zonder exception (E55);
  - `test_repo_hygiene.py`: `ENV_KEYS` krijgt `OPERATOR_USER_ID` erbij (waarde leeg). `test_actions_pinned_to_commit_sha`: elke `uses:` in `.github/workflows/*.yml` matcht `^[\w.-]+/[\w.-]+@[0-9a-f]{40}$`;
  - `test_hourly_workflow.py`: de verwachte env en `test_only_known_secrets` krijgen `OPERATOR_USER_ID` erbij.
- **Web:**
  - `auth.test.ts` en `login.test.ts` verwachten `shouldCreateUser: true`;
  - `authErrorMessage({ code: 'signup_disabled' })` geeft `notAuthorized`;
  - de guard in `schema-columns.test.ts` (zie Bestanden).

## Externe afhankelijkheden

Er komen geen nieuwe packages bij, en geen nieuwe externe endpoints die de ingest aanroept.

Gecontroleerd op 15 oktober 2026:

| Onderwerp | Bevinding | Bron |
|---|---|---|
| pywebpush `webpush()` | Signatuur met `timeout: None \| float` en `requests_session`. De timeout gaat naar `requests.post(endpoint, timeout=timeout, …)`. Een fout geeft `WebPushException(response=…)`; requests-fouten worden niet opgevangen. De synchrone weg gebruikt requests. | https://raw.githubusercontent.com/web-push-libs/pywebpush/main/pywebpush/__init__.py |
| requests-uitzonderingen | `class RequestException(IOError)`; `ConnectionError`, `Timeout`, `ConnectTimeout` en `ReadTimeout` erven daarvan. Basis voor `except OSError` → herhaalbaar. | https://raw.githubusercontent.com/psf/requests/main/src/requests/exceptions.py |
| Apple Web Push | "allow URLs from `*.push.apple.com` if you are in control of your server push endpoints"; iOS/iPadOS 16.4, alleen voor apps op het beginscherm | https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ |
| Mozilla autopush | Productie-endpoint `https://updates.push.services.mozilla.com/wpush/…`. De URL is "opaque", en Mozilla mag hem wijzigen. | https://autopush.readthedocs.io/en/latest/http.html |
| Microsoft WNS | Het kanaal-URI moet het domein `notify.windows.com` gebruiken; "never push notifications to a channel on any other domain". Edge gebruikt subdomeinen zoals `*.notify.windows.com`. | https://docs.microsoft.com/en-us/windows/uwp/controls-and-patterns/tiles-and-notifications-windows-push-notification-services--wns--overview |
| Chrome/FCM | Endpoints `https://fcm.googleapis.com/fcm/send/…`. Alleen bevestigd via voorbeelden in de praktijk, niet via een Google-pagina. Daarom wordt geblokkeerd verkeer geteld en zichtbaar gemaakt (R2). | (zie R2) |
| Chrome-staging `jmt17.google.com` (review B-4) | "Chrome on every channel but Stable subscribes at `https://jmt17.google.com/fcm/send/…`, Chromium's FCM staging endpoint", met verwijzing naar `chrome/browser/push_messaging/push_messaging_constants.cc` en `push_messaging_utils.cc` in Chromium. De Chromium-bestanden zelf kon ik niet ophalen (Gitiles en GitHub-mirror gaven 404 voor de raw-weergave); de bron is de PR die de reviewer ook noemt. Andere Google-hosts dan `fcm.googleapis.com` en `jmt17.google.com` worden daar niet genoemd. | https://github.com/Significant-Gravitas/AutoGPT/pull/15356 |
| Supabase Auth rate limits | Instelbaar onder Authentication > Rate Limits. E-mails: 2 per uur met de ingebouwde provider, en instelbaar met eigen SMTP. Sign-ups/sign-ins: 30 per 5 minuten per IP. OTP: 60 s per gebruiker. Verificaties: 30 per 5 minuten. Tokens: 150 per 5 minuten. Een overschrijding geeft 429. | https://supabase.com/docs/guides/auth/rate-limits |
| Supabase eigen SMTP | Velden: host, poort, gebruiker, wachtwoord, afzenderadres, afzendernaam. Na het inschakelen geldt eerst een "low rate-limit of 30 messages per hour". Een eigen domein met DKIM, DMARC en SPF wordt aangeraden. Genoemde diensten: Resend, AWS SES, Postmark, Twilio SendGrid, ZeptoMail, Brevo. | https://supabase.com/docs/guides/auth/auth-smtp |
| Supabase e-mailtemplates | `{{ .ConfirmationURL }}` = `https://project-ref.supabase.co/auth/v1/verify?token=…&type=…&redirect_to=…`. Linkscanners kunnen het token verbruiken ("Token has expired or is invalid"). "disable email tracking features with external providers, as they can overwrite Supabase links". | https://supabase.com/docs/guides/auth/auth-email-templates |
| Resend | Gratis: 3.000 per maand, "limited to 100 emails per day", 3 domeinen. "Open and click tracking is disabled by default for all domains"; tracking werkt alleen als het per domein aan staat én een trackingsubdomein geverifieerd is. "You must add and verify at least one domain to send emails with Resend." SMTP: `smtp.resend.com`, poorten 25, 465, 587, 2465, 2587, gebruiker `resend`, wachtwoord = API-sleutel; vereist een geverifieerd domein. API-sleutelpermissie `sending_access`: "Can only send emails." | https://resend.com/pricing, https://resend.com/docs/dashboard/domains/tracking, https://resend.com/docs/dashboard/domains/introduction, https://resend.com/docs/send-with-smtp, https://resend.com/docs/api-reference/api-keys/create-api-key |
| Postmark | Gratis (Developer): "100 emails/month", verloopt niet, geen overages. Links: default "None - No links will be replaced or tracked. This is the default setting for all messages and new and existing servers"; per bericht via SMTP-header `X-PM-TrackLinks`. Opens: "The default value of `TrackOpens` is `false`", maar een serverinstelling "Open tracking" aan overschrijft dat. Sender signature: "it needs to be a private domain that you have access to" (geen Gmail/Yahoo). Vóór handmatige goedkeuring van het account alleen mail naar de eigen geverifieerde domeinen. SMTP `smtp.postmarkapp.com`, poorten 25, 2525, 587. | https://postmarkapp.com/pricing, https://postmarkapp.com/developer/user-guide/tracking-links, https://postmarkapp.com/developer/user-guide/tracking-opens/tracking-opens-per-email, https://postmarkapp.com/developer/user-guide/managing-your-account/managing-sender-signatures, https://postmarkapp.com/support/article/1084-how-does-the-account-approval-process-work, https://postmarkapp.com/developer/user-guide/send-email-with-smtp |
| Gmail SMTP | Server `smtp.gmail.com`, "For SSL, enter 465. For TLS, enter 587", met volledig adres en app-wachtwoord (pagina voor Workspace; dezelfde server geldt voor gewone accounts). App-wachtwoorden: "can only be used with accounts that have 2-Step Verification turned on"; "aren't recommended and are unnecessary in most cases". Limiet persoonlijk account: meer dan 500 e-mails per dag geeft een blokkade van 1 tot 24 uur. | https://knowledge.workspace.google.com/admin/gmail/send-email-from-a-printer-scanner-or-app, https://support.google.com/accounts/answer/185833, https://support.google.com/mail/answer/22839 |
| Brevo (afgewezen) | Brevo-medewerker op het eigen forum: "Disabling tracking is not planned (at least not yet), for security reasons. EDIT: Disabling tracking will be available, upon request and to our Enterprise plans." | https://community.brevo.com/t/no-way-to-disable-by-option-tracking-in-transactional-e-mail/201 |
| SMTP2GO (niet voorgesteld) | Gratis 1.000 per maand, 200 per dag, 25 per uur tot het domein geverifieerd is. Het standaardgedrag van tracking staat niet in die bron; alleen in reviews van derden. | https://www.smtp2go.com/blog/know-your-sending-limits/ |
| MapTiler (maandcheck, review B-6) | Met MapLibre GL JS (geen MapTiler-SDK) rekent MapTiler in API-requests: 100.000 per maand gratis, alleen tiles tellen. Map sessions gelden alleen voor de MapTiler-SDK en de Leaflet-plugin, dus niet voor Shakka. Overgenomen uit WORK_PACKAGES ("Gecontroleerde externe documentatie") en de blueprint van WP-15. | https://www.maptiler.com/cloud/pricing/, https://docs.maptiler.com/guides/maps-apis/maps-platform/tile-requests-and-map-sessions-compared/ |
| Supabase-foutcodes | `signup_disabled`: "Sign ups (new account creation) are disabled on the server."; `otp_disabled`; `email_address_not_authorized` | https://supabase.com/docs/guides/auth/debugging/error-codes |
| GoTrue | Bij een onbekende gebruiker met `CreateUser=false` volgt `ErrorCodeOTPDisabled` ("Signups not allowed for otp"). Met `CreateUser=true` doet `MagicLink` een `Signup()`, en dat geeft bij `config.DisableSignup` `ErrorCodeSignupDisabled`. | https://raw.githubusercontent.com/supabase/auth/master/internal/api/otp.go, …/magic_link.go, …/signup.go |
| Supabase "Allow new users to sign up" | "If this config is disabled, only existing users can sign in." | https://supabase.com/docs/guides/auth/general-configuration |
| Supabase databasegrootte | Aanbevolen query: `sum(pg_database_size(pg_database.datname)) from pg_database`. Boven 500 MB gaat een Free-project in read-only. | https://supabase.com/docs/guides/platform/database-size |
| Open-Meteo-voorwaarden | Niet-commercieel = "private or non-profit websites or apps that do not have subscriptions or advertising". Limieten: 600 per minuut, 5.000 per uur, 10.000 per dag, 300.000 per maand. Contact: info@open-meteo.com. | https://open-meteo.com/en/terms |
| pip-audit | `pip-audit --require-hashes -r <file>`; `--disable-pip` mag bij gehashte requirements; exitcode 1 bij bevindingen | https://raw.githubusercontent.com/pypa/pip-audit/main/README.md |
| uv export | `uv export --format requirements-txt --frozen --no-emit-project -o <file>` (standaard met hashes) | https://docs.astral.sh/uv/reference/cli/ |
| npm audit | `--omit=dev` laat dev-dependencies weg; `--audit-level` bepaalt vanaf welke ernst de exitcode niet 0 is | https://raw.githubusercontent.com/npm/cli/latest/docs/lib/content/commands/npm-audit.md |
| GitHub Actions-SHA's | `actions/checkout` v7.0.1 = `3d3c42e5aac5ba805825da76410c181273ba90b1`; `actions/setup-node` v7.1.0 = `949feb2413d6458794dcd2491c4babbbce0c15c1`. **De builder controleert deze vóór gebruik** met `gh api repos/actions/checkout/git/ref/tags/v7.0.1 --jq .object.sha` en `gh api repos/actions/setup-node/git/ref/tags/v7.1.0 --jq .object.sha` (een `object.type` "tag" vergt nog één dereferentie via `gh api repos/<repo>/git/tags/<sha> --jq .object.sha`). Wijken ze af, gebruik dan de uitkomst van `gh` en noteer dat in `deviations.md`. | https://api.github.com/repos/actions/checkout/releases/latest, https://api.github.com/repos/actions/setup-node/releases/latest |

## Risico's

- **R1. Langere runs door retries.** In het slechtste geval kost één Open-Meteo-chunk 3 × 30 + 3 s, een RWS-station 93 s en een DB-aanroep 3 × 30 + 1,5 s. De stroomonderbreker (A7), het getijbudget (240 s) en het runbudget (600 s, A12) houden de run onder de job-timeout van 900 s. Eén stap die na de budgetcheck start, kan nog uitlopen; dat accepteren we. Bij een trage ingest is het juist `alerts` die wordt overgeslagen (A12, review N-11). Herhaalde `update`/`delete` kunnen tellers te laag laten uitvallen (A6, review N-4).
- **R2. Allowlist te streng.** Verandert een push-service van host (Mozilla behoudt zich dat voor), dan krijgen die gebruikers geen meldingen meer. Zichtbaar via `blocked_targets`, een `::warning::` per run en de logregel. Herstel: een host toevoegen aan `PUSH_SERVICE_HOSTS` of de suffixen (een codewijziging en een release).
- **R3. Een tijdelijke 403 gaat verloren** (bijvoorbeeld klokverschil bij de VAPID-JWT). Dat event komt dan niet aan. Volgende events wel; het abonnement blijft. Zichtbaar via `push_non_retryable`, de warning en de `partial` stap (A8).
- **R3a. Verkeerde `PUBLIC_VAPID_PUBLIC_KEY` in de PWA** (WP-17 R1). Elke aflevering geeft 403; alle alerts gaan verloren zolang de fout bestaat, in plaats van uitgesteld te worden. Zichtbaar in elke run (warning, `partial`, `push_failures {"HTTP 403": n}`) en in het weekrapport. Herstel: RUNBOOK §14.10 (sleutels gelijk zetten, abonnementen opnieuw aanmaken).
- **R4. Open aanmelden.** Wie zich aanmeldt maar nooit klikt, laat een rij achter in `auth.users`/`profiles`. Misbruik wordt begrensd door de Auth-rate-limits (30 per 5 minuten per IP, e-mails per uur) en de daglimiet van de SMTP-dienst. De groei is zichtbaar in het weekrapport (`profiles`). Opruimen hoort bij WP-23 (privacy).
- **R5. Volgorde van deploy.** Na de merge naar `develop` draait de nieuwe `auth.ts` op de Cloudflare-preview, en na de promotie naar `main` in productie. Staat "Allow new users to sign up" dan nog aan zonder eigen SMTP, dan kunnen onbekende adressen een account aanmaken. De standaard-SMTP mailt alleen aan teamleden, maar de rij in `auth.users` ontstaat mogelijk wel. Mitigatie: Lars zet de instelling uit vóór de merge (Nodig van Lars, punt 1, een harde poort). Dat kan nu al: met `shouldCreateUser: false` verandert er niets. Omdat de client-vlag nooit een beveiligingsgrens was, controleert Lars de instelling direct, los van deze WP (A14).
- **R6. `db_usage` wijkt af van het dashboard.** De som over databases met `CONNECT`-recht kan een interne database missen. De drempel van 300 MB laat ruim marge tot 500 MB. Lars vergelijkt bij de eerste maandcheck.
- **R7. Weekrapport gemist** als alle maandagruns tussen 08:00 en 22:00 falen (A3). Een gefaalde run geeft al een mail van GitHub.
- **R8. Verouderde SHA-pins.** Zonder Dependabot moet Lars de actions zelf bijwerken (maandcheck). Een oude actie blijft werken; het risico is alleen dat beveiligingsfixes uitblijven.
- **R9. `npm audit` faalt op een advisory zonder fix** (AC-5). Dan stopt de builder en schrijft hij een `deviations.md` (geen `--force`, geen ongeteste major-upgrade).
- **R10. Samenloop met WP-23 (review N-3).**
  - Bestanden die beide raken: `supabase/tests/07_sessions.test.sql` (regels 67–69; eindvorm in Interfaces), `docs/RUNBOOK.md`, `ci.yml` en mogelijk `package-lock.json`. Dat zijn additieve wijzigingen; houd bij een conflict beide kanten aan. Bij `package-lock.json`: opnieuw `npm install` op de gemergde `package.json`.
  - pgTAP: WP-23 heeft `09_delete_my_account.test.sql`, WP-22 `10_hardening.test.sql`. Geen botsing.
  - RUNBOOK: de nieuwe sectie krijgt het eerstvolgende vrije nummer bij de merge. Merget WP-22 eerst, dan is het §17 en wordt die van WP-23 §18 (zoals WP-23 zelf vastlegt). Merget WP-23 eerst, dan wordt die van WP-22 §18; de builder past dan alle verwijzingen in deze WP (§11.2, §11.5, §14.7, §14.14, de sectie zelf) aan.
  - Migraties: die van WP-23 (`20261016090000`) heeft een latere tijdstempel dan die van WP-22 (`20261015220000`, `20261015220100`). Staat die van WP-23 al op het remote project, dan heeft de push van WP-22 `supabase db push --include-all` nodig (RUNBOOK §17.5).
  - `docs/PRIVACY.md` (van WP-23): na de verwijdering van de legacy-kolom klopt de bijzin in de rij "Profiel" niet meer. Wie als tweede merget, haalt hem weg (stap 13).
- **R12. Een eigen domein kost geld.** Resend en Postmark vereisen een domein; registratie is een jaarlijkse uitgave. Dat botst met "€0 per maand, geen betaalde dienst zonder akkoord van Lars". Daarom staat er een voorstel zonder domein naast (Gmail, A15). Lars beslist.
- **R13. Gmail als SMTP-dienst** (als Lars die kiest): Google kan app-wachtwoorden beperken of het account blokkeren bij verdacht verkeer. Dan komen er geen inloglinks meer; bestaande sessies blijven werken. Zichtbaar doordat inloggen faalt; herstel is een andere dienst kiezen (A15).
- **R14. Linkscanners** van maildiensten of virusscanners kunnen een magic link openen en het token verbruiken. Dat staat los van tracking en bestond al. De test in AC-6 controleert dat de link direct naar Supabase wijst. Inloggen met een code (in plaats van een link) blijft buiten scope.
- **R15. `alter table … disable trigger` in de pgTAP-test** vereist dat `postgres` eigenaar is van `public.sessions`. Dat is zo als de migraties lokaal als `postgres` draaien (`supabase db reset`). Faalt het toch (`42501 must be owner`), dan gebruikt de builder deze terugvaloptie: rij `…0002` wordt zonder `disable trigger` ingevoegd met `starts_at = now() + interval '369 days'`; assert 27 blijft (`note` bijwerken met `starts_at = starts_at`); assert 28 zet `starts_at = starts_at + interval '2 days'` (dus 371 dagen) en verwacht `23514`. Hij noteert dat in `deviations.md`. Die variant toetst de "ongewijzigd"-tak minder scherp, maar het aantal asserts blijft 28.
- **R11. Push buiten het venster.** Waarschuwingen tussen 22:00 en 08:00 wachten tot 08:17. Voor database- en budgetdrempels is dat ruim op tijd (de guard stopt bij 80%).

## Buiten scope

| Punt (bron) | Reden |
|---|---|
| Kolom `fetched_at` in `evaluations` en een UI-wijziging (WP-14 R3) | Opgelost in de backend met A11, zonder schema- of UI-wijziging. |
| Moderatie-RPC voor de organisator (WP-19 N-7, WP-21 R6, review N-10) | Staat niet in de WP-22-sectie. WP-23 zet hem onder "WP-22", WP-22 niet: zonder vastlegging valt hij tussen wal en schip. **Open punt voor de orchestrator:** voorstel een aparte WP-25 (RPC plus UI op de sessiepagina voor de organisator), niet nu. Tot dan geldt RUNBOOK §16.5 (SQL-editor). |
| Dubbele `browserStorage` (WP-20/21) | Frontend-opruiming; WP-21 noemt "uiterlijk WP-23". |
| Inputs delen tussen evaluatie- en alertjob (WP-10 R5, WP-11 A8) | De egress (≈ 2 GB van 5 GB) past. Bewaking via de maandcheck, met een actiedrempel bij 3,5 GB. |
| `profiles` zonder filter in de uurlijkse run (WP-10) | Bij 1.000 gebruikers ≈ 70 MB egress per maand. Paginering dekt de correctheid al (WP-10 review N-4). Opnieuw bekijken boven 500 gebruikers. |
| Evaluatie per favoriet cachen (WP-10 R7) | Alleen CPU in GitHub Actions, geen kosten. |
| `cell_selection` of model per spot (WP-03, WP-12) | Werk aan spotdata dat de verificatie van Lars vergt; er is nog geen geval. |
| `api_usage` voor RWS (WP-04 A7) | RWS publiceert geen limiet; er valt niets te bewaken. |
| Gedeelde `requests.Session` voor push (WP-17 R3) | Alleen performance op schaal; het runbudget dekt de looptijd. |
| Inloggen met een code (WP-13 A6, WP-18) | Vergt een UI en een e-mailtemplate; kan na eigen SMTP in een volgende WP. Het zou ook R14 (linkscanners) oplossen. |
| Een eigen domein registreren | Betaald; alleen met akkoord van Lars (R12). |
| De regel "De maildienst" op `/privacy` en in `docs/PRIVACY.md` | Hangt af van de keuze van Lars (A15). Vervolgactie zodra die keuze er is (Nodig van Lars, punt 4). |
| "Ik ga" voor uitgelogde crew (WP-20 A16) | Een UI-besluit. |
| E-mail als alertkanaal (voorstel WP-24) | Nog niet besloten; alertkanalen blijven ongemoeid. |
| CAPTCHA, IP-limieten | Een script van derden in de browser (privacy, CSP), en de gratis tier heeft geen per-IP-limiet op PostgREST. |
| Onbevestigde Auth-gebruikers opruimen | Privacy-inventaris en bewaartermijnen horen bij WP-23. |
| Directe melding bij een `partial` die blijft hangen (WP-11 R4, WP-12 A15) | Het weekrapport toont de stappen die niet `ok` waren, en een gefaalde run mailt al. |
| `least(p_now, now())` in de purge (WP-19 N-10) | Geen bekend probleem, en het zou `test_session_retention_matches_migration` breken. |
| `npm audit` als CI-stap, Dependabot, `uv audit` | Zie A17. De details van `uv audit` konden niet worden geverifieerd. |
| Betaalde monitoring, de Management API van Supabase voor egress | Kosten; het access token blijft bij Lars. Egress gaat via de maandcheck. |
| Wijzigingen aan `shakka doctor` | Niet nodig; `OPERATOR_USER_ID` is optioneel. |

## Stappenplan voor de builder

Werk op branch `wp/WP-22` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-22`. Lees of print `.env` nooit. Na elke stap, vanuit `ingest/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`. Na stap 8 ook `supabase test db` vanuit de root (met lokale stack; zonder Docker komt het bewijs uit de CI-job `db`). Na stap 8 en 11 vanuit `web/`: `npm run check && npm test && npm run build`. Eén commit per stap, commitberichten in het Engels.

1. **Retry-helper.** Breid `shakka/http.py` uit (Interfaces) en voeg in `conftest.py` de fixture `_no_retry_sleep` toe. Schrijf eerst de `with_retries`-tests en de twee AC-1-tests in `test_http.py`, dan de implementatie. Commit: `WP-22: add with_retries helper`.
2. **Open-Meteo.** Laat `request_json` intern via `with_retries` lopen. `test_openmeteo_client.py`, `test_openmeteo_forecast.py`, `test_openmeteo_marine.py`, `test_job_forecast.py` en `test_job_marine.py` moeten ongewijzigd groen blijven.
3. **RWS.** Retries in `_post_json` (A6) en nieuwe tests in `test_rws_tides.py`.
4. **Supabase REST.** Retries, stroomonderbreker en logging in `SupabaseRest`, met nieuwe tests in `test_db.py`. Bestaande tests moeten groen blijven; een test die van één request uitging bij een herhaalbare fout, krijgt het juiste aantal.
5. **Push-hardening.**
   - `notify/base.py`: `retryable`, allowlist, `send_payload` in het Protocol.
   - `notify/webpush.py` en `jobs/push.py`: `TargetsLoad`, de filtering en `EventDelivery.non_retryable`.
   - `jobs/alerts.py`: `blocked_targets`, `PlanDelivery.non_retryable`, `push_non_retryable`, logregel en CLI; in `pipeline.py` `alert_counts`, `non_retryable_warning`, de warnings en `partial` (A8, review B-2). `test_cli_push.py` mee aanpassen.
   - `push_fixtures.py`: het fcm-endpoint, `FakeResponse` en `FakeNotifier.send_payload`.
   - Vervang `push.example.test` in `test_job_push.py:110`, `test_pipeline.py:772` en `test_notify_webpush.py:286` door `fcm.googleapis.com/fcm`.
   - Voeg `test_push_allowlist.py` toe en pas de tests aan uit Testplan, "Gevolgen-punten, Push".
6. **Veroudering per spot.** `jobs/inputs.py`, `jobs/evaluate.py`, `jobs/alerts.py` met hun tests (E24–E27).
7. **Runbudget.** `pipeline.py` (`RUN_TIME_BUDGET_S`, `_run`, `exit_code_for`, `build_annotations`) en `test_run_time_budget_skips_remaining_steps`.
8. **Database.**
   - De twee migraties (let op de twee statische tests, zie Interfaces).
   - pgTAP: `01`, `02` en `04` aanpassen; `07_sessions.test.sql` regels 68 en 69 (review B-1; staat `supabase/tests/09_delete_my_account.test.sql` van WP-23 al in de werkboom, schrijf dan direct de eindvorm met `delete_my_account` uit Interfaces); `10_hardening.test.sql` toevoegen.
   - In `fakes.py` de ingebouwde RPC `db_usage` (importeer `DB_USAGE_RPC` uit `shakka.jobs.usage`; maak in deze stap `jobs/usage.py` aan met alleen die constante) en `self.database_bytes = 50 * 1024 * 1024`.
   - Test in `test_fakes.py`, plus `test_migrations.py::test_db_usage_counts_every_table`.
   - Web: de guard in `schema-columns.test.ts`.
   - Controleer `supabase test db` (alle bestanden groen, `plan`-aantallen kloppen).
9. **Domein van het gebruiksrapport (tests eerst).** Schrijf `tests/test_usage.py` volgens AC-2, met de golden-teksten letterlijk zoals hierboven, en daarna `domain/usage.py`. Wijkt een golden-tekst af door een telfout in deze blueprint, dan geldt de regel uit "Interfaces en contracten" en noteer je het in `deviations.md`.
10. **Jobs, pipeline en CLI van het gebruiksrapport.**
    - `config.py`, `logsetup.py`, `.env.example`, `hourly.yml` (env) en de tests daarvan (`test_config`, `test_logsetup`, `test_repo_hygiene::ENV_KEYS`, `test_hourly_workflow`).
    - `jobs/usage.py` volledig, met `test_job_usage.py`.
    - `step_usage_report` en `usage_counts` in `pipeline.py` (`STEPS`, `STEP_NAMES`, docstring), met `test_pipeline_usage.py` (AC-3) en de aanpassingen in `test_pipeline.py`.
    - `cli.py` (`usage show`), met `test_cli_usage.py`.
11. **Web-auth.** `auth.ts`, `auth.test.ts`, `login.test.ts`.
12. **Dependency-audit.**
    1. Controleer de SHA's (Externe afhankelijkheden) met `gh api` en vervang in `ci.yml` en `hourly.yml` elke `uses: actions/checkout@v7` door `uses: actions/checkout@<sha> # v7.0.1`, en `actions/setup-node@v7` door `@<sha> # v7.1.0`. Voeg `test_actions_pinned_to_commit_sha` toe.
    2. `cd web && npm audit --omit=dev --audit-level=high`. Faalt het, los het dan op met een minimale update (`npm update <pakket>` of `npm audit fix --omit=dev`, nooit `--force`). Draai `npm run check && npm test && npm run build` opnieuw. Lukt dat niet zonder een major-upgrade, stop dan en schrijf `deviations.md`.
    3. `cd ingest && uv export --format requirements-txt --frozen --no-emit-project -o /tmp/shakka-req.txt && uvx pip-audit --require-hashes --disable-pip -r /tmp/shakka-req.txt`. Bij een bevinding: `uv lock --upgrade-package <pakket>` binnen de bestaande grenzen in `pyproject.toml`, dan de volledige test. Kan het alleen buiten de grenzen, stop dan en schrijf `deviations.md`.
    4. Zet beide uitkomsten (geen geheimen) in de PR-beschrijving.
13. **Documentatie.**
    - **`docs/RUNBOOK.md`:**
      - §4: rij `OPERATOR_USER_ID | .env, GitHub Secret | ingest: push-abonnementen van Lars voor het gebruiksrapport | WP-22`.
      - §11.2: inloggen werkt voor bestaande gebruikers; aanmelden hangt af van "Allow new users to sign up" (§17.6).
      - §11.5: de standaard-SMTP-beperking geldt tot eigen SMTP (§17.6).
      - §13.1: de stappenlijst met `usage_report`.
      - §13.6: exitcode 1 ook bij `run_time_budget`.
      - §14.7 (review B-2), nieuwe tekst van de tellers: `sent`, `failed`, `no_target`, `deferred`, `push_non_retryable`, `blocked_targets`, `removed`, `push_enabled` en `push_failures`. `deferred` alleen bij 429, 5xx en netwerkfouten: de state blijft staan en de volgende run probeert het opnieuw. 400/401/403/413 en andere 4xx (behalve 404/410/429) tellen in `push_non_retryable`: geen herhaling, het event is voor dat apparaat verloren, het abonnement blijft staan. Dan staat er `::warning::alerts: <n> push delivery(ies) failed without retry …` in de Actions-log en is de stap `partial`. Staat die warning in elke run en toont `push_failures` `HTTP 403`, controleer dan of `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare gelijk is aan `VAPID_PUBLIC_KEY` en volg punt 10. `blocked_targets`: zie §17.4.
      - §14.14: hoogstens 20 abonnementen per account in de database. Bij precies 20 geeft het opnieuw aanmelden van een bestaand apparaat een algemene foutmelding in plaats van "staat al aan" (E53); verwijder dan oude abonnementen in de SQL-editor (`delete from public.push_subscriptions where user_id = '<id>' and last_success_at is null;` of de oudste).
      - **Nieuwe sectie "Hardening en kostenbewaking (vanaf WP-22)"**, met het eerstvolgende vrije nummer (§17 als WP-23 nog niet gemerged is, anders §18; zie R10). Hieronder heet ze §17.
        1. **Gebruiksrapport en waarschuwingen.** Wat, wanneer (A3), waar (`ingest_runs`, stap `usage_report`, `counts.report`), drempels (A2), `shakka usage show`.
        2. **`OPERATOR_USER_ID` instellen.** Dashboard, Authentication, Users, UID kopiëren; `gh secret set OPERATOR_USER_ID` (plakken bij de prompt); `.env`; push aanzetten op de telefoon (§14.12).
        3. **Retries en budgetten.** Tabel A6 (met de opmerking over tellers na een herhaling), stroomonderbreker, runbudget 600 s en de afweging dat dan `alerts` wordt overgeslagen (A12), `run_time_budget`-annotatie, veroudering per spot en de begrenzing tot ongeveer 6 uur (A11).
        4. **Push.** Allowlist (A9, inclusief `jmt17.google.com` voor Chrome Beta/Dev/Canary) en wat te doen bij `blocked_targets` (host controleren, toevoegen aan `PUSH_SERVICE_HOSTS` of de suffixen, release); de grens van 20.
        5. **Migraties van WP-22.** `supabase db push` na de merge en vóór de promotie naar `main` (anders is `usage_report` elk uur `partial` door `PGRST202`). Staat de migratie van WP-23 (`20261016090000_…`) al op het remote project, gebruik dan `supabase db push --include-all`, omdat de migraties van WP-22 een eerdere tijdstempel hebben. Bij `PGRST202`: `notify pgrst, 'reload schema';`. De sessiegrens (A13) controleert bestaande rijen niet; een controlequery vooraf is niet nodig.
        6. **Eigen SMTP en aanmelden.**
           - Eerst, los van deze WP: controleer dat "Allow new users to sign up" (Dashboard, Authentication, de algemene instellingen; de docs linken naar `https://supabase.com/dashboard/project/_/auth`) uit staat (A14).
           - Eisen: gratis tier, open- en kliktracking aantoonbaar uit, geverifieerde afzender.
           - De tabel uit A15 met de onderzochte diensten, de voorkeur met de voorwaarde (met domein: Resend; zonder domein: een apart Gmail-account) en de waarschuwing dat een domein geld kost (akkoord van Lars). Brevo staat er als "afgewezen: tracking niet uit te zetten".
           - Instellen onder Authentication, SMTP Settings: host, poort, gebruiker, wachtwoord/sleutel, afzenderadres, afzendernaam "Shakka". Per voorgestelde dienst de waarden uit A15. Tracking bij de dienst niet aanzetten (Resend: niets aanzetten; Gmail: n.v.t.).
           - Test (AC-6): de zes stappen uit Testplan AC-6, met de controle dat de link direct naar `https://<project-ref>.supabase.co/auth/v1/verify?…` wijst.
           - Daarna "Allow new users to sign up" aanzetten.
           - Daarna "De maildienst" op `/privacy` en in `docs/PRIVACY.md` laten bijwerken (vervolgactie, een kleine wijziging met test).
           - Veld "Gekozen SMTP-dienst: nog in te vullen door Lars".
        7. **Rate limits van Supabase Auth.** Tabel met defaults en voorstellen (A16, "Emails sent per hour" = daglimiet van de dienst / 24, naar beneden afgerond), waar je ze instelt, en wat een 429 in de app betekent ("Te veel inlogpogingen").
        8. **Maandcheck (handmatig, eerste werkdag van de maand).** Tabel:

           | Dienst | Waar | Gratis grens | Actie bij |
           |---|---|---|---|
           | Supabase egress | Dashboard, Usage | 5 GB | > 3,5 GB |
           | Supabase database | Dashboard, Usage, en het weekrapport | 500 MB | > 300 MB |
           | Open-Meteo | Weekrapport | 10.000 per dag, 300.000 per maand | warning |
           | MapTiler | Cloud, Analytics (requests) | 100.000 requests per maand, alleen tiles | > 70.000 |
           | GitHub Actions | Actions-tab (publieke repo: minuten onbeperkt) | – | Schedule niet actief, of geen run in de laatste 2 uur |
           | Cloudflare Pages | Builds | 500 per maand | > 350 |
           | SMTP-dienst | Dashboard van de dienst | Resend 100 per dag en 3.000 per maand; Gmail 500 per dag | > 70% |
           | Dependencies | `npm audit` en `pip-audit` (punt 10) | – | high of critical |
           | Actions-pins | Releases van `actions/checkout` en `actions/setup-node` | – | Nieuwe release |

           Onder de tabel één zin: "MapTiler rekent Shakka in requests, omdat de kaart MapLibre GL JS gebruikt en niet de MapTiler-SDK; de grens van 5.000 map sessions uit het projectplan geldt alleen voor die SDK en is hier niet van toepassing." (review B-6)

        9. **Open-Meteo-bevestiging.** Een conceptmail aan info@open-meteo.com (Engels, kort: gratis publieke PWA zonder ads of abonnementen, server-side gecachet, ongeveer 40.000 calls per maand, met bronvermelding). Velden "Datum: nog in te vullen door Lars" en "Uitkomst: nog in te vullen door Lars".
        10. **Dependency-audit.** De commando's van stap 12, en hoe je een SHA-pin bijwerkt (`gh api …`, commentaar met de versie).
    - **`docs/WORK_PACKAGES.md`:** alleen de env-rij `OPERATOR_USER_ID` ("(bevestigd in WP-22)").
    - **`docs/PRIVACY.md`, alleen na merge WP-23:** bestaat het bestand in de werkboom, haal dan in de rij "Profiel" de bijzin "; plus een ongebruikte, altijd lege legacy-kolom die WP-22 verwijdert" weg (de rest van de rij blijft letterlijk staan). Laat de regel "Maildienst: Supabase (tot WP-22)" staan tot Lars een dienst kiest. Bestaat het bestand niet, dan doet de builder niets; WP-23 haalt de bijzin dan zelf weg als die als tweede merget (de orchestrator geeft dat door). `/privacy` (web) wijzigt niet in deze WP.
    - Commit: `docs(WP-22): runbook hardening and cost monitoring`.

**Nodig van Lars** (de orchestrator legt dit voor; dit is niet aan de builder):
1. **Harde poort, nu en in elk geval vóór de merge:** in Supabase Authentication controleren dat "Allow new users to sign up" uit staat, en zo niet, uitzetten (A14, R5, review N-2). Zonder deze bevestiging geen merge.
2. Na de merge en vóór de promotie naar `main`: `supabase db push` (met `--include-all` als de migratie van WP-23 al gepusht is, §17.5).
3. `OPERATOR_USER_ID` in `.env` en als GitHub Secret; push aan op de telefoon.
4. Een SMTP-dienst kiezen (A15: met domein Resend, zonder domein een apart Gmail-account; een domein kost geld en vergt dus zijn akkoord), instellen, de Auth-rate-limits instellen, de test met een magic link (AC-6: testgebruiker via Add user mét "Auto Confirm User", link wijst direct naar Supabase), en daarna aanmelden aanzetten. Daarna een kleine vervolgwijziging voor "De maildienst" op `/privacy` en in `docs/PRIVACY.md`.
5. De mail aan Open-Meteo, en datum en uitkomst invullen in §17.9 (AC-6).

**Open punten voor de orchestrator:**
- Moderatie-RPC voor organisatoren (review N-10): vastleggen als open punt, voorstel een aparte WP-25, niet nu.
- Samenloop met WP-23 (R10): wie als tweede merget, voegt `07_sessions.test.sql` regels 67–69 samen tot de eindvorm in Interfaces, kiest het volgende vrije RUNBOOK-nummer en haalt (als WP-23 tweede is) de legacy-bijzin uit `docs/PRIVACY.md`.
- De vervolgwijziging "De maildienst" na de SMTP-keuze van Lars.

## Verwerking review

Ronde 1 (CHANGES_REQUIRED). Per punt wat er is aangepast.

| Punt | Verwerking |
|---|---|
| **B-1** `07_sessions.test.sql` breekt door `db_usage` | Overgenomen. `07_sessions.test.sql` staat in Bestanden; de exacte nieuwe regels 68 (`('purge_expired_sessions'), ('db_usage')`) en 69 (lijst plus `('db_usage')`) staan in Interfaces, `plan(112)` blijft. De eindvorm na samenvoegen met WP-23 (`delete_my_account` in regels 67 en 69) staat erbij: wie als tweede merget, voegt beide samen; is WP-23 al in de werkboom, dan schrijft de builder direct de eindvorm (stap 8). Vastgelegd dat `push_subscriptions_limit` en `sessions_starts_at_horizon` (security invoker, geen `EXECUTE`) bewust in geen van de vier sets staan (Ontwerp, Interfaces). |
| **B-2** 401/403 worden stil | Overgenomen. Nieuwe teller `push_non_retryable` (`EventDelivery.non_retryable` → `PlanDelivery.non_retryable` → `AlertJobResult.push_non_retryable` → `alert_counts`). Bij > 0 een warning `non_retryable_warning(n)` en de stap `alerts` `partial` (A8, Interfaces Pipeline). CLI toont `non_retryable=` en geeft exitcode 1. Tests: `test_non_retryable_4xx_is_stored` uitgebreid, `test_non_retryable_push_is_partial_with_warning` met de annotatie, `test_job_push.py`, `test_cli_push.py`. RUNBOOK §14.7 herschreven (diagnose verkeerde `PUBLIC_VAPID_PUBLIC_KEY` via deze warning); R3a toegevoegd. WP-17 R1 is een afgesloten blueprint en wordt niet aangepast; RUNBOOK §14.7 is de actuele bron. |
| **B-3** Brevo kan tracking niet uitzetten | Overgenomen. Brevo afgewezen. Onderzocht en geverifieerd: Resend (tracking standaard uit, vereist domein), Postmark (opens en links standaard uit, maar 100 per maand, privédomein en goedkeuring vereist), Gmail via app-wachtwoord (geen tracking, geen domein, kanttekeningen), SMTP2GO (standaardtracking niet verifieerbaar). Voorkeur met voorwaarde: met domein Resend, zonder domein een apart Gmail-account; de keuze en het eventuele domein (kosten) liggen bij Lars (A15, R12, R13). De Supabase-instelling blijft provider-agnostisch. RUNBOOK-test toegevoegd: de link wijst direct naar `<project>.supabase.co/auth/v1/verify…` (AC-6, §17.6), met de Supabase-bron die tracking uitzetten aanraadt. A16 rekent het uurlimiet nu af van de daglimiet van de gekozen dienst. |
| **B-4** `jmt17.google.com` ontbreekt | Overgenomen. Exacte host in `PUSH_SERVICE_HOSTS`, rij in `test_push_allowlist.py`, E52, bron in Externe afhankelijkheden. Verder gezocht: geen andere Google-hosts genoemd; `android.googleapis.com` (legacy GCM) blijft bewust buiten de lijst (A9). |
| **B-5** CHECK botst met bewerken | Optie (a). De CHECK is vervangen door de trigger `sessions_starts_at_horizon` (`BEFORE INSERT OR UPDATE OF starts_at`, `starts_at <= now() + 370 dagen`, alleen als `starts_at` verandert, SQLSTATE `23514`). De UI-grens (vandaag + 365) valt daarbinnen; geen webwijziging. pgTAP-asserts voor het bewerkgeval (sessie 10 dagen oud, verzet naar 369 dagen: gaat goed; naar 371: `23514`) en voor een ongewijzigde `starts_at` op een oudere rij (asserts 22–28). De controlequery vóór `db push` is vervallen. |
| **B-6** MapTiler-sessies ontbreken | Volgens de beslissing van de orchestrator: de grens blijft 100.000 requests per maand (alleen tiles), met één zin in §17.8 dat map sessions alleen voor de MapTiler-SDK gelden en voor Shakka niet van toepassing zijn. Bron toegevoegd. |
| N-1 | A11 en "Belangrijkste keuzes" geformuleerd als "begrensd tot ongeveer 6 uur", niet "eerlijk"; ook in RUNBOOK §17.3. |
| N-2 | "Allow new users to sign up" uit is een harde poort vóór de merge, en Lars controleert het nu al (A14, R5, Nodig van Lars 1). "Auto Confirm User" bij de test van AC-6. |
| N-3 | pgTAP-bestand heet `10_hardening.test.sql`. RUNBOOK-sectie: eerstvolgend vrij nummer (§17 of §18), consistent met WP-23. `--include-all` in §17.5. `docs/PRIVACY.md`-wijziging als "alleen na merge WP-23" (Bestanden, stap 13), anders doet WP-23 het als tweede. |
| N-4 | Toegevoegd in A6 en R1: tellers na een herhaalde `update`/`delete` zijn indicatief. |
| N-5 | 520–524 toegevoegd aan `DB_RETRY_STATUSES` (A6, Interfaces, E54, `test_retry_statuses`). |
| N-6 | E53 en RUNBOOK §14.14. Geen codewijziging. |
| N-7 | E50 gecorrigeerd: de drie waarschuwingen passen bij de testwaarden (ongeveer 136 tekens); bij grotere getallen begrenst het algoritme. |
| N-8 | `secret_values` neemt ook de canonieke UUID-vorm op als die afwijkt (A1, Config, E55, test in `test_logsetup.py`). |
| N-9 | Fixture en insertpatroon van `07_sessions.test.sql` letterlijk opgenomen in Testplan AC-4, met alle verplichte kolommen. |
| N-10 | Vastgelegd als open punt voor de orchestrator, voorstel WP-25 (Buiten scope, Open punten). |
| N-11 | Afweging expliciet in A12 en R1. |
