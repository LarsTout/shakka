# Review WP-01, ronde 2
Oordeel: APPROVED

Beide blokkerende punten uit ronde 1 zijn echt opgelost:
- **B-1 (`updated_at`-test):** sectie (e) zet `updated_at` als `postgres` terug met de trigger tijdelijk uit. Assert 21 is een preconditie op de teruggezette waarde, en assert 26 toetst `is(updated_at, now())` na de update door A. Dat werkt omdat `now()` binnen de transactie constant is en de trigger exact die waarde zet. De DDL blijft ongewijzigd.
- **B-2 (paginering):** `effective_order` zet de ontbrekende PK-kolommen als tiebreaker achter de `order`, en client en fake gebruiken die allebei. Daarmee is de volgorde uniek. De tests en de pariteitscases (`order_ties_*`) dekken het.

De niet-blokkerende punten N-1 tot en met N-12 zijn ook verwerkt.

Wat ik opnieuw heb nagelopen:
- het aantal asserts per bestand (71/70, 55, 22 en 42);
- de 86 kolommen in de kolom-`set_eq`;
- alle 22 `FILTER_CASES` met de verwachte volgorde, tegen `PARITY_ROWS`;
- de 19 redencodes tegen de tabel van WP-05;
- de bereiken tegen WP-02 en WP-16;
- de RLS-volgorde bij insert: de WITH CHECK gaat vóór de CHECK-constraints en de unieke index, dus assert 16 geeft 42501 en niet 23505;
- de PostgREST-statuscodes in de fake.

Op correctheid en contracten vond ik geen blokkerende fouten meer.

## Blokkerend
Geen.

## Niet-blokkerend
N-1: De FK-`set_eq` in `01_schema.test.sql` heeft geen schemafilter. Waar: Testplan AC-2(a), "Eén `set_eq` op `pg_constraint` (`contype = 'f'`)". Waarom: zonder filter komen ook de FK's van `auth` (bijv. `auth.identities` → `auth.users`, `auth.sessions`, `auth.mfa_factors`) en lokaal ook die van `storage` in de set, en dan faalt de assert altijd. Voorstel: filter op `connamespace = 'public'::regnamespace`. Dat is geen ontwerpkeuze; de builder mag dit zonder `deviations.md`-melding doen.

N-2: `table_privs_are` voor `authenticated` op `profiles` moet `array['SELECT']::name[]` verwachten. Waar: Rechtenmatrix ("SELECT (+ kolom-UPDATE op 5 kolommen)") en `02_privileges.test.sql`. Waarom: pgTAP gebruikt `has_table_privilege`, en dat kijkt alleen naar rechten op tabelniveau. De kolom-UPDATE hoort bij `column_privs_are`, en die staat al correct in de blueprint. Voorstel: zet de verwachte waarde letterlijk in het testplan, zodat de builder niet `['SELECT','UPDATE']` invult.

N-3: De CHECK-`throws_ok`-inserts in `01` moeten alle `not null`-kolommen zonder default meegeven. Voorbeelden: `evaluations.evaluated_at`, `forecast_hours.fetched_at`, `alert_state.snapshot`/`window_*`/`status`, `tide_extremes.level_cm`/`fetched_at` en `ingest_runs.started_at`. Anders geeft Postgres 23502 in plaats van 23514. Voor `alert_rules` staat het al goed ("alleen `user_id`, `spot_id` en de te toetsen kolom(men)"). Voor de andere tabellen kan één zin volstaan: "vul alle verplichte kolommen met een geldige waarde, behalve de te toetsen kolom".

N-4: `alter table … disable trigger` in sectie (e) vereist dat de rol eigenaar is van de tabel. Dat klopt zolang de migraties en `pg_prove` allebei als `postgres` draaien, wat bij de Supabase CLI het geval is. Geeft dit toch "must be owner", noteer dan de uitwijkroute in `deviations.md`, bijvoorbeeld een `security definer`-hulpfunctie binnen de testtransactie. Kleine kans; alleen ter info.

## Gecontroleerde bronnen
- https://raw.githubusercontent.com/PostgREST/postgrest/main/docs/references/errors.rst (23503/23505 → 409; 42501 → 401/403; 21000, 23502, 23514, 42P10 en 428C9 → 400 als "other"; PGRST202 → 404)
- https://raw.githubusercontent.com/theory/pgtap/master/sql/pgtap.sql.in (`table_privs_are(NAME, NAME, NAME, NAME[], TEXT)` via `_get_table_privs` en `has_table_privilege`; de gecontroleerde privileges zijn DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE en UPDATE, zonder MAINTAIN)
- https://www.postgresql.org/docs/17/functions-info.html (`has_table_privilege` tegenover `has_any_column_privilege`/`has_column_privilege` bij kolomrechten)
- Ronde 1 (blijft geldig, niet opnieuw opgehaald): supabase-start, supabase-test-db, supabase-db-push, setup-cli v3.0.1 SHA, npm `supabase` 2.121.0, api-keys, discussie #45329, PostgREST tables_views.rst
