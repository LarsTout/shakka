# Review WP-01, ronde 1
Oordeel: CHANGES_REQUIRED

De blueprint is grondig en dekt alle acceptatiecriteria. Contracten, schema, rechtenmatrix, CI-pinning en externe bronnen kloppen grotendeels; ik heb ze nagelopen. Twee punten blokkeren. Het eerste is een pgTAP-test die zoals beschreven niet groen kan worden. Het tweede is een correctheidsfout in de paginering van `SupabaseRest`.

## Blokkerend

B-1: De test op `updated_at` in AC-2(e) faalt altijd. Waar: Testplan, AC-2 (e) ("`updated_at` is gewijzigd ten opzichte van vóór de update (`isnt`)"). Waarom: elk pgTAP-bestand draait in één transactie (`begin; … rollback;`), en binnen een transactie geeft `now()` steeds dezelfde waarde (het begin van de transactie). Het profiel van A wordt in dezelfde transactie aangemaakt (`default now()`), en `set_updated_at()` zet `new.updated_at := now()`. Daardoor is de waarde vóór en na de update identiek en faalt `isnt`. De DDL is "exact", dus de builder mag de functie niet naar `clock_timestamp()` omzetten. Hij moet dan zelf kiezen hoe hij A7 (trigger werkt zonder EXECUTE) bewijst. Voorstel: leg de test vast zonder afhankelijkheid van de klok. Bijvoorbeeld zo, als `postgres` vóór de update van A: `alter table public.profiles disable trigger profiles_set_updated_at; update public.profiles set updated_at = '2000-01-01T00:00:00Z' where user_id = A; alter table public.profiles enable trigger profiles_set_updated_at;`. Daarna als A `update … set weight_kg = 80`, en na `reset role` `is(updated_at, now())` of `isnt(updated_at, '2000-01-01T00:00:00Z'::timestamptz)`. Een alternatief is `set local session_replication_role = replica` rond de voorbereidende update. Leg de gekozen variant exact vast, inclusief het aantal asserts in `plan(N)`.

B-2: Paginering is niet deterministisch als de aanroeper een niet-unieke `order` meegeeft. Waar: Ontwerp, "`select` pagineert … altijd met een deterministische `order`", en Interfaces, "Paginering in `select`" plus `test_select_default_order` ("Met `order="valid_at.desc"` gaat die exact door"). Waarom: zonder `order` gebruikt `select` de PK, en dan klopt het. Met een eigen `order` op een niet-unieke kolom (bijv. `order="valid_at"` op `forecast_hours`, met 25 spots × 4 modellen per uur) zijn er gelijke sorteerwaarden. Postgres garandeert dan geen stabiele volgorde tussen de losse `limit`/`offset`-queries: een bounded top-N-sort kiest per `offset` een andere volgorde binnen gelijke waarden. Pagina's kunnen dan rijen overslaan of dubbel teruggeven, zonder foutmelding. WP-10 (`load_inputs`, circa 20.000 forecastrijen) en WP-03 lopen daar stil tegenaan, met verkeerde evaluaties als gevolg. Voorstel: voeg voor tabellen in `TABLE_KEYS` altijd de PK-kolommen toe als tiebreaker, achter de opgegeven `order`, en sla kolommen over die er al in staan. Voorbeeld: `order="valid_at.desc"` op `forecast_hours` wordt `valid_at.desc,spot_id,model`. Een onbekende tabel met een eigen `order` mag ongewijzigd blijven; zet dat in de docstring. Pas `test_select_default_order` daarop aan. `FakeSupabase` doet hetzelfde, zodat de volgorde bij gelijke waarden overeenkomt.

## Niet-blokkerend

N-1: De positieve `lives_ok` in AC-2(g) (`dir_classes = {onshore,side_onshore,sideshore}`) botst met de fixture. In `04` bestaat de regel (A, `pgtap-spot`) al, dus een insert op dezelfde sleutel geeft 23505. Leg de sleutel vast. Bijvoorbeeld: als `postgres` eerst favoriet (A, `pgtap-spot-2`) toevoegen en de positieve insert daarop doen. Dat is los van (d), waar A juist geen favoriet op `pgtap-spot-2` mag aanmaken voor B.

N-2: E3 en E4 claimen 23514 voor `alert_rules` (weekdag 0 of 8, `{}`, null-element, `earliest_local >= latest_local`, `min_kn >= max_kn`), maar de CHECK-tabel in `01_schema.test.sql` heeft geen rij voor `alert_rules`. De fixture-favoriet (A, `pgtap-spot`) staat er wel, kennelijk met dit doel. Voeg een rij `alert_rules` toe met in elk geval: `weekdays='{0}'`, `'{8}'`, `'{}'`, `earliest_local='18:00', latest_local='17:00'`, `min_kn=20, max_kn=15`, `min_go_hours=0`, `days_ahead=8` en `min_kn=4`. `forecast_hours.gust_kn=-1` en `tide_extremes` zijn optioneel.

N-3: Er zijn pgTAP-overloads waarbij ongetypeerde literals dubbelzinnig of verkeerd resolven:
- `function_privs_are('public','handle_new_user','{}',<rol>,'{}')` past ook op de variant `(:function, :args, :role, :privileges, :description)`;
- `policies_are('public','api_usage','{}')` past ook op `(:table, :policies, :description)`;
- `has_trigger('auth','users','on_auth_user_created')` resolvet bij drie `unknown`-argumenten naar `(table, trigger, description)`, omdat `text` het preferred type is.

Schrijf voor: arrays altijd casten (`'{}'::name[]`) en bij deze functies altijd een beschrijving meegeven. In de FK-`set_eq` is `confdeltype` van type `"char"`, dus gebruik `confdeltype::text`, zodat de vergelijking met de `values`-lijst typeert.

N-4: A3 wijkt bewust af van de letterlijke tekst van AC-2(c) ("leest 0 rijen" wordt `permission denied`, 42501). Inhoudelijk is dit strenger en consistent met WP-19 en de rechtenmatrix; ik ga akkoord. Zorg wel dat de verifier dit als invulling van AC-2(c) accepteert (de orchestrator kan het in STATUS of in de verificatie-opdracht noemen).

N-5: Een upsert met twee rijen met dezelfde PK in één batch faalt in Postgres met 21000 ("ON CONFLICT DO UPDATE command cannot affect row a second time"). De fake zou die rijen stil mergen. Leg vast dat `FakeSupabase.upsert` dan `DatabaseError(code="21000")` geeft, zodat een parserbug in WP-03 of WP-12 (dubbele `(spot_id, model, valid_at)`) in jobtests zichtbaar wordt.

N-6: De fake bewaart timestamps zoals ze zijn verstuurd (`…Z`, of `+02:00` bij `zzp-b`). Echt PostgREST geeft ze genormaliseerd terug (`+00:00`, sessietijdzone UTC). Zet dit in de lijst "Wat de fake níet nabootst", met de regel dat latere WP's timestamps altijd parsen (`datetime.fromisoformat`) en nooit als string vergelijken.

N-7: Vul "Gevolgen voor latere WP's" aan met de CHECKs die nieuw zijn ten opzichte van de contracten. Anders faalt een sync of CLI pas tegen de echte database:
- WP-02 moet een lege of witruimte-`name` weigeren (`spots_name_not_blank`);
- WP-07 en WP-10 (`admin rule set`) moeten `weekdays` en `dir_classes` niet leeg laten zijn en `earliest_local < latest_local` afdwingen;
- WP-10 (`admin profile set --telegram-chat-id`) moet het formaat `^-?[0-9]{1,20}$` controleren.

N-8: Overweeg in migratie 1 een backfill direct na de trigger: `insert into public.profiles (user_id) select id from auth.users on conflict do nothing;`. A2 garandeert geen migraties, maar niet dat er nog geen auth-users zijn. Als Lars al een user heeft aangemaakt, mist anders het profiel, en een `update` via de PWA (R8) raakt dan 0 rijen. Lokaal is dit een no-op.

N-9: `filter_params` accepteert kolomnamen die in PostgREST gereserveerde queryparameters zijn (`select`, `order`, `limit`, `offset`, `on_conflict`, `columns`, `or`, `and`, `not`). Geen enkele huidige kolom heet zo, maar een weigering met `ValueError` kost één regel en voorkomt verwarrende fouten.

N-10: R3, stille afkapping bij "Max rows" < 1000: een robuuster stopcriterium is "stop bij een lege pagina", in plaats van `len(page) < want`. Dat kost hooguit één extra request per `select`. Het mag ook bij de RUNBOOK-waarschuwing blijven.

N-11: In A6 staat "Supabase bevestigt dit". In discussie #45329 spreken de bronnen elkaar juist tegen: een maintainer adviseert wél een sequence-grant. De conclusie klopt wel: Postgres evalueert identity-defaults via `NextValueExpr` zonder rechtencheck, en pgTAP toetst het. Pas de onderbouwing aan, zodat niemand later een sequence-grant toevoegt "omdat Supabase dat zegt".

N-12 (optioneel): `FakeSupabase` legt `on_conflict` niet vast. WP-02 AC-5 en WP-03 AC-5 toetsen "gebruikt `on_conflict=…`" nu alleen indirect, via de 42P10-check op verzamelingsgelijkheid. Een attribuut `upserts: list[tuple[str, str]]` (tabel, `on_conflict`) maakt die AC's direct toetsbaar.

## Gecontroleerde bronnen
- https://supabase.com/docs/reference/cli/supabase-start (`-x`: `gotrue, realtime, storage-api, imgproxy, kong, mailpit, postgrest, postgres-meta, studio, edge-runtime, logflare, vector, supavisor`; de uitsluitingen in de blueprint zijn geldig)
- https://supabase.com/docs/reference/cli/supabase-test-db (`supabase/tests`, `.sql`/`.pg`, vereist `supabase start`)
- https://supabase.com/docs/reference/cli/supabase-db-push (`--dry-run`, `--linked`; `migration list --linked`)
- https://api.github.com/repos/supabase/setup-cli/tags (v3.0.1 = `45a513f8c64c0bc8e0e3dfe572b5c95be85f6359`)
- https://raw.githubusercontent.com/supabase/setup-cli/v3.0.1/action.yml (input `version`)
- https://registry.npmjs.org/supabase/latest (2.121.0)
- https://supabase.com/docs/guides/api/api-keys (secret key alleen in `apikey`, `service_role` met BYPASSRLS, grants blijven nodig, 401 bij een browser-User-Agent)
- https://github.com/orgs/supabase/discussions/45329 (`auto_expose_new_tables` onder `[api]`, sinds v2.102, verwijdering 2026-10-30; tegenstrijdige uitspraken over sequence-grants; PUBLIC houdt EXECUTE op functies)
- https://raw.githubusercontent.com/PostgREST/postgrest/main/docs/references/api/tables_views.rst (quoting van gereserveerde tekens in `in`, bulk insert "all-matching keys", upsert met `on_conflict` en `merge-duplicates`)
- https://docs.postgrest.org/en/v10/_sources/releases/v10.0.0.rst.txt (`max-rows` geldt niet meer voor POST/PATCH/DELETE-representaties, dus de telling via `return=representation` wordt niet afgekapt)
- https://pgtap.org/documentation.html (signatures van `throws_ok`, `results_eq`, `set_eq`, `is_empty`, `table_privs_are`, `column_privs_are`, `function_privs_are`, `policies_are`)
