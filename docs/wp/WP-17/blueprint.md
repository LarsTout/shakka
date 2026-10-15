# Blueprint WP-17: Web Push: backend (enige meldingskanaal)
Status: APPROVED
Revisie: 2

## Doel
Alerts als Web Push afleveren, het enige meldingskanaal (A-16), naar alle geregistreerde apparaten van een gebruiker, en dode abonnementen automatisch opruimen:
1. Migratie `push_subscriptions` met RLS, grants en pgTAP-tests.
2. `shakka.domain.push` (puur): een `AlertMessage` inkorten tot een pushtekst (titel hoogstens 50, body hoogstens 150 tekens) en de payload bouwen.
3. `shakka.notify.base` (kanaalinterface) en `shakka.notify.webpush.WebPushNotifier` (pywebpush, VAPID, TTL 12 uur, `tag` per `alert_state`, 404/410 permanent, geen endpoints of sleutels in logs of exceptions).
4. `shakka.jobs.alerts` uitbreiden: doelen laden, afleveren tussen "plannen" en "opslaan", afleverregel, alles-of-niets per (gebruiker, spot), `id` vooraf toekennen, abonnementen opruimen, `last_notified_at` vullen.
5. `shakka.pipeline.run_hourly(..., notifiers=None)`; zonder VAPID-configuratie is het kanaal uit (waarschuwing), en `run_alerts` gedraagt zich dan als in WP-10.
6. `hourly.yml` geeft de VAPID-secrets door; CLI `shakka alerts test-push --user-id UUID`; RUNBOOK: sleutels maken en beheren.

## Aannames
- **A1. Overgang M1 → push (open punt, voorstel): geen automatische eenmalige stap; een optionele handmatige reset in de RUNBOOK.**
  - Windows die in M1 een `new`-event kregen, staan `active` in `alert_state` met `last_notified_at = NULL`. Door de deduplicatie geven ze pas weer een event bij een wezenlijke wijziging (`improved`, `worsened`, `cancelled`); die wordt wél gepusht, met dezelfde `tag`. Het eerste bericht over zo'n window komt dus niet als push.
  - Dat is acceptabel:
    - het raakt alleen Lars (M1 heeft één gebruiker), die de windows al via de CLI zag;
    - zulke windows liggen hoogstens `days_ahead` dagen vooruit (standaard 3, maximaal 7) en verlopen daarna vanzelf;
    - WP-17 gaat live vóór WP-18. Op het moment van livegang heeft niemand een push-abonnement, dus een eenmalige "opnieuw als `new` behandelen" bij livegang bereikt niemand;
    - een blijvende regel "actieve rijen zonder `last_notified_at` opnieuw als `new` pushen" zou "nooit afgeleverd omdat er geen abonnement was" (`no_target`, zie A6) verwarren met "uit M1", en zou elke run terugkomen bij gebruikers zonder abonnement. Dat past niet bij "één melding per window".
  - Wil Lars na het aanzetten van push (WP-18) de lopende windows alsnog als melding krijgen, dan verwijdert hij zijn actieve rijen (RUNBOOK §14, punt 9): `delete from public.alert_state where user_id = '<id>' and status = 'active';`. De volgende run geeft dan voor elk huidig window een `new`-event, dat gepusht wordt. Een geannuleerde rij die overlapt met een huidig window wordt dan heractiveerd met `new` (WP-08 A8); ook dat wordt gepusht.
  - **Blijvend effect, niet alleen voor M1.** Hetzelfde geldt voor elke gebruiker die push pas aanzet nadat hij al favorieten heeft: de windows die op dat moment lopen, hebben hun `new`-event al gehad (`no_target`, de state schoof door) en komen niet meer als melding, tot een wezenlijke wijziging (`improved`, `worsened`, `cancelled`) of een nieuw window. WP-18 beslist of het daar iets mee doet (bijvoorbeeld een uitleg in de UI bij het aanzetten: "meldingen gelden voor nieuwe windows en wijzigingen"). De handmatige reset uit de RUNBOOK (§14, punt 9) werkt per gebruiker en is de enige ingreep die WP-17 levert.
- **A2. `last_notified_at` = de `now` van de run waarin het event voor het eerst minstens één geslaagde aflevering had.** Afgestemd op WP-10 A2 (in M1 altijd `NULL`) en WP-08 A9 (`diff_windows` wijzigt het veld nooit). Een event zonder geslaagde aflevering (geen abonnement, of alleen permanente fouten) laat het veld ongewijzigd. Wordt een diff door de alles-of-nietsregel opnieuw afgeleverd in een latere run, dan krijgt het veld de `now` van die latere run (de run waarin de state werd opgeslagen). De run-`now` en niet de klok van het moment van versturen: jobfuncties lezen geen klok (afspraak WORK_PACKAGES); het verschil is hooguit enkele minuten.
- **A3. Nieuwe `alert_state`-rijen krijgen altijd vooraf een `id` (`uuid4`), ook zonder pushkanaal.** WP-10 A10 liet de database de `id` kiezen. WP-17 kent hem toe vóór de aflevering (WP-10 en WP-08 "Gevolgen"), zodat `tag` en rij overeenkomen. Om één codepad te hebben gebeurt dat in elke run die niet `dry_run` is; `store_plan` blijft ongewijzigd, want `AlertStateEntry.to_row()` neemt een gezette `id` mee in de insert. Bij `dry_run` blijft `state_id` van een nieuwe rij `None` (WP-10-contract).
- **A4. Afleverregel en alles-of-niets (bindend, uit WORK_PACKAGES en WP-08 "Gevolgen").** Per event:
  - minstens één aflevering geslaagd → het event is afgeleverd (`notified`), de state mag door;
  - geen enkele geslaagd en minstens één niet-permanente fout → het event moet opnieuw (`retryable`);
  - geen enkele geslaagd en alleen permanente fouten → de state mag door, zonder `last_notified_at`;
  - geen (levend) abonnement → `no_target`, de state mag door.

  Is één event van een diff `retryable`, dan wordt voor die (gebruiker, spot) **niets** uit de diff opgeslagen (geen updates, geen inserts, ook geen stille wijzigingen) en komen de berichten niet in `AlertJobResult.messages`; teller `deferred`. De overige events van die diff worden in deze run **niet meer** afgeleverd (vroeg stoppen): de volgende run berekent dezelfde diff en levert alles opnieuw af, dus later afleveren gaf alleen extra dubbele meldingen. Events vóór het mislukte event zijn al afgeleverd en komen de volgende run nog een keer (voor bestaande rijen vervangt dezelfde `tag` de melding; voor een nieuw window kan de gebruiker hem twee keer zien; geaccepteerd in WP-08).
- **A5. Permanent = alleen HTTP 404 en 410** (contract; [web.dev, Web Push Protocol](https://web.dev/articles/push-notifications-web-push-protocol): 404 "The subscription is expired … you should delete the PushSubscription", 410 "should be removed from application server"). Alle andere fouten (400, 403, 413, 429, 5xx, time-outs, verbindingsfouten, onverwachte exceptions) zijn niet-permanent. Gevolg en risico: zie R1.
- **A6. Tellers.** `sent` en `failed` tellen afleveringen (event × abonnement). `no_target` telt events van een gebruiker zonder levend abonnement. `deferred` telt favorieten waarvan de state niet is opgeslagen (A4). `removed` telt verwijderde abonnementen. Erbij (additief): `push_enabled` en `push_failures` (`DeliveryResult.detail` → aantal, bijv. `{"HTTP 410": 1, "HTTP 503": 2}`), voor diagnose in `ingest_runs`.
- **A7. Doelen laden zonder user-id in de URL.** WP-10 A9 garandeert dat `run_alerts` geen user-id in een request-URL zet (`test_no_user_id_in_request_filters`). Daarom laadt `run_alerts` alle abonnementen in één select zonder filter (`load_all_targets`). Het contract `load_targets(db, user_id)` bestaat ook (met filter op `user_id`) en wordt gebruikt door de lokale CLI `test-push` (en later WP-22).
- **A8. Hooguit 10 doelen per gebruiker** (`MAX_TARGETS_PER_USER`, de nieuwste op `created_at`). Een ingelogde gebruiker kan zelf rijen toevoegen; zonder grens kan één account de uurlijkse run vertragen. Een grens in de database hoort bij WP-22 (hardening).
- **A9. VAPID-configuratie: alle drie of geen.**
  - Een waarde telt als afwezig als ze `None` is, leeg na `strip()`, of (alleen bij `VAPID_SUBJECT`) precies `mailto:`. Dat laatste is de waarde uit `.env.example`; zonder deze regel zou een ongewijzigde `.env` als "half ingevuld" gelden.
  - Alle drie afwezig → kanaal uit (`{}`), met een waarschuwing in de log en een `::warning::`-annotatie per run.
  - Eén of twee aanwezig, een ongeldige private key, een ongeldig subject, of een `VAPID_PUBLIC_KEY` die niet bij de private key hoort → `ValueError` met een vaste tekst zonder waarden. In de pipeline maakt dat de stap `alerts` `failed` (run `failed`, exitcode 1, mail van GitHub): een configuratiefout moet opvallen, en anders zou elke aflevering stil falen.
  - **"Geldig subject" = wat py_vapid bij het ondertekenen accepteert** (review B-1). `WebPushNotifier.__init__` zet één proefhandtekening met de echte sleutel en het echte subject; elke exception daaruit wordt de vaste `ValueError` voor `VAPID_SUBJECT`. Zo kan een subject dat pas bij `webpush()` faalt (bijv. `https://shakka.nl/contact`: py_vapid staat bij `https` geen pad toe; `mailto:lars@example`: py_vapid eist een domein met een punt) niet door de constructie komen en daarna elke aflevering `deferred` maken. Geldige vormen in de praktijk: `mailto:<adres>@<domein.tld>` of `https://<host>` zonder pad.
  - `VAPID_SUBJECT` is een e-mailadres en dus een persoonsgegeven. Het komt nooit in een foutmelding, log of uitvoer; als vangnet staat het ook in `secret_values` (redactie van log en `ingest_runs`, review N-11).
- **A10. Sleutelformaat: raw base64url (32 bytes private, 65 bytes publiek, zonder `=`).** `py_vapid.Vapid.from_string` herkent een raw sleutel van 32 bytes (anders DER); PEM werkt daar niet (gecontroleerd in de broncode, zie Externe afhankelijkheden). De nieuwe CLI `shakka alerts vapid-keys` maakt zo'n paar; de publieke sleutel is ook de `applicationServerKey` voor de PWA (`PUBLIC_VAPID_PUBLIC_KEY`, WP-18).
- **A11. `shakka alerts run` (lokaal) levert ook af**, met de notifiers uit `Settings`, net als de uurlijkse run. Anders zou een lokale run de state laten doorschuiven zonder melding. `--dry-run` levert nooit af. `shakka admin alerts preview` levert nooit af.
- **A12. Additieve uitbreidingen van het contract** (alle signatures uit WORK_PACKAGES blijven exact; dit komt erbij):
  - `shakka.notify.base`: `WEBPUSH_CHANNEL`; validatie in `DeliveryResult` en `PushTarget`; `PushTarget.from_row`; `repr=False` voor endpoint en sleutels;
  - `shakka.domain.push`: `PUSH_PAYLOAD_MAX_BYTES`, `PUSH_TAG_MAX`, `ELLIPSIS`, `FALLBACK_TITLE`, `PushPayload`, `shorten_words`, `spot_path`, `push_tag`, `build_push_payload`, `payload_size`;
  - `WebPushNotifier(..., *, ttl_s, timeout_s, webpush_fn)`, `.public_key`, `.send_payload(target, payload)`; `notifiers_from_settings`, `generate_vapid_keys`, `VapidKeys`; `VAPID_PROBE_AUD` en de foutconstanten `INCOMPLETE_ERROR`, `SUBJECT_ERROR`, `PRIVATE_KEY_ERROR`, `PUBLIC_KEY_ERROR`;
  - `shakka.pipeline`: `PUSH_DISABLED_WARNING`, `deferred_warning`; `shakka.logsetup.secret_values` neemt ook het VAPID-subject mee;
  - `shakka.jobs.push` (doelen laden, één event afleveren, abonnementen bijwerken, test-push, sleutels maken);
  - `shakka.jobs.alerts`: `assign_new_ids`, `deliver_plan`, `PlanDelivery`; `AlertJobResult.deferred`, `.removed`, `.push_enabled`, `.push_failures`;
  - `alert_counts` krijgt ook `deferred`, `removed`, `push_enabled`, `push_failures`; de stap `alerts` is ook `partial` bij `deferred > 0`;
  - `PipelineContext.notifiers`;
  - CLI `shakka alerts vapid-keys`; de regel `push: …` in de uitvoer van `shakka alerts run`;
  - tabel: `user_id default auth.uid()`, insert-recht alleen op `user_id, endpoint, p256dh, auth`, CHECKs op formaat en lengte, index op `user_id`.
- **A13. Dependencies:** `pywebpush` (in het plan, gratis, MPL-2.0), plus `py-vapid` en `cryptography` expliciet, omdat de code ze rechtstreeks importeert (sleutel parsen, publieke sleutel afleiden, sleutelpaar maken). Beide komen al mee met pywebpush. Geen nieuwe dienst; push-services van de browsers zijn gratis.

## Ontwerp

### Lagen
```
shakka.cli ── alerts run / test-push / vapid-keys ──> shakka.jobs.alerts / shakka.jobs.push
shakka.pipeline.step_alerts ──> notifiers_from_settings (shakka.notify.webpush) ──> run_alerts
shakka.jobs.alerts ──> shakka.jobs.push ──> shakka.notify.base (Notifier, PushTarget, DeliveryResult)
                                         └─> shakka.domain.push (puur: inkorten, payload)
shakka.notify.webpush ──> pywebpush, py_vapid, cryptography; shakka.domain.push
```
`shakka.domain.push` importeert alleen `json`, `re`, `typing`, `pydantic` en `shakka.domain.messages` (puurheidstest). `shakka.notify` importeert nooit `shakka.jobs` of `shakka.db`.

### Inkorten (`shakka.domain.push`)
`shorten_words(text, limit)` (voor `limit >= 2`, anders `ValueError`):
```
if len(text) <= limit: return text
head = text[: limit - 1]                         # room for "…"
if not text[limit - 1].isspace():                # the cut falls inside a word
    cut = last index i in head with head[i].isspace(), or -1
    if cut > 0: head = head[:cut]
head = head.rstrip(" \t·,;:–-")                  # no dangling separator before "…"
if not head:                                     # one word longer than the limit: no boundary exists
    head = text[: limit - 1].rstrip()
return head + "…"                                # U+2026, one code point
```
Lengtes zijn Unicode code points (`len()` in Python), zoals het contract zegt.

`to_push_text(message)`:
1. `title = shorten_words(message.title, PUSH_TITLE_MAX)`; is `title.strip()` leeg, dan `FALLBACK_TITLE` (`"Shakka"`). De titel is nooit leeg.
2. Body: past `message.body` (`len <= 150`), dan ongewijzigd. Anders `lines = body.split("\n")` en neem regels vanaf het begin zolang `"\n".join(taken + [line])` hoogstens 150 tekens is; stop bij de eerste regel die niet past (geen regels overslaan). Is er minstens één regel genomen, dan `"\n".join(taken)` (zonder "…"). Anders `shorten_words(lines[0], PUSH_BODY_MAX)`.
3. De volgorde van de regels komt uit WP-08 (A11 daar) en wordt niet gewijzigd.

`build_push_payload(message, *, tag)`:
1. `text = to_push_text(message)`; `url = message.go_url or spot_path(message.spot_id)` met `spot_path(id) = f"/spot/{id}"`.
2. `payload = PushPayload(title, body, url, tag)`. Is `payload_size(payload) > 3000` en `go_url` gezet, dan opnieuw met `url = spot_path(spot_id)` (een extreem lange `APP_BASE_URL` blokkeert zo nooit een melding). Is hij dan nog te groot, dan `ValueError` (kan alleen bij een spot-id van duizenden tekens; spot-id's zijn korte slugs).
3. `PushPayload.to_json()` = `json.dumps({"title", "body", "url", "tag"}, ensure_ascii=False, separators=(",", ":"))`, sleutels in die volgorde. `payload_size` = lengte in UTF-8-bytes.

Bovengrens: titel 50 en body 150 code points van hoogstens 4 bytes, of 6 bytes als `\uXXXX`-escape; `tag` hoogstens 64 ASCII-tekens; plus de URL. Zonder `go_url` blijft de payload ruim onder de 3.000 bytes.

### Kanaal (`shakka.notify.base`, `shakka.notify.webpush`)
- `DeliveryResult(ok, permanent_failure, detail)`: `ok and permanent_failure` → `ValueError`. `detail` is altijd een korte, vaste tekst: `"ok"`, `"HTTP <status>"`, `"WebPushException"` of de naam van een exceptietype. Nooit een melding, endpoint, sleutel of user-id.
- `PushTarget`: frozen dataclass; `endpoint`, `p256dh` en `auth` met `field(repr=False)`, zodat ze ook niet via `repr()` in een traceback of assert belanden.
- `WebPushNotifier.__init__` (A9, review B-1), exact in deze volgorde:
  ```
  subject = vapid_subject.strip() if isinstance(vapid_subject, str) else ""
  if not subject or any(c.isspace() for c in subject):          # quick pre-check only
      raise ValueError(SUBJECT_ERROR)
  key = vapid_private_key.strip() if isinstance(vapid_private_key, str) else ""
  try:
      vapid = Vapid.from_string(private_key=key)                 # parsed once, reused per send
  except Exception:
      raise ValueError(PRIVATE_KEY_ERROR) from None
  try:
      vapid.sign({"sub": subject, "aud": VAPID_PROBE_AUD})       # trial signature: the library decides
  except Exception:
      raise ValueError(SUBJECT_ERROR) from None
  self._vapid, self._subject = vapid, subject
  ```
  - Geen eigen regex voor het subject: de bron van waarheid is `py_vapid._check_sub`, via `_base_sign` in `sign`. De proefhandtekening gebruikt dezelfde `Vapid`-instantie (zelfde `conf`, dus strikte controle) die later aan `webpush()` wordt meegegeven, dus wat hier slaagt, slaagt daar ook. `VAPID_PROBE_AUD = "https://push.example.invalid"` voldoet aan de `aud`-controle van `_base_sign` (`^https?://[^/:]+(:\d+)?$`), dus een fout uit `sign` komt van het subject (de sleutel is op dat moment al geparsed).
  - `_base_sign` leest `time.time()` voor `exp`; dat mag hier (notifier, geen domeincode). De handtekening zelf wordt weggegooid; er gaat niets over het netwerk.
  - De sleutelfout gaat vóór de subjectfout (de proef heeft de sleutel nodig); alleen de witruimte-voorcheck van het subject komt eerder.
  - `public_key` = de bijbehorende publieke sleutel (X9.62 uncompressed point, base64url zonder `=`).
- `send(target, message, *, tag)`: `payload = build_push_payload(message, tag=tag)` (een `ValueError` daar → `DeliveryResult(False, False, "ValueError")`), dan `send_payload`.
- `send_payload(target, payload)`:
  ```
  fn = self._webpush_fn or pywebpush.webpush        # looked up at call time (tests patch pywebpush.webpush)
  try:
      fn(subscription_info={"endpoint": target.endpoint,
                            "keys": {"p256dh": target.p256dh, "auth": target.auth}},
         data=payload.to_json(),
         vapid_private_key=self._vapid,              # parsed py_vapid.Vapid instance
         vapid_claims={"sub": self._subject},        # a NEW dict per call: webpush() adds aud/exp to it
         content_encoding="aes128gcm", ttl=self._ttl_s, timeout=self._timeout_s)
  except WebPushException as exc:
      status = exc.status_code
      if status in (404, 410): return DeliveryResult(False, True, f"HTTP {status}")
      return DeliveryResult(False, False, "WebPushException" if status is None else f"HTTP {status}")
  except Exception as exc:
      return DeliveryResult(False, False, type(exc).__name__)
  return DeliveryResult(True, False, "ok")
  ```
  - Nieuwe claims per aanroep is verplicht: `webpush()` zet `aud` (het origin van het endpoint) in de meegegeven dict als die ontbreekt. Een hergebruikte dict zou het `aud` van het eerste push-service naar een ander sturen (gecontroleerd in de broncode, zie Externe afhankelijkheden).
  - `str(exc)` en `exc.message` worden nooit gebruikt: de `WebPushException`-melding bevat de response-body, en een `requests`-fout bevat de URL (het endpoint).
  - `verbose` blijft `False` (pywebpush logt anders claims en headers).
  - Expliciete timeout: `timeout=` gaat naar `requests.post` (`PUSH_TIMEOUT_S = 10.0`).
- `notifiers_from_settings(settings)`: volgt A9; bij een volledige, geldige configuratie `{WEBPUSH_CHANNEL: WebPushNotifier(private, subject)}`. De publieke sleutel uit `Settings` (na `strip()` en zonder afsluitende `=`) moet gelijk zijn aan `notifier.public_key`, anders `ValueError("VAPID_PUBLIC_KEY does not belong to VAPID_PRIVATE_KEY")`. De functie logt niets.
- `generate_vapid_keys()`: `ec.generate_private_key(ec.SECP256R1())`; private = `private_value.to_bytes(32, "big")`, publiek = `public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)`; beide base64url zonder `=`.

### Doelen en aflevering (`shakka.jobs.push`)
- `load_targets(db, user_id)`: `db.select("push_subscriptions", columns=SUBSCRIPTION_COLUMNS, filters={"user_id": f"eq.{user_id}"}, order="created_at.desc", limit=MAX_TARGETS_PER_USER)` → `PushTarget.from_row` per rij. Alleen voor lokaal gebruik (CLI) en WP-22.
- `load_all_targets(db)`: `db.select("push_subscriptions", columns=SUBSCRIPTION_COLUMNS, order="user_id,created_at.desc")` zonder filter; gegroepeerd per `user_id`, per gebruiker de eerste `MAX_TARGETS_PER_USER`. Een rij die `PushTarget.from_row` niet doorstaat (lege waarde; de CHECKs maken dat onmogelijk) wordt overgeslagen, zonder logregel met waarden.
- `deliver_event(notifier, targets, message, *, tag)`: per doel `notifier.send(target, message, tag=tag)` in een `try`; een exception uit de notifier (de interface belooft van niet) wordt een niet-permanente fout met `detail = type(exc).__name__` en één logregel `push: a notifier raised (%s)` met alleen het type. Resultaat `EventDelivery` (zie Interfaces): `retryable = sent == 0 and any(not r.ok and not r.permanent_failure)`.
- `update_subscriptions(db, *, gone, ok, now)`: per blok van `SUBSCRIPTION_BATCH` (100) id's, gesorteerd: `db.delete("push_subscriptions", filters={"id": in_filter(blok)})` voor `gone`, en daarna `db.update("push_subscriptions", {"last_success_at": now}, filters={"id": in_filter(blok)})` voor `ok - gone`. Een `DatabaseError` per blok → foutregel `f"push_subscriptions: {db_error_summary(exc)}"` en door naar het volgende blok. Resultaat `SubscriptionUpdate(removed=<som van delete-counts>, errors=...)`.
- Filters op abonnement-`id` (een willekeurige uuid) staan in de URL; dat is geen user-id, endpoint of sleutel.

### Alertjob (`shakka.jobs.alerts`)
**`assign_new_ids(plan, *, new_id=None)`**: alleen voor `planned`. Voor `i` van `len(plan.previous)` tot `len(new_state)` met `new_state[i].id is None`: `new_state[i].model_copy(update={"id": (new_id or _new_state_id)()})`. Geeft `dataclasses.replace(plan, diff=DiffResult(events=plan.diff.events, new_state=...))`. `_new_state_id()` = `str(uuid.uuid4())`, een module-attribuut dat op het moment van aanroepen wordt opgezocht.

**`deliver_plan(plan, notifier, targets, *, now, gone=())`** (alleen `planned`; elke entry met een event heeft een `id`, anders `ValueError("state id missing; call assign_new_ids first")`):
```
gone_local = set(gone); notified = set(); counters = 0
for index, message in plan.messages:                       # sorted by state_index (WP-10)
    live = [t for t in targets if t.subscription_id not in gone_local]
    if not live: no_target += 1; continue
    d = deliver_event(notifier, live, message, tag=push_tag(plan.diff.new_state[index].id))
    add d.sent, d.failed, d.failures; ok_ids |= d.ok_ids; gone_local |= d.gone_ids; gone_ids |= d.gone_ids
    if d.sent: notified.add(index)
    if d.retryable:
        return PlanDelivery(plan, deferred=True, <counters so far>)     # stop: A4
new_state = [e.model_copy(update={"last_notified_at": now}) if i in notified else e
             for i, e in enumerate(plan.diff.new_state)]
return PlanDelivery(replace(plan, diff=DiffResult(events=plan.diff.events, new_state=new_state)),
                    deferred=False, <counters>)
```
`push_tag(state_id) = f"alert-{state_id}"`.

**`run_alerts(db, *, now, base_url, dry_run=False, notifiers=None)`** (wijzigingen ten opzichte van WP-10 vet):
1. `now` naïef → `ValueError`; `base = normalize_base_url(base_url)`; `ctx = load_alert_context(db, now=now)`.
2. **`push = None if dry_run else (notifiers or {}).get(WEBPUSH_CHANNEL)`.**
3. **`targets = load_all_targets(db) if push is not None and ctx.favorites else {}`** (een `DatabaseError` gaat door, net als bij het laden in WP-10).
4. Per favoriet, zoals WP-10 (plannen, tellers voor `skipped`, `ineligible`, `disabled`). Voor een `planned` favoriet:
   - `dry_run`: zoals WP-10 (`ids` uit `new_state`, nieuwe rijen `None`);
   - **anders: `plan = assign_new_ids(plan)`;**
   - **als `push is not None` en `plan.messages` niet leeg: `d = deliver_plan(plan, push, targets.get(fav.user_id, []), now=now, gone=gone_all)`; tellers optellen; `gone_all |= d.gone_ids`; `ok_all |= d.ok_ids`; `failures.update(d.failures)`. Bij `d.deferred`: `deferred += 1`, log `alerts: no delivery succeeded for a favorite; state kept for a retry` op `WARNING`, en door naar de volgende favoriet (geen opslag, geen berichten). Anders `plan = d.plan`;**
   - `ids = store_plan(db, fav.user_id, plan)` met de foutafhandeling van WP-10 (een `DatabaseError` na een geslaagde aflevering: `write_errors`; de volgende run levert opnieuw af);
   - berichten als `RenderedAlert(user_id, ids[index], message)`.
5. **Als `push is not None` en (`gone_all` of `ok_all`): `u = update_subscriptions(db, gone=gone_all, ok=ok_all, now=now)`; `removed = u.removed`; per foutregel `write_errors += 1` en de regel in `errors`; bij fouten één log `alerts: updating push subscriptions failed (DatabaseError)`.**
6. Opruimen van `alert_state` zoals WP-10 (niet bij `dry_run`).
7. Logregel, alleen aantallen: de WP-10-regel plus ` sent=%d failed=%d no_target=%d deferred=%d removed=%d push=%s`.
8. `AlertJobResult(..., sent, failed, no_target, deferred, removed, push_enabled=push is not None, push_failures=dict(failures))`.

Zonder notifier (`None`, `{}` of zonder `"webpush"`) is alles behalve stap 4 (vooraf `id`) gelijk aan WP-10: geen select op `push_subscriptions`, geen aflevering, de state schuift door, `last_notified_at` blijft zoals het is.

### Pipeline
- `PipelineContext` krijgt het veld `notifiers: Mapping[str, Notifier] | None = None` (als laatste veld); `run_hourly(..., notifiers=None)` geeft het door.
- `step_alerts`: na de stale-regel `notifiers = ctx.notifiers if ctx.notifiers is not None else notifiers_from_settings(ctx.settings)`. Een `ValueError` daaruit maakt de stap `failed` (A9). Is `notifiers` leeg: log `alerts: push disabled (no VAPID configuration); alert state is stored without delivery` op `WARNING`, en de stapwarning `PUSH_DISABLED_WARNING = "push disabled: VAPID secrets not set; alerts are stored but not delivered"` (wordt een `::warning::`-annotatie; status blijft `ok`). Dan `run_alerts(..., notifiers=notifiers)`. `partial` als `skipped`, `write_errors` of `deferred` niet 0 is.
- **Stapwarning bij `deferred > 0`** (review N-1): `deferred_warning(result.deferred)` = `f"{result.deferred} favorite(s) deferred: no push delivery succeeded; retried next run (see push_failures in ingest_runs)"`. Via `build_annotations` wordt dat `::warning::alerts: <n> favorite(s) deferred: …` in de Actions-log, elke run zolang het duurt. Zo valt een volledige uitval van het enige kanaal op (bijv. 403 voor iedereen doordat `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare niet bij de ingest-sleutel hoort, R1), ook al is de run alleen `partial` met exitcode 0. De tekst bevat alleen een aantal. De volgorde in `warnings`: eerst de push-disabled-warning (als die er is), dan de deferred-warning (de twee sluiten elkaar in de praktijk uit: zonder kanaal is `deferred` 0).
- `alert_counts`: de WP-11-sleutels plus `sent`, `failed`, `no_target`, `deferred`, `removed`, `push_enabled` en `push_failures` (dict). De logregel per stap toont alleen scalaire tellingen, dus `push_failures` komt alleen in `ingest_runs`.

### Logging
- `shakka.logsetup.QUIET_LOGGERS` krijgt `"urllib3"` erbij (op `WARNING`): pywebpush gebruikt `requests`/`urllib3`, en urllib3 logt op `DEBUG` het request-pad, dus het endpoint.
- Niemand logt endpoints, sleutels, user-id's, berichtteksten of het VAPID-subject. `secret_values` bevat de VAPID-private key al (WP-11), dus de log en `ingest_runs.steps[].error` worden er ook op geredigeerd.
- `secret_values(settings)` krijgt als vangnet ook het subject (review N-11): na de bestaande waarden `settings.vapid_subject.strip()` als `vapid_subject` niet `None` is en de gestripte waarde niet leeg is. `redact` slaat waarden korter dan `MIN_SECRET_LENGTH` (8) over, dus de placeholder `mailto:` (7 tekens) wordt niet geredigeerd. Volgorde van het resultaat: `(supabase_secret_key, vapid_private_key?, vapid_subject?)`.

### CLI
- `shakka alerts run [--dry-run]`: bouwt `notifiers_from_settings(settings)` vóór `open_db` (een `ValueError` → `alerts: invalid VAPID configuration: <vaste tekst>`, exit 1). Uitvoer zoals WP-10, met na de samenvatting (en na `alerts: dry run, nothing stored`) één regel:
  - `push: sent=<n> failed=<n> no_target=<n> deferred=<n> removed=<n>` als het kanaal aan is;
  - `push: disabled (no VAPID configuration)` als het uit is;
  - `push: nothing sent (dry run)` bij `--dry-run`.

  Daarna de `error`-regels en `alerts: ok|failed`. Exit 1 ook bij `deferred > 0`.
- `shakka alerts test-push --user-id UUID` en `shakka alerts vapid-keys`: zie Interfaces.

### Database (`push_subscriptions`)
Eén migratie met tabel, index, RLS, revoke, grants en policies, in het patroon van WP-01 (expliciete grants omdat "auto expose" uit staat). `authenticated` mag eigen rijen lezen, toevoegen (alleen de kolommen `user_id`, `endpoint`, `p256dh`, `auth`) en verwijderen, niet wijzigen; `user_id` krijgt standaard `auth.uid()`, zodat de PWA hem niet hoeft mee te sturen ([Supabase, Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)). `anon` heeft niets. `service_role` (de ingest) alles.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `supabase/migrations/20261015150000_push_subscriptions.sql` | aanmaken | Exact zoals onder Interfaces. |
| `supabase/tests/05_push_subscriptions.test.sql` | aanmaken | pgTAP, `plan(32)`, zie Testplan AC-1. |
| `supabase/tests/01_schema.test.sql` | wijzigen | `tables_are` met `push_subscriptions` (omschrijving `'public has exactly the expected tables'`); de zeven kolommen in de `set_eq` van types; `('push_subscriptions', 'auth.users', 'c')` in de `set_eq` van foreign keys. `plan(71)` blijft. |
| `ingest/pyproject.toml` | wijzigen | Dependencies erbij: `"cryptography>=47,<51"`, `"py-vapid>=1.9.6,<2"`, `"pywebpush>=2.5,<3"` (alfabetisch tussen de bestaande). |
| `ingest/uv.lock` | wijzigen | `uv lock`. |
| `ingest/src/shakka/db.py` | wijzigen | `TABLE_KEYS["push_subscriptions"] = ("id",)` (na `alert_state`). |
| `ingest/src/shakka/domain/push.py` | aanmaken | Constanten, `PushText`, `PushPayload`, `shorten_words`, `to_push_text`, `spot_path`, `push_tag`, `build_push_payload`, `payload_size`. |
| `ingest/src/shakka/notify/__init__.py` | aanmaken | Alleen een docstring. |
| `ingest/src/shakka/notify/base.py` | aanmaken | `WEBPUSH_CHANNEL`, `DeliveryResult`, `PushTarget`, `DeliveryTarget`, `Notifier`. |
| `ingest/src/shakka/notify/webpush.py` | aanmaken | `PUSH_TTL_S`, `PUSH_TIMEOUT_S`, `VapidKeys`, `generate_vapid_keys`, `WebPushNotifier`, `notifiers_from_settings`. |
| `ingest/src/shakka/jobs/push.py` | aanmaken | Constanten, `load_targets`, `load_all_targets`, `EventDelivery`, `deliver_event`, `SubscriptionUpdate`, `update_subscriptions`, `send_test_push`, `run_test_push_cli`, `run_vapid_keys_cli`. |
| `ingest/src/shakka/jobs/alerts.py` | wijzigen | Docstring (levert nu af); expliciete re-export `from shakka.jobs.push import load_targets as load_targets` (contract `shakka.jobs.alerts.load_targets`; de redundante alias voorkomt ruff `F401`, review N-3); `AlertJobResult`-velden; `_new_state_id`, `assign_new_ids`, `PlanDelivery`, `deliver_plan`; `run_alerts` met `notifiers`; `run_alerts_cli` met notifiers en de `push:`-regel. |
| `ingest/src/shakka/pipeline.py` | wijzigen | `PUSH_DISABLED_WARNING`, `PipelineContext.notifiers`, `run_hourly(notifiers=)`, `step_alerts` (met de push-disabled- en deferred-warning), `alert_counts`. |
| `ingest/src/shakka/logsetup.py` | wijzigen | `QUIET_LOGGERS = ("httpx", "httpcore", "urllib3")`; `secret_values` met het VAPID-subject (Ontwerp, Logging). |
| `ingest/src/shakka/cli.py` | wijzigen | Groepsdocstring `alerts`; commando's `alerts test-push` en `alerts vapid-keys`. |
| `ingest/tests/fakes.py` | wijzigen | Default voor `push_subscriptions`: `id` = `f"00000000-0000-4000-9000-{seq:012d}"` (eigen teller `_push_subscription_seq`) en `created_at` = `now`. |
| `ingest/tests/conftest.py` | wijzigen | Autouse-fixture `_no_real_webpush` (review N-2): `monkeypatch.setattr(pywebpush, "webpush", _blocked_webpush)` met `def _blocked_webpush(*args, **kwargs): pytest.fail("real web push in a test", pytrace=False)`. `pytest.fail` geeft `Failed`, een subklasse van `BaseException`; de `except Exception` in `send_payload`, `deliver_event` en `run_step` vangt hem dus niet en de test faalt echt. `import pywebpush` bovenaan. |
| `ingest/tests/push_fixtures.py` | aanmaken | Zie Testplan. |
| `ingest/tests/test_conftest_guard.py` | aanmaken | `test_real_webpush_is_blocked` (review N-2, zie Testplan "Overige tests"). |
| `ingest/tests/test_push_text.py` | aanmaken | AC-3 en de payload. |
| `ingest/tests/test_notify_webpush.py` | aanmaken | AC-2, statusmapping, configuratie, sleutels, AC-8 (notifierniveau). |
| `ingest/tests/test_job_push.py` | aanmaken | Doelen laden, `deliver_event`, `update_subscriptions`, `send_test_push`. |
| `ingest/tests/test_job_alerts_push.py` | aanmaken | AC-4, AC-5, AC-8 (jobniveau), alles-of-niets, ids, `last_notified_at`. |
| `ingest/tests/test_cli_push.py` | aanmaken | `alerts run` met push, `test-push`, `vapid-keys`. |
| `ingest/tests/test_pipeline.py` | wijzigen | `test_alert_counts_shape` met de nieuwe sleutels; nieuwe tests AC-6 en notifiers via `run_hourly`. |
| `ingest/tests/test_cli_jobs.py` | wijzigen | `test_alerts_run_cli`: de samenvatting staat nu op `lines[-3]` en `lines[-2] == "push: disabled (no VAPID configuration)"`. |
| `ingest/tests/test_migrations.py` | wijzigen | `test_no_later_milestone_tables` zonder `push_subscriptions` in de regex. |
| `ingest/tests/test_logsetup.py` | wijzigen | Fixture `restore_logging` herstelt alle `QUIET_LOGGERS`; `test_httpx_and_httpcore_quiet` controleert ook `urllib3` op `WARNING`; `test_secret_values` krijgt er een geval met `vapid_subject` bij (de bestaande asserts blijven). |
| `ingest/tests/test_cli_pipeline.py` | wijzigen | `test_budget_warning_on_stdout`: `line.startswith("::warning::forecast:")` in plaats van `"::warning::"` (review N-5); de push-disabled-warning verschijnt nu elke run en zou de test anders altijd laten slagen. |
| `ingest/tests/test_hourly_workflow.py` | wijzigen | AC-7 (zie Testplan). |
| `.github/workflows/hourly.yml` | wijzigen | In de `env` van de stap "Hourly pipeline" na `SUPABASE_SECRET_KEY`: `VAPID_PUBLIC_KEY: ${{ secrets.VAPID_PUBLIC_KEY }}`, `VAPID_PRIVATE_KEY: ${{ secrets.VAPID_PRIVATE_KEY }}`, `VAPID_SUBJECT: ${{ secrets.VAPID_SUBJECT }}`. Verder niets. |
| `docs/RUNBOOK.md` | wijzigen | Nieuwe §14; aanpassingen in §12 en §13 (zie Stappenplan stap 10). |

Geen wijziging aan `shakka.domain` buiten het nieuwe `push.py`, en niet aan `shakka.config`, `.env.example`, `ci.yml`, `02_privileges.test.sql`, `03_rls_anon.test.sql` of `04_rls_users.test.sql`. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### Migratie `supabase/migrations/20261015150000_push_subscriptions.sql`
```sql
-- Web Push subscriptions (WP-17). One row per browser or device. Written by the PWA (WP-18),
-- read and cleaned up by the ingest (secret key -> service_role). The endpoint is a capability
-- URL: never log it.

create table public.push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  endpoint text not null
    constraint push_subscriptions_endpoint_unique unique
    constraint push_subscriptions_endpoint_https
    check (endpoint ~ '^https://[^[:space:]]+$' and char_length(endpoint) <= 2048),
  p256dh text not null constraint push_subscriptions_p256dh_format
    check (p256dh ~ '^[A-Za-z0-9_-]+={0,2}$' and char_length(p256dh) <= 256),
  auth text not null constraint push_subscriptions_auth_format
    check (auth ~ '^[A-Za-z0-9_-]+={0,2}$' and char_length(auth) <= 64),
  created_at timestamptz not null default now(),
  last_success_at timestamptz null
);
create index push_subscriptions_user_id_idx on public.push_subscriptions (user_id);

alter table public.push_subscriptions enable row level security;

revoke all on table public.push_subscriptions from public, anon, authenticated, service_role;

-- Own subscriptions: read, add (only these columns) and remove. No update.
grant select, delete on table public.push_subscriptions to authenticated;
grant insert (user_id, endpoint, p256dh, auth) on table public.push_subscriptions to authenticated;

-- Ingest.
grant select, insert, update, delete on table public.push_subscriptions to service_role;

create policy push_subscriptions_select_own on public.push_subscriptions for select to authenticated
  using (user_id = (select auth.uid()));
create policy push_subscriptions_insert_own on public.push_subscriptions for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy push_subscriptions_delete_own on public.push_subscriptions for delete to authenticated
  using (user_id = (select auth.uid()));
```
De sleutels `p256dh` en `auth` zijn volgens de Push API "URL-safe base64 encoding without padding" ([W3C Push API, toJSON](https://w3c.github.io/push-api/)); de regex staat optionele `=` toe als vangnet.

### `shakka.domain.push`
```python
PUSH_TITLE_MAX: Final = 50               # code points (decision Lars)
PUSH_BODY_MAX: Final = 150               # code points (decision Lars)
PUSH_PAYLOAD_MAX_BYTES: Final = 3000     # UTF-8 bytes of PushPayload.to_json()
PUSH_TAG_MAX: Final = 64
ELLIPSIS: Final = "…"                    # U+2026
FALLBACK_TITLE: Final = "Shakka"
_TAG_PATTERN: Final = re.compile(r"[A-Za-z0-9_.:-]+")

class PushText(BaseModel):               # frozen, extra="forbid"
    title: str                           # 1..PUSH_TITLE_MAX, no "\n" or "\r"
    body: str                            # 0..PUSH_BODY_MAX

class PushPayload(BaseModel):            # frozen, extra="forbid"
    title: str                           # 1..PUSH_TITLE_MAX, no "\n" or "\r"
    body: str                            # 0..PUSH_BODY_MAX
    url: str                             # min_length 1, no whitespace
    tag: str                             # 1..PUSH_TAG_MAX, fullmatch _TAG_PATTERN
    def to_json(self) -> str: ...        # json.dumps({"title","body","url","tag"}, ensure_ascii=False,
                                         #            separators=(",", ":"))

def shorten_words(text: str, limit: int) -> str: ...      # see Ontwerp; ValueError if limit < 2
def to_push_text(message: AlertMessage) -> PushText: ...
def spot_path(spot_id: str) -> str: ...                    # f"/spot/{spot_id}"
def push_tag(state_id: str) -> str: ...                    # f"alert-{state_id}"
def payload_size(payload: PushPayload) -> int: ...         # len(payload.to_json().encode("utf-8"))
def build_push_payload(message: AlertMessage, *, tag: str) -> PushPayload: ...
    # ValueError if it cannot fit in PUSH_PAYLOAD_MAX_BYTES even with spot_path
```

### `shakka.notify.base`
```python
WEBPUSH_CHANNEL: Final = "webpush"

@dataclass(frozen=True, slots=True)
class DeliveryResult:
    ok: bool
    permanent_failure: bool
    detail: str          # "ok", "HTTP <status>", "WebPushException" or an exception type name;
                         # never a message, endpoint, key or user id
    # __post_init__: ValueError if ok and permanent_failure, or if detail is empty

@dataclass(frozen=True, slots=True)
class PushTarget:
    subscription_id: str
    endpoint: str = field(repr=False)
    p256dh: str = field(repr=False)
    auth: str = field(repr=False)
    # __post_init__: ValueError("push target fields must be non-empty strings") -- no values
    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "PushTarget": ...   # id, endpoint, p256dh, auth

DeliveryTarget = PushTarget          # alias; a later channel can widen this to a union

class Notifier(Protocol):
    channel: str
    def send(self, target: DeliveryTarget, message: AlertMessage, *, tag: str) -> DeliveryResult: ...
```
`field(repr=False)` zonder default is toegestaan; de velden blijven positioneel: `PushTarget(subscription_id, endpoint, p256dh, auth)`. `repr(target)` toont alleen `subscription_id`.

### `shakka.notify.webpush`
```python
PUSH_TTL_S: Final = 12 * 60 * 60        # contract: TTL 12 hours
PUSH_TIMEOUT_S: Final = 10.0            # passed to requests.post via pywebpush
VAPID_PROBE_AUD: Final = "https://push.example.invalid"   # aud of the trial signature in __init__
INCOMPLETE_ERROR: Final = "incomplete VAPID configuration: set VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY and VAPID_SUBJECT together"
SUBJECT_ERROR: Final = "invalid VAPID_SUBJECT: expected mailto:<address> with a domain, or https://<host> without a path"
PRIVATE_KEY_ERROR: Final = "invalid VAPID_PRIVATE_KEY: expected the base64url key from 'shakka alerts vapid-keys'"
PUBLIC_KEY_ERROR: Final = "VAPID_PUBLIC_KEY does not belong to VAPID_PRIVATE_KEY"

@dataclass(frozen=True, slots=True)
class VapidKeys:
    public_key: str = field(repr=True)   # base64url, 65-byte uncompressed point, no "="
    private_key: str = field(repr=False) # base64url, 32 bytes, no "="

def generate_vapid_keys() -> VapidKeys: ...

class WebPushNotifier:
    channel: str = WEBPUSH_CHANNEL
    def __init__(self, vapid_private_key: str, vapid_subject: str, *,
                 ttl_s: int = PUSH_TTL_S, timeout_s: float = PUSH_TIMEOUT_S,
                 webpush_fn: Callable[..., Any] | None = None) -> None: ...
        # ValueError (fixed texts, no values) for an invalid key (PRIVATE_KEY_ERROR) or a subject
        # that fails the whitespace pre-check or the trial signature (SUBJECT_ERROR); see Ontwerp
    @property
    def public_key(self) -> str: ...      # base64url, no "="
    def send(self, target: PushTarget, message: AlertMessage, *, tag: str) -> DeliveryResult: ...
    def send_payload(self, target: PushTarget, payload: PushPayload) -> DeliveryResult: ...
    def __repr__(self) -> str: ...        # "WebPushNotifier()" -- no key, no subject

def notifiers_from_settings(settings: Settings) -> dict[str, Notifier]: ...
    # {} if no VAPID variable is set; ValueError (fixed text) if incomplete or invalid
```
Vaste foutteksten (exact, zonder waarden; de constanten hierboven):
- `INCOMPLETE_ERROR`: `"incomplete VAPID configuration: set VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY and VAPID_SUBJECT together"`;
- `SUBJECT_ERROR`: `"invalid VAPID_SUBJECT: expected mailto:<address> with a domain, or https://<host> without a path"`;
- `PRIVATE_KEY_ERROR`: `"invalid VAPID_PRIVATE_KEY: expected the base64url key from 'shakka alerts vapid-keys'"`;
- `PUBLIC_KEY_ERROR`: `"VAPID_PUBLIC_KEY does not belong to VAPID_PRIVATE_KEY"`.

`notifiers_from_settings` geeft `vapid_private_key.get_secret_value()` en `vapid_subject` ongewijzigd door aan `WebPushNotifier`; het strippen gebeurt in `__init__`. Langer dan 100 tekens per regel mag niet (ruff `E501`): schrijf de teksten als impliciete concatenatie van stringliterals tussen haakjes; de resulterende tekst is exact zoals hierboven.

Push-payload naar de PWA (contract, ongewijzigd): JSON `{"title": str, "body": str, "url": str, "tag": str}`, hoogstens 3.000 bytes; `url` is de `go_url` (absoluut, uit `APP_BASE_URL`) of anders `/spot/{spot_id}` (relatief, bijvoorbeeld bij `cancelled`); `tag` is `alert-{alert_state.id}`. De test-push gebruikt `url = "/"` en `tag = "shakka-test"`.

### `shakka.jobs.push`
```python
MAX_TARGETS_PER_USER: Final = 10
SUBSCRIPTION_COLUMNS: Final = "id,user_id,endpoint,p256dh,auth,created_at"
SUBSCRIPTION_BATCH: Final = 100
TEST_PUSH_TITLE: Final = "Shakka: testmelding"
TEST_PUSH_BODY: Final = "Meldingen werken op dit apparaat."
TEST_PUSH_URL: Final = "/"
TEST_PUSH_TAG: Final = "shakka-test"

def load_targets(db: SupabaseRest, user_id: str) -> list[DeliveryTarget]: ...
def load_all_targets(db: SupabaseRest) -> dict[str, list[DeliveryTarget]]: ...

@dataclass(frozen=True, slots=True)
class EventDelivery:
    sent: int
    failed: int
    retryable: bool                 # sent == 0 and >= 1 non-permanent failure
    ok_ids: frozenset[str]
    gone_ids: frozenset[str]        # permanent failure (404/410)
    failures: tuple[str, ...]       # DeliveryResult.detail of every failed delivery

def deliver_event(notifier: Notifier, targets: Sequence[DeliveryTarget], message: AlertMessage,
                  *, tag: str) -> EventDelivery: ...

@dataclass(frozen=True, slots=True)
class SubscriptionUpdate:
    removed: int
    errors: tuple[str, ...]          # "push_subscriptions: <db_error_summary>"

def update_subscriptions(db: SupabaseRest, *, gone: Collection[str], ok: Collection[str],
                         now: datetime) -> SubscriptionUpdate: ...

@dataclass(frozen=True, slots=True)
class TestPushResult:
    device: int                      # 1-based, in load_targets order
    result: DeliveryResult

def send_test_push(db: SupabaseRest, notifier: WebPushNotifier, user_id: str, *,
                   now: datetime) -> list[TestPushResult]: ...
    # load_targets, send_payload(TEST payload) per target, then update_subscriptions
def run_test_push_cli(user_id: str, *, echo: Callable[[str], None]) -> int: ...
def run_vapid_keys_cli(*, echo: Callable[[str], None]) -> int: ...
```
`update_subscriptions` en `send_test_push` geven een naïeve `now` een `ValueError`.

Uitvoer `shakka alerts test-push --user-id UUID` (`run_test_push_cli`):
1. `get_settings()`; `ValidationError` → `test-push: configuration incomplete; run shakka doctor`, exit 1.
2. `notifiers_from_settings(settings)`; `ValueError` → `test-push: invalid VAPID configuration: <vaste tekst>`, exit 1; leeg → `test-push: push is disabled; set VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY and VAPID_SUBJECT (docs/RUNBOOK.md, section 14)`, exit 1.
3. `db = runtime.open_db(settings)`, in `try/finally db.close()`: `send_test_push(db, notifier, user_id, now=runtime.utcnow())`; `DatabaseError` → `test-push: database error: <exc>`, exit 1.
4. Geen doelen → `test-push: no push subscriptions for this user; turn on notifications in the app first`, exit 1.
5. Per apparaat: `test-push: device <n>: ok`, `test-push: device <n>: failed (<detail>)` of `test-push: device <n>: gone (<detail>); subscription removed`. Daarna `test-push: sent=<n> failed=<n> removed=<n>` en `test-push: ok` (exit 0, minstens één `ok`) of `test-push: failed` (exit 1).

Geen endpoints, sleutels, user-id's of het subject in de uitvoer.

Uitvoer `shakka alerts vapid-keys` (`run_vapid_keys_cli`, leest geen `Settings`, raakt geen database), exit 0:
```
VAPID_PUBLIC_KEY=<base64url>
VAPID_PRIVATE_KEY=<base64url>
note: put both in .env and in the GitHub Secrets (docs/RUNBOOK.md, section 14). The web app uses the same public key as PUBLIC_VAPID_PUBLIC_KEY. Never commit or share the private key.
```

### `shakka.jobs.alerts` (uitbreiding)
```python
from shakka.jobs.push import load_targets as load_targets   # explicit re-export (no F401);
                                                            # contract: shakka.jobs.alerts.load_targets

@dataclass(frozen=True, slots=True)
class AlertJobResult:
    ...                                      # WP-10 fields unchanged
    sent: int = 0                            # successful deliveries (event x subscription)
    failed: int = 0                          # failed deliveries, permanent or not
    no_target: int = 0                       # events of users without a live subscription
    deferred: int = 0                        # favorites not stored because of a retryable failure
    removed: int = 0                         # push subscriptions deleted after 404/410
    push_enabled: bool = False               # webpush notifier given and not a dry run
    push_failures: Mapping[str, int] = field(default_factory=dict)   # detail -> count

@dataclass(frozen=True, slots=True)
class PlanDelivery:
    plan: FavoritePlan                       # last_notified_at = now for notified events
    deferred: bool
    sent: int = 0
    failed: int = 0
    no_target: int = 0
    ok_ids: frozenset[str] = frozenset()
    gone_ids: frozenset[str] = frozenset()
    failures: tuple[str, ...] = ()

def _new_state_id() -> str: ...              # str(uuid.uuid4()); looked up at call time
def assign_new_ids(plan: FavoritePlan, *, new_id: Callable[[], str] | None = None) -> FavoritePlan: ...
def deliver_plan(plan: FavoritePlan, notifier: Notifier, targets: Sequence[DeliveryTarget], *,
                 now: datetime, gone: Collection[str] = ()) -> PlanDelivery: ...
def run_alerts(db: SupabaseRest, *, now: datetime, base_url: str | None, dry_run: bool = False,
               notifiers: Mapping[str, Notifier] | None = None) -> AlertJobResult: ...
```
`assign_new_ids` en `deliver_plan` geven een `ValueError` voor een plan dat niet `planned` is. `store_plan`, `plan_favorite`, `load_alert_context` en `RenderedAlert` blijven ongewijzigd.

### `shakka.pipeline` (uitbreiding)
```python
PUSH_DISABLED_WARNING: Final = (
    "push disabled: VAPID secrets not set; alerts are stored but not delivered"
)

def deferred_warning(deferred: int) -> str: ...
    # f"{deferred} favorite(s) deferred: no push delivery succeeded; "
    # "retried next run (see push_failures in ingest_runs)"

@dataclass(slots=True)
class PipelineContext:
    ...                                                   # WP-11 fields unchanged
    notifiers: Mapping[str, Notifier] | None = None       # None: build from Settings in step_alerts

def run_hourly(settings, *, now, db=None, http=None, steps=STEPS, forecast_fetch=None,
               tide_fetch=None, clock=None, notifiers=None) -> RunReport: ...
def alert_counts(result: AlertJobResult) -> dict[str, Any]: ...
    # WP-11 keys plus sent, failed, no_target, deferred, removed, push_enabled,
    # push_failures (dict). Never messages, user ids, endpoints or texts.
```

### Workflow `hourly.yml`
Stap "Hourly pipeline", exact:
```yaml
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SECRET_KEY: ${{ secrets.SUPABASE_SECRET_KEY }}
          VAPID_PUBLIC_KEY: ${{ secrets.VAPID_PUBLIC_KEY }}
          VAPID_PRIVATE_KEY: ${{ secrets.VAPID_PRIVATE_KEY }}
          VAPID_SUBJECT: ${{ secrets.VAPID_SUBJECT }}
          APP_BASE_URL: ${{ vars.APP_BASE_URL }}
```
Een niet-gezet secret is een lege string; `Settings` (`env_ignore_empty=True`) maakt er `None` van, dus het kanaal is dan uit (A9). De schedule draait de code van `main` met het workflowbestand van `develop` (WP-11 A5): de oude code negeert de extra variabelen (de velden bestaan al in `Settings`).

### Consistentie met afhankelijke WP's
- **WP-08:** `AlertMessage` en de regelvolgorde ongewijzigd; `tag` per `alert_state.id`, ook bij heractiveren (A8 daar); alles-of-niets per (gebruiker, spot) en schrijfvolgorde (A4 hier); `id` vooraf toegekend en via `to_row()` meegestuurd; `last_notified_at` pas na een geslaagde aflevering. Golden-berichten uit `GOLDEN_CASES` voor AC-3.
- **WP-10:** de aflevering zit tussen `plan_favorite` en `store_plan`; `store_plan` en de schrijfvolgorde ongewijzigd; geen user-id in URL's van `run_alerts` (A7); `run_alerts` zonder `notifiers` gedraagt zich als WP-10 (behalve de vooraf toegekende `id`, A3); `dry_run` schrijft en levert niets.
- **WP-11:** `notifiers` via `PipelineContext`; `alert_counts` met `sent`, `failed`, `no_target`; alleen aantallen in log en `counts`; een stapfout wordt `failed` met redactie; `secret_values` bevat de VAPID-private key al.
- **WP-01:** patroon van RLS, revoke en expliciete grants; `TABLE_KEYS` en `test_table_keys_match_migrations`.

### Gevolgen voor latere WP's
- **WP-18:**
  - Insert in `push_subscriptions` met alleen `endpoint`, `p256dh` en `auth` uit `subscription.toJSON()` (`user_id` volgt uit `auth.uid()`). Andere kolommen mag `authenticated` niet zetten; `update` mag niet.
  - `endpoint` is uniek. Een insert van een endpoint dat al bestaat geeft `23505` (bijvoorbeeld: opnieuw aanzetten op hetzelfde apparaat). Behandel dat als "staat al aan" als de eigen select de rij vindt; vindt de eigen select hem niet, dan hoort het endpoint bij een ander account op dit apparaat; toon dan een melding.
  - Uitzetten: eerst de eigen rij verwijderen (filter op `endpoint`), dan `subscription.unsubscribe()`.
  - **Uitloggen** (review N-7): eerst de eigen rij van dit apparaat verwijderen (filter op `endpoint`, terwijl de sessie nog geldig is), dan uitloggen. Anders blijft door `endpoint unique` en RLS het abonnement van gebruiker A op een gedeeld apparaat bestaan: A's meldingen over zijn favoriete spots blijven daar binnenkomen, en gebruiker B kan op dat apparaat geen abonnement maken (`23505`). Of `subscription.unsubscribe()` daarbij ook nodig is, beslist WP-18.
  - Push pas aanzetten na favorieten (A1): lopende windows komen niet meer als melding; WP-18 beslist over een uitleg in de UI.
  - De `push`-handler krijgt exact de payload hierboven; `url` kan absoluut (`go_url`) of relatief (`/spot/{id}`, `/`) zijn; `tag` vervangt een eerdere melding met dezelfde `tag`.
  - `PUBLIC_VAPID_PUBLIC_KEY` = `VAPID_PUBLIC_KEY` (base64url, 65 bytes na decoderen).
  - AC-5 van WP-18 gebruikt `shakka alerts test-push`.
- **WP-22:**
  - pushmeldingen aan Lars: `load_targets(db, OPERATOR_USER_ID)` en `WebPushNotifier.send_payload` met een eigen `PushPayload` (geen `AlertMessage` nodig);
  - een grens op het aantal abonnementen per gebruiker in de database (nu alleen `MAX_TARGETS_PER_USER` in de job), eventueel een allowlist van push-service-hosts voor `endpoint`;
  - een maximum aantal herhaalpogingen of een leeftijdsgrens voor een niet-permanente fout (R1), en een tijdsbudget voor de afleveringen (R3);
  - de egress van `load_all_targets` groeit met het aantal abonnementen (orde 400 bytes per rij);
  - **SSRF/egress via endpoints** (review N-10): een ingelogde gebruiker kan rijen toevoegen met een willekeurig `https`-endpoint (alleen begrensd door de CHECK en, in de job, `MAX_TARGETS_PER_USER`), en de ingest POST daarheen vanuit GitHub Actions. Het risico is nu beperkt (de `aud` is de host van de aanvaller, de payload is versleuteld voor zijn eigen sleutels en gaat over zijn eigen alerts, er komen geen geheimen mee), maar WP-22 hoort te beslissen over een allowlist van push-service-hosts (in de CHECK of in `PushTarget.from_row`) en een grens in de database op het aantal rijen per gebruiker.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | Geen VAPID-variabelen (of alleen `VAPID_SUBJECT=mailto:` uit `.env.example`) | Kanaal uit: `{}`; in de pipeline een `WARNING` en een `::warning::`-annotatie; `run_alerts` als WP-10; `push_enabled=False`; alle pushtellers 0. |
| E2 | Een of twee VAPID-variabelen gezet | `ValueError` "incomplete VAPID configuration"; pipeline: stap `alerts` `failed`, run `failed`, exit 1; CLI `alerts run` exit 1 vóór `open_db`. |
| E3 | Ongeldige private key of subject, of publieke sleutel hoort niet bij de private key | `ValueError` met vaste tekst; zoals E2. De waarde staat nergens in uitvoer of `ingest_runs`. |
| E3a | Subject dat er goed uitziet maar door py_vapid geweigerd wordt (`https://shakka.nl/contact`, `mailto:lars@example`) | De proefhandtekening in `__init__` faalt → `SUBJECT_ERROR`; zoals E2 (stap `alerts` `failed`, mail van GitHub). Nooit pas bij de aflevering. |
| E3b | Subject met witruimte eromheen (bijv. een geplakt secret met `\n`) | Gestript in `__init__`; geldig als de rest geldig is. Witruimte ín het subject → `SUBJECT_ERROR`. |
| E4 | Gebruiker zonder abonnement | Per event `no_target += 1`; geen aanroep van de notifier; de state schuift door; `last_notified_at` blijft `NULL`. |
| E5 | Twee abonnementen, één geeft 503 | Twee afleveringen; `sent=1`, `failed=1`; event afgeleverd; state door; `last_notified_at = now`; alleen het geslaagde abonnement krijgt `last_success_at`. |
| E6 | Eén abonnement, 410 (of 404) | `failed=1`; abonnement verwijderd (`removed=1`); state door; `last_notified_at` ongewijzigd. Volgende events van die gebruiker in dezelfde run: `no_target`. |
| E7 | Eén abonnement, 503 (of 429, 403, 413, time-out, verbindingsfout) | `deferred=1`; geen schrijfactie op `alert_state` voor die favoriet; geen bericht in `messages`; de volgende run berekent dezelfde diff en levert opnieuw af. In de pipeline: stap `alerts` `partial` en `::warning::alerts: 1 favorite(s) deferred: …` (elke run zolang het duurt). |
| E8 | Split (update `worsened` + insert `new`), het tweede event faalt niet-permanent | Het eerste event is afgeleverd, maar niets wordt opgeslagen (alles-of-niets). Volgende run: beide opnieuw; het eerste vervangt de vorige melding (zelfde `tag`). |
| E9 | Eerste event van een diff faalt niet-permanent | De overige events van die diff worden niet afgeleverd (A4); `deferred=1`. |
| E10 | `cancelled`-event | Afgeleverd met `url = "/spot/{spot_id}"` (geen `go_url`) en de `tag` van de bestaande rij, zodat de annulering de eerdere melding vervangt. |
| E11 | Heractiveerde geannuleerde rij (`new` met bestaande `id`) | `tag` = de bestaande `id`; vervangt de annuleringsmelding. Geen nieuwe `id`. |
| E12 | Stille wijzigingen zonder event (`expired`, verschoven span) | Geen aflevering; opslaan zoals WP-10 (behalve bij `deferred`). |
| E13 | Opslaan faalt na een geslaagde aflevering | `write_errors`; geen bericht in `messages`; de volgende run levert opnieuw af (dubbel, geaccepteerd). `last_success_at` wordt wel bijgewerkt. |
| E14 | `dry_run` met `notifiers` | Geen aflevering, geen select op `push_subscriptions`, geen schrijfactie; `push_enabled=False`; `state_id` van nieuwe rijen `None`. |
| E15 | Notifier geeft een exception (in strijd met de interface) | Niet-permanente fout met `detail` = exceptietype; één `WARNING` met alleen het type. |
| E16 | Meer dan 10 abonnementen voor één gebruiker | Alleen de 10 nieuwste (`created_at`) worden bediend. |
| E17 | Verwijderen of bijwerken van abonnementen faalt (`DatabaseError`) | `write_errors += 1` per blok, foutregel `push_subscriptions: DatabaseError (...)`; de rest gaat door. Een niet-verwijderd dood abonnement geeft de volgende run opnieuw 410 en wordt dan verwijderd. |
| E18 | Hetzelfde abonnement slaagt voor event 1 en geeft 410 voor event 2 | Verwijderd, geen `last_success_at`-update (`ok - gone`). |
| E19 | Body past al (≤ 150) | Ongewijzigd. Titel ≤ 50: ongewijzigd. |
| E20 | Eerste bodyregel langer dan 150 | Afgekapt op een woordgrens, eindigt op "…", hoogstens 150 tekens. Eén woord langer dan de grens: hard afgekapt plus "…" (er is geen woordgrens). |
| E21 | Afgekapt op een woordgrens die eindigt op `·`, `,` of `–` | Dat scheidingsteken wordt weggehaald vóór "…". |
| E22 | Titel van alleen spaties | `FALLBACK_TITLE` ("Shakka"). |
| E23 | `go_url` zo lang dat de payload boven 3.000 bytes komt | `url = "/spot/{spot_id}"`. |
| E24 | `APP_BASE_URL` leeg | `go_url = None`, dus `url = "/spot/{spot_id}"`. |
| E25 | Endpoint met `http://`, spaties of langer dan 2.048 tekens | Database weigert (`23514`). |
| E26 | Ingelogde gebruiker voegt een rij toe voor een ander, of zet `last_success_at` | `42501` (RLS, kolomrecht). |
| E27 | Gebruiker wordt verwijderd | Abonnementen verdwijnen via de cascade. |
| E28 | `load_all_targets` faalt (`DatabaseError`) | Gaat door naar de aanroeper (als bij het laden in WP-10): stap `alerts` `failed`. |
| E29 | `pywebpush` zou het netwerk op gaan in een test | De autouse-fixture roept `pytest.fail` aan (`Failed` is een `BaseException`, dus geen `except Exception` slikt hem in); de test faalt. |

## Testplan
Tests eerst voor `shakka.domain.push` (puur) en de notifier. Geen netwerk: `pywebpush.webpush` is in elke test geblokkeerd (conftest); tests geven een nep-functie via `webpush_fn` of `monkeypatch.setattr(pywebpush, "webpush", ...)`. Geen klok: `now` expliciet (`NOW` uit `job_fixtures`). Alle databasetests gebruiken `FakeSupabase`.

### Fixtures (`ingest/tests/push_fixtures.py`)
```python
KEYS = generate_vapid_keys()                       # fresh dummy pair per test session
SUBJECT = "mailto:test@example.org"
OK = DeliveryResult(True, False, "ok")
GONE = DeliveryResult(False, True, "HTTP 410")
DOWN = DeliveryResult(False, False, "HTTP 503")

def endpoint(user_id: str, n: int) -> str: ...     # f"https://push.example.test/send/{user_id[:8]}-{n}"
def sub_row(user_id: str, n: int, *, created_at: datetime | None = None) -> dict[str, Any]: ...
    # {"user_id", "endpoint": endpoint(...), "p256dh": f"BP256DH{n}", "auth": f"AUTH{n}",
    #  "created_at": created_at or NOW - timedelta(days=n)}
def seed_subs(db: FakeSupabase, user_id: str, n: int) -> list[str]: ...   # returns endpoints

@dataclass
class Sent:
    subscription_id: str
    endpoint: str
    tag: str
    kind: str
    title: str

class FakeNotifier:
    channel = "webpush"
    def __init__(self, results: Mapping[str, DeliveryResult | list[DeliveryResult]] | None = None,
                 raises: Exception | None = None): ...
        # per endpoint a fixed result or a list consumed in order (last repeats); default OK
    calls: list[Sent]
    def send(self, target, message, *, tag) -> DeliveryResult: ...

class FakeResponse:                                # for WebPushException(response=...)
    def __init__(self, status_code: int): ...      # .status_code, .text = "body with endpoint", .headers = {}

class RecordingWebpush:                            # a webpush_fn
    def __init__(self, *, raises: BaseException | None = None): ...
    calls: list[dict[str, Any]]                    # copies of the kwargs (vapid_claims copied before
                                                   # mutation), plus "claims_id": id(vapid_claims)
    def __call__(self, **kwargs) -> object: ...    # simulates pywebpush: sets kwargs["vapid_claims"]
                                                   # ["aud"] = origin of the endpoint; raises if given
```

### AC-1: `supabase/tests/05_push_subscriptions.test.sql` (`supabase test db`)
`begin; create extension if not exists pgtap with schema extensions; select plan(32);`. Fixture als postgres: auth-users A (`11111111-1111-1111-1111-111111111111`) en B (`22222222-…`); één rij voor B (`endpoint 'https://push.example.test/b1'`, `p256dh 'BBBB'`, `auth 'bbbb'`). Asserts in deze volgorde:
1. `columns_are` met `id, user_id, endpoint, p256dh, auth, created_at, last_success_at`;
2. `col_is_pk` op `id`;
3. `has_index` `push_subscriptions_user_id_idx`;
4. `table_privs_are` anon `{}`;
5. `table_privs_are` authenticated `{DELETE, SELECT}`;
6. `table_privs_are` service_role `{DELETE, INSERT, SELECT, UPDATE}`;
7–10. `column_privs_are` authenticated `{INSERT, SELECT}` op `user_id`, `endpoint`, `p256dh`, `auth`;
11–13. `column_privs_are` authenticated `{SELECT}` op `id`, `created_at`, `last_success_at`;
14. `policies_are` `{push_subscriptions_select_own, push_subscriptions_insert_own, push_subscriptions_delete_own}`;
15–19 draaien als `postgres` en geven **expliciet `user_id` A** (`'11111111-1111-1111-1111-111111111111'`) mee (review N-4): zonder `user_id` geeft de default `auth.uid()` als `postgres` `NULL`, en Postgres controleert NOT NULL vóór CHECK, dus dan kwam `23502` terug in plaats van de bedoelde code. De overige kolommen zijn in elk van die inserts geldig, op de ene ongeldige waarde na.
15. `throws_ok` insert `(user_id A, endpoint 'http://push.example.test/x', p256dh 'AAAA', auth 'aaaa')` → `23514`;
16. `throws_ok` insert `(user_id A, endpoint 'https://push.example.test/a b', 'AAAA', 'aaaa')` → `23514`;
17. `throws_ok` insert `(user_id A, 'https://push.example.test/a2', p256dh 'ab cd', 'aaaa')` → `23514`;
18. `throws_ok` insert `(user_id A, 'https://push.example.test/a3', 'AAAA', auth 'a+b')` → `23514`;
19. `throws_ok` insert `(user_id A, endpoint 'https://push.example.test/b1' (dat van B), 'AAAA', 'aaaa')` → `23505`;
20. als authenticated A (`set local role authenticated`, claims met `sub` A): `lives_ok` insert `(endpoint, p256dh, auth)` = `('https://push.example.test/a1', 'AAAA', 'aaaa')` zonder `user_id`;
21. `results_eq('select user_id from public.push_subscriptions', $$values ('1111…'::uuid)$$)`: A ziet alleen zijn eigen rij, en `user_id` kwam uit `auth.uid()`;
22. `throws_ok` insert met `user_id` B → `42501`;
23. `throws_ok` insert met `last_success_at` → `42501`;
24. `throws_ok` `update public.push_subscriptions set last_success_at = now()` → `42501`;
25. `lives_ok` delete van de rijen van B (raakt 0 rijen);
26. `lives_ok` delete van de eigen rij `a1`;
27. na `reset role`: `isnt_empty` de rij van B bestaat nog;
28. `is_empty` de rij `a1` is weg;
29. als anon: `throws_ok` select → `42501`;
30. als anon: `throws_ok` insert → `42501`;
31. als service_role: `lives_ok` update `last_success_at = now()` op de rij van B;
32. na `delete from auth.users where id = B` (als postgres): `is_empty` abonnementen van B (cascade).

`finish(); rollback;`. Plus `01_schema.test.sql` aangepast (tabellenlijst, kolomtypes, foreign keys) en groen.

### AC-2: `tests/test_notify_webpush.py`
- `test_payload_contract` (AC-2): `n = WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=rec)`; voor elk `GoldenCase`: `message = render_alert(...)`, `n.send(target, message, tag="alert-x")` → `json.loads(call["data"])` heeft exact de sleutels `{"title", "body", "url", "tag"}`; `title`/`body` gelijk aan `to_push_text(message)`; `len(call["data"].encode()) <= 3000`; `call["vapid_claims"]["sub"] == SUBJECT`; `call["ttl"] == 43200`; `call["timeout"] == 10.0`; `call["content_encoding"] == "aes128gcm"`; `call["subscription_info"] == {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}`; `isinstance(call["vapid_private_key"], py_vapid.Vapid)`; `url == message.go_url or "/spot/test-strand"`; `tag == "alert-x"`. Resultaat `DeliveryResult(True, False, "ok")`.
- `test_fresh_claims_per_call`: twee `send`s naar endpoints met verschillende hosts; de nep-functie zet `aud` in de dict → de tweede aanroep krijgt een andere dict (`claims_id` verschilt) en bij binnenkomst alleen `{"sub": SUBJECT}`.
- `test_status_mapping`, geparametriseerd: `WebPushException("Push failed: …", response=FakeResponse(s))` met `s` in 404, 410 → `(False, True, f"HTTP {s}")`; 400, 403, 413, 429, 500, 503 → `(False, False, f"HTTP {s}")`; `response=None` → `(False, False, "WebPushException")`; `requests.exceptions.ConnectTimeout("…")` → `(False, False, "ConnectTimeout")`; `RuntimeError` → `"RuntimeError"`.
- `test_payload_value_error_is_retryable`: een `AlertMessage` met een spot-id van 4.000 tekens → `DeliveryResult(False, False, "ValueError")`, webpush niet aangeroepen.
- `test_invalid_key`: `WebPushNotifier("not-a-key", SUBJECT)` → `ValueError` met exact `PRIVATE_KEY_ERROR`, zonder `"not-a-key"`; `exc.__cause__ is None` en `exc.__suppress_context__` is waar (`from None`).
- `test_subject_validation` (review B-1), geparametriseerd, steeds met `KEYS.private_key`:
  - `ValueError` met exact `SUBJECT_ERROR` (en het subject niet in de tekst) voor: `"https://shakka.nl/contact"`, `"https://example.org/contact"` (pad), `"mailto:lars@example"` (domein zonder punt), `"lars@example.org"` (zonder `mailto:`), `"mailto:"`, `""`, `"   "`, `"http://example.org"` (geen https), `"mailto:a b@example.org"` (witruimte, voorcheck);
  - geldig (geen exception) voor: `"mailto:test@example.org"`, `"https://example.org"`, `"https://shakka.nl"`, `"  mailto:test@example.org\n"` (gestript; `RecordingWebpush` ziet daarna `vapid_claims["sub"] == "mailto:test@example.org"`).
- `test_subject_check_matches_library`: voor elk geldig subject uit de vorige test slaagt ook `Vapid.from_string(private_key=KEYS.private_key).sign({"sub": s.strip(), "aud": "https://fcm.googleapis.com"})`, en voor elk ongeldig subject dat de voorcheck passeert (`"https://shakka.nl/contact"`, `"mailto:lars@example"`, `"lars@example.org"`, `"mailto:"`, `"http://example.org"`) geeft die aanroep `py_vapid.VapidException`. Dit legt vast dat de constructie en de echte aflevering hetzelfde oordeel hebben; breekt een nieuwe py_vapid-versie dat, dan faalt deze test.
- `test_key_error_before_subject_error`: `WebPushNotifier("not-a-key", "mailto:lars@example")` → `PRIVATE_KEY_ERROR`.
- `test_public_key_matches_generated`: `WebPushNotifier(KEYS.private_key, SUBJECT).public_key == KEYS.public_key`; `repr()` bevat de sleutel en het subject niet.
- `test_generate_vapid_keys`: base64url zonder `=` (regex `^[A-Za-z0-9_-]+$`); gedecodeerd 65 bytes (eerste byte `0x04`) en 32 bytes; twee aanroepen geven verschillende sleutels; `repr(keys)` bevat de private key niet.
- `test_notifiers_from_settings`: geen VAPID → `{}`; alleen `vapid_subject="mailto:"` → `{}`; alleen `vapid_subject="  "` → `{}`; private + subject zonder public → `ValueError` "incomplete …"; volledig → `{"webpush": WebPushNotifier}`; public met afsluitende `=` en spaties → nog steeds geldig; public van een ander paar → `ValueError` "does not belong"; in geen enkele foutmelding staat een sleutelwaarde of het subject.
- **AC-8 (notifierniveau)** `test_failure_detail_has_no_secrets`: target met endpoint `"https://push.example.test/send/ENDPOINT-SECRET-123"`, `p256dh="P256DH-SECRET-456"`, `auth="AUTH-SECRET-789"`; nep-functies die geven (a) `WebPushException(f"Push failed: 503 {endpoint}", response=FakeResponse(503))` met `.text` met endpoint en sleutels, (b) `Exception(f"{endpoint} {p256dh} {auth} {KEYS.private_key}")` → in `result.detail` staat geen van die waarden; ook niet in `repr(target)` en `repr(result)`; `caplog` (op `DEBUG`) en `capsys` bevatten ze niet.

### AC-3: `tests/test_push_text.py`
- `test_golden_lengths` (AC-3), over `GOLDEN_CASES`: `t = to_push_text(render_alert(case.event, case.spot, kite=case.kite, tides=case.tides, base_url=case.base_url))` → `len(t.title) <= 50`, `len(t.body) <= 150`, `t.title == case.title` (alle golden-titels zijn hoogstens 26 tekens).
- `test_golden_bodies` (AC-3: wat past blijft ongewijzigd, anders hele regels): `new_summer_plain`, `worsened_winter` en `cancelled_winter` → `t.body == case.body` (110, 142 en 132 tekens); `new_summer_kite_tide` → de eerste 4 regels (133 tekens; de getijregel valt weg); `improved_summer` → de eerste 4 regels (148 tekens; de kiteregel valt weg); `new_winter_tide` → de eerste 3 regels (105 tekens; de getijregel valt weg). Verwacht wordt telkens `"\n".join(case.body.split("\n")[:k])`, plus een assert op de lengte.
- `test_unchanged_when_fits`: titel van precies 50 en body van precies 150 tekens → beide ongewijzigd (grens inclusief).
- `test_body_cut_on_line_boundary`: body = 3 regels van 60 tekens → 2 regels (121 tekens), geen "…".
- `test_first_line_too_long`: body `("woord " * 40).strip() + "\nregel 2"` → eindigt op "…", lengte ≤ 150, `t.body[:-1].split()` bevat alleen `"woord"` (geen afgekapt woord), `t.body[:-1]` is een prefix van de eerste regel.
- `test_single_long_word`: eerste regel van 200 keer `"x"` → precies 149 keer `"x"` plus "…".
- `test_trailing_separator_stripped`: `shorten_words("za 18 jul 14:00–18:00 · " + "a" * 140, 150) == "za 18 jul 14:00–18:00…"` (de woordgrens valt na `" ·"`; het `·` gaat weg vóór "…").
- `test_title_shortened`: titel `"Go: " + "Zeer lange spotnaam " * 5` → ≤ 50, eindigt op "…", hele woorden.
- `test_title_never_empty`: titel `"   "` → `"Shakka"`; elke uitkomst van `to_push_text` heeft `title.strip() != ""`.
- `test_code_points`: titel met `"ü"` en `"🌊"` telt per teken 1 (titel van 50 code points blijft ongewijzigd).
- `test_shorten_words_limit`: `shorten_words("abc", 1)` → `ValueError`.
- `test_build_payload`: `go_url` gezet → `url == go_url`; `cancelled` → `url == "/spot/test-strand"`; `tag` met spatie → `ValidationError`; `to_json()` bevat het teken `–` (U+2013) letterlijk en niet de escape-reeks `–` (`ensure_ascii=False`), en de sleutels in de volgorde `title, body, url, tag`; `payload_size` telt UTF-8-bytes.
- `test_payload_fallback_url`: `go_url` van 3.000 tekens (geldige `base_url` met een lang pad) → `url == "/spot/test-strand"` en `payload_size <= 3000`.
- `test_domain_purity.py` blijft groen met `shakka/domain/push.py` (AC-3, laatste punt; de bestaande test leest alle bestanden in `shakka/domain`).

### `tests/test_job_push.py`
- `test_load_targets_order_and_cap`: 12 abonnementen voor A, 1 voor B → `load_targets(db, USER_A)` geeft 10, nieuwste eerst; `load_all_targets` geeft `{A: 10, B: 1}` in één select zonder filter.
- `test_from_row_skips_invalid`: een rij met lege `auth` (alleen in de fake mogelijk) wordt overgeslagen.
- `test_deliver_event`: twee doelen, `OK` en `DOWN` → `EventDelivery(sent=1, failed=1, retryable=False, ok_ids={s1}, gone_ids=∅, failures=("HTTP 503",))`; `DOWN`+`DOWN` → `retryable=True`; `GONE`+`GONE` → `retryable=False`, `gone_ids` beide; `GONE`+`DOWN` → `retryable=True`; een notifier die `RuntimeError` geeft → `failures == ("RuntimeError",)`, `retryable=True`, één `WARNING` met `"RuntimeError"` en zonder endpoint.
- `test_update_subscriptions`: `gone={s1}`, `ok={s1, s2}` → s1 weg, s2 `last_success_at == NOW` (geparsed), s1 niet bijgewerkt; `removed == 1`; met 150 id's twee blokken (`in`-filters met 100 en 50 id's); een fake die bij `delete` `DatabaseError("x", status=503)` geeft → `errors == ("push_subscriptions: DatabaseError (HTTP 503)",)` en de update gaat door.
- `test_send_test_push`: drie doelen met `OK`, `DOWN`, `GONE` (via een `webpush_fn` op endpoint) → resultaten per apparaat 1..3; de payload heeft `title "Shakka: testmelding"`, `url "/"`, `tag "shakka-test"`; het `GONE`-abonnement is verwijderd; het `OK`-abonnement heeft `last_success_at`.

### AC-4, AC-5, AC-8: `tests/test_job_alerts_push.py`
Opzet: `make_db()`-patroon uit `test_job_alerts.py` (geverifieerde spot, scenario-forecasts), `seed_favorite(db, USER_A, min_kn=12)`, `notifiers={"webpush": FakeNotifier(...)}`.
- `test_new_event_delivered_with_state_tag`: één abonnement → één aanroep met `tag == f"alert-{rows[0]['id']}"`, `kind == "new"`; de rij heeft `last_notified_at` gelijk aan `NOW`, `last_event == "new"`; `result.sent == 1`, `push_enabled is True`; `result.messages[0].state_id == rows[0]["id"]`; de `id` is een geldige uuid (`uuid.UUID(...)`).
- `test_ids_assigned_before_insert`: `monkeypatch.setattr(shakka.jobs.alerts, "_new_state_id", lambda: "aaaaaaaa-0000-4000-8000-000000000001")` → de rij heeft precies die `id` en de `tag` is `alert-aaaaaaaa-…`; ook zonder notifiers krijgt de rij die `id` (A3).
- **AC-5** `test_two_subscriptions_one_fails`: twee abonnementen, één `DOWN` → twee aanroepen per event; `sent == 1`, `failed == 1`, `deferred == 0`; de state is opgeslagen met `last_notified_at = NOW`; `push_failures == {"HTTP 503": 1}`.
- **AC-5** `test_no_subscriptions`: geen abonnementen → geen crash, `no_target == 1`, `sent == failed == 0`, één `alert_state`-rij met `last_notified_at is None`, één bericht in `messages`.
- **AC-4** `test_gone_subscription_removed`: één abonnement met `GONE` → `failed == 1`, `removed == 1`, `push_subscriptions` leeg; de state is opgeslagen (`status active`, `last_event new`, `last_notified_at None`). Tweede run: 0 events, 0 aanroepen.
- **AC-4** `test_retryable_failure_keeps_state`: één abonnement met `DOWN` → `deferred == 1`, `messages == []`, `alert_rows(db) == []`, geen `("insert", "alert_state")` in `db.writes`. Daarna resultaat `OK` en tweede run → één `new`-aanroep (totaal 2), één rij met `last_notified_at = NOW`.
- `test_all_or_nothing_on_split` (A4, E8): run 1 met `OK` (rij R, 10–16Z). Forecasts naar `SPLIT_WINDS` (`WINDS | {13: 13.0}`), `db.writes.clear()`, notifier geeft eerst `OK` (voor `worsened`) en daarna `DOWN` (voor `new`) → twee aanroepen, `deferred == 1`, geen `update` of `insert` op `alert_state`, R ongewijzigd. Daarna alles `OK` en run 3 → `worsened` met `tag alert-<R.id>` en `new` met een nieuwe `id`; update vóór insert (`[("update","alert_state"), ("insert","alert_state"), ("delete","alert_state")]`).
- `test_stop_after_first_retryable_event` (E9): zelfde split, maar het eerste event (`worsened`) `DOWN` → precies één aanroep in run 2.
- `test_cancelled_reuses_tag` (E10): run 1 `new`; forecasts naar 6 kn; run 2 → `cancelled` met dezelfde `tag`; de rij `status cancelled`, `last_notified_at = NOW`.
- `test_dry_run_with_notifiers` (E14): `dry_run=True` → `FakeNotifier.calls == []`, `db.writes == []`, `push_enabled is False`, geen select op `push_subscriptions` (Recording-subklasse).
- `test_without_notifier_is_m1` (AC-6, functieniveau): `notifiers=None`, `{}` en `{"other": FakeNotifier()}` geven dezelfde `messages` (kind, titel, body), `push_enabled False`, alle pushtellers 0, geen select op `push_subscriptions`, en de rij zoals WP-10 AC-2.
- `test_targets_loaded_once_without_user_filter` (A7): A en B met abonnementen → precies één select op `push_subscriptions` met `filters is None`; `USER_A`/`USER_B` in geen enkele vastgelegde filter (zelfde controle als `test_no_user_id_in_request_filters`).
- `test_notifier_exception_retryable` (E15): `FakeNotifier(raises=RuntimeError(endpoint))` → `deferred == 1`; het endpoint staat niet in `caplog.text`.
- `test_max_targets` (E16): 12 abonnementen → 10 aanroepen.
- `test_subscription_update_error` (E17): `delete` op `push_subscriptions` geeft `DatabaseError("x", status=503)` → `write_errors == 1`, `"push_subscriptions: DatabaseError (HTTP 503)" in result.errors`, de alert-state is wel opgeslagen.
- `test_success_then_gone_same_run` (E18): twee favorieten van A (twee geverifieerde spots met dezelfde forecasts), één abonnement: `OK` voor het eerste event, `GONE` voor het tweede → abonnement verwijderd, geen `last_success_at`-update ervoor.
- **AC-8 (jobniveau)** `test_no_endpoints_keys_or_user_ids_in_logs`: `caplog.set_level(logging.DEBUG)`; echte `WebPushNotifier(KEYS.private_key, SUBJECT, webpush_fn=...)` met een nep-functie die `Exception(f"{endpoint} {p256dh} {auth} {KEYS.private_key}")` geeft; abonnement met de dummywaarden uit `test_failure_detail_has_no_secrets` → het endpoint, `p256dh`, `auth`, `KEYS.private_key`, `SUBJECT` en `USER_A` staan niet in `caplog.text`, niet in `capsys.readouterr()` (out en err), niet in `"\n".join(result.errors)` en niet in `str(result.push_failures)`.
- `test_no_bypass_parameters` (bestaand) blijft groen met de nieuwe parameter `notifiers`.

### AC-6 en notifiers via de pipeline: `tests/test_pipeline.py`
- **AC-6** `test_hourly_without_vapid(tmp_path, caplog)`: `seed_user(db)`, `run_real(tmp_path, db)` met `make_settings` zonder VAPID → geen exception; stap `alerts` `ok`; `counts`: `events == 1`, `new == 1`, `sent == failed == no_target == deferred == removed == 0`, `push_enabled is False`; een `WARNING` met `"push disabled"` in `caplog`; een annotatie die begint met `"::warning::alerts: push disabled"`; de `alert_state`-rij `status active`, `last_event new`, `last_notified_at None`.
- `test_hourly_incomplete_vapid`: `make_settings(..., vapid_private_key=KEYS.private_key, vapid_subject=SUBJECT)` zonder public → stap `alerts` `failed`, `error_type == "ValueError"`, run `failed`, exitcode 1; `KEYS.private_key` en `SUBJECT` staan niet in `db.rows("ingest_runs")` (als tekst) en niet in de log.
- `test_hourly_with_notifiers`: `run_real(..., notifiers={"webpush": FakeNotifier()})` en een abonnement voor A → `counts["sent"] == 1`, `push_enabled is True`; zonder `"push disabled"`-warning.
- **AC-8 (pipelineniveau)** `test_hourly_push_failure_leaks_nothing(tmp_path, caplog, capsys)`: `configure_logging()` (zoals `test_alerts_errors_only_in_ingest_runs`), settings met de volledige VAPID-dummyconfiguratie (`KEYS`, `SUBJECT`), `monkeypatch.setattr(pywebpush, "webpush", <geeft Exception met endpoint, sleutels en private key>)`, abonnement met de dummywaarden → endpoint, `p256dh`, `auth`, `KEYS.private_key`, `SUBJECT` en `USER_A` staan niet in `caplog.text`, niet in stdout/stderr, niet in `report.annotations` en niet in `str(db.rows("ingest_runs"))`; `counts["push_failures"] == {"Exception": 1}`; stap `alerts` `partial` (`deferred == 1`).
- `test_hourly_deferred_warning` (review N-1): `run_real(..., notifiers={"webpush": FakeNotifier({<endpoint>: DOWN})})` met één abonnement voor A → stap `alerts` `partial`, `report.exit_code == 0`, de stap heeft `warnings == (deferred_warning(1),)`, en `report.annotations` bevat exact `"::warning::alerts: 1 favorite(s) deferred: no push delivery succeeded; retried next run (see push_failures in ingest_runs)"`. Met `OK` in plaats van `DOWN`: geen annotatie die met `"::warning::alerts:"` begint.
- `test_alert_counts_shape` (aangepast): exact de WP-11-sleutels plus `sent`, `failed`, `no_target`, `deferred`, `removed`, `push_enabled`, `push_failures`; geen `messages`.

### AC-7: `tests/test_hourly_workflow.py`
- `test_pipeline_step_env`: de `env` van de pipelinestap is exact de dict uit Interfaces (zes sleutels).
- `test_only_known_secrets`: de verzameling secrets is exact `{SUPABASE_URL, SUPABASE_SECRET_KEY, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT}` (`==` in plaats van `<=`).
- Bestaand: geen `sb_secret_` en geen `telegram`.

### CLI: `tests/test_cli_push.py` en `tests/test_cli_jobs.py`
Seams zoals `test_cli_jobs.py` (`runtime.open_db`, `runtime.utcnow`); env `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, en waar nodig `VAPID_PUBLIC_KEY=KEYS.public_key`, `VAPID_PRIVATE_KEY=KEYS.private_key`, `VAPID_SUBJECT=SUBJECT`; `monkeypatch.setattr(pywebpush, "webpush", ...)`.
- `test_alerts_run_push_disabled` (aanpassing `test_alerts_run_cli`): zonder VAPID → `lines[-3]` is de samenvatting, `lines[-2] == "push: disabled (no VAPID configuration)"`, `lines[-1] == "alerts: ok"`.
- `test_alerts_run_push_enabled`: VAPID gezet, één abonnement, nep-webpush slaagt → regel `push: sent=1 failed=0 no_target=0 deferred=0 removed=0`, exit 0; geen endpoint en geen `USER_A` in de uitvoer.
- `test_alerts_run_deferred_exit_1`: nep-webpush geeft `WebPushException(..., response=FakeResponse(503))` → `deferred=1` in de pushregel, `alerts: failed`, exit 1, `db.rows("alert_state") == []`.
- `test_alerts_run_dry_run_push_line`: `--dry-run` met VAPID → `push: nothing sent (dry run)`, nep-webpush niet aangeroepen.
- `test_alerts_run_invalid_vapid`: alleen `VAPID_PRIVATE_KEY` gezet → exit 1, `alerts: invalid VAPID configuration: incomplete VAPID configuration: …`, `open_db` niet aangeroepen, de sleutel niet in de uitvoer.
- `test_test_push_cli`: drie abonnementen (`OK`, `DOWN`, `GONE` per endpoint) → regels `test-push: device 1: ok`, `test-push: device 2: failed (HTTP 503)`, `test-push: device 3: gone (HTTP 410); subscription removed`, `test-push: sent=1 failed=2 removed=1`, `test-push: ok`; exit 0; geen endpoint, sleutel of user-id in de uitvoer.
- `test_test_push_cli_errors`: zonder VAPID → exit 1 met de "push is disabled"-regel en geen `open_db`; zonder abonnementen → exit 1 met de "no push subscriptions"-regel; alle afleveringen mislukt → `test-push: failed`, exit 1; ongeldige UUID → click exit 2.
- `test_vapid_keys_cli`: exit 0; drie regels; de eerste twee matchen `^VAPID_PUBLIC_KEY=[A-Za-z0-9_-]{87}$` en `^VAPID_PRIVATE_KEY=[A-Za-z0-9_-]{43}$`; de private key uit de uitvoer geeft via `WebPushNotifier(..., SUBJECT).public_key` de publieke sleutel uit de uitvoer; geen database geopend.
- `test_help_lists_push_commands`: `shakka alerts --help` toont `run`, `test-push` en `vapid-keys`.

### Overige tests
- `tests/test_migrations.py`: `test_table_keys_match_migrations` groen met `push_subscriptions`; `test_every_migration_table_enables_rls` dekt de nieuwe tabel.
- `tests/test_logsetup.py`: `urllib3` op `WARNING` na `configure_logging`. `test_secret_values` (uitgebreid, review N-11): met `vapid_subject=" mailto:test@example.org "` → het resultaat eindigt op `"mailto:test@example.org"`; met `vapid_subject="mailto:"` staat de waarde er wel in maar `redact("x mailto: y", secret_values(s))` laat de tekst ongewijzigd (korter dan 8); de bestaande twee asserts blijven ongewijzigd.
- `tests/test_cli_pipeline.py::test_budget_warning_on_stdout` (review N-5): controleert `any(line.startswith("::warning::forecast:") ...)`. Bewijs dat de test iets toetst: zonder de geseede `api_usage`-rij zou hij falen (de builder controleert dat één keer lokaal door de seed tijdelijk weg te laten; geen extra test).
- `tests/test_conftest_guard.py` (nieuw, review N-2) `test_real_webpush_is_blocked`: `n = WebPushNotifier(KEYS.private_key, SUBJECT)` (zonder `webpush_fn`) en `with pytest.raises(pytest.fail.Exception): n.send_payload(target, payload)`: de autouse-fixture komt door de `except Exception` van `send_payload` heen. Idem via `deliver_event(n, [target], message, tag="alert-x")`.
- `tests/test_job_alerts_push.py::test_load_targets_reexported` (review N-3): `shakka.jobs.alerts.load_targets is shakka.jobs.push.load_targets`.
- `tests/test_fakes.py` (bestaand) blijft groen; `test_generated_defaults` hoeft niet te wijzigen.
- Volledige suite: `cd ingest && uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`; `supabase test db`.

## Externe afhankelijkheden

| Package | Versie | Reden | Gecontroleerd (15 oktober 2026) |
|---|---|---|---|
| `pywebpush` | `>=2.5,<3` (laatste 2.5.0, 29 augustus 2026; MPL-2.0; Python ≥ 3.10) | Web Push-encryptie (aes128gcm) en versturen met VAPID; staat in het plan. Afhankelijkheden: `aiohttp`, `cryptography>=47.0.0`, `http-ece>=1.1.0`, `requests>=2.21.0`, `py-vapid>=1.7.0`. | https://pypi.org/project/pywebpush/, https://pypi.org/pypi/pywebpush/json |
| `py-vapid` | `>=1.9.6,<2` (laatste 1.9.6; MPL-2.0) | Direct geïmporteerd: `Vapid.from_string` (sleutel één keer parsen), `Vapid.public_key`. | https://pypi.org/pypi/py-vapid/json |
| `cryptography` | `>=47,<51` (laatste 50.0.2) | Direct geïmporteerd: sleutelpaar maken (`ec.generate_private_key(ec.SECP256R1())`) en publieke sleutel serialiseren (`Encoding.X962`, `PublicFormat.UncompressedPoint`). Ondergrens = eis van pywebpush 2.5.0. | https://pypi.org/pypi/cryptography/json |

Gecontroleerd in de broncode van pywebpush (`main`, https://github.com/web-push-libs/pywebpush/blob/main/pywebpush/__init__.py):
- `webpush(subscription_info, data=None, vapid_private_key=None, vapid_claims=None, content_encoding="aes128gcm", curl=False, timeout=None, ttl=0, verbose=False, headers=None, requests_session=None)`;
- `vapid_claims`: als `aud` ontbreekt, zet `webpush()` hem op `scheme://netloc` van het endpoint, **in de meegegeven dict**; `exp` wordt 12 uur vooruit gezet als hij ontbreekt of verlopen is. Daarom een nieuwe dict per aanroep;
- `vapid_private_key` mag een `Vapid01`-instantie zijn (`py_vapid.Vapid` is daar een subklasse van), een bestandspad, of een string voor `Vapid.from_string`;
- een status boven 202 geeft `WebPushException("Push failed: {status} {reason}\nResponse body:{text}", response=response)`; `exc.status_code` leest de status uit de response (of `None`); `__str__` voegt de response-tekst toe. Daarom gebruikt WP-17 alleen `status_code`;
- `ttl` wordt de `TTL`-header (standaard 0: bericht vervalt als het apparaat offline is; WP-17 zet 43.200 s);
- `timeout` gaat ongewijzigd naar `requests.post(endpoint, timeout=timeout, ...)` ([requests, Timeouts](https://requests.readthedocs.io/en/latest/user/advanced/#timeouts));
- logging alleen bij `verbose=True` (claims en headers), dus WP-17 laat `verbose` uit.

Gecontroleerd in de broncode van py_vapid (https://raw.githubusercontent.com/web-push-libs/vapid/main/python/py_vapid/__init__.py, opnieuw op 15 oktober 2026 voor revisie 2): `from_string` haalt `\n` weg, decodeert base64url en gebruikt `from_raw` bij 32 bytes, anders `from_der`; geen PEM. `from_raw` gebruikt `ec.derive_private_key(..., ec.SECP256R1())` en maakt de instantie met `cls(key)` (lege `conf`, dus strikte controle). `sign(claims)` (Vapid01 en Vapid02) roept `_base_sign(claims)` aan; die kopieert de claims, zet `exp = int(time.time()) + 86400` als die ontbreekt, controleert `sub` met `_check_sub` (tenzij `conf["no-strict"]`) en `aud` met `^https?://[^/:]+(:\d+)?$`, en geeft anders `VapidException`. `_check_sub` gebruikt (hoofdletterongevoelig, `re.match`) `^(mailto:.+@((localhost|[%\w-]+(\.[%\w-]+)+|<ipv6>)))|https:\/\/(localhost|[\w-]+\.[\w\.-]+|<ipv6>)$`: een mailto-domein moet een punt hebben (of `localhost`/IPv6), een `https`-subject is alleen een host zonder pad. Daarom beslist de proefhandtekening in `__init__` en geen eigen regex (review B-1).

Web Push-protocol (https://web.dev/articles/push-notifications-web-push-protocol): 201 Created is succes; 404 "The subscription is expired … you should delete the PushSubscription"; 410 "should be removed from application server"; 429 met `Retry-After`; 400; 413 (minimaal ondersteund 4.096 bytes). TTL is verplicht. Push API (https://w3c.github.io/push-api/): `toJSON().keys` is "URL-safe base64 encoding without padding"; het endpoint is een capability-URL.

Supabase: kolomdefault `auth.uid()` voor `user_id` en een insert-policy met `with check` ([Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security), [RAG with Permissions](https://supabase.com/docs/guides/ai/rag-with-permissions)).

GitHub CLI: `gh secret set NAAM` zonder `--body` leest de waarde van stdin of uit een prompt (https://cli.github.com/manual/gh_secret_set), zodat de sleutel niet in de shell-history komt.

Geen API-endpoints van derden behalve de push-services van de browsers (FCM, Mozilla, Apple, WNS), die de endpoint-URL zelf bepaalt. Geen nieuwe betaalde dienst.

## Risico's
- **R1. Aanhoudende niet-permanente fout blokkeert de state van één (gebruiker, spot).** Een 403 (bijv. een abonnement dat met een oude VAPID-sleutel is gemaakt), 400 of 413 komt elke run terug; zolang er geen ander abonnement van die gebruiker slaagt, blijft de diff `deferred` en wordt hij elk uur opnieuw geprobeerd. Zichtbaar via `deferred` en `push_failures` in `ingest_runs`, een `partial` stap en een `::warning::alerts: <n> favorite(s) deferred …`-annotatie per run (review N-1). Mitigatie: RUNBOOK (bij sleutelwissel alle abonnementen verwijderen); een retry-limiet hoort bij WP-22.
  - 401/403 blijven bewust niet-permanent (review N-1): ze komen meestal door onze eigen VAPID-configuratie (ongeldige of verlopen JWT, verkeerde sleutel, klokverschil) en niet door een dood abonnement. Ze permanent maken zou bij één configuratiefout alle abonnementen van alle gebruikers wissen.
  - **Scenario "verkeerde publieke sleutel in de PWA":** hoort `PUBLIC_VAPID_PUBLIC_KEY` (Cloudflare Pages, WP-18) niet bij de ingest-sleutel, dan zijn alle abonnementen met die verkeerde sleutel gemaakt en geeft elke aflevering 403. Elke favoriet met events is dan `deferred`; de run blijft `partial` met exitcode 0 (geen mail), maar de deferred-annotatie staat in elke run in de Actions-log en `push_failures` toont `{"HTTP 403": n}`. Herstel: de juiste sleutel in Cloudflare, `delete from public.push_subscriptions;`, push in de app opnieuw aanzetten (RUNBOOK §14, punt 10).
  - Een `ValueError` bij het bouwen van de payload (review N-9) is deterministisch maar telt als niet-permanent, en zou die favoriet dan elke run blokkeren. Dat kan alleen bij een spot-id van duizenden tekens; spot-id's zijn korte slugs uit `spots.yaml`. Geaccepteerd; de deferred-annotatie maakt het zichtbaar als het toch gebeurt.
- **R2. Dubbele meldingen na een tijdelijke fout** (A4, E13). Geaccepteerd in WP-08; voor bestaande rijen vervangt de `tag` de melding.
- **R3. Looptijd.** Elke aflevering kost een VAPID-handtekening en een TLS-verbinding (geen gedeelde sessie); bij een hangende push-service tot 10 s per aflevering. Bij M2 (een paar gebruikers, enkele events per uur) seconden; bij veel gebruikers moet WP-22 een tijdsbudget of een gedeelde `requests.Session` toevoegen. De job-timeout is 15 minuten.
- **R4. Zwaardere installatie.** `aiohttp`, `requests` en `cryptography` komen mee met pywebpush; `uv sync` in de uurlijkse workflow duurt daardoor iets langer (wheels, geen build). Geen licentie- of kostenprobleem (MPL-2.0, Apache/BSD).
- **R5. Weergave van 50/150 tekens niet gemeten** (WORK_PACKAGES); WP-18 AC-5 toont het op Lars' telefoon.
- **R6. Endpoint als capability.** Wie het endpoint en de sleutels heeft, kan meldingen sturen (met een eigen VAPID-sleutel weigert de push-service dat niet altijd). De rijen zijn alleen voor de eigenaar en de service role leesbaar; ze komen nergens in logs, `ingest_runs` of uitvoer.
- **R7. `last_notified_at` is de run-tijd**, niet het exacte verzendmoment (A2).
- **R8. Verbruik van de gratis push-services.** FCM, Mozilla en Apple rekenen niets voor Web Push; bij misbruik (veel abonnementen) kan een service rate-limiten (429, R1). `MAX_TARGETS_PER_USER` beperkt het per account.

## Buiten scope
- Abonneren in de browser, de service worker en de iOS-installatie-uitleg (WP-18).
- Pushmeldingen aan Lars over gebruik, drempels of storingen (WP-22), retry-limiet, tijdsbudget, host-allowlist en een database-grens op abonnementen per gebruiker (WP-22).
- `Topic`- en `Urgency`-headers, stille uren, meldingsvoorkeuren, andere kanalen.
- Een automatische overgangsstap M1 → push (A1).
- `shakka doctor` uitbreiden met een VAPID-controle.
- De kolom `profiles.telegram_chat_id` verwijderen (WP-22).
- Wijzigingen aan `shakka.domain` buiten `push.py`, aan `store_plan`, `plan_favorite`, `diff_windows` of `render_alert`.

## Stappenplan voor de builder
Werk op branch `wp/WP-17` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-17`. Lees of print `.env` nooit. Draai na elke stap vanuit `ingest/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`; na stap 2 ook `supabase test db` (vanuit de worktree-root, met de lokale stack; zonder Docker komt het bewijs uit de CI-job `db`). Eén commit per stap, commitberichten in het Engels.

1. **Dependencies.** Voeg `cryptography>=47,<51`, `py-vapid>=1.9.6,<2` en `pywebpush>=2.5,<3` toe aan `ingest/pyproject.toml`; `uv lock` en `uv sync`. Controleer `uv run python -c "import pywebpush, py_vapid, cryptography"`. Voeg de autouse-fixture `_no_real_webpush` toe aan `tests/conftest.py` (met `pytest.fail`, zie Bestanden). Suite groen. Commit: `build(WP-17): add pywebpush, py-vapid and cryptography`.
2. **Tabel `push_subscriptions`.** Migratie exact uit Interfaces; `05_push_subscriptions.test.sql` (32 asserts, volgorde uit het Testplan); `01_schema.test.sql` bijwerken; `TABLE_KEYS`; de default in `tests/fakes.py`; `test_migrations.py` (regex zonder `push_subscriptions`). `supabase db reset && supabase test db` groen. Commit: `feat(WP-17): push_subscriptions table with RLS and pgTAP tests`.
3. **`shakka.domain.push`, tests eerst.** Schrijf `tests/test_push_text.py` (rood), dan `domain/push.py`. Controleer de lengtes uit `test_golden_bodies` (110/142/132 ongewijzigd; 133, 148, 105 na inkorten). Wijkt een telling af, controleer dan eerst de telling (handmatig geteld door de planner) en niet de regel; de regel is leidend. `test_domain_purity.py` groen. Commit: `feat(WP-17): push text shortening and payload (pure)`.
4. **`shakka.notify`, tests eerst.** `push_fixtures.py`, `tests/test_notify_webpush.py` (met `test_subject_validation` en `test_subject_check_matches_library`) en `tests/test_conftest_guard.py`, dan `notify/__init__.py`, `notify/base.py` en `notify/webpush.py`. Subjectvalidatie alleen via de witruimte-voorcheck en de proefhandtekening (Ontwerp, Kanaal); geen eigen regex. Commit: `feat(WP-17): notifier interface and WebPushNotifier`.
5. **`shakka.jobs.push`.** `tests/test_job_push.py`, dan `jobs/push.py` (zonder de CLI-runners). Commit: `feat(WP-17): load push targets, deliver one event, maintain subscriptions`.
6. **Alertjob.** `tests/test_job_alerts_push.py`, dan in `jobs/alerts.py`: `AlertJobResult`-velden, `_new_state_id`, `assign_new_ids`, `PlanDelivery`, `deliver_plan`, `run_alerts(notifiers=)`, de re-export `from shakka.jobs.push import load_targets as load_targets` (laat ruff de import sorteren; de alias blijft staan), de docstring. Alle bestaande tests in `test_job_alerts.py` blijven ongewijzigd groen. Commit: `feat(WP-17): deliver alerts between planning and storing (all-or-nothing)`.
7. **Pipeline en logging.** `PUSH_DISABLED_WARNING`, `deferred_warning`, `PipelineContext.notifiers`, `run_hourly(notifiers=)`, `step_alerts` (beide warnings), `alert_counts`; `QUIET_LOGGERS` met `urllib3`; `secret_values` met het subject; tests in `test_pipeline.py` (AC-6, AC-8, `test_hourly_deferred_warning`, shape), `test_logsetup.py` en `test_cli_pipeline.py::test_budget_warning_on_stdout` (`::warning::forecast:`). Commit: `feat(WP-17): pass notifiers through the hourly pipeline`.
8. **CLI.** `run_alerts_cli` met notifiers en de `push:`-regel; `run_test_push_cli` en `run_vapid_keys_cli` in `jobs/push.py`; commando's `alerts test-push --user-id` (type `click.UUID`, `required=True`) en `alerts vapid-keys` in `cli.py` (imports binnen de functies); groepsdocstring `alerts`: `"Alerts: evaluate favorites, record the state and deliver Web Push."`. Tests in `test_cli_push.py`; `test_cli_jobs.py::test_alerts_run_cli` aanpassen zoals in Bestanden. Commit: `feat(WP-17): alerts test-push and vapid-keys commands`.
9. **Workflow.** `hourly.yml` (alleen de drie `VAPID_*`-regels erbij, exact zoals in Interfaces) en `test_hourly_workflow.py`. Commit: `ci(WP-17): pass VAPID secrets to the hourly run`.
10. **RUNBOOK.**
    - Nieuwe §14 "Pushmeldingen (vanaf WP-17)":
      1. wat er gebeurt (alerts gaan als Web Push naar alle apparaten van een gebruiker; abonneren komt met WP-18);
      2. sleutels maken: `cd ingest && uv run shakka alerts vapid-keys`, en de twee regels plus `VAPID_SUBJECT=mailto:<jouw adres>` in `.env` zetten; de uitvoer niet delen of in een workflow draaien. Het subject is `mailto:<adres>` met een domein met een punt, of `https://<host>` zonder pad (bijv. niet `https://…/contact`); een ander subject laat de stap `alerts` falen;
      3. GitHub Secrets: `gh secret set VAPID_PUBLIC_KEY`, `gh secret set VAPID_PRIVATE_KEY`, `gh secret set VAPID_SUBJECT`, en de waarde plakken bij de prompt (niet met `--body`, dan staat hij in je shell-history);
      4. Cloudflare Pages (WP-18): `PUBLIC_VAPID_PUBLIC_KEY` = dezelfde publieke sleutel;
      5. database: `supabase db push` na de merge (§8);
      6. controleren (na WP-18): `uv run shakka alerts test-push --user-id <id>` en de betekenis van de uitvoerregels;
      7. tellers in `ingest_runs` (stap `alerts`): `sent`, `failed`, `no_target`, `deferred`, `removed`, `push_enabled`, `push_failures`, en wat `deferred` betekent (opnieuw geprobeerd in de volgende run; zichtbaar als `::warning::alerts: <n> favorite(s) deferred …` in de Actions-log). Staat die warning in elke run en toont `push_failures` `HTTP 403`, controleer dan of `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare gelijk is aan `VAPID_PUBLIC_KEY` (R1) en volg punt 10;
      8. zonder VAPID-secrets: kanaal uit, `::warning::` per run, de state schuift door zonder melding; onvolledige of ongeldige configuratie: stap `alerts` faalt, mail van GitHub;
      9. overgang naar push (optioneel, A1): wie push aanzet nadat hij al favorieten had (Lars bij de overgang uit M1, maar ook elke latere gebruiker), krijgt de lopende windows niet als melding. Wil je dat voor één gebruiker toch: na het aanzetten van push in de app de SQL `delete from public.alert_state where user_id = '<id>' and status = 'active';` in de SQL Editor; de volgende run pusht de lopende windows als nieuw;
      10. sleutels vervangen: nieuwe sleutels overal zetten, daarna `delete from public.push_subscriptions;` (oude abonnementen werken niet met een nieuwe sleutel, R1) en push in de app opnieuw aanzetten;
      11. privacy: endpoints, sleutels en het subject komen nooit in logs of uitvoer; `shakka alerts run` levert lokaal ook echt af (A11).
    - §12 punt 7: "`last_notified_at` is in M1 altijd leeg; vanaf WP-17 het tijdstip van de run waarin de melding voor het eerst is afgeleverd." Punt 9: `alerts run` levert vanaf WP-17 ook af.
    - §13 punt 2: de secrets `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` en `VAPID_SUBJECT` bij de eenmalige setup (vanaf WP-17; zonder deze secrets geen pushmeldingen).

    Commit: `docs(WP-17): runbook for VAPID keys and push delivery`.
11. **Eindcontrole.** Volledige suite, ruff, `supabase test db`. Controleer met grep: `grep -rn "pywebpush" ingest/src/shakka/domain` geeft niets; `grep -rnE "logger\.(debug|info|warning|error)\(.*(endpoint|p256dh|auth|subject)" ingest/src` geeft niets; `grep -n "verbose=True" -r ingest/src` geeft niets; `grep -n "re.compile" ingest/src/shakka/notify/webpush.py` geeft niets (geen eigen subjectregex). Geen commit als er niets verandert.

## Verwerking review
Ronde 1 (`docs/wp/WP-17/review.md`, CHANGES_REQUIRED), verwerkt in revisie 2.

| Punt | Verwerking |
|---|---|
| **B-1** (blokkerend) subjectvalidatie ruimer dan py_vapid | Overgenomen. De eigen regexen zijn weg. `WebPushNotifier.__init__` stript het subject, doet een witruimte-voorcheck, parseert de sleutel en zet daarna één proefhandtekening `vapid.sign({"sub": subject, "aud": VAPID_PROBE_AUD})` met `VAPID_PROBE_AUD = "https://push.example.invalid"`; elke exception wordt `ValueError(SUBJECT_ERROR) from None` (vaste tekst, nu met "with a domain" en "without a path"). In de pipeline maakt dat de stap `alerts` `failed` (exit 1, mail). Bijgewerkt: A9, Ontwerp "Kanaal" (exacte pseudocode), Interfaces (constanten), E3a/E3b, Externe afhankelijkheden (`_check_sub`/`_base_sign` opnieuw gecontroleerd en geciteerd), RUNBOOK §14 punt 2, stap 4 en 11. Tests: `test_subject_validation` (o.a. `https://shakka.nl/contact`, `https://example.org/contact`, `mailto:lars@example` falen bij constructie; `https://example.org`, `mailto:test@example.org` geldig) en `test_subject_check_matches_library` (constructie en `Vapid.sign` oordelen hetzelfde). |
| N-1 403/401 en een warning bij `deferred` | Overgenomen. 401/403 blijven niet-permanent (onderbouwing in R1). Nieuwe stapwarning `deferred_warning(n)` → `::warning::alerts: <n> favorite(s) deferred: …` in elke run met `deferred > 0`; R1 beschrijft het scenario "verkeerde `PUBLIC_VAPID_PUBLIC_KEY` in de PWA" (403 voor iedereen). Test `test_hourly_deferred_warning`; E7 en RUNBOOK §14 punt 7 bijgewerkt. |
| N-2 autouse-fixture slikt de fout in | Overgenomen. `_no_real_webpush` roept `pytest.fail(..., pytrace=False)` aan (`Failed` is een `BaseException`). Nieuwe test `test_conftest_guard.py::test_real_webpush_is_blocked` bewijst dat hij door `send_payload` en `deliver_event` heen komt. E29 aangepast. |
| N-3 F401 op `load_targets` | Overgenomen: `from shakka.jobs.push import load_targets as load_targets` (redundante alias = expliciete re-export volgens de ruff-documentatie van F401). Test `test_load_targets_reexported`. |
| N-4 pgTAP 15–18 geven `23502` | Overgenomen. Asserts 15–19 geven expliciet `user_id` A mee; de volledige insertwaarden staan nu in het Testplan. |
| N-5 `test_budget_warning_on_stdout` toetst niets meer | Overgenomen: `startswith("::warning::forecast:")`; `test_cli_pipeline.py` staat in Bestanden en stap 7. |
| N-6 renderfout in `test_build_payload` | Overgenomen: "bevat het teken `–` (U+2013) letterlijk en niet de escape-reeks `–`". |
| N-7 uitloggen op een gedeeld apparaat | Overgenomen in "Gevolgen voor latere WP's", WP-18: eerst de eigen rij verwijderen, dan uitloggen. |
| N-8 A1 is blijvend | Overgenomen: A1 zegt nu expliciet dat het voor elke gebruiker geldt die push na favorieten aanzet; WP-18 beslist over een UI-uitleg; RUNBOOK §14 punt 9 en WP-18-gevolgen aangepast. Geen nieuw gedrag (geen scope-uitbreiding). |
| N-9 `ValueError` bij payload blokkeert | Alleen een opmerking in R1, zoals de review voorstelt; geen codewijziging. |
| N-10 SSRF/egress via endpoints | Overgenomen als expliciet WP-22-punt (allowlist van push-hosts, grens in de database). Geen wijziging in WP-17. |
| N-11 subject in `secret_values` | Overgenomen: `secret_values` voegt het gestripte `vapid_subject` toe (vangnet); `test_secret_values` uitgebreid, bestaande asserts ongewijzigd. |
