# Work packages Shakka v2 (mijlpaal M5)

> Opgesteld door de architect op 15 oktober 2026. Bron van waarheid blijft `docs/PROJECT_PLAN.md`; dit document werkt sectie 9 ("v2") daarvan uit. Status per WP staat in `docs/STATUS.md`. **Opdeling v2: wacht op akkoord van Lars.**
>
> v2 bevat geen nieuwe ideeën. Elke WP is geoogst uit de v1-documenten (WORK_PACKAGES, blueprints, reviews, deviations, NIGHT) of is een van de door Lars al benoemde kandidaten. De herkomst staat per WP onder **Bron**.

## Uitgangspunten

- **Nummering.** v2 begint bij WP-24. De v1-nummers (WP-00 t/m WP-23, met het vervallen WP-09) blijven ongewijzigd.
- **Startmoment.** Elke v2-WP start pas als WP-22 en WP-23 `done` zijn. Beide raken bijna elk bestand dat v2 ook raakt: pipeline, pushjob, pgTAP-functielijsten, privacypagina en RUNBOOK. Die afhankelijkheid staat daarom bij elke WP.
- **Stand van WP-22 en WP-23.** Dit plan gaat uit van de blueprints zoals ze op 15 oktober 2026 in hun worktrees staan:
  - WP-22: `Status: DRAFT`, revisie 1, review ronde 1 `CHANGES_REQUIRED` (B-1 t/m B-6);
  - WP-23: `APPROVED`, revisie 2.

  Valt een punt dat WP-22 nu op zich neemt er bij de herziening uit, dan komt het terug in v2. Concreet gaat het om A11 (veroudering per spot), A13 (bovengrens `starts_at`), A14 (open aanmelden technisch) en A15 (SMTP). De orchestrator voegt het dan toe aan WP-27 (ingest) of WP-31 (aanmelden). De planner van elke v2-WP controleert eerst de gemergde stand van WP-22 en WP-23.
- **Harde regels blijven gelden.**
  - €0 per maand.
  - Open-Meteo alleen server-side.
  - Bronvermelding blijft zichtbaar.
  - Geen scraping.
  - Offshore en side-offshore zijn altijd `no_go`.
  - Minimale persoonsgegevens.
  - Geen tracking of third-party analytics.
  - Secrets alleen in `.env` en GitHub Secrets.

  Geen enkele v2-WP raakt de evaluatieregels. WP-32 verandert alleen de rastercel waarvan de wind komt.
- **Soort per WP.** Elke WP heeft een veld **Soort**:
  - **opruimen/afmaken**: maakt iets af dat in v1 al bedoeld was. De scope uit het plan verandert niet.
  - **scopewijziging**: verandert wat de app voor gebruikers doet ten opzichte van een eerder besluit. Zo'n WP wordt pas gebouwd na expliciet akkoord van Lars. Dat akkoord staat dan in `docs/PROJECT_PLAN.md`.
  - **besluit Lars**: geen scopewijziging, maar het draait een expliciete v1-keuze terug of hangt af van iets dat alleen Lars kan aanleveren.

## Afspraken die voor alle v2-WP's gelden

Alle afspraken uit `docs/WORK_PACKAGES.md` ("Afspraken die voor alle WP's gelden") blijven gelden: repo, git en branches, Supabase-project, code-indeling, commando's en de bewaking van de harde regels. Daarbovenop gelden de regels hieronder. Ze komen uit de v1-blueprints en voorkomen bekende valkuilen.

1. **Geen nieuwe tabellen.** v2 voegt alleen kolommen, constraints en functies toe. `TABLE_KEYS` en `db_usage()` (WP-22) hoeven daardoor niet mee te veranderen.
2. **Nieuwe functies in `public`.** `supabase/tests/07_sessions.test.sql` somt per rol de uitvoerbare functies op, en daarnaast alle `security definer`-functies (WP-19 R4, WP-22 B-1, WP-23 A1). Elke WP die een functie toevoegt, werkt die regels in hetzelfde commit bij en doet expliciet `revoke all … from public, anon, authenticated, service_role` met daarna alleen de bedoelde `grant`.
3. **`alter table` in een migratie.**
   - `web/test/schema-columns.test.ts` heeft een alter-guard (WP-16, WP-22). Elke v2-migratie met `alter table` werkt die guard bij, zoals WP-22 deed.
   - Raakt de migratie een van de vijf sessie-RPC's of `public.rsvps`, dan werkt de WP ook de drift-check (0) in `web/test/rsvp-contract.test.ts` bij (WP-21).
4. **Kolomrechten.** `authenticated` mag alleen de kolommen van `profiles` en `sessions` wijzigen die expliciet een `grant update (…)` hebben (WP-01, WP-19). Een nieuwe kolom die de app wijzigt, krijgt een eigen grant en een pgTAP-assert.
5. **Migratietijdstempels.** Elke WP gebruikt de eerstvolgende vrije tijdstempel. Wordt er een migratie met een eerdere tijdstempel later gemerged, dan noemt die WP onder "Nodig van Lars" dat `supabase db push --include-all` nodig is (WP-12 R6).
6. **Persoonsgegevens.** WP-23 ("Gevolgen") legt vast dat een WP die persoonsgegevens, een externe dienst of een `localStorage`-sleutel toevoegt, ook `/privacy`, `docs/PRIVACY.md` en zo nodig `web/static/_headers` en `checkHeaders` bijwerkt. Komt er een bewaartermijn bij, dan breidt de WP ook `retention-consistency.test.ts` uit.
7. **Pipelinestappen.** Na WP-22 is `STEPS`:

   `spots_sync`, `forecast`, `marine`, `tides`, `evaluate`, `alerts`, `sessions_cleanup`, `usage_report`

   `usage_report` blijft de laatste stap. Een nieuwe stap komt direct vóór `usage_report`.
8. **Logs.** De Actions-logs zijn openbaar. In logs, `ingest_runs`, exceptions en `DeliveryResult.detail` komen nooit e-mailadressen, user-id's, berichtteksten, endpoints of sleutels.

## Overzicht

| WP | Naam | Soort | Afhankelijk van | Omvang |
|---|---|---|---|---|
| WP-24 | E-mail als tweede meldingskanaal | scopewijziging | WP-17, WP-18, WP-22, WP-23; niet parallel met WP-30 | M |
| WP-25 | Moderatie voor organisatoren | opruimen/afmaken | WP-20, WP-21, WP-22, WP-23 | M |
| WP-26 | Forecast-horizon 8 dagen (`days_ahead` 7 werkt) | opruimen/afmaken | WP-03, WP-16, WP-22, WP-23 | S |
| WP-27 | Ingest-hygiëne: RWS-verbruik, stationvolgorde, `doctor`, puurheidscheck | opruimen/afmaken | WP-04, WP-11, WP-22, WP-23 | S |
| WP-28 | Dependabot | besluit Lars | WP-22, WP-23 | S |
| WP-29 | Inloggen met een code | opruimen/afmaken | WP-18, WP-22, WP-23 | S |
| WP-30 | Stille uren voor meldingen | scopewijziging | WP-16, WP-17, WP-18, WP-22, WP-23; niet parallel met WP-24 | M |
| WP-31 | Open aanmelden: crew organiseert zelf | scopewijziging | WP-20, WP-22, WP-23, WP-25, WP-29 | M |
| WP-32 | `cell_selection` per spot | besluit Lars (voorwaardelijk) | WP-02, WP-03, WP-12, WP-22, WP-23, WP-26 | S |
| WP-33 | Eigen app-icoon en installeerbaarheid | besluit Lars (voorwaardelijk) | WP-13, WP-23 | S |

Aantallen: 10 WP's, allemaal in M5. Daarvan:
- 3 scopewijzigingen: WP-24, WP-30 en WP-31;
- 4 opruimen/afmaken: WP-25, WP-26, WP-27 en WP-29;
- 3 besluit Lars: WP-28, WP-32 en WP-33.

## Mijlpaal M5 "v2": aanbevolen volgorde

M5 is geen blok dat in één keer af moet. De WP's lopen in drie sporen, met twee voorwaardelijke WP's ernaast.

| Golf | Spoor A: opruimen | Spoor B: crew en sessies | Spoor C: meldingen | Voorwaarde |
|---|---|---|---|---|
| 1 (direct na v1, terwijl Lars v1 test) | WP-26, WP-27, en WP-28 na akkoord | WP-25 | – | v1 `done` |
| 2 | – | WP-29 | WP-30 | WP-29: eigen SMTP draait (WP-22). WP-30: akkoord van Lars op stille uren. |
| 3 | – | WP-31 | WP-24 | WP-31: akkoord open aanmelden, na WP-25 en WP-29. WP-24: akkoord e-mailkanaal, na WP-30. |
| Voorwaardelijk | WP-32 (na WP-26) | – | – | Lars wijst een spot aan waar `sea` aantoonbaar verkeerd is. |
| Voorwaardelijk | WP-33 | – | – | Lars levert een icoon of de installeerbaarheidsbevindingen uit WP-23 AC-6. |

**Wat parallel kan, en waar het botst:**
- Golf 1 kan volledig parallel. WP-26 raakt `shakka.openmeteo` en het alertformulier, WP-27 de getijjob, `doctor` en het gebruiksrapport, WP-28 alleen `.github/`, WP-25 de sessies.
  - Raakpunt: WP-26 en WP-27 voegen allebei een regel toe aan het RUNBOOK. Dat is triviaal.
- **WP-24 en WP-30 nooit tegelijk.** Allebei voegen ze kolommen en grants toe aan `profiles`, en ze wijzigen allebei `shakka.jobs.alerts.run_alerts`, `PROFILE_COLUMNS` en `/alerts`. Aanbevolen is eerst WP-30, zodat het e-mailkanaal de poort van stille uren meteen meekrijgt.
- **WP-25 vóór WP-31.** Allebei voegen ze een functie toe aan de functielijsten in `07_sessions.test.sql` (afspraak 2).
- **WP-29 vóór WP-31.** Allebei wijzigen ze `/login`. Open aanmelden is bovendien pas prettig als nieuwe iOS-gebruikers in de geïnstalleerde app kunnen inloggen (WP-13 R3).
- **WP-26 vóór WP-32.** Allebei wijzigen ze `build_forecast_params` en de Open-Meteo-fixture.
- **WP-27 vóór WP-24.** Allebei voegen ze een regel toe aan het gebruiksrapport van WP-22 (`build_usage_report`, golden-tekst).

**Na M5:** Lars test een week, zoals na elke mijlpaal (plan, sectie 5).

## Gecontroleerde externe documentatie (15 oktober 2026)

| Onderwerp | Bevinding die een contract raakt | Bron |
|---|---|---|
| Open-Meteo `cell_selection` | Waarden `land` (standaard), `sea`, `nearest`. `land` zoekt een landcel met vergelijkbare hoogte; `sea` geeft voorkeur aan zeecellen; `nearest` neemt de dichtstbijzijnde cel. | https://open-meteo.com/en/docs |
| Open-Meteo `forecast_days` | 0–16, standaard 7. Gewicht verandert niet tot 14 dagen (WP-03 A10, factor `d/14` < 1). | https://open-meteo.com/en/docs, https://open-meteo.com/en/pricing |
| Supabase e-mail-OTP | Template met `{{ .Token }}` (6 cijfers); `signInWithOtp()` verstuurt, `verifyOtp({ email, token, type: 'email' })` controleert. Standaard één aanvraag per 60 s, verloopt na 1 uur; "Email OTP Expiration" geldt ook voor magic links. | https://supabase.com/docs/guides/auth/auth-email-passwordless, https://supabase.com/docs/guides/auth/auth-email-templates |
| Supabase templates en standaard-SMTP | De huidige docs noemen **geen** beperking op het aanpassen van templates zonder eigen SMTP. WP-13 A6 stelt dat nieuwe free-projecten (na 3 juni 2026) templates niet kunnen aanpassen met de standaard-SMTP. Dat is niet bevestigd: de planner van WP-29 controleert het in het dashboard. | https://supabase.com/docs/guides/auth/auth-email-templates, https://supabase.com/docs/guides/auth/auth-smtp |
| Supabase eigen SMTP | Standaard-SMTP: alleen naar vooraf toegestane adressen, 2 per uur. Na het inschakelen van eigen SMTP eerst een limiet van 30 per uur (instelbaar). | https://supabase.com/docs/guides/auth/auth-smtp |
| Resend | Gratis: 3.000 mails per maand, 100 per dag, 3 domeinen, SMTP-relay. Open- en kliktracking staan standaard uit, per domein. API: `POST https://api.resend.com/emails`, header `Authorization: Bearer …`, velden `from`, `to`, `subject`, `text` of `html`. | https://resend.com/pricing, https://resend.com/docs/dashboard/domains/tracking, https://resend.com/docs/api-reference/emails/send-email |
| Postmark | Gratis: 100 mails per maand. API: `POST https://api.postmarkapp.com/email`, header `X-Postmark-Server-Token`, velden `From`, `To`, `Subject`, `TextBody`, `MessageStream`, `TrackOpens` (bool) en `TrackLinks` (`None`, `HtmlAndText`, `HtmlOnly`, `TextOnly`). De standaardwaarden van de tracking zijn **niet** bevestigd; WP-24 zet ze daarom expliciet uit. | https://postmarkapp.com/pricing, https://postmarkapp.com/developer/api/email-api |
| Brevo | Tracking bij transactionele mail is niet uit te zetten (WP-22 review B-3). Niet bruikbaar voor Shakka. | https://community.brevo.com/t/no-way-to-disable-by-option-tracking-in-transactional-e-mail/201 |
| SMTP vanaf GitHub-hosted runners | Meldingen in de praktijk: poort 25 dicht, 465/587 onbetrouwbaar. **Geen GitHub-documentatie gevonden**; de bron is zwak. Daarom kiest WP-24 voor de HTTPS-API van de maildienst, niet voor SMTP. | https://github.com/21072026/Internship/issues/2322 (melding van derden, niet officieel) |
| Dependabot | `uv`, `npm` en `github-actions` zijn geldige `package-ecosystem`-waarden. Of Dependabot een actie die op een commit-SHA is vastgezet bijwerkt mét het versiecommentaar, staat niet in de gelezen pagina's; de planner van WP-28 verifieert dat. | https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference, https://docs.github.com/en/code-security/dependabot/working-with-dependabot/keeping-your-actions-up-to-date-with-dependabot |

**De planner verifieert dit per WP opnieuw**, want het bleek niet volledig uit de documentatie:
- welke template Supabase gebruikt bij `signInWithOtp` voor een **nieuwe** gebruiker ("Magic Link" of "Confirm signup"), en de instelbare lengte van de code (WP-29, WP-31);
- de standaard van `TrackOpens` en `TrackLinks` bij Postmark, en of tracking bij Resend op domeinniveau echt uit staat voor Lars' domein (WP-24);
- of de Marine API van Open-Meteo `cell_selection` ondersteunt (WP-32);
- het SHA-gedrag van Dependabot (WP-28).

---

## M5: "v2"

## WP-24: E-mail als tweede meldingskanaal
**Mijlpaal:** M5
**Soort:** scopewijziging. Lars besloot op 15 oktober 2026: "Web Push is het enige meldingskanaal" (A-16). Deze WP voegt e-mail toe als tweede kanaal, en vraagt dus expliciet akkoord van Lars.
**Afhankelijk van:** WP-17, WP-18, WP-22, WP-23. Niet parallel met WP-30. Aanbevolen na WP-27 en WP-30.
**Bron:** kandidaat WP-24 (Lars); WP-20 "Gevolgen" (WP-22/WP-24); WP-22 A15 en review B-3 (niet Brevo); WP-17 contract `DeliveryTarget` ("een later kanaal kan de union uitbreiden").
**Doel:** Per gebruiker kiezen of alerts als push, als e-mail of als allebei binnenkomen. E-mail gaat via dezelfde `Notifier`-interface en afleverregel als WP-17, als platte tekst, zonder tracking, naar het e-mailadres waarmee de gebruiker inlogt.
**In scope:**
- Een migratie:
  - kolom `profiles.alert_channel text not null default 'push'`, met CHECK `alert_channel in ('push', 'email', 'both')`;
  - `grant update (alert_channel) on public.profiles to authenticated`;
  - de CHECK op `api_usage.source` uitgebreid met `email`;
  - een service-only RPC `alert_email_targets()`.
- pgTAP-tests, plus de bijgewerkte functielijsten in `07_sessions.test.sql` (afspraak 2).
- `shakka.domain.email` (puur): een `AlertMessage` omzetten naar een onderwerp en platte tekst.
- `shakka.notify.email`:
  - `EmailNotifier`;
  - twee senders voor de HTTPS-API: `ResendSender` en `PostmarkSender`. Alleen de dienst die Lars kiest hoeft live getest te worden; beide worden met MockTransport getest;
  - alle HTTP via `shakka.http.make_client` en `with_retries` (WP-22).
- Geen SMTP vanuit de runner (zie "Gecontroleerde externe documentatie").
- Tracking:
  - geen HTML-body;
  - bij Postmark expliciet `TrackOpens: false` en `TrackLinks: "None"`;
  - bij Resend geen tracking-opties meesturen. Het RUNBOOK laat Lars controleren dat tracking voor het domein uit staat.
- Een dagbudget voor e-mail in `api_usage` (bron `email`). Boven het budget gaat er geen request uit; het event is dan voor dat kanaal verloren (niet herhaalbaar), en er volgt een stapwarning. De gratis tier wordt gedeeld met de inlogmails van Supabase als Lars dezelfde dienst gebruikt.
- `shakka.jobs.alerts`:
  - per gebruiker doelen laden volgens `alert_channel`;
  - de afleverregel van WP-17 en WP-22 ongewijzigd toepassen over alle doelen van alle kanalen. Slaagt één aflevering, dan schuift de state door. Slaagt er geen en is er minstens één herhaalbare fout, dan wordt het event uitgesteld.
- `run_hourly` bouwt de `EmailNotifier` uit `Settings`. Ontbreekt de configuratie, dan is het kanaal uit, met een warning (zoals bij VAPID in WP-17 AC-6).
- CLI: `shakka alerts test-email --user-id UUID` (naar analogie van `test-push` uit WP-17). Verstuurt één testmail naar het bevestigde login-adres van die gebruiker (gevonden via `alert_email_targets()`, dus alleen als het kanaal `email` of `both` is) en toont alleen ok, `no_target` of de foutcategorie, nooit het adres.
- `hourly.yml`, `.env.example` en `Settings` krijgen de nieuwe variabelen.
- PWA, op `/alerts`: een sectie "Meldingen via" met drie keuzes:
  - Push;
  - E-mail naar `<login-adres>` (alleen-lezen);
  - Push en e-mail.

  De app schrijft alleen `profiles.alert_channel`.
- `/privacy` en `docs/PRIVACY.md`: de maildienst ontvangt het e-mailadres en de alerttekst. Daarnaast `docs/RUNBOOK.md`: account, domein, API-sleutel, controle dat tracking uit staat, en het budget.
**Buiten scope:**
- Een apart e-mailadres voor alerts (minimale gegevens: alleen het login-adres).
- HTML-mail, opmaak en afbeeldingen.
- Uitschrijven via een link zonder in te loggen (one-click unsubscribe). De mail linkt naar `/alerts`.
- Stille uren (WP-30; de poort van WP-30 geldt dan vanzelf ook voor e-mail).
- Het gebruiksrapport voor Lars per e-mail (dat blijft push, WP-22).
- De SMTP voor Supabase Auth (WP-22).
- Andere kanalen.
**Contracten:**
- Kolom `profiles.alert_channel text not null default 'push'`, CHECK `('push', 'email', 'both')`. `authenticated` mag hem bijwerken op de eigen rij.
- `api_usage.source` mag nu ook `email` zijn. `BudgetGuard` (WP-03) telt alleen `open_meteo_*` en wordt niet geraakt.
- RPC `public.alert_email_targets() returns table (user_id uuid, email text)`:
  - `security definer`, `set search_path = ''`, uitvoerbaar alleen door `service_role`;
  - geeft alleen gebruikers met `alert_channel in ('email', 'both')` en een bevestigd e-mailadres (`auth.users.email_confirmed_at is not null`).
- `shakka.domain.email` (puur):
  - `EmailText(subject: str, body: str)`;
  - `EMAIL_SUBJECT_MAX = 120` (voorstel, de planner bevestigt);
  - `to_email_text(message: AlertMessage, *, settings_url: str | None) -> EmailText`. Het onderwerp is `message.title`, ingekort op een woordgrens met "…". De body is `message.body`, dan de `go_url` als die er is, dan een voettekst met:
    - waarom je deze mail krijgt;
    - de link `settings_url` om het uit te zetten;
    - de regel "Weerdata: Open-Meteo.com (CC BY 4.0)" (voorstel; Lars mag hem schrappen).

    Geen HTML.
- `shakka.notify.base` (uitbreiding):
  - `EmailTarget(user_id: str, address: str)` (frozen; `repr` toont het adres niet);
  - `DeliveryTarget = PushTarget | EmailTarget`.
- `shakka.notify.email`:
  - `EmailSender` (Protocol) met `send_email(to: str, subject: str, text: str) -> DeliveryResult`;
  - `ResendSender(api_key: str, from_address: str, *, http: httpx.Client)` en `PostmarkSender(server_token: str, from_address: str, *, http: httpx.Client)`;
  - `EmailNotifier(sender: EmailSender, *, settings_url: str | None)` met `channel = "email"` en `send(target: EmailTarget, message: AlertMessage, *, tag: str) -> DeliveryResult` (`tag` wordt genegeerd);
  - `EMAIL_DAILY_BUDGET: Final = 60` (voorstel, zie "Nodig van Lars").
  - Het `Notifier`-Protocol bevat na WP-22 ook `send_payload` (push-specifiek). De planner kiest: (a) `EmailNotifier.send_payload` geeft altijd `DeliveryResult(ok=False, permanent_failure=False, detail="unsupported", retryable=False)`, of (b) het Protocol splitsen in `Notifier` en een push-variant. Geen gedragswijziging voor `usage_report`.
- Foutclassificatie per sender:
  - 2xx: `ok`;
  - 429, 5xx en transportfouten: herhaalbaar;
  - andere 4xx: niet herhaalbaar, en ook niet permanent. Er is geen abonnement om op te ruimen.
- Omgevingsvariabelen (nieuw in het env-contract):

  | Variabele | Waar | Gebruikt door |
  |---|---|---|
  | `EMAIL_PROVIDER` | `.env`, GitHub Actions-variable | ingest, `resend` of `postmark` |
  | `EMAIL_API_KEY` | `.env`, GitHub Secret | ingest |
  | `ALERT_EMAIL_FROM` | `.env`, GitHub Actions-variable | ingest, bijv. `Shakka <alerts@domein>` |

  `Settings` krijgt `email_provider: Literal["resend", "postmark"] | None`, `email_api_key: SecretStr | None` en `alert_email_from: str | None`.
- `AlertJobResult` krijgt de velden `email_sent: int = 0`, `email_failed: int = 0` en `email_skipped_budget: int = 0`. De bestaande velden blijven.
- `web/src/lib/user-data.ts` krijgt `saveAlertChannel(channel: 'push' | 'email' | 'both'): Promise<void>`. Het type `AlertChannel` komt in `web/src/lib/types.ts`.
**Acceptatiecriteria:**
- AC-1: `supabase test db` is groen. Daarin:
  - `alert_channel` heeft de default `push`, en `'sms'` wordt geweigerd;
  - gebruiker A kan zijn eigen `alert_channel` wijzigen en niet die van B;
  - `anon` en `authenticated` kunnen `alert_email_targets()` niet uitvoeren;
  - de functie geeft geen gebruiker met `push` of met een onbevestigd adres;
  - een insert in `api_usage` met `source = 'email'` slaagt.
- AC-2: `cd ingest && uv run pytest tests/test_email_text.py`. Voor de vier golden-berichten van WP-08 (`new`, `improved`, `worsened`, `cancelled`):
  - het onderwerp is gelijk aan de titel, of ingekort op een woordgrens met "…" en hoogstens `EMAIL_SUBJECT_MAX` tekens;
  - de body begint met `message.body`;
  - de body bevat `go_url` precies als die niet `None` is;
  - de body bevat `settings_url` en "Open-Meteo.com";
  - de body bevat geen `<html` en geen `<a `.

  `tests/test_domain_purity.py` is groen.
- AC-3: `tests/test_notify_email.py` met `httpx.MockTransport`:
  - Resend krijgt `POST https://api.resend.com/emails` met `Authorization: Bearer <key>` en een JSON met `from`, `to`, `subject` en `text`, zonder `html`;
  - Postmark krijgt `POST https://api.postmarkapp.com/email` met `X-Postmark-Server-Token`, `TextBody`, `TrackOpens: false` en `TrackLinks: "None"`, zonder `HtmlBody`;
  - 429 en 503 geven `retryable=True`, en 400 en 401 geven `ok=False, permanent_failure=False, retryable=False`;
  - de sleutel en het adres staan niet in `DeliveryResult.detail` en niet in caplog of capsys.
- AC-4: `tests/test_job_alerts_email.py` met `FakeSupabase` en nep-notifiers. Een gebruiker met `push` krijgt alleen push, met `email` alleen e-mail en met `both` beide.
  - `both`: push slaagt en e-mail geeft 503. De state schuift door.
  - `email`: e-mail geeft 503. De state blijft ongewijzigd en de volgende run levert opnieuw af.
  - `email`: e-mail geeft 400. De state schuift door, en `email_failed` is 1.
- AC-5: Budget. Een fake `api_usage` met `email` op `EMAIL_DAILY_BUDGET` geeft 0 HTTP-requests naar de maildienst (MockTransport telt 0), `email_skipped_budget` groter dan 0, en een warning bij de stap `alerts`. Na een geslaagde mail stijgt `api_usage` (`email`, vandaag) met 1.
- AC-6: Zonder `EMAIL_PROVIDER` of `EMAIL_API_KEY` draait `run_hourly` zonder exception en logt het een warning. Push werkt zoals voorheen; de tests van WP-17 blijven ongewijzigd groen.
- AC-7: `hourly.yml` geeft `EMAIL_API_KEY` door via `${{ secrets.EMAIL_API_KEY }}`, en `EMAIL_PROVIDER` en `ALERT_EMAIL_FROM` via `${{ vars.* }}`. `tests/test_repo_hygiene.py` (`ENV_KEYS`) en `tests/test_hourly_workflow.py` zijn bijgewerkt en groen.
- AC-8: `cd web && npm run check && npm test && npm run build` slaagt. Een componenttest van `/alerts` toont de drie keuzes met Nederlandse labels en het login-adres. Kiezen leidt tot precies één update op `profiles` met alleen `alert_channel` (de gemockte client registreert de kolommen).
- AC-9: `/privacy` en `docs/PRIVACY.md` noemen de maildienst als ontvanger van het e-mailadres en de alerttekst. `privacy-page.test.ts` (WP-23) is daarop uitgebreid en groen.
- AC-10: Lars zet het kanaal op "Push en e-mail" en draait `uv run shakka alerts test-email --user-id <id>`, of wacht op een echt event. De mail komt aan als platte tekst. De link in de mail wijst direct naar `APP_BASE_URL`, zonder redirectdomein. Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- Akkoord op de scopewijziging (e-mail naast push), vast te leggen in `docs/PROJECT_PLAN.md`.
- Keuze van de maildienst. Resend of Postmark; Brevo niet (WP-22 B-3).
  - Let op: het gratis plan van Postmark heeft 100 mails per maand. Dat is te weinig voor alerts naast inlogmails.
  - Resend heeft 100 per dag en 3.000 per maand.
  - Gebruik bij voorkeur dezelfde dienst als voor Supabase Auth (WP-22).
- Een geverifieerd afzenderdomein (SPF en DKIM), de API-sleutel als GitHub Secret `EMAIL_API_KEY`, en de variabelen `EMAIL_PROVIDER` en `ALERT_EMAIL_FROM`.
- Bevestiging van `EMAIL_DAILY_BUDGET`. Voorstel: 60 per dag, zodat er bij Resend ruimte blijft voor inlogmails.
- Na de merge `supabase db push`.
**Omvang:** M. Vindt de planner hem een L, dan splitsen in backend (migratie, domein, notifier, job) en PWA (keuze op `/alerts`, privacytekst).

## WP-25: Moderatie voor organisatoren
**Mijlpaal:** M5
**Soort:** opruimen/afmaken. Het lost een bekend risico op (WP-19 R1, WP-21 R1 en R6) en verandert niets aan het plan.
**Afhankelijk van:** WP-20, WP-21, WP-22, WP-23
**Bron:** kandidaat WP-25 (Lars); WP-19 R1 en review N-7; WP-21 R1, R6 en "Gevolgen" (WP-22); WP-22 "Buiten scope" en review N-10 (valt tussen wal en schip); WP-23 "Buiten scope".
**Doel:** Een organisator kan op zijn eigen sessie een aanmelding van iemand anders verwijderen (spam, dubbele aanmelding of een verloren token) en het aanmelden sluiten en weer openen, zonder Lars en zonder de SQL-editor.
**In scope:**
- Een migratie:
  - kolom `sessions.rsvps_closed_at timestamptz null`, plus `grant update (rsvps_closed_at)` voor `authenticated` (RLS beperkt dit al tot de eigen sessies);
  - een nieuwe versie van `rsvp_create`: geweigerd met de bestaande foutcode `session_closed` als `rsvps_closed_at is not null`;
  - een nieuwe versie van `get_public_session`, met `session.rsvps_closed: boolean` erbij;
  - de RPC `organizer_delete_rsvp`.
- `rsvp_update` en `rsvp_delete` met een geldige token blijven werken bij gesloten aanmelden. Een deelnemer kan zich dus altijd afmelden.
- pgTAP (nieuw bestand), plus de functielijsten in `07_sessions.test.sql`.
- PWA:
  - `/mijn-sessies` krijgt per komende sessie de link "Aanmeldingen beheren";
  - nieuwe route `/sessie/[slug]/beheer`, alleen voor de organisator. Daar staan de aanmeldingen (via `getPublicSession`) met per aanmelding "Verwijderen" en een bevestiging, plus een schakelaar "Aanmelden open/gesloten";
  - op `/s/[slug]`: is `rsvps_closed` waar, dan geen formulier maar de melding "De organisator heeft het aanmelden gesloten." Afmelden blijft zichtbaar voor wie een token heeft.
- De aanpassing in `web/src/lib/rsvp-types.ts`, de drift-check in `rsvp-contract.test.ts`, en `RPC_FILES` in `user-tables.test.ts`.
- `docs/RUNBOOK.md` §16.5: de SQL-route wordt de terugvaloptie.
**Buiten scope:**
- Sessies verwijderen (er is bewust geen delete-recht; annuleren bestaat al, WP-20).
- Meldingen aan deelnemers.
- CAPTCHA of IP-limieten (geparkeerd, zie onderaan).
- Moderatie door Lars over alle sessies heen (blijft de SQL-editor).
- Een capaciteitscontrole voor meerijders (geparkeerd).
**Contracten:**
- Kolom `sessions.rsvps_closed_at timestamptz null`. `authenticated` mag hem bijwerken op de eigen sessies.
- RPC `public.organizer_delete_rsvp(p_rsvp_id uuid) returns boolean`:
  - `security definer`, `set search_path = ''`, uitvoerbaar alleen door `authenticated`;
  - verwijdert de RSVP alleen als de bijbehorende sessie `organizer_id = auth.uid()` heeft;
  - geeft `true` bij verwijderd, en `false` bij onbekend of niet van jou. Zo verraadt de functie niet of een id bestaat;
  - `rides_with`-verwijzingen naar de verwijderde RSVP worden `null` door de bestaande FK `on delete set null`.
- `get_public_session(p_slug)`: het object `session` krijgt `rsvps_closed: boolean`. Verder blijft de vorm ongewijzigd (WP-19-contract). Nooit `organizer_id`.
- `rsvp_create`: dezelfde signatuur. Bij gesloten aanmelden de fout `session_closed`.
- `web/src/lib/moderation.ts`:
  - `deleteRsvpAsOrganizer(rsvpId: string): Promise<{ ok: boolean; error?: string }>`;
  - `setRsvpsClosed(sessionId: string, closed: boolean): Promise<void>`. Zet `rsvps_closed_at` op nu of `null`, via een update op `sessions`.
- Routetabel (aanvulling op WP-13): `/sessie/[slug]/beheer` hoort bij WP-25.
**Acceptatiecriteria:**
- AC-1: `supabase test db` is groen. Daarin:
  - organisator A verwijdert een RSVP op zijn eigen sessie: `true`, en de rij is weg;
  - B roept het aan voor een RSVP op A's sessie: `false`, en de rij blijft;
  - een onbekend id geeft `false`;
  - `anon` kan de functie niet uitvoeren;
  - een RSVP met `rides_with` naar de verwijderde rij krijgt `rides_with = null`.
- AC-2: `supabase test db`:
  - A kan `rsvps_closed_at` op zijn eigen sessie zetten, en B kan dat niet op A's sessie;
  - `rsvp_create` op een sessie met `rsvps_closed_at` gezet geeft `session_closed`;
  - `rsvp_delete` en `rsvp_update` met een geldige token werken daar nog;
  - `get_public_session` geeft `rsvps_closed: true`, en de JSON-sleutels bevatten nog steeds geen `organizer_id`, `edit_token_hash` of `email`.
- AC-3: `07_sessions.test.sql` noemt `organizer_delete_rsvp` in de lijst van functies die `authenticated` mag uitvoeren en in de lijst van `security definer`-functies. `supabase test db` is volledig groen.
- AC-4: `cd web && npm run check && npm test && npm run build` slaagt. Componenttests van `/sessie/[slug]/beheer`:
  - uitgelogd: een loginprompt en geen queries;
  - een slug die niet van jou is (de gemockte select op `sessions` geeft niets): "Sessie niet gevonden" en geen aanroep van `organizer_delete_rsvp`;
  - een eigen sessie: "Verwijderen" vraagt eerst om bevestiging; daarna volgt precies één aanroep van `organizer_delete_rsvp` met het juiste id, en de rij verdwijnt uit de lijst;
  - de schakelaar doet een update op `sessions` met alleen `rsvps_closed_at`.
- AC-5: Een componenttest van `/s/[slug]` met `rsvps_closed: true` toont de Nederlandse melding en geen formulier "Ik ook". Met een opgeslagen token is "Afmelden" er nog.
- AC-6: `RPC_FILES` in `web/test/user-tables.test.ts` bevat `lib/moderation.ts`, en `rsvp-contract.test.ts` kent `rsvps_closed`. Beide zijn groen.
- AC-7: Op een telefoon: een sessie aanmaken, met een tweede browser zonder account aanmelden, de aanmelding als organisator verwijderen, het aanmelden sluiten, en in de tweede browser zien dat er geen formulier meer is. Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- Bevestiging dat "sessie sluiten" betekent: het aanmelden stoppen zonder te annuleren. Annuleren bestaat al.
- Na de merge `supabase db push`.
**Omvang:** M

## WP-26: Forecast-horizon 8 dagen (`days_ahead` 7 werkt)
**Mijlpaal:** M5
**Soort:** opruimen/afmaken. `days_ahead = 7` mag volgens de database, maar heeft nu nooit data (WP-03 A10). De UI verbergt het (WP-16 A8).
**Afhankelijk van:** WP-03, WP-16, WP-22, WP-23
**Bron:** WP-03 A10, "Gevolgen" (WP-10/WP-16) en review N-4; WP-10 "Buiten scope"; WP-16 A8 en "Buiten scope".
**Doel:** De windverwachting 8 dagen ophalen in plaats van 7, zodat een alertregel met "7 dagen vooruit" echt daglichturen met data heeft. Dit gebeurt zonder extra Open-Meteo-gewicht.
**In scope:**
- `DEFAULT_FORECAST_DAYS` in `shakka.openmeteo.forecast` gaat van 7 naar 8. `build_forecast_params`, `fetch_forecast` en de gewichtsberekening in `shakka.jobs.forecast` gebruiken die constante al.
- Een nieuwe capture van de fixture in `ingest/tests/fixtures/openmeteo/`, met 192 uren. De tests van WP-03 en de bijbehorende README worden bijgewerkt.
- `test_fixture_matches_current_params` blijft de bewaker.
- `/alerts`: de keuze "dagen vooruit" toont 0 t/m 7. De uitleg "dag 7 heeft geen data" vervalt.
- RUNBOOK: één regel bij de forecaststap.
**Buiten scope:**
- Marine (`fetch_marine` blijft 7 dagen; de Marine API kan hoogstens 8).
- Getij (loopt al 8 dagen vooruit).
- De standaard `DEFAULT_DAYS_AHEAD` (blijft 3, WP-07).
- `cell_selection` (WP-32).
**Contracten:**
- `shakka.openmeteo.forecast`: `DEFAULT_FORECAST_DAYS: Final = 8`, `build_forecast_params(locations, *, forecast_days: int = DEFAULT_FORECAST_DAYS)` en `fetch_forecast(http, locations, *, forecast_days: int = DEFAULT_FORECAST_DAYS)`. Dit vervangt het WP-03-contract `forecast_days: int = 7` en WP-03 AC-2 (`forecast_days=7`).
- `web/src/lib/forms.ts` (WP-16): `DAYS_AHEAD_UI_MAX` gaat van 6 naar 7. `daysAheadOptions(current)` geeft dan `"0"` t/m `"7"`.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv run pytest tests/test_openmeteo_forecast.py`. `build_forecast_params` bevat `forecast_days=8`, en de nieuwe fixture heeft per locatie 192 elementen in `hourly.time`, in stappen van 3600 s. Alle bestaande parsertests (AC-1 van WP-03) zijn groen op de nieuwe fixture.
- AC-2: `estimate_call_weight(25, 3, 4, 8) == estimate_call_weight(25, 3, 4, 7)`, getoetst in `tests/test_budget.py`.
- AC-3: Een test op `find_windows` (WP-07) met evaluaties op de lokale dag vandaag+7 en een regel met `days_ahead=7` geeft een window op die dag. Met `days_ahead=6` geeft hij daar geen.
- AC-4: `cd web && npm run check && npm test && npm run build` slaagt. Een componenttest van `AlertRuleForm` toont de optie 7 met een Nederlands label en zonder waarschuwing.
- AC-5: `cd ingest && uv run pytest` en `uv run ruff check . && uv run ruff format --check .` zijn volledig groen.
- AC-6: Na de promotie naar `main` en één uurlijkse run geeft deze query minstens 1 voor `icon`, `ecmwf` en `gfs`:

  ```sql
  select model, count(*) from forecast_hours
  where valid_at >= date_trunc('day', now() at time zone 'utc') + interval '7 days'
  group by model;
  ```

  Dit is `NEEDS_LARS`.
**Nodig van Lars:** Akkoord op 8 dagen. Er zijn geen kosten: het gewicht verandert niet.
**Omvang:** S

## WP-27: Ingest-hygiëne: RWS-verbruik, stationvolgorde, `doctor`, puurheidscheck
**Mijlpaal:** M5
**Soort:** opruimen/afmaken
**Afhankelijk van:** WP-04, WP-11, WP-22, WP-23
**Bron:**
- WP-04 A7 en "Gevolgen" (WP-22: `api_usage` voor `rws`). WP-22 zet dit buiten scope ("RWS publiceert geen limiet").
- WP-11 review N-2 (stationvolgorde onder het getijbudget).
- WP-00 verificatie N-3 en N-4 (gat in de puurheidscheck, traceback in `doctor`).
- WP-00 en WP-17 "Buiten scope" (`doctor` controleert geen VAPID en geen `APP_BASE_URL`).
**Doel:** Vier kleine losse eindjes in de ingest dichten:
- het RWS-verbruik zichtbaar maken;
- bij een gedeeltelijke RWS-storing de oudste stations eerst bedienen;
- `doctor` vertelt welke optionele variabelen ontbreken en crasht niet op een ongeldige URL;
- de puurheidscheck vangt `datetime.now` ook zonder aanroep.
**In scope:**
- `shakka.jobs.tides`:
  - per request één boeking in `api_usage` onder bron `rws` (de waarde staat al in de CHECK van WP-01). `calls` = `requests` = het aantal requests, ook voor mislukte;
  - stations sorteren op de oudste laatste fetch, met nooit opgehaalde stations eerst en bij gelijke stand alfabetisch, zodat het budget van 240 s de oudste data eerst ververst.
- Gebruiksrapport (WP-22): `UsageStats` krijgt `rws_requests_7d: int | None = None`. `build_usage_report` krijgt één regel `Rijkswaterstaat (7 dagen): <n> requests`, of `onbekend`. De golden-tekst wordt bijgewerkt. Er komt geen drempelwaarschuwing.
- `shakka doctor`:
  - toont per optionele variabele (`APP_BASE_URL`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`, `OPERATOR_USER_ID`) "gezet" of "niet gezet", zonder waarden. Ontbrekende optionele variabelen veranderen de exitcode niet;
  - een ongeldige `SUPABASE_URL` of een sleutel met niet-ASCII-tekens geeft één foutregel en exitcode 1, zonder traceback.
- `tests/test_domain_purity.py` meldt ook een verwijzing zonder aanroep naar `datetime.now`, `datetime.utcnow`, `date.today` en `time.time` (bijv. `Field(default_factory=datetime.now)`).
**Buiten scope:**
- Een limiet of drempelwaarschuwing voor RWS (er is geen gepubliceerde limiet).
- Retries voor RWS (WP-22).
- Variabelen van WP-24 in `doctor`. Die voegt WP-24 zelf toe als het na deze WP komt; anders voegt deze WP ze toe.
**Contracten:**
- `shakka.jobs.tides`: `SOURCE_RWS: Final = "rws"`. `TideIngestResult` blijft gelijk.
- `shakka.domain.usage.UsageStats.rws_requests_7d: int | None = None` (een uitbreiding van het WP-22-contract).
- `shakka.doctor.run_doctor(*, echo)`: de signatuur blijft gelijk. De bestaande uitvoerregels blijven, met een blok "optioneel" erbij.
**Acceptatiecriteria:**
- AC-1: `tests/test_job_tides.py`. Een run met 3 stations, waarvan 1 faalt, geeft in `api_usage` (vandaag, `rws`) `requests == 3` en `calls == 3`. Een run die alle stations overslaat (20-uursregel) boekt niets.
- AC-2: `tests/test_job_tides.py`. Met een nep-klok waarbij het budget na één station op is, wordt het station met de oudste `fetched_at` opgehaald. Een station zonder rijen gaat voor alle andere.
- AC-3: `tests/test_usage.py`. De golden-tekst bevat de regel `Rijkswaterstaat (7 dagen): 12 requests` bij `rws_requests_7d=12`, en `Rijkswaterstaat (7 dagen): onbekend` bij `None`. `tests/test_job_usage.py` leest de som uit `api_usage`.
- AC-4: `tests/test_cli.py`:
  - met alleen de verplichte variabelen eindigt `doctor` met exitcode 0, en de uitvoer noemt de vijf optionele variabelen bij naam met "niet gezet";
  - met `SUPABASE_URL="http://exa mple"` is de exitcode 1, staat er geen `Traceback` in de uitvoer, en staan er geen waarden van gezette variabelen in.
- AC-5: `tests/test_domain_purity.py`. De broncode-strings `Field(default_factory=datetime.now)` en `x = date.today` worden als overtreding gemeld; `from datetime import datetime` alleen niet.
- AC-6: `cd ingest && uv run pytest` en de ruff-commando's zijn volledig groen.
**Nodig van Lars:** Niets. Optioneel: het RWS-verbruik schrappen als je het niet wilt zien (WP-22 vond het overbodig).
**Omvang:** S

## WP-28: Dependabot
**Mijlpaal:** M5
**Soort:** besluit Lars. WP-22 A17 koos bewust voor een handmatige maandcheck zonder Dependabot. Deze WP draait dat terug.
**Afhankelijk van:** WP-22, WP-23
**Bron:** WP-00 R3 en "Buiten scope" (Dependabot); WP-11 R8; WP-22 A17, R8 en "Buiten scope"; kandidatenlijst van Lars.
**Doel:** Dependency- en Actions-updates automatisch als gegroepeerde pull requests naar `develop` laten binnenkomen, zodat de handmatige maandcheck alleen nog hoeft te reviewen.
**In scope:**
- `.github/dependabot.yml` (version 2) met drie ecosystemen:
  - `github-actions` in `/`;
  - `npm` in `/web`;
  - `uv` in `/ingest`.

  Elk met `schedule.interval: monthly`, `target-branch: develop`, één `groups`-regel per ecosysteem, en `open-pull-requests-limit: 3`.
- Een test in `tests/test_repo_hygiene.py` die het bestand parseert.
- RUNBOOK §17 (maandcheck van WP-22):
  - de rij "Actions-pins" wordt "Dependabot-PR's reviewen en mergen";
  - uitleg dat Dependabot-PR's geen secrets krijgen (CI heeft ze niet nodig, WP-00);
  - dat elke PR een preview-build op Cloudflare kost (500 per maand).
**Buiten scope:**
- `npm audit` of `pip-audit` als CI-stap (WP-22 A17).
- Automatisch mergen.
- Wijzigingen aan versiegrenzen in `pyproject.toml` en `package.json`.
**Contracten:** `.github/dependabot.yml` zoals hierboven. `test_actions_pinned_to_commit_sha` (WP-22) blijft gelden. Zet Dependabot een actie op een tag in plaats van een SHA, dan faalt die test op de Dependabot-PR. Dat is bedoeld als signaal.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv run pytest tests/test_repo_hygiene.py` is groen, met een nieuwe test die het volgende toetst:
  - `.github/dependabot.yml` is geldige YAML met `version: 2`;
  - er zijn precies drie `updates` met de paren (`github-actions`, `/`), (`npm`, `/web`) en (`uv`, `/ingest`);
  - elk heeft `interval: monthly`, `target-branch: develop` en een niet-lege `groups`.
- AC-2: `docs/RUNBOOK.md` §17 noemt Dependabot in de maandcheck en de afweging van de Cloudflare-builds.
- AC-3: Na de merge en het aanzetten door Lars staat onder Insights → Dependency graph → Dependabot een geslaagde controle per ecosysteem. Een eventuele PR voor `github-actions` houdt de SHA-pin met het versiecommentaar. Doet hij dat niet, dan noteert de verifier het, en beslist Lars of de pin-test of de Dependabot-config wordt aangepast. Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- Akkoord om WP-22 A17 terug te draaien.
- In de repo-instellingen "Dependabot alerts" en "Dependabot security updates" aanzetten.
**Omvang:** S

## WP-29: Inloggen met een code
**Mijlpaal:** M5
**Soort:** opruimen/afmaken. Het lost het bekende iOS-probleem op: een magic link opent Safari in plaats van de geïnstalleerde app (WP-13 R3 en R4, WP-18 R1).
**Afhankelijk van:** WP-18, WP-22 (eigen SMTP is actief), WP-23
**Bron:** WP-13 A6, R3, R4 en "Buiten scope"; WP-18 R1 en "Gevolgen" (WP-22); WP-22 "Buiten scope" ("kan na eigen SMTP in een volgende WP"); kandidatenlijst van Lars.
**Doel:** Naast de magic link stuurt de inlogmail een code van 6 cijfers. Die vul je in de geïnstalleerde PWA in, zodat de sessie in de app zelf ontstaat. Het plakveld voor de link uit WP-18 vervalt.
**In scope:**
- `web/src/lib/auth.ts`: `verifyEmailCode(email, code)` met `supabase.auth.verifyOtp({ email, token: code, type: 'email' })` en Nederlandse foutmeldingen.
- `/login`: na "Check je mail" komt het veld "Of vul de code uit de mail in", met `inputmode="numeric"` en `autocomplete="one-time-code"`.
- De terugkeer na inloggen (`shakka:return_to`, WP-20) werkt ook na inloggen met de code.
- Het plakveld uit WP-18 gaat weg: `signInWithPastedLink`, `pastedLinkUsed`, `parseMagicLink`, `pastedLinkErrorMessage` en de sectie "Inloglink plakken", met hun tests.
- `docs/RUNBOOK.md`: de exacte templatetekst voor "Magic Link" en, als de planner dat nodig vindt, "Confirm signup", met `{{ .ConfirmationURL }}` én `{{ .Token }}`, en waar Lars die instelt.
**Buiten scope:**
- Wachtwoorden, OAuth en SMS.
- Open aanmelden (WP-31).
- Wijzigingen aan Supabase-instellingen in code (die doet Lars in het dashboard).
**Contracten:**
- `web/src/lib/auth.ts`:
  - `EMAIL_CODE_LENGTH: number` = 6 (de planner verifieert de instelling in Supabase);
  - `verifyEmailCode(email: string, code: string): Promise<{ error?: string }>`. Weigert zonder netwerkaanroep een code die niet uit precies `EMAIL_CODE_LENGTH` cijfers bestaat (na het weghalen van spaties);
  - `AUTH_MESSAGES` krijgt `codeInvalid`, `codeExpired` en `codeFormat`.
- `AUTH_MESSAGES.linkInvalid` en `pastedLinkUsed` vervallen.
**Acceptatiecriteria:**
- AC-1: `cd web && npm run check && npm test && npm run build` slaagt.
- AC-2: `auth.test.ts`. `verifyEmailCode('a@b.nl', '123 456')` roept `verifyOtp` precies één keer aan met `{ email: 'a@b.nl', token: '123456', type: 'email' }`. `'12345'` en `'12a456'` geven `codeFormat` zonder aanroep.
- AC-3: De fouten `otp_expired` en een ongeldige code geven elk een eigen Nederlandse melding. Een 429 geeft de bestaande melding voor te veel pogingen.
- AC-4: `login.test.ts`. Na het versturen van de link staat het codeveld er, met `autocomplete="one-time-code"`. Een geslaagde verificatie met een opgeslagen `shakka:return_to` leidt naar dat pad (via de bestaande layoutlogica).
- AC-5: `grep -rnE "signInWithPastedLink|pastedLinkUsed|parseMagicLink" web/src` geeft niets, en `/login` bevat de tekst "Inloglink plakken" niet meer.
- AC-6: `docs/RUNBOOK.md` bevat de templatetekst met `{{ .Token }}` en `{{ .ConfirmationURL }}`.
- AC-7: Op een iPhone, met Shakka op het beginscherm: inloggen via de code in de geïnstalleerde app werkt, en daarna kan push aan. Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- Eigen SMTP actief (WP-22).
- De e-mailtemplate(s) aanpassen volgens het RUNBOOK.
- Akkoord dat het plakveld verdwijnt. Wil je het houden, dan vervalt AC-5 en blijft de sectie staan.
**Omvang:** S

## WP-30: Stille uren voor meldingen
**Mijlpaal:** M5
**Soort:** scopewijziging. "Niet opgenomen" in WORK_PACKAGES (Beslissingen voor Lars): "Wil je dit wel, dan is het een scopewijziging via het plan." Lars besliste eerder "niet in v1".
**Afhankelijk van:** WP-16, WP-17, WP-18, WP-22, WP-23. Niet parallel met WP-24.
**Bron:** WORK_PACKAGES "Niet opgenomen"; "Buiten scope" van WP-07, WP-08, WP-10, WP-17 en WP-18 ("stille uren").
**Doel:** Een gebruiker stelt een periode in (bijv. 22:00–07:00) waarin geen alerts binnenkomen. Wat in die periode verandert, komt na afloop als één actuele melding binnen, en niet als een reeks oude.
**In scope:**
- Een migratie:
  - kolommen `profiles.quiet_from time null` en `profiles.quiet_until time null`;
  - CHECK: beide `null`, of beide gezet en ongelijk;
  - `grant update (quiet_from, quiet_until)` voor `authenticated`.
- pgTAP.
- `shakka.domain.quiet` (puur): `QuietHours` en `in_quiet_hours`, in lokale tijd (`LOCAL_TZ`), ook over middernacht en rond de wisseling van zomer- en wintertijd.
- `shakka.jobs.alerts.run_alerts`: valt `now` voor een gebruiker binnen zijn stille uren, dan:
  - geen aflevering via welk kanaal dan ook;
  - de diff van die gebruiker wordt **niet** opgeslagen (dezelfde alles-of-niets-regel als bij uitstel in WP-17), zodat de eerste run na de stille uren de diff opnieuw berekent tegen de laatst gemelde stand;
  - niet als `deferred` tellen en geen stapwarning, maar een eigen teller `quiet`.
- `shakka.jobs.alerts.PROFILE_COLUMNS` (nu `user_id,weight_kg,level,quiver_m2,default_min_kn,default_max_kn`) krijgt de twee kolommen. WP-24 voegt er `alert_channel` aan toe.
- `/alerts`: een sectie "Stille uren" met twee tijdkeuzes (hele uren) en "Uit". De validatie is gelijk aan de CHECK.
- `/privacy` en `docs/PRIVACY.md`: stille uren als profielgegeven.
**Buiten scope:**
- Stille uren per spot of per dag van de week.
- Een "niet storen"-knop voor een tijdje.
- Het operatorvenster 08:00–22:00 van WP-22. Dat blijft apart: het gebruiksrapport valt niet onder de stille uren van Lars' profiel.
- Het tijdvenster van alertregels (`earliest_local`/`latest_local`). Dat bepaalt welke uren in een window tellen, niet wanneer je een melding krijgt.
**Contracten:**
- Kolommen `profiles.quiet_from time null` en `profiles.quiet_until time null`, met CHECK `(quiet_from is null) = (quiet_until is null) and (quiet_from is null or quiet_from <> quiet_until)`.
- `shakka.domain.quiet`:
  - `QuietHours(start: time, end: time)` (frozen; `ValueError` bij `start == end`);
  - `quiet_hours_from_row(row: Mapping[str, Any]) -> QuietHours | None`;
  - `in_quiet_hours(now: datetime, quiet: QuietHours | None) -> bool`. `now` moet aware zijn. Lokaal halfopen `[start, end)`; bij `start > end` loopt de periode over middernacht. `None` geeft `False`.
- `shakka.jobs.alerts.AlertJobResult` krijgt een laatste veld `quiet: int = 0` (aantal gebruikers dat deze run stil was).
- `web/src/lib/forms.ts`: `parseQuietHours(from: string, until: string): { quiet_from: string | null; quiet_until: string | null } | { error: string }`.
**Acceptatiecriteria:**
- AC-1: `supabase test db` is groen. Daarin:
  - de CHECK weigert alleen `quiet_from` gezet, en weigert `quiet_from = quiet_until`;
  - A kan zijn eigen stille uren wijzigen en die van B niet.
- AC-2: `cd ingest && uv run pytest tests/test_quiet.py`:
  - `22:00–07:00` is stil om 23:30 en om 06:59 lokaal, en niet om 07:00 en 21:59;
  - `13:00–14:00` is stil om 13:00 en niet om 14:00;
  - de grenzen kloppen op 29-03-2026 en 25-10-2026 in lokale tijd;
  - `None` is nooit stil;
  - `tests/test_domain_purity.py` is groen.
- AC-3: `tests/test_job_alerts_quiet.py` met `FakeSupabase` en een nep-notifier. Een gebruiker met `22:00–07:00` en een nieuw window om 23:17 lokaal geeft 0 afleveringen, `quiet == 1` en een ongewijzigde `alert_state`. De run om 07:17 met dezelfde data geeft precies 1 `new`-aflevering. Een tweede gebruiker zonder stille uren krijgt om 23:17 gewoon zijn melding.
- AC-4: Een window dat tijdens de stille uren ontstaat en weer verdwijnt, geeft na afloop 0 events. De stap `alerts` krijgt door stilte geen status `partial`.
- AC-5: `cd web && npm run check && npm test && npm run build` slaagt. Componenttests:
  - "Uit" schrijft `quiet_from` en `quiet_until` als `null`;
  - gelijke tijden geven een Nederlandse fout zonder schrijfactie;
  - een geldige keuze schrijft alleen de twee kolommen.
- AC-6: `/privacy` noemt stille uren bij de profielgegevens, en `privacy-page.test.ts` is groen.
**Nodig van Lars:**
- Akkoord op de scopewijziging, vast te leggen in `docs/PROJECT_PLAN.md` sectie 4 ("Alerts").
- Bevestiging van het gedrag: na de stille uren één actuele melding, geen inhaalreeks.
- Na de merge `supabase db push`.
**Omvang:** M

## WP-31: Open aanmelden: crew organiseert zelf
**Mijlpaal:** M5
**Soort:** scopewijziging. Het besluit uit WP-20 "Nodig van Lars" (mogen crewleden zelf organiseren?) en WP-13 (`shouldCreateUser: false`, "open aanmelden komt pas met eigen SMTP"). WP-22 A14 maakt het technisch mogelijk; deze WP maakt de app er klaar voor en ruimt de gevolgen op.
**Afhankelijk van:** WP-20, WP-22, WP-23, WP-25, WP-29
**Bron:** WP-20 A16, R7 en "Gevolgen" (WP-22/WP-24); WP-13 review N-9; WP-22 A14, R4, R5 en "Buiten scope" (onbevestigde Auth-gebruikers opruimen: "hoort bij WP-23", maar WP-23 doet het niet).
**Doel:** Iedereen uit de crew kan met alleen een e-mailadres een account maken en zelf een sessie organiseren. Accounts die nooit bevestigd zijn, worden automatisch verwijderd.
**In scope:**
- Spotpagina: de knop "Ik ga" bij een reeks go-uren is er ook voor uitgelogde bezoekers. Die gaat via de bestaande route `/go` naar `/login` met terugkeer (WP-20 AC-2), met de hint "Log in of maak een account om een sessie te organiseren."
- `/login`: een tekst voor nieuwe gebruikers ("Nog geen account? Vul je e-mailadres in, dan maken we er een."). Staat aanmelden server-side uit, dan blijft de melding `notAuthorized` (WP-22).
- Een migratie met de service-only RPC `purge_unconfirmed_users`, plus pgTAP en de functielijsten in `07_sessions.test.sql`.
- `shakka.jobs.accounts` en de pipelinestap `unconfirmed_users_cleanup`, direct vóór `usage_report`.
- `/privacy`, `docs/PRIVACY.md` en `retention-consistency.test.ts`: de bewaartermijn voor onbevestigde accounts.
- RUNBOOK: de volgorde "eigen SMTP werkt → WP-29 → 'Allow new users to sign up' aan", en dat Lars testaccounts via Add user met "Auto Confirm User" aanmaakt (anders verwijdert de opruimstap ze).
**Buiten scope:**
- Een openbare lijst van sessies, of sessies zoeken. Dat zou een open markt tussen vreemden worden, een non-goal.
- CAPTCHA (geparkeerd).
- Uitnodigingscodes.
- Wijzigingen aan de rate limits van WP-19.
**Contracten:**
- RPC `public.purge_unconfirmed_users(p_now timestamptz) returns integer`:
  - `security definer`, `set search_path = ''`, uitvoerbaar alleen door `service_role`;
  - verwijdert `auth.users` met `email_confirmed_at is null and created_at < p_now - <termijn>`.
  - De cascade ruimt `profiles` op.
- `shakka.jobs.accounts`:
  - `UNCONFIRMED_USER_RETENTION: Final = timedelta(hours=24)` (voorstel; de inloglink verloopt na 1 uur);
  - `PURGE_UNCONFIRMED_RPC: Final = "purge_unconfirmed_users"`;
  - `purge_unconfirmed_users(db, *, now: datetime) -> int`.
- Pipeline: `STEPS` wordt … `sessions_cleanup`, `unconfirmed_users_cleanup`, `usage_report`.
- `web/src/lib/privacy.ts`: `UNCONFIRMED_ACCOUNT_RETENTION_HOURS = 24`.
**Acceptatiecriteria:**
- AC-1: `supabase test db` is groen. Daarin:
  - een onbevestigde gebruiker van 25 uur oud wordt verwijderd, inclusief zijn `profiles`-rij;
  - een onbevestigde van 23 uur oud en een bevestigde van 30 dagen oud blijven;
  - `anon` en `authenticated` kunnen de functie niet uitvoeren;
  - `07_sessions.test.sql` noemt de functie in de lijst voor `service_role` en in de lijst van `security definer`-functies.
- AC-2: `cd ingest && uv run pytest tests/test_pipeline.py`. `STEPS` eindigt op `sessions_cleanup`, `unconfirmed_users_cleanup`, `usage_report`. Faalt de nieuwe stap, dan wordt de run `partial` zonder dat andere stappen geraakt worden. Het aantal verwijderde accounts staat in `counts`, zonder ids of adressen.
- AC-3: `test_session_retention_matches_migration` en een nieuwe test `test_unconfirmed_retention_matches_migration` zijn groen. `retention-consistency.test.ts` vergelijkt `UNCONFIRMED_ACCOUNT_RETENTION_HOURS` met de Python-constante.
- AC-4: `cd web && npm run check && npm test && npm run build` slaagt.
  - Een spotpaginatest: uitgelogd met go-uren toont de knop "Ik ga" met een link naar `/go?spot=…&start=…&end=…` en de hint;
  - ingelogd blijft het gedrag van WP-20 ongewijzigd;
  - een logintest toont de tekst voor nieuwe gebruikers.
- AC-5: `/privacy` noemt dat onbevestigde accounts na 24 uur worden verwijderd. `privacy-page.test.ts` is groen.
- AC-6: Met aanmelden aan: een e-mailadres dat geen teamlid is, maakt via de app een account, krijgt de mail, logt in (link of code) en organiseert een sessie. Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- Akkoord op de scopewijziging (crew maakt zelf accounts en organiseert), vast te leggen in `docs/PROJECT_PLAN.md`.
- Bevestiging van de termijn voor onbevestigde accounts (voorstel 24 uur).
- Na de merge `supabase db push`, en daarna "Allow new users to sign up" aanzetten.
**Omvang:** M

## WP-32: `cell_selection` per spot
**Mijlpaal:** M5
**Soort:** besluit Lars, voorwaardelijk. Start pas als Lars een concrete spot aanwijst waar de standaard `sea` aantoonbaar een slechte rastercel kiest (bijv. een meer bij een grof model). Zonder zo'n geval blijft deze WP `todo`.
**Afhankelijk van:** WP-02, WP-03, WP-12, WP-22, WP-23, WP-26
**Bron:** NIGHT.md beslissing 2; bevestigde beslissing WP-03 (`cell_selection=sea`: "per spot te herzien in WP-22"); WP-03 R3 en "Buiten scope"; WP-12 "Buiten scope"; WP-22 "Buiten scope" ("er is nog geen geval").
**Doel:** Per spot de rastercel van Open-Meteo kunnen kiezen (`land`, `sea` of `nearest`). De globale standaard blijft `sea`.
**In scope:**
- Een optioneel veld `cell_selection` in `data/spots.yaml` en `shakka.domain.spot.SpotProfile`, met validatie.
- Een migratie met kolom `spots.cell_selection text null` en een CHECK, plus pgTAP. De aanpassingen uit WP-02 R7: `SPOT_COLUMNS`, `to_row` en de kolomtest (die moet de `alter table` meenemen).
- `shakka.openmeteo.forecast`: locaties per chunk groeperen op effectieve `cell_selection`. Per groep één request; het gewicht per locatie blijft gelijk.
- Marine alleen als de planner verifieert dat de Marine API `cell_selection` ondersteunt. Anders blijft marine ongewijzigd, en dat staat in de blueprint.
- `docs/SPOT_DATA.md`: wanneer je dit veld invult, met de definities van Open-Meteo.
**Buiten scope:**
- Een model per spot kiezen.
- Feitelijke waarden invullen (Lars).
- Golfmodel per spot.
- De UI: het veld is niet zichtbaar in de app.
**Contracten:**
- `shakka.domain.spot`: `CellSelection` (StrEnum: `land`, `sea`, `nearest`) en `SpotProfile.cell_selection: CellSelection | None = None`.
- Kolom `spots.cell_selection text null`, CHECK `in ('land', 'sea', 'nearest')`.
- `shakka.domain.forecast.SpotLocation` krijgt `cell_selection: str = "sea"`.
- `build_forecast_params` neemt de `cell_selection` van de locaties (allemaal gelijk binnen één aanroep; anders `ValueError`).
- `fetch_forecast` groepeert.
- `DEFAULT_CELL_SELECTION: Final = "sea"`.
**Acceptatiecriteria:**
- AC-1: `cd ingest && uv run pytest tests/test_spots_validation.py`. `cell_selection: ocean` geeft een `SpotValidationError` met de spot-id en de veldnaam, en het veld weglaten is geldig. `from_row(to_row(s)) == s` geldt met en zonder het veld.
- AC-2: `tests/test_openmeteo_forecast.py`, met MockTransport en drie spots: één met `land`, één met `sea` en één zonder veld. Er gaan precies 2 requests uit: `cell_selection=land` met 1 locatie en `cell_selection=sea` met 2. Het totale geboekte gewicht is gelijk aan dat van 3 locaties.
- AC-3: `supabase test db` is groen, en `spots.cell_selection = 'ocean'` wordt geweigerd. `uv run shakka spots validate` geeft exitcode 0 op `data/spots.yaml`.
- AC-4: `docs/SPOT_DATA.md` beschrijft het veld met de drie waarden en de bron https://open-meteo.com/en/docs.
- AC-5: Lars vult het veld in voor de aangewezen spot. Na een uurlijkse run verschilt de wind in `forecast_hours` voor die spot aantoonbaar van die met `sea`; Lars vergelijkt met `shakka forecast fetch --dry-run` en de pagina. Dit is `NEEDS_LARS`.
**Nodig van Lars:** De spot (of spots) en de gewenste waarde, met je waarneming waarom `sea` niet klopt. Na de merge `supabase db push`.
**Omvang:** S

## WP-33: Eigen app-icoon en installeerbaarheid
**Mijlpaal:** M5
**Soort:** besluit Lars, voorwaardelijk. Start als Lars een icoon aanlevert, of als WP-23 AC-6 (Lighthouse en installeerbaarheid) bevindingen oplevert die WP-23 niet heeft opgelost.
**Afhankelijk van:** WP-13, WP-23
**Bron:** WP-13 A3 (placeholder-icoon, "later vervangen door een eigen ontwerp met dezelfde bestandsnamen"); NIGHT.md beslissing 7; bevestigde beslissing WP-13 ("placeholder-icoon tot er een echt icoon is"); WP-23 AC-6 en A17 (installeerbaarheid via DevTools).
**Doel:** Shakka krijgt een eigen icoon op het beginscherm van iOS en Android, en de installeerbaarheidscontrole in Chrome geeft geen fouten.
**In scope:**
- Lars' ontwerp omzetten naar de bestaande bestandsnamen en afmetingen: 192, 512 en maskable 512, plus het Apple-touch-icoon en de favicon, voor zover WP-13 die heeft (de planner inventariseert dat).
- `web/scripts/make-placeholder-icons.mjs` verwijderen of laten staan als hulpmiddel. De planner beslist en noteert het.
- Bevindingen uit `docs/wp/WP-23/verification.md` (AC-6) over installeerbaarheid en PWA-metadata die zonder nieuwe functionaliteit op te lossen zijn.
**Buiten scope:**
- Splash screens per apparaat, schermafbeeldingen in het manifest, een nieuwe huisstijl of kleuren in de app.
- Bevindingen die een gedragswijziging vragen (die worden een besluit van Lars).
**Contracten:** De bestandsnamen en het manifest van WP-13 blijven ongewijzigd. Elke wijziging aan het manifest staat in de blueprint.
**Acceptatiecriteria:**
- AC-1: `cd web && npm run check && npm test && npm run build && npm run verify:build` slaagt.
- AC-2: Een test leest de PNG-headers van de iconen in `web/static/` en toont de exacte afmetingen uit het manifest (192×192, 512×512, en maskable 512×512). Het manifest verwijst alleen naar bestaande bestanden.
- AC-3: `node scripts/check-bundle-size.mjs` (WP-23) blijft binnen het precachebudget.
- AC-4: Chrome DevTools → Application → Manifest geeft bij "Installability" geen fouten, en het icoon is goed te zien op het beginscherm van een iPhone en een Android-toestel (maskable zonder afgesneden rand). Dit is `NEEDS_LARS`.
**Nodig van Lars:**
- Het icoonontwerp, bij voorkeur als SVG of een PNG van minstens 1024×1024, met een veilige zone voor maskable.
- De installeerbaarheidsbevindingen uit WP-23 AC-6.
**Omvang:** S

## WP-34: Visueel ontwerp: strak, licht en donker
**Mijlpaal:** M5
**Soort:** besluit Lars. Het is een verzoek van Lars van 28 oktober 2026: "het is echt heel lelijk. ik wil dat je het er mooi en strak uit laat zien." De functionaliteit verandert niet. Alleen het uiterlijk verandert.
**Afhankelijk van:** WP-13, WP-14, WP-15, WP-16, WP-20, WP-21, WP-23, WP-30. Bouwen na WP-30, want die raakt ook `/web` (profiel). Niet parallel met andere WP's die `/web` raken (WP-24, WP-29, WP-31, WP-33), omdat `app.css` en de pagina's anders conflicteren.
**Bron:** het verzoek van Lars van 28 oktober 2026, met zijn stijlkeuze:
- strak en licht als basis: wit en lichtgrijs, met één accentkleur zeeblauw;
- kaarten met een zachte schaduw;
- per spot een groot, duidelijk go/no-go-label, zoals in een moderne weer-app;
- een donkere modus die automatisch `prefers-color-scheme` volgt.

Daarnaast WP-33 "Buiten scope" ("een nieuwe huisstijl of kleuren in de app").
**Doel:** Shakka ziet er op een telefoon strak en verzorgd uit, in een lichte en een donkere modus. Wat de app doet en toont blijft gelijk. Contrast en toegankelijkheid blijven in beide modi minstens WCAG AA.
**In scope:**
- **Design tokens** als CSS custom properties in `web/src/app.css`:
  - kleuren, vlakken, randen, schaduw, radius, afstanden en een typografische schaal;
  - een lichte set in `:root` en een donkere set in `@media (prefers-color-scheme: dark)`;
  - `color-scheme: light dark`, zodat formulierelementen en scrollbars meegaan.
- **Kleuren alleen via tokens.** Alle vaste kleuren in componenten en routes gaan naar tokens. Nu staan er hexwaarden in de `<style>`-blokken van `spot/[id]`, `sessie/[slug]/delen`, `mijn-sessies` en `MapView.svelte`.
- **Typografie:** alleen de systeemfontstack, met een vaste schaal voor koppen, tekst en kleine tekst.
- **Layout en navigatie:**
  - mobile-first, met de huidige `max-width` of een betere;
  - een header die op 375 px breed niet overloopt (inclusief e-mailadres en de knop "Uitloggen");
  - aanraakdoelen voor navigatie en knoppen van minstens 44×44 px;
  - het liefst zonder JavaScript-menu. Komt er toch een, dan staat het in de blueprint en verandert het geen route of link.
- **Spotlijst (`/`):**
  - elke spot is een kaart met een zachte schaduw;
  - de kaart toont een groot go/no-go-label voor vandaag (`VerdictBadge`, met een groottevariant) en een kleiner label voor morgen;
  - naam, regio, favorietster, "niet geverifieerd" en de dagtekst blijven staan.
- **Overige pagina's in dezelfde stijl:**
  - spotpagina (uren, golven, profiel);
  - kaartweergave: `MapSwitch`, de laad- en foutmelding van `MapView` en de markers volgen de verdict-tokens;
  - `/profiel`, `/alerts`, `/login`, `/mijn-sessies`, `/sessie/nieuw`, `/sessie/[slug]/beheer` en `/sessie/[slug]/delen`;
  - de publieke sessiepagina `/s/[slug]`, `/go`, `/over` en `/privacy`;
  - banners, foutmeldingen, formulieren, fieldsets en knoppen (primair, secundair, `danger`).
- **Focus en toegankelijkheid:**
  - een zichtbare focusring met minstens 3:1 contrast in beide modi;
  - tekst minstens 4.5:1 en niet-tekst minstens 3:1;
  - een oordeel nooit alleen via kleur: het label blijft tekst;
  - animaties of transities alleen met `prefers-reduced-motion: reduce`-uitzondering.
- **PWA-themakleur:**
  - `app.html` krijgt twee `<meta name="theme-color">`, met `media="(prefers-color-scheme: light)"` en `media="(prefers-color-scheme: dark)"`;
  - `theme_color` en `background_color` in `web/static/manifest.webmanifest` gaan naar de lichte waarden. Het manifest kent geen media query.
- **Contrasttest:** `web/test/contrast.test.ts` wordt omgebouwd naar kleurparen per modus, met de waarden uit `app.css` gelezen (zie Contracten).
- **Screenshots:** de hoofdpagina's in licht en donker op 375×812 in `docs/wp/WP-34/screens/` (zie AC-7).

**Buiten scope:**
- Een handmatige thema-schakelaar of een opgeslagen themavoorkeur. De app volgt alleen `prefers-color-scheme`. Een schakelaar zou nieuw gedrag en opslag zijn.
- Een donkere kaartstijl van MapTiler. `MAPTILER_STYLE_ID` blijft `streets-v4`; zie de vraag aan Lars.
- Een nieuw app-icoon of favicon (WP-33).
- Andere teksten, labels (`labels.ts`), routes, volgorde of data, en alle domeinlogica.
- Externe fonts, icon-fonts of CDN's.
- Een CSS-framework dat bij de build of in de browser iets van het netwerk haalt.
- Wijzigingen aan de CSP in `web/static/_headers`.

**Contracten:**
- **Tokennamen in `app.css`.** Elke token staat in `:root` én in het donkere blok.
  - Kleuren: `--color-bg`, `--color-surface`, `--color-surface-muted`, `--color-text`, `--color-muted`, `--color-border`, `--color-accent`, `--color-on-accent`, `--color-focus`, `--color-header-bg`, `--color-header-text`, `--color-go`, `--color-marginal`, `--color-no-go`, `--color-none`, `--color-on-verdict`, `--color-error`, `--color-warning-bg`, `--color-notice-bg`.
  - Overige tokens: `--shadow-card`, `--radius`, `--radius-lg`, `--space-1` t/m `--space-6` en `--font-size-sm`, `--font-size-base`, `--font-size-lg`, `--font-size-xl`, `--font-size-verdict`.
  - De bestaande namen `--color-brand` (= `var(--color-accent)`), `--color-text`, `--color-muted`, `--color-bg` en `--color-error` blijven bestaan.
- **Hexkleuren alleen in de tokenblokken.** Hexkleuren staan alleen in de twee tokenblokken van `app.css`, plus de theme-color-metatags in `app.html` en het manifest. `.svelte`-bestanden bevatten geen hexkleur.
- **`VerdictBadge`.**
  - Props: `{ verdict: Verdict; size?: 'sm' | 'lg' }`, met standaard `'sm'`.
  - De klassen `verdict` en `verdict-{verdict}` en het attribuut `data-verdict` blijven.
  - `size='lg'` voegt de klasse `verdict-lg` toe.
- **DOM-haken blijven ongewijzigd:** `data-spot`, `data-verdict`, `.spot-list`, `.spot-item`, `.spot-link`, `.skip-link`, `#main` en `.site-header`. Bestaande tests selecteren erop.
- **Contrasttest leest uit `app.css`.** `contrast.test.ts` leest de tokenwaarden per modus uit `app.css`, met een kleine parser in `web/test/helpers/tokens.ts`: `readTokens(css: string): { light: Record<string, string>; dark: Record<string, string> }`. Hij toetst `PAIRS` als tokenparen, bijv. `['--color-text', '--color-bg', 4.5]`, in beide modi.
- **Geen nieuwe dependency in `web/package.json`.** Wil de planner toch een UI-library, dan alleen als die klein en gratis is (MIT/ISC of vergelijkbaar), geen netwerkverkeer doet en in de blueprint gemotiveerd wordt. Zelfgeschreven CSS heeft de voorkeur.

**Acceptatiecriteria:**
- AC-1: `cd web && npm run check && npm test && npm run build && npm run verify:build` slaagt. `node scripts/check-bundle-size.mjs` blijft binnen het precachebudget.
- AC-2: Er verandert geen gedrag.
  - `git diff develop...wp/WP-34 --name-only -- web/src` toont alleen `.svelte`- en `.css`-bestanden en `app.html`.
  - Een uitzondering staat in de blueprint onder "Niet-CSS-wijzigingen", met reden, en verandert geen exportsignatuur.
  - Bestaande tests in `web/test/` worden niet inhoudelijk gewijzigd, met uitzondering van `contrast.test.ts`. Een andere aanpassing (bijv. een selector) staat met reden in de blueprint.
- AC-3: `npm test -- contrast` is groen.
  - Elke kleurtoken staat in de lichte en de donkere set (de sets van tokennamen zijn gelijk).
  - Elk paar in `PAIRS` haalt in beide modi zijn minimum: 4.5 voor tekst, 3 voor niet-tekst. De paren omvatten minstens:
    - tekst, muted en accent op `--color-bg` en `--color-surface`;
    - `--color-on-verdict` op go, marginal, no-go en none;
    - `--color-on-accent` op accent;
    - `--color-header-text` op `--color-header-bg`;
    - error op bg en op `--color-warning-bg`;
    - `--color-focus` op bg en surface.
  - De inventaristest faalt als een `.svelte`-bestand een hexkleur bevat.
- AC-4: Een test leest `web/src/app.html` en vindt precies twee `theme-color`-metatags, één voor licht en één voor donker. Hun waarden zijn gelijk aan `--color-header-bg` van de modus in `app.css`. `theme_color` in het manifest is gelijk aan de lichte waarde.
- AC-5: Geen externe bronnen.
  - `rg -n "@import|@font-face|fonts\.googleapis|fonts\.gstatic|cdn\." web/src web/static` geeft geen treffers die naar een andere origin wijzen.
  - `web/static/_headers` is ongewijzigd: `git diff develop...wp/WP-34 -- web/static/_headers` is leeg.
  - Het build-artefact bevat geen `https://`-URL in CSS-bestanden.
- AC-6: De bestaande a11y-tests (`web/test/a11y-*.test.ts`) zijn groen. Een nieuwe componenttest rendert `VerdictBadge` met `size="lg"` en controleert:
  - de klassen `verdict`, `verdict-go` en `verdict-lg`;
  - het attribuut `data-verdict="go"`;
  - de tekst uit `verdictLabel('go')`.
- AC-7: Screenshots in `docs/wp/WP-34/screens/` op 375×812 (DPR 1 of 2), elk als `<pagina>-light.png` en `<pagina>-dark.png`. Dat zijn 16 bestanden voor deze pagina's:
  - `home` (lijst);
  - `home-map` (kaart, of de foutmelding als er geen MapTiler-key is);
  - `spot`;
  - `login`;
  - `profiel`;
  - `alerts`;
  - `mijn-sessies`;
  - `sessie` (publieke `/s/[slug]`).

  De modus wordt geëmuleerd met `prefers-color-scheme` (bijv. Chrome DevTools "Rendering" of de preview-tool), dus niet met een schakelaar in de app. Bij elke pagina geldt `document.documentElement.scrollWidth <= 375`; de verifier noteert de waarde in `verification.md`. De planner legt in de blueprint vast waar de data voor ingelogde pagina's en de sessiepagina vandaan komt (lokale Supabase met seed of de preview-deploy).
- AC-8: Op de screenshots van `home` en `spot` is in beide modi zichtbaar:
  - de footer met de bronvermelding (Open-Meteo, KNMI, Rijkswaterstaat, CC BY 4.0);
  - op `home`: per spot een kaart met een groot label voor vandaag.

  Op `home-map` is de kaartattributie (MapTiler, OpenStreetMap, MapLibre) zichtbaar als de kaart laadt.
- AC-9: Lars bekijkt de screenshots en de app op zijn eigen telefoon in licht en donker. Hij keurt het ontwerp goed, of geeft punten terug. Dit is `NEEDS_LARS`.

**Nodig van Lars:**
- Akkoord op het ontwerp via de screenshots (AC-9).
- De keuze of de kaart in de donkere modus licht blijft (voorstel: ja, `streets-v4` ongewijzigd) of een donkere MapTiler-stijl krijgt. Dat laatste is een vervolg-WP: een extra stijl en markers op donkere tegels.
- Optioneel: een voorkeur voor de exacte tint zeeblauw. Zonder voorkeur kiest de planner er een die in beide modi AA haalt.

**Omvang:** M. Vrijwel alles is CSS, maar het raakt ongeveer 25 bestanden. Wordt de blueprint groter dan M, dan splitst de planner hem in WP-34a en WP-34b:
- WP-34a: tokens, header, footer, spotlijst, spotpagina en kaartweergave;
- WP-34b: profiel, alerts, login en sessiepagina's.

---

## Geoogst, maar niet als v2-WP opgenomen

Elk uitgesteld punt uit de v1-documenten staat óf in een v2-WP hierboven, óf in deze tabel met de reden. Zo valt niets tussen wal en schip.

### Al gedekt door WP-22 of WP-23

Komt een punt er bij de herziening van WP-22 toch uit, dan gaat het naar de genoemde v2-WP.

| Punt | Bron | Gedekt door | Valt anders naar |
|---|---|---|---|
| Dubbele `browserStorage` opruimen | WP-20 "Gevolgen", WP-21 A20, deviations, "Gevolgen" | WP-23 A19 (APPROVED) | WP-27 (als web-opruimpunt) |
| `fetched_at` in `evaluations` / eerlijke versheid | WP-14 A5, R3, "Gevolgen" | WP-22 A11 (veroudering per spot, zonder nieuwe kolom) | WP-27 |
| Veroudering per spot bij meer dan één forecast-chunk | WP-11 review N-1, "Gevolgen" | WP-22 A11 | WP-27 |
| Tijdsbudget voor de hele run | WP-04 R5, WP-11 N-5 | WP-22 A12 | WP-27 |
| Bovengrens `starts_at` (privacybelofte bewaartermijn) | WP-19 review N-4 | WP-22 A13 (review B-5 nog open) | WP-25 |
| Open aanmelden technisch (`shouldCreateUser: true`) | WP-13 deviation 3 | WP-22 A14 | WP-31 |
| Eigen SMTP, Auth-rate-limits | WP-13, WP-18, WP-20 | WP-22 A15 en A16 (review B-3: niet Brevo) | WP-29 (voorwaarde) |
| Retry-limiet push, host-allowlist, grens op abonnementen | WP-17 R1, N-10; WP-18 A8 | WP-22 A8 t/m A10 | – |
| Actions op SHA pinnen | WP-11 R8 | WP-22 A17 | WP-28 |
| `profiles.telegram_chat_id` verwijderen | A-16 | WP-22 | – |
| Golfmodellen in de bronvermelding | WP-12 review N-9 | WP-23 A18 | – |
| `X-Robots-Tag` voor `/s/*`, CSP, `Referrer-Policy` | WP-21 A18, WP-15 R7 | WP-23 | – |
| `shakka:return_to` opruimen | WP-23 review B-1a | WP-23 A21 | – |

### Na de testweek, na een besluit van Lars

Kalibratie: hier staat nog geen WP. Wordt er na een testweek iets gewijzigd, dan wordt dat een eigen kleine WP met de gekozen waarden.

| Punt | Bron |
|---|---|
| Eén model aflandig terwijl de consensus rijdbaar is (O1) | WP-05 "Open punten" |
| Vlagen ten opzichte van `max_kn` (O2), vlaagratio bij hogere wind (O3), vlaagcorrectie per model | WP-05 O2, O3, R2 |
| Drempels evaluatie, daglichtmarge, spreiding | WP-05 "Drempelwaarden", STATUS |
| Defaults `min_go_hours` en `days_ahead` | WP-07 R1, STATUS |
| Dedup-drempels (2 uur, 4 kn), klapperen bij splitsen en samensmelten | WP-08 R1, R2 |
| Factoren kite-advies, voorbeeldtabel (`checked_by_lars`) | WP-06 R1, STATUS |

### Geparkeerd, met een trigger

| Punt | Bron | Waarom niet nu | Wanneer wel |
|---|---|---|---|
| CAPTCHA op RSVP | Kandidatenlijst van Lars; WP-22 "Buiten scope" | Vergt een script van derden in de browser (privacy, CSP `script-src 'self'`) en een server-side controle buiten PostgREST. Is een scopewijziging. | Bij aantoonbaar misbruik dat WP-25 (moderatie) niet oplost. |
| `pushsubscriptionchange`-handler | WP-18 A12 | Vraagt een sessie in de service worker. Nu ruimt WP-17 het oude endpoint op (410) en zet de gebruiker push opnieuw aan. | Als gebruikers dit in de praktijk vaak merken. |
| Gedeelde `requests.Session` voor push, inputs delen tussen evaluatie- en alertjob, `profiles` zonder filter, evaluatie per favoriet cachen | WP-17 R3; WP-10 R5 en R7; WP-11 A8; WP-10 review N-4 | Alleen performance of egress op schaal. Het runbudget en de maandcheck dekken het. | Egress boven 3,5 GB per maand (WP-22 maandcheck), meer dan 500 gebruikers, of runs tegen het runbudget. |
| Directe melding bij een `partial` die blijft hangen | WP-11 R4, WP-12 A15 | Het weekrapport (WP-22) toont stappen die niet `ok` waren. | Als het weekrapport te laat blijkt. |
| `least(p_now, now())` in de purge | WP-19 review N-10 | Geen bekend probleem; zou een bestaande test breken. | Bij een incident met de klok. |
| Capaciteitscontrole meerijders, `seats_free` koppelen aan RSVP's | WP-19 en WP-21 "Buiten scope" | Is een nieuwe feature, geen afmaken. | Op verzoek van Lars (scopewijziging). |
| Meldingen aan deelnemers, dynamische OG-previews | WP-20 en WP-21 "Buiten scope" | Deelnemers hebben geen account; de site is statisch (geen server voor previews). | Niet binnen de huidige architectuur. |
| Golven op de publieke sessiepagina | WP-12 "Gevolgen" | Nieuwe weergave, niet gevraagd. | Op verzoek van Lars. |
| `formatWindowLocal` en `sessionWindowText` samenvoegen | WP-20 "Gevolgen", WP-23 A19 | Bewust twee formaten voor twee doelen. | – |
| Opruimronde over `shakka:rsvp:*`, data-export, MapLibre uit de precache, CSP-nonces of -rapportage | WP-21 "Gevolgen", WP-23 A5, A9 en "Buiten scope" | Bewuste keuzes in WP-23; rapportage vraagt een extra dienst. | Als het precachebudget of de privacy dat vraagt. |
| `npm audit` of `pip-audit` als CI-stap, `uv audit` | WP-22 A17 | Willekeurige PR's zouden rood worden door nieuwe advisories. | Eventueel als losse geplande workflow, na WP-28. |
| `skipWaiting` of een melding "nieuwe versie" | WP-13 A7, WP-18 "Buiten scope" | Bewuste keuze: oude shell en chunks passen altijd bij elkaar. | Als gebruikers lang op een oude versie blijven hangen. |
| ESLint en Prettier, Supabase-typegeneratie | WP-13 en WP-14 "Buiten scope" | Tooling zonder gebruikerswaarde; `svelte-check` en de schematests dekken de types. | Op verzoek. |
| Clustering op de kaart, volgorde of notities bij favorieten, bevestigingsdialogen | WP-15 en WP-16 "Buiten scope" | Nieuwe features, niet gevraagd. Geolocatie blijft uitgesloten (privacy). | Op verzoek van Lars. |

## Wat Lars moet aanleveren vóór de start van v2

**Vóór golf 1 (WP-25, WP-26, WP-27, WP-28):**
1. Akkoord op deze opdeling (STATUS: "Opdeling v2: wacht op akkoord van Lars.").
2. WP-22 en WP-23 op `done`, gemerged en met `supabase db push` toegepast.
3. Voor WP-28: akkoord om WP-22 A17 ("geen Dependabot") terug te draaien.
4. Voor WP-25: bevestiging dat "sessie sluiten" "aanmelden sluiten zonder annuleren" betekent.
5. Voor WP-26: akkoord op 8 dagen forecast.

**Vóór golf 2 en 3:**
- WP-29: eigen SMTP draait (WP-22). Daarna de templatetekst instellen en akkoord geven op het verdwijnen van het plakveld.
- WP-30: akkoord op de scopewijziging stille uren.
- WP-24: akkoord op de scopewijziging e-mailkanaal, de keuze Resend of Postmark (niet Brevo; Postmark gratis is maar 100 per maand), een geverifieerd afzenderdomein, `EMAIL_API_KEY`, `EMAIL_PROVIDER`, `ALERT_EMAIL_FROM` en het dagbudget.
- WP-31: akkoord op de scopewijziging open aanmelden en de termijn voor onbevestigde accounts.

**Voorwaardelijk:**
- WP-32: een spot waar `sea` aantoonbaar niet klopt.
- WP-33: een icoonontwerp en/of de bevindingen van WP-23 AC-6.

**Op verzoek (28 oktober 2026):**
- WP-34: de keuze licht of donker voor de kaart in de donkere modus, en na de bouw het akkoord op de screenshots.
