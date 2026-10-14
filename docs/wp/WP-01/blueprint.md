# Blueprint WP-01: Datamodel M1, RLS en database-client
Status: APPROVED
Revisie: 2

## Doel
Alle tabellen die M1 nodig heeft, als migraties in `supabase/migrations/`, met CHECK-constraints, indexen, RLS-policies en expliciete grants. Daarnaast de `profiles`-trigger en pgTAP-tests die het gedrag aantonen. Aan de Python-kant komen er twee dingen bij:
- `shakka.db.SupabaseRest`: een dunne PostgREST-client op httpx;
- `ingest/tests/fakes.py::FakeSupabase`: een in-memory nep-database met dezelfde publieke methoden en dezelfde filtersemantiek.

Na deze WP kunnen WP-02, WP-03 en WP-04 parallel bouwen. Hun jobtests draaien op `FakeSupabase` en hun lokale acceptatietests op de lokale stack.

## Aannames
- A1. **Docker bij de builder.** De builder heeft Docker (Docker Desktop of OrbStack) en de Supabase CLI 2.121.0 lokaal, zodat `supabase start`, `supabase db reset` en `supabase test db` lokaal draaien. Ontbreekt Docker, dan schrijft de builder de SQL en pgTAP toch. Het bewijs komt dan uit de CI-job `db` na een push. Pushen gebeurt alleen met toestemming van de orchestrator.
- A2. **Remote project.** Lars' remote project is aangemaakt met "Automatically expose new tables" uit (WORK_PACKAGES, "Supabase-project") en heeft nog geen migraties. De migraties hangen niet af van die instelling, want ze doen per tabel een expliciete `revoke all` en daarna `grant` (zie Ontwerp).
- A3. **Lezen zonder grant.** AC-2(c) zegt "`anon` leest 0 rijen" uit de privé-tabellen. Dit ontwerp is strenger: `anon` krijgt op die tabellen géén grant, dus een `select` als `anon` geeft `permission denied` (SQLSTATE 42501) en levert geen enkele rij op. De pgTAP-test toetst precies dat (`throws_ok … '42501'`). Waarom: minste rechten, en de PWA leest deze tabellen nooit uitgelogd (WP-16 AC-6). Via REST geeft dit een 401/403 in plaats van `[]`. De reviewer heeft deze afwijking geaccepteerd (review ronde 1, N-4). De orchestrator noemt in de verificatieopdracht dat de `throws_ok … '42501'`-asserts in `03_rls_anon.test.sql` de invulling van AC-2(c) zijn.
- A4. **Alleen de `apikey`-header.** De secret key gaat alleen in de `apikey`-header, zonder `Authorization`. Dat schrijven de Supabase-docs voor bij `sb_secret_…`-sleutels, en zo werkte het in WP-00 al tegen Lars' project. Legacy JWT-sleutels worden door `SupabaseRest` niet ondersteund.
- A5. **Pagineringsgrens.** De PostgREST-instelling `max_rows` is 1000: lokaal in `config.toml` en in het hosted project als standaard. `SupabaseRest` vraagt pagina's van 1000 en stopt pas bij een lege pagina. Verlaagt Lars "Max rows" in het dashboard, dan blijft het resultaat compleet; het kost alleen meer requests (zie R3).
- A6. **Identity-kolom zonder sequence-grant.** Een identity-kolom (`ingest_runs.id`) heeft geen sequence-grant nodig voor inserts via de API. De onderbouwing is Postgres zelf: een identity-default wordt geëvalueerd via `NextValueExpr`, en daarbij controleert Postgres geen rechten op de sequence (anders dan bij een expliciete `nextval()`). Supabase-bronnen zijn hierover niet eenduidig: in discussie #45329 adviseert een maintainer juist wél een sequence-grant. Daarom is het geen aanname op gezag: pgTAP toetst het (`service_role` insert in `ingest_runs`, zonder sequence-grant). Voeg dus geen sequence-grant toe zolang die test groen is.
- A7. **EXECUTE op triggerfuncties.** Triggerfuncties hebben bij het afgaan geen `EXECUTE`-recht van de aanroepende rol nodig. Daarom wordt `EXECUTE` op `set_updated_at()` en `handle_new_user()` voor alle API-rollen ingetrokken. pgTAP toetst dat de triggers als `authenticated` en bij een insert in `auth.users` gewoon werken.
- A8. **Drempels in de database zijn de bron voor de formulieren.** WP-16 eist "validatie gelijk aan de DB-constraints". Daarom staan de bereiken voor de profiel- en regelvelden hier vast (zie Interfaces): kn 5–60, quiver 3–21 m² met maximaal 10 kites, `min_go_hours` 1–24, `days_ahead` 0–7. WP-07 en WP-16 nemen deze bereiken over.

## Ontwerp

**Twee migraties.** `…_m1_schema.sql` maakt de tabellen, constraints, indexen, de `updated_at`-triggers en de `profiles`-trigger op `auth.users`. `…_m1_security.sql` doet RLS, revokes, grants, policies en functieprivileges. Zo staat de hele beveiliging op één plek en is die als geheel te reviewen. `supabase db push` past beide in volgorde toe. Er is geen `seed.sql`: spots komen via `shakka spots sync` (WP-02).

**Grants deterministisch, los van de instelling.** De Supabase CLI kent sinds v2.102 `[api] auto_expose_new_tables`. De documentatie is tegenstrijdig over de standaardwaarde: de release notes van v2.106.0 zeggen `false`, maar het template van 2.121.0 zegt "Left unset, a fresh project falls back to `true`". Ook staat de vlag gepland voor verwijdering op 2026-10-30. Daarom twee lagen:
1. `config.toml` zet `auto_expose_new_tables = false` expliciet, zodat de lokale stack zich gedraagt als het remote project, zoals WORK_PACKAGES eist.
2. De migratie doet per tabel `revoke all … from public, anon, authenticated, service_role` en geeft daarna precies de bedoelde grants, ook aan `service_role`.

Het resultaat is identiek, ongeacht de instelling. pgTAP legt de privileges per tabel en rol exact vast met `table_privs_are`. `TRUNCATE`, `REFERENCES` en `TRIGGER`, die Supabase standaard nog wel uitdeelt, verdwijnen daarmee ook.

**Schema.**
- Enums zijn `text` met een CHECK (geen Postgres-enumtypes). Een nieuwe waarde is dan een simpele constraintwissel in een latere migratie.
- Bereiken uit de contracten van WP-01 en WP-02 worden in de database afgedwongen als vangnet. WP-02 valideert ze ook in Python.
- Twee extra CHECKs beschermen de harde regel "offshore en side-offshore zijn altijd `no_go`":
  - `alert_rules.dir_classes` mag alleen `onshore`, `side_onshore` en `sideshore` bevatten (contract);
  - een `evaluations`-rij met `dir_class` in (`offshore`, `side_offshore`) moet `verdict = 'no_go'` hebben. Een bug in WP-05 of WP-10 kan zo nooit een rijdbaar offshore-uur in de database zetten.
- `evaluations.reasons` krijgt een CHECK tegen de vaste lijst redencodes uit WP-05. Een nieuwe redencode vraagt dus een migratie (R5).
- `updated_at` wordt door een triggerfunctie `public.set_updated_at()` gezet op `spots`, `profiles`, `alert_rules` en `alert_state`.

**RLS.**
- `enable row level security` staat op alle tien tabellen.
- Policies gebruiken `(select auth.uid())`, het patroon dat Supabase aanbeveelt voor performance.
- Leestabellen (`spots`, `forecast_hours`, `tide_extremes`, `evaluations`) hebben een `select`-policy `using (true)` voor `anon` en `authenticated`, en alleen een `select`-grant.
- `profiles`:
  - `select` en `update` op de eigen rij;
  - `update` is als kolomprivilege alleen toegestaan op `weight_kg`, `level`, `quiver_m2`, `default_min_kn` en `default_max_kn`. Dat volgt het patroon uit de docs: `revoke update` op de tabel en `grant update (kolommen)`. `telegram_chat_id`, `user_id` en de tijdstempels zijn daardoor niet wijzigbaar door `authenticated`.
- `favorites` en `alert_rules`: vier policies (select, insert, update en delete) op de eigen rijen.
- `alert_state`: alleen `select` op de eigen rijen.
- `api_usage` en `ingest_runs`: geen policies en geen grants voor `anon` en `authenticated`. Alleen `service_role` (secret key, `BYPASSRLS`) komt erbij.

**`profiles`-trigger.** Dit volgt het patroon uit de Supabase-docs: `handle_new_user()` als `security definer set search_path = ''`, aangeroepen door `on_auth_user_created after insert on auth.users`. Met `on conflict do nothing` blokkeert een dubbele aanroep de signup niet. Direct na de trigger volgt een backfill (`insert … select id from auth.users on conflict do nothing`). Heeft Lars in het remote project al een auth-user aangemaakt vóór de migratie, dan krijgt die alsnog een profiel; anders raakt een `update` vanuit de PWA (R8) 0 rijen. Lokaal en in CI is de backfill een no-op.

**`SupabaseRest`.** Een dunne client voor PostgREST (`{SUPABASE_URL}/rest/v1/…`):
- Alleen de header `apikey: <secret>`. Validatie gebeurt vóór elke request:
  - tabel- en kolomnamen moeten identifiers zijn (`^[a-z_][a-z0-9_]*$`);
  - een filterkolom mag geen door PostgREST gereserveerde queryparameter zijn (`select`, `order`, `limit`, `offset`, `on_conflict`, `columns`, `or`, `and`, `not`);
  - de operatoren moeten in een vaste set zitten (`eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `in`, `is.null`).

  Zo kan een pad- of query-injectie niet ontstaan, en gedragen de echte client en de fake zich precies hetzelfde.
- **Filters** zijn `Mapping[str, str | Sequence[str]]`. Een lijst geeft dezelfde parameter meerdere keren, en PostgREST combineert die met AND. Postgrest-js doet dat ook voor `.gte().lt()` op één kolom. Het contract (`Mapping[str, str]`) blijft geldig, want dit is een uitbreiding. Zonder die uitbreiding zijn bereiken op één kolom (WP-03, WP-10) niet uit te drukken.
- **`select`** pagineert met `limit` en `offset` in pagina's van 1000, altijd met een deterministische `order` (helper `effective_order`):
  - zonder `order` wordt de primaire sleutel uit `TABLE_KEYS` gebruikt;
  - met een eigen `order` op een tabel uit `TABLE_KEYS` worden de PK-kolommen die nog niet in de `order` staan er als tiebreaker achter gezet (oplopend). Voorbeeld: `order="valid_at.desc"` op `forecast_hours` wordt `valid_at.desc,spot_id,model`. Zonder tiebreaker garandeert Postgres bij gelijke sorteerwaarden geen stabiele volgorde tussen losse `limit`/`offset`-queries, en zouden pagina's stil rijen overslaan of dubbel geven;
  - een onbekende tabel met een eigen `order` gaat ongewijzigd door (staat in de docstring: de aanroeper is dan zelf verantwoordelijk voor een unieke volgorde);
  - een onbekende tabel zonder `order` geeft een `ValueError`.

  De lus stopt pas bij een lege pagina (of als `limit` bereikt is), niet bij een korte pagina. Zo blijft het resultaat compleet als de server minder rijen per pagina geeft dan gevraagd.
- **`upsert`** gebruikt `POST ?on_conflict=…` met `Prefer: resolution=merge-duplicates, return=minimal`, in batches van 500. Alle rijen moeten dezelfde sleutels hebben (eis van PostgREST bij bulk inserts), anders volgt een `ValueError` vóór de eerste request.
- **`update` en `delete`** weigeren een lege filterset met een `ValueError`. Ze vragen `return=representation` met `select=<sleutelkolommen>` en tellen de teruggegeven rijen. PostgREST documenteert geen telling via `Content-Range` voor schrijfacties.
- **JSON-codering:**
  - `datetime` moet tz-aware zijn en wordt UTC met `Z`;
  - `date` en `time` worden ISO;
  - `set` en `frozenset` worden een gesorteerde lijst;
  - NaN of oneindig geeft een `ValueError`.
- **Fouten** worden een `DatabaseError` met `status` en de PostgREST-`code`. De melding is ingekort en de secret is eruit geredigeerd. Bij transportfouten staat alleen de klassenaam in de melding (`from None`).
- **Geen retries.** Die komen uniform in WP-22 (`with_retries`).

**`FakeSupabase`.** De fake gebruikt dezelfde validatie- en parseerhelpers uit `shakka.db`: filters, order, kolommen en JSON-codering. Daarmee zijn de foutgevallen en de codering per definitie gelijk. Het gedrag volgt de semantiek van PostgREST en SQL:
- `null` matcht nooit bij `eq`, `neq`, `lt`, `lte`, `gt`, `gte` en `in`, alleen bij `is.null`;
- timestamps worden als tijdstip vergeleken, ongeacht de offsetnotatie;
- getallen worden numeriek vergeleken;
- `asc` zet nulls achteraan, `desc` vooraan, en `.nullsfirst` en `.nullslast` overschrijven dat;
- `upsert` werkt kolomsgewijs (merge van alleen de meegegeven kolommen);
- PK-schending geeft `23505`; twee rijen met dezelfde PK in één upsert-batch geven `21000`, zoals Postgres;
- de volgorde gebruikt dezelfde `effective_order` (inclusief PK-tiebreaker) als de echte client;
- kolomdefaults en de `updated_at`-trigger worden nagebootst;
- de cascades `spots` → … en `favorites` → `alert_rules` worden ook nagebootst.

FK- en CHECK-constraints worden níet nagebootst; daarvoor zijn de pgTAP-tests. Een gedeelde casuslijst (`tests/fake_cases.py`) draait tegen de fake (altijd) en optioneel tegen de lokale stack (`tests/test_fake_parity.py`, alleen als `SHAKKA_TEST_SUPABASE_URL` naar localhost wijst). Zo is de pariteit met echt PostgREST aantoonbaar en niet alleen beweerd.

**CI.** Er komt een nieuwe job `db` in `ci.yml`:
- `supabase/setup-cli`, gepind op de SHA van v3.0.1, met CLI 2.121.0 (dezelfde versie als lokaal);
- `supabase start` zonder de diensten die de tests niet nodig hebben;
- daarna `supabase test db`.

`gotrue` (die het `auth`-schema migreert), `kong` en `postgrest` blijven aan. Er zijn geen secrets nodig.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `supabase/config.toml` | wijzigen | In `[api]` wordt de regel `# auto_expose_new_tables = true` vervangen door `auto_expose_new_tables = false`. De commentaarregels erboven blijven. Verder niets. |
| `supabase/migrations/20261015090000_m1_schema.sql` | aanmaken | Functie `set_updated_at`, 10 tabellen, constraints, indexen, `updated_at`-triggers, `handle_new_user`, de trigger `on_auth_user_created` en de profiel-backfill. Exacte DDL staat in Interfaces. |
| `supabase/migrations/20261015090100_m1_security.sql` | aanmaken | RLS aan, revokes, grants, kolomprivileges, policies en functieprivileges (zie Interfaces). |
| `supabase/tests/01_schema.test.sql` | aanmaken | pgTAP: tabellen, kolommen, types en nullability, PK's, FK's met cascade, CHECK-constraints, RLS aan en triggers. |
| `supabase/tests/02_privileges.test.sql` | aanmaken | pgTAP: `table_privs_are` per tabel en rol, kolomprivileges `profiles` en functieprivileges. |
| `supabase/tests/03_rls_anon.test.sql` | aanmaken | pgTAP: wat `anon` wel en niet mag. |
| `supabase/tests/04_rls_users.test.sql` | aanmaken | pgTAP: gebruiker A tegenover B, `telegram_chat_id`, trigger, `dir_classes`, cascade en `service_role`. |
| `.github/workflows/ci.yml` | wijzigen | Job `db` toevoegen. Job `ingest` blijft ongewijzigd. |
| `ingest/src/shakka/db.py` | aanmaken | `DatabaseError`, `SupabaseRest`, `TABLE_KEYS`, constanten en helpers (zie Interfaces). |
| `ingest/tests/fakes.py` | aanmaken | `FakeSupabase` (zie Interfaces). |
| `ingest/tests/fake_cases.py` | aanmaken | `PARITY_ROWS` en `FILTER_CASES`, gedeeld door `test_fakes.py` en `test_fake_parity.py`. |
| `ingest/tests/test_db.py` | aanmaken | AC-3 (MockTransport). |
| `ingest/tests/test_fakes.py` | aanmaken | AC-4. |
| `ingest/tests/test_fake_parity.py` | aanmaken | Optionele pariteitstest tegen de lokale stack. Wordt overgeslagen zonder env. |
| `ingest/tests/test_migrations.py` | aanmaken | AC-6, plus de controle dat `TABLE_KEYS` en de migraties overeenkomen. |
| `ingest/tests/test_repo_hygiene.py` | wijzigen | `test_ci_workflow_contract` uitbreiden met de job `db`, en een nieuwe test `test_supabase_config_disables_auto_expose`. |
| `docs/RUNBOOK.md` | wijzigen | Sectie 6 aanvullen en een nieuwe sectie 8 "Database en migraties" (zie Interfaces). Sectie 7 noemt de job `db`. |

Geen andere bestanden. `docs/STATUS.md` werkt de orchestrator bij. Geen nieuwe Python-dependencies.

## Interfaces en contracten

### `supabase/config.toml` (alleen deze regel wijzigt)
```toml
[api]
...
# auto_expose_new_tables comment lines stay as generated
auto_expose_new_tables = false
```

### Migratie 1: `supabase/migrations/20261015090000_m1_schema.sql` (exact)
```sql
-- M1 schema: tables, constraints, indexes, triggers. Security lives in *_m1_security.sql.

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create table public.spots (
  id text primary key
    constraint spots_id_slug check (id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  name text not null constraint spots_name_not_blank check (btrim(name) <> ''),
  region text null,
  lat double precision null constraint spots_lat_range check (lat between -90 and 90),
  lon double precision null constraint spots_lon_range check (lon between -180 and 180),
  shore_normal_deg smallint null
    constraint spots_shore_normal_range check (shore_normal_deg between 0 and 359),
  ridable_dirs jsonb null
    constraint spots_ridable_dirs_array check (ridable_dirs is null or jsonb_typeof(ridable_dirs) = 'array'),
  hazards text null,
  tide_sensitive text not null default 'none'
    constraint spots_tide_sensitive_enum
    check (tide_sensitive in ('none', 'prefer_low', 'prefer_high', 'avoid_low')),
  tide_min_level_cm integer null
    constraint spots_tide_min_level_range check (tide_min_level_cm between -300 and 300),
  rws_station text null,
  season jsonb not null default '[]'::jsonb
    constraint spots_season_array check (jsonb_typeof(season) = 'array'),
  status text null constraint spots_status_enum check (status in ('allowed', 'limited', 'forbidden')),
  level text null
    constraint spots_level_enum check (level in ('beginner', 'intermediate', 'advanced')),
  default_min_kn smallint null
    constraint spots_default_min_kn_range check (default_min_kn between 5 and 40),
  notes text null,
  verified boolean not null default false,
  updated_at timestamptz not null default now(),
  constraint spots_lat_lon_together check ((lat is null) = (lon is null))
);

create table public.forecast_hours (
  spot_id text not null references public.spots (id) on delete cascade,
  model text not null constraint forecast_hours_model_enum check (model in ('knmi', 'icon', 'ecmwf', 'gfs')),
  valid_at timestamptz not null,
  wind_kn real null constraint forecast_hours_wind_nonneg check (wind_kn >= 0),
  gust_kn real null constraint forecast_hours_gust_nonneg check (gust_kn >= 0),
  dir_deg smallint null constraint forecast_hours_dir_range check (dir_deg between 0 and 359),
  fetched_at timestamptz not null,
  primary key (spot_id, model, valid_at)
);
create index forecast_hours_valid_at_idx on public.forecast_hours (valid_at);

create table public.tide_extremes (
  station text not null,
  at timestamptz not null,
  kind text not null constraint tide_extremes_kind_enum check (kind in ('high', 'low')),
  level_cm integer not null,
  fetched_at timestamptz not null,
  primary key (station, at)
);
create index tide_extremes_at_idx on public.tide_extremes (at);

create table public.evaluations (
  spot_id text not null references public.spots (id) on delete cascade,
  valid_at timestamptz not null,
  verdict text not null constraint evaluations_verdict_enum check (verdict in ('go', 'marginal', 'no_go')),
  reasons text[] not null default '{}'
    constraint evaluations_reasons_enum check (
      array_position(reasons, null) is null
      and reasons <@ array[
        'no_data', 'wind_too_light', 'wind_too_strong', 'wind_borderline', 'too_gusty', 'gusty',
        'offshore', 'side_offshore', 'direction_unknown', 'direction_not_ridable', 'dark',
        'season_closed', 'spot_forbidden', 'spot_limited', 'status_unknown', 'tide_too_low',
        'tide_unfavorable', 'tide_unknown', 'low_confidence'
      ]::text[]
    ),
  wind_kn real null,
  gust_kn real null,
  dir_deg smallint null constraint evaluations_dir_range check (dir_deg between 0 and 359),
  dir_class text null constraint evaluations_dir_class_enum
    check (dir_class in ('onshore', 'side_onshore', 'sideshore', 'side_offshore', 'offshore')),
  confidence text null
    constraint evaluations_confidence_enum check (confidence in ('high', 'medium', 'low')),
  tide_level_cm integer null,
  evaluated_at timestamptz not null,
  primary key (spot_id, valid_at),
  -- Hard rule: offshore and side-offshore are never ridable.
  constraint evaluations_offshore_is_no_go
    check (dir_class is null or dir_class not in ('offshore', 'side_offshore') or verdict = 'no_go')
);
create index evaluations_valid_at_idx on public.evaluations (valid_at);

create table public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  weight_kg smallint null constraint profiles_weight_range check (weight_kg between 30 and 200),
  level text null
    constraint profiles_level_enum check (level in ('beginner', 'intermediate', 'advanced')),
  quiver_m2 real[] not null default '{}'
    constraint profiles_quiver_valid check (
      cardinality(quiver_m2) <= 10
      and array_position(quiver_m2, null) is null
      and 3 <= all (quiver_m2)
      and 21 >= all (quiver_m2)
    ),
  default_min_kn smallint null constraint profiles_min_kn_range check (default_min_kn between 5 and 60),
  default_max_kn smallint null constraint profiles_max_kn_range check (default_max_kn between 5 and 60),
  telegram_chat_id text null
    constraint profiles_telegram_chat_id_format check (telegram_chat_id ~ '^-?[0-9]{1,20}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_min_lt_max
    check (default_min_kn is null or default_max_kn is null or default_min_kn < default_max_kn)
);

create table public.favorites (
  user_id uuid not null references auth.users (id) on delete cascade,
  spot_id text not null references public.spots (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, spot_id)
);
create index favorites_spot_id_idx on public.favorites (spot_id);

create table public.alert_rules (
  user_id uuid not null,
  spot_id text not null,
  enabled boolean not null default true,
  min_kn smallint null constraint alert_rules_min_kn_range check (min_kn between 5 and 60),
  max_kn smallint null constraint alert_rules_max_kn_range check (max_kn between 5 and 60),
  -- Hard rule: only ridable direction classes can be selected.
  dir_classes text[] null constraint alert_rules_dir_classes_ridable check (
    dir_classes is null or (
      cardinality(dir_classes) >= 1
      and array_position(dir_classes, null) is null
      and dir_classes <@ array['onshore', 'side_onshore', 'sideshore']::text[]
    )
  ),
  weekdays smallint[] null constraint alert_rules_weekdays_iso check (
    weekdays is null or (
      cardinality(weekdays) >= 1
      and array_position(weekdays, null) is null
      and weekdays <@ array[1, 2, 3, 4, 5, 6, 7]::smallint[]
    )
  ),
  earliest_local time null,
  latest_local time null,
  min_go_hours smallint null constraint alert_rules_min_go_hours_range check (min_go_hours between 1 and 24),
  days_ahead smallint null constraint alert_rules_days_ahead_range check (days_ahead between 0 and 7),
  updated_at timestamptz not null default now(),
  primary key (user_id, spot_id),
  foreign key (user_id, spot_id) references public.favorites (user_id, spot_id) on delete cascade,
  constraint alert_rules_min_lt_max check (min_kn is null or max_kn is null or min_kn < max_kn),
  constraint alert_rules_time_window
    check (earliest_local is null or latest_local is null or earliest_local < latest_local)
);

create table public.alert_state (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  spot_id text not null references public.spots (id) on delete cascade,
  window_start timestamptz not null,
  window_end timestamptz not null,
  status text not null
    constraint alert_state_status_enum check (status in ('active', 'cancelled', 'expired')),
  snapshot jsonb not null constraint alert_state_snapshot_object check (jsonb_typeof(snapshot) = 'object'),
  last_event text null constraint alert_state_last_event_enum
    check (last_event in ('new', 'improved', 'worsened', 'cancelled')),
  last_notified_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint alert_state_window_order check (window_end > window_start)
);
create index alert_state_user_spot_idx on public.alert_state (user_id, spot_id);
create index alert_state_spot_id_idx on public.alert_state (spot_id);
create index alert_state_window_end_idx on public.alert_state (window_end);

create table public.api_usage (
  day date not null,
  source text not null
    constraint api_usage_source_enum check (source in ('open_meteo_forecast', 'open_meteo_marine', 'rws')),
  calls numeric(10, 2) not null default 0 constraint api_usage_calls_nonneg check (calls >= 0),
  requests integer not null default 0 constraint api_usage_requests_nonneg check (requests >= 0),
  primary key (day, source)
);

create table public.ingest_runs (
  id bigint generated always as identity primary key,
  started_at timestamptz not null,
  finished_at timestamptz null,
  status text not null
    constraint ingest_runs_status_enum check (status in ('running', 'ok', 'partial', 'failed')),
  steps jsonb not null default '[]'::jsonb constraint ingest_runs_steps_array check (jsonb_typeof(steps) = 'array'),
  error_summary text null,
  constraint ingest_runs_finished_after_start check (finished_at is null or finished_at >= started_at)
);
create index ingest_runs_started_at_idx on public.ingest_runs (started_at desc);

create trigger spots_set_updated_at before update on public.spots
  for each row execute function public.set_updated_at();
create trigger profiles_set_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();
create trigger alert_rules_set_updated_at before update on public.alert_rules
  for each row execute function public.set_updated_at();
create trigger alert_state_set_updated_at before update on public.alert_state
  for each row execute function public.set_updated_at();

-- Create a profile row for every new auth user (pattern from Supabase docs).
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (user_id) values (new.id) on conflict (user_id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- Backfill: users that existed before this migration also get a profile (no-op on a fresh stack).
insert into public.profiles (user_id)
select id from auth.users
on conflict (user_id) do nothing;
```
De builder mag regels anders afbreken of anders inspringen. Namen, types, constraints, defaults en waarden liggen vast.

Gevolgen voor latere WP's (opnemen in hun blueprints):
- WP-03 en WP-05 normaliseren een richting naar 0–359 (`% 360`), want 360 wordt geweigerd.
- WP-05 voegt een nieuwe `ReasonCode` alleen toe met een migratie die `evaluations_reasons_enum` vervangt.
- Hoe NaN uit Open-Meteo wordt behandeld, bepaalt WP-03. `SupabaseRest` weigert NaN in de JSON.
- CHECKs die strenger zijn dan de contracten. Valideer ze vooraf, anders faalt een sync of CLI pas tegen de echte database:
  - WP-02 weigert een lege of alleen-witruimte `name` (`spots_name_not_blank`);
  - WP-07 en WP-10 (`admin rule set`) laten `weekdays` en `dir_classes` niet leeg zijn (wel `null`), dwingen `earliest_local < latest_local` af en `min_kn < max_kn`;
  - WP-10 (`admin profile set --telegram-chat-id`) controleert het formaat `^-?[0-9]{1,20}$` (`profiles_telegram_chat_id_format`).
- WP-03, WP-10 en WP-12 sturen binnen één upsert nooit twee rijen met dezelfde PK (Postgres geeft 21000; de fake ook). Dedupliceer vóór de upsert.
- Timestamps uit `select` worden altijd geparst (`datetime.fromisoformat`) en nooit als string vergeleken (zie "Wat de fake níet nabootst").

### Migratie 2: `supabase/migrations/20261015090100_m1_security.sql` (exact in inhoud)
```sql
-- RLS, explicit grants and policies. Independent of the "auto expose new tables" setting:
-- every table first loses all API privileges, then gets exactly what it needs.

alter table public.spots enable row level security;
alter table public.forecast_hours enable row level security;
alter table public.tide_extremes enable row level security;
alter table public.evaluations enable row level security;
alter table public.profiles enable row level security;
alter table public.favorites enable row level security;
alter table public.alert_rules enable row level security;
alter table public.alert_state enable row level security;
alter table public.api_usage enable row level security;
alter table public.ingest_runs enable row level security;

revoke all on table
  public.spots, public.forecast_hours, public.tide_extremes, public.evaluations,
  public.profiles, public.favorites, public.alert_rules, public.alert_state,
  public.api_usage, public.ingest_runs
from public, anon, authenticated, service_role;

-- Public read data.
grant select on table public.spots, public.forecast_hours, public.tide_extremes, public.evaluations
  to anon, authenticated;

-- Own profile: read, and update only user-editable columns (never telegram_chat_id).
grant select on table public.profiles to authenticated;
grant update (weight_kg, level, quiver_m2, default_min_kn, default_max_kn)
  on table public.profiles to authenticated;

-- Own favorites and alert rules: full CRUD (RLS restricts to own rows).
grant select, insert, update, delete on table public.favorites, public.alert_rules to authenticated;

-- Own alert state: read only.
grant select on table public.alert_state to authenticated;

-- Ingest (secret key -> service_role, BYPASSRLS).
grant select, insert, update, delete on table
  public.spots, public.forecast_hours, public.tide_extremes, public.evaluations,
  public.profiles, public.favorites, public.alert_rules, public.alert_state,
  public.api_usage, public.ingest_runs
to service_role;

-- Policies.
create policy spots_read on public.spots for select to anon, authenticated using (true);
create policy forecast_hours_read on public.forecast_hours for select to anon, authenticated using (true);
create policy tide_extremes_read on public.tide_extremes for select to anon, authenticated using (true);
create policy evaluations_read on public.evaluations for select to anon, authenticated using (true);

create policy profiles_select_own on public.profiles for select to authenticated
  using (user_id = (select auth.uid()));
create policy profiles_update_own on public.profiles for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

create policy favorites_select_own on public.favorites for select to authenticated
  using (user_id = (select auth.uid()));
create policy favorites_insert_own on public.favorites for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy favorites_update_own on public.favorites for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy favorites_delete_own on public.favorites for delete to authenticated
  using (user_id = (select auth.uid()));

create policy alert_rules_select_own on public.alert_rules for select to authenticated
  using (user_id = (select auth.uid()));
create policy alert_rules_insert_own on public.alert_rules for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy alert_rules_update_own on public.alert_rules for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy alert_rules_delete_own on public.alert_rules for delete to authenticated
  using (user_id = (select auth.uid()));

create policy alert_state_select_own on public.alert_state for select to authenticated
  using (user_id = (select auth.uid()));

-- api_usage, ingest_runs: no policies (service_role only).

-- Trigger functions are never callable through the API.
revoke all on function public.set_updated_at() from public, anon, authenticated, service_role;
revoke all on function public.handle_new_user() from public, anon, authenticated, service_role;
```

### Rechtenmatrix (wat pgTAP vastlegt)

| Tabel | `anon` | `authenticated` | `service_role` |
|---|---|---|---|
| `spots`, `forecast_hours`, `tide_extremes`, `evaluations` | SELECT | SELECT | SELECT, INSERT, UPDATE, DELETE |
| `profiles` | – | SELECT (+ kolom-UPDATE op 5 kolommen) | SELECT, INSERT, UPDATE, DELETE |
| `favorites`, `alert_rules` | – | SELECT, INSERT, UPDATE, DELETE | SELECT, INSERT, UPDATE, DELETE |
| `alert_state` | – | SELECT | SELECT, INSERT, UPDATE, DELETE |
| `api_usage`, `ingest_runs` | – | – | SELECT, INSERT, UPDATE, DELETE |

### `shakka.db`
```python
"""Thin client for the Supabase REST API (PostgREST). The only module that talks to the database."""

PAGE_SIZE: Final = 1000          # equals PostgREST max_rows (config.toml, hosted default)
BATCH_SIZE: Final = 500          # rows per upsert/insert request
MAX_ERROR_MESSAGE: Final = 300   # chars of PostgREST message kept in DatabaseError
SUPPORTED_OPERATORS: Final = frozenset({"eq", "neq", "lt", "lte", "gt", "gte", "in", "is"})
# PostgREST query parameters that can never be used as a filter column.
RESERVED_PARAMS: Final = frozenset(
    {"select", "order", "limit", "offset", "on_conflict", "columns", "or", "and", "not"}
)

# Primary key per table, in key order. Used for default ordering, for counting rows on
# update/delete, and by FakeSupabase. Later WPs add their tables here (marine_hours, ...).
TABLE_KEYS: Final[Mapping[str, tuple[str, ...]]] = {
    "spots": ("id",),
    "forecast_hours": ("spot_id", "model", "valid_at"),
    "tide_extremes": ("station", "at"),
    "evaluations": ("spot_id", "valid_at"),
    "profiles": ("user_id",),
    "favorites": ("user_id", "spot_id"),
    "alert_rules": ("user_id", "spot_id"),
    "alert_state": ("id",),
    "api_usage": ("day", "source"),
    "ingest_runs": ("id",),
}

Filters = Mapping[str, str | Sequence[str]]

class DatabaseError(Exception):
    def __init__(self, message: str, *, status: int | None = None, code: str | None = None) -> None: ...
    status: int | None   # HTTP status, None for transport errors
    code: str | None     # PostgREST/Postgres code, e.g. "23505", "42501", "PGRST116"

class OrderTerm(NamedTuple):
    column: str
    descending: bool
    nulls_first: bool    # resolved: explicit .nullsfirst/.nullslast, else descending

def iso_utc(value: datetime) -> str:
    """Aware datetime -> 'YYYY-MM-DDTHH:MM:SS[.ffffff]Z'. ValueError if naive."""

def in_filter(values: Iterable[str | int]) -> str:
    """Build 'in.(a,b)'. Values containing , ( ) or leading/trailing space are double-quoted.
    ValueError on empty input or on values containing '"' or '\\'."""

def to_json(payload: Any) -> str:
    """json.dumps with allow_nan=False and a default that encodes aware datetime (iso_utc),
    date/time (isoformat), set/frozenset (sorted list), Enum (.value).
    Naive datetime, NaN/inf or unknown types -> ValueError."""

def validate_table(table: str) -> str            # identifier regex, else ValueError
def parse_columns(columns: str) -> list[str] | None   # "*" -> None; "a,b" -> ["a","b"]; else ValueError
def parse_order(order: str) -> list[OrderTerm]   # "a.desc,b,c.asc.nullsfirst"; else ValueError
def default_order(table: str) -> str             # ",".join(TABLE_KEYS[table]); unknown table -> ValueError
def effective_order(table: str, order: str | None) -> str
    # order None -> default_order(table) (ValueError for unknown table).
    # Otherwise parse_order(order) validates it (ValueError). If table is in TABLE_KEYS, the PK
    # columns that do not occur as a column in the parsed terms are appended in TABLE_KEYS order,
    # without direction: order + "," + ",".join(missing). Nothing missing -> order unchanged.
    # Unknown table -> order unchanged (caller must make it unique; documented in the docstring).
    # Examples: ("forecast_hours", "valid_at.desc") -> "valid_at.desc,spot_id,model"
    #           ("forecast_hours", "model,valid_at.desc") -> "model,valid_at.desc,spot_id"
    #           ("spots", "lat.asc,id.desc") -> "lat.asc,id.desc"
def filter_params(filters: Filters | None) -> list[tuple[str, str]]
    # Flattens lists to repeated pairs, validates column identifier and operator:
    # column must not be in RESERVED_PARAMS;
    # value must be "<op>.<rest>" with op in SUPPORTED_OPERATORS; "is" only "is.null";
    # "in" rest must be "(...)". Otherwise ValueError.

class SupabaseRest:
    def __init__(self, url: str, secret_key: str, *, client: httpx.Client | None = None) -> None:
        """url without trailing slash is used as-is (rstrip('/')); client None -> make_client() (owned)."""
    @classmethod
    def from_settings(cls, settings: Settings) -> "SupabaseRest": ...
    def close(self) -> None                      # closes only an owned client
    def __enter__(self) -> "SupabaseRest"; def __exit__(self, *exc: object) -> None
    def __repr__(self) -> str                    # "SupabaseRest()" - never url or key

    def select(self, table: str, *, columns: str = "*", filters: Filters | None = None,
               order: str | None = None, limit: int | None = None) -> list[dict[str, Any]]: ...
    def upsert(self, table: str, rows: Sequence[Mapping[str, Any]], *, on_conflict: str) -> int: ...
    def insert(self, table: str, rows: Sequence[Mapping[str, Any]], *,
               returning: bool = False) -> list[dict[str, Any]]: ...
    def update(self, table: str, values: Mapping[str, Any], *, filters: Filters) -> int: ...
    def delete(self, table: str, *, filters: Filters) -> int: ...
    def rpc(self, function: str, args: Mapping[str, Any] | None = None) -> Any: ...
```
`Filters` is een superset van het contract `Mapping[str, str]`. De parameternamen zijn exact die uit het contract.

**Requests.** De basis is `f"{url}/rest/v1/{table}"`, en `f"{url}/rest/v1/rpc/{function}"` voor RPC's. Elke request krijgt de headers `apikey: <secret>` en `Accept: application/json`, plus `Content-Type: application/json` als er een body is. Nooit `Authorization`. De body is altijd `content=to_json(...)`.

| Methode | HTTP | Query | `Prefer` | Resultaat |
|---|---|---|---|---|
| `select` | `GET /{table}` | `select=<columns>`, filterparen, `order=<effective_order(table, order)>`, `limit=<n>`, `offset=<n>` | – | lijst van dicts |
| `upsert` | `POST /{table}` | `on_conflict=<on_conflict>` | `resolution=merge-duplicates, return=minimal` | `len(rows)` |
| `insert` | `POST /{table}` | – | `return=representation` of `return=minimal` | teruggegeven rijen of `[]` |
| `update` | `PATCH /{table}` | filterparen, `select=<TABLE_KEYS joined>` (onbekende tabel: `select=*`) | `return=representation` | aantal rijen in de respons |
| `delete` | `DELETE /{table}` | filterparen, `select=<TABLE_KEYS joined>` (onbekende tabel: `select=*`) | `return=representation` | aantal rijen in de respons |
| `rpc` | `POST /rpc/{function}` | – | – | geparste JSON, of `None` bij 204 of een lege body |

**Paginering in `select`** (exact):
```
if limit is not None and limit < 1: raise ValueError
order = effective_order(table, order)       # PK tiebreaker; ValueError for unknown table without order
rows, offset = [], 0
while True:
    want = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - len(rows))
    page = GET ... limit=want, offset=offset
    if not page:
        return rows
    rows.extend(page)
    if limit is not None and len(rows) >= limit:
        return rows[:limit]
    offset += len(page)
```
Stopcriterium is een lege pagina, niet `len(page) < want`. Zonder `limit` kost dat altijd één extra request (ook bij minder dan 1000 rijen), maar een server die minder per pagina teruggeeft dan gevraagd ("Max rows" < 1000) leidt dan niet tot stille afkapping.

**Batches.** `upsert` en `insert` splitsen in stukken van `BATCH_SIZE`, in volgorde. Is `rows` leeg, dan gaat er geen request uit (`upsert` geeft 0, `insert` geeft `[]`). Vóór de eerste request wordt gecontroleerd:
- alle rijen hebben exact dezelfde sleutelverzameling, anders `ValueError`;
- elke kolom uit `on_conflict` komt in die sleutels voor, anders `ValueError`;
- elke rij is te coderen met `to_json`, anders `ValueError`.

Faalt een latere batch, dan zijn de eerdere batches al opgeslagen. Dat staat in de docstring. Upserts zijn idempotent, dus opnieuw draaien is veilig.

**Validatie** (allemaal `ValueError`, vóór een request):
- `table` en `function` voldoen niet aan `^[a-z_][a-z0-9_]*$`;
- `columns` is niet `*` of een kommalijst van identifiers;
- `order` voldoet niet aan `ident(.asc|.desc)?(.nullsfirst|.nullslast)?`, kommagescheiden;
- `on_conflict` is geen kommalijst van identifiers;
- een filtersleutel is geen identifier of staat in `RESERVED_PARAMS`, of een filterwaarde heeft een operator buiten de set;
- `update` of `delete` zonder filterparen (`None`, `{}`, of alleen lege lijsten);
- `update` met lege `values`;
- `limit < 1`.

**Fouten.**
- Een 2xx met onverwachte JSON (`select`, `update`, `delete` en `insert(returning=True)` verwachten een lijst) wordt `DatabaseError("<op> <table>: unexpected response", status=...)`.
- Elke status buiten 200–299 (ook 3xx, want redirects worden niet gevolgd) wordt `DatabaseError(f"{op} {table}: HTTP {status}[ {code}][: {message[:300]}]", status=status, code=code)`. `code` en `message` komen uit de JSON-body (`{"code", "message", "details", "hint"}`) als die te parsen is.
- In elke melding wordt de secret vervangen door `***`.
- `httpx.HTTPError` wordt `raise DatabaseError(f"{op} {table}: {type(exc).__name__}") from None`.
- `op` is `select`, `upsert`, `insert`, `update`, `delete` of `rpc`. Bij `rpc` staat de functienaam op de plek van `table`.

### `ingest/tests/fakes.py::FakeSupabase`
```python
class FakeSupabase:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        """clock defaults to a fixed 2026-01-01T00:00:00Z; used for now()-defaults and updated_at."""
    writes: list[tuple[str, str]]            # (operation, table): "upsert" | "insert" | "update" | "delete"
    upserts: list[tuple[str, str]]           # (table, on_conflict exactly as passed), one per non-empty upsert call
    rpc_calls: list[tuple[str, dict[str, Any]]]
    def seed(self, table: str, rows: Sequence[Mapping[str, Any]]) -> None   # like insert, NOT recorded in writes
    def rows(self, table: str) -> list[dict[str, Any]]                     # deep copy, insertion order
    def register_rpc(self, name: str, fn: Callable[[dict[str, Any]], Any]) -> None
    # Same signatures as SupabaseRest (checked by a test):
    def select(...); def upsert(...); def insert(...); def update(...); def delete(...); def rpc(...)
    def close(self) -> None; __enter__; __exit__
```
Gedrag:
- **Opslag.** Per tabel een lijst van dicts. Tabellen buiten `TABLE_KEYS` geven `ValueError` (net als `default_order`). Waarden worden opgeslagen als `json.loads(to_json(row))`, zodat de codering en de foutgevallen gelijk zijn aan die van de echte client.
- **Validatie.** De fake gebruikt dezelfde functies als de echte client: `validate_table`, `parse_columns`, `parse_order`, `default_order` en `filter_params`. Ook de lege-filterregel, de gelijke-sleutelsregel en de `limit`-regel zijn dezelfde.
- **Filters**, toegepast per paar en met AND gecombineerd:
  - een opgeslagen `None` (of een ontbrekende sleutel) matcht alleen `is.null`;
  - `bool` vergelijkt met `true`/`false`; een andere tekst geeft `ValueError`;
  - `int` en `float` vergelijken met `float(waarde)`;
  - een `str` die matcht op `^\d{4}-\d{2}-\d{2}T` wordt met de filterwaarde vergeleken als tz-aware datetime (`datetime.fromisoformat`; naive telt als UTC);
  - een andere `str` wordt als string vergeleken;
  - een `list` of `dict` geeft `ValueError("FakeSupabase: comparing array/json columns is not supported")`;
  - `in.(…)` wordt gesplitst met respect voor dubbele aanhalingstekens en matcht als minstens één element `eq` geeft.
- **Order:** `parse_order(effective_order(table, order))`, dus zonder `order` de PK en met een eigen `order` de PK als tiebreaker, precies als de echte client. Nulls volgens `OrderTerm.nulls_first`. Daarna stabiel sorteren, waarbij de waarden op dezelfde manier worden vergeleken als bij de filters. `limit` wordt na het sorteren toegepast. `columns` projecteert; een ontbrekende kolom wordt `None`.
- **Defaults bij insert, upsert en seed** (alleen als de kolom ontbreekt):

  | Tabel | Defaults |
  |---|---|
  | `spots` | `tide_sensitive="none"`, `season=[]`, `verified=False`, `updated_at=NOW` |
  | `evaluations` | `reasons=[]` |
  | `profiles` | `quiver_m2=[]`, `created_at=NOW`, `updated_at=NOW` |
  | `favorites` | `created_at=NOW` |
  | `alert_rules` | `enabled=True`, `updated_at=NOW` |
  | `alert_state` | `id=f"00000000-0000-4000-8000-{n:012d}"` (oplopende teller per fake), `created_at=NOW`, `updated_at=NOW` |
  | `api_usage` | `calls=0`, `requests=0` |
  | `ingest_runs` | `id=n` (oplopend vanaf 1), `steps=[]` |

  `NOW` is `iso_utc(clock())`. Een insert in `ingest_runs` met een expliciete `id` geeft `DatabaseError(code="428C9")`, zoals bij `generated always`.
- **Primaire sleutel.**
  - PK-waarden worden vergeleken zoals bij de filters: een timestamp-string als tijdstip (`…Z` en `…+00:00` zijn dezelfde sleutel), getallen numeriek. Dat geldt voor 23505, 21000 en het vinden van de bestaande rij bij upsert.
  - Een insert met een PK die al bestaat, of een dubbele PK binnen de batch, geeft `DatabaseError(code="23505", status=409)`. Er wordt dan niets ingevoegd: de batch is atomair.
  - Ontbreekt een PK-kolom na het toepassen van de defaults, dan volgt `DatabaseError(code="23502", status=400)`.
- **Upsert.**
  - `on_conflict` moet als verzameling gelijk zijn aan `TABLE_KEYS[table]`, anders `DatabaseError(code="42P10", status=400)`.
  - Elke niet-lege aanroep voegt `(table, on_conflict)` toe aan `upserts`, ook als hij daarna faalt.
  - Twee rijen met dezelfde PK binnen één batch van `BATCH_SIZE` (na het toepassen van de defaults) geven `DatabaseError(code="21000", status=400)`, zoals Postgres ("ON CONFLICT DO UPDATE command cannot affect row a second time"; PostgREST mapt 21000 naar 400). Er wordt dan niets uit die batch opgeslagen; eerdere batches blijven staan, net als bij de echte client. Dezelfde PK in twee verschillende batches wordt gewoon gemerged, ook net als bij de echte client.
  - Een bestaande rij krijgt alleen de meegegeven kolommen.
  - Een nieuwe rij krijgt de meegegeven kolommen plus de defaults.
- **`updated_at`-trigger:** bij `update` en bij een upsert die een bestaande rij raakt, wordt `updated_at = NOW` gezet in `spots`, `profiles`, `alert_rules` en `alert_state`.
- **Cascades bij `delete`:**
  - `spots` neemt `forecast_hours`, `evaluations`, `favorites` (en daarmee `alert_rules`) en `alert_state` met dezelfde `spot_id` mee;
  - `favorites` neemt `alert_rules` met dezelfde (`user_id`, `spot_id`) mee.

  Cascades komen niet als aparte entry in `writes`.
- **Wat de fake níet nabootst:**
  - FK- en CHECK-constraints en unieke constraints buiten de PK;
  - de afronding van `numeric(10,2)`;
  - de collatie van Postgres (tekst wordt op codepoint gesorteerd);
  - de notatie van timestamps in de respons. De fake geeft ze terug zoals ze verstuurd zijn (`…Z`, of `+02:00` bij `zzp-b`); echt PostgREST geeft ze genormaliseerd terug (`+00:00`, sessietijdzone UTC). Regel voor latere WP's: timestamps uit `select` altijd parsen met `datetime.fromisoformat` en nooit als string vergelijken.
- **Telling en terugkeerwaarden.**
  - `writes` krijgt een entry per aanroep van `upsert`, `insert`, `update` en `delete`, ook als er 0 rijen geraakt worden. Een lege `upsert` of `insert` (geen rijen) geeft geen entry, net zoals de echte client dan geen request doet.
  - `select` en `rpc` komen nooit in `writes`. `rpc` komt in `rpc_calls`.
  - `rpc` op een niet-geregistreerde naam geeft `DatabaseError(code="PGRST202", status=404)`.
  - `update` en `delete` geven het aantal geraakte rijen terug. `insert(returning=True)` geeft kopieën van de opgeslagen rijen.

### `ingest/tests/fake_cases.py`
- `PARITY_IDS = ["zzp-a", "zzp-b", "zzp-c", "zzp-d", "zzp-e"]`.
- `PARITY_ROWS`, rijen voor `spots`. Alle rijen hebben dezelfde sleutels: `id`, `name`, `region`, `lat`, `lon`, `shore_normal_deg`, `status`, `verified` en `updated_at`. `name` is gelijk aan het id.

| id | region | lat | lon | shore_normal_deg | status | verified | updated_at |
|---|---|---|---|---|---|---|---|
| zzp-a | `noord` | 52.0 | 4.5 | 270 | allowed | true | `2026-10-14T12:00:00Z` |
| zzp-b | `zuid` | 51.5 | 3.6 | 300 | limited | false | `2026-10-14T14:00:00+02:00` |
| zzp-c | null | null | null | null | null | false | `2026-10-13T23:30:00Z` |
| zzp-d | `noord, holland` | 53.0 | 5.0 | 0 | forbidden | true | `2026-10-15T00:00:00Z` |
| zzp-e | `oost` | 52.0 | 6.0 | 359 | allowed | false | `2026-10-14T12:00:01Z` |

- `FILTER_CASES: list[FilterCase]`, met `FilterCase(name: str, filters: dict[str, str | list[str]], order: str | None, limit: int | None, expected: list[str])`. Zonder `order` gebruikt de test `"id"`. `expected` is een geordende lijst van ids.

| name | filters | order | limit | expected |
|---|---|---|---|---|
| eq_text | `region: eq.noord` | | | a |
| eq_number | `lat: eq.52` | | | a, e |
| eq_bool | `verified: eq.true` | | | a, d |
| eq_timestamp_offsets | `updated_at: eq.2026-10-14T12:00:00Z` | | | a, b |
| neq_excludes_null | `region: neq.noord` | | | b, d, e |
| lt_number | `shore_normal_deg: lt.300` | | | a, d |
| lte_number | `shore_normal_deg: lte.300` | | | a, b, d |
| gt_number | `shore_normal_deg: gt.300` | | | e |
| gte_timestamp | `updated_at: gte.2026-10-14T12:00:00Z` | | | a, b, d, e |
| lt_timestamp_plus_offset | `updated_at: lt.2026-10-14T12:00:00+00:00` | | | c |
| in_text | `id: in_filter(["zzp-a","zzp-c"])` | | | a, c |
| in_quoted_comma | `region: in_filter(["noord, holland","oost"])` | | | d, e |
| is_null | `region: is.null` | | | c |
| and_two_columns | `verified: eq.false`, `status: eq.limited` | | | b |
| range_same_column | `shore_normal_deg: [gte.270, lt.359]` | | | a, b |
| order_desc_nulls_first | – | `shore_normal_deg.desc` | | c, e, b, a, d |
| order_asc_nulls_last | – | `shore_normal_deg` | | d, a, b, e, c |
| order_asc_nullsfirst | – | `shore_normal_deg.asc.nullsfirst` | | c, d, a, b, e |
| order_multi | – | `lat.asc,id.desc` | | b, e, a, d, c |
| order_ties_pk_tiebreak | – | `lat.desc` | | c, d, a, e, b |
| order_ties_bool | – | `verified` | | b, c, e, a, d |
| limit | – | `id` | 2 | a, b |

De twee `order_ties_*`-cases hebben gelijke sorteerwaarden (`lat` 52.0 bij a en e; `verified`). De verwachte volgorde binnen een gelijke waarde is `id` oplopend, door de PK-tiebreaker van `effective_order`.

(In de tabel staan de ids zonder het prefix `zzp-`; in de code staan de volledige ids.)

### `ingest/tests/test_fake_parity.py` (optioneel, tegen de lokale stack)
- Leest `SHAKKA_TEST_SUPABASE_URL` en `SHAKKA_TEST_SUPABASE_SECRET_KEY`. Zijn die niet allebei gezet, of is de host van de URL niet `127.0.0.1` of `localhost`, dan volgt `pytest.skip`, met in de reden alleen "set SHAKKA_TEST_SUPABASE_URL (localhost only) and SHAKKA_TEST_SUPABASE_SECRET_KEY", zonder waarden. Zo kan de test nooit het remote project raken.
- Fixture (module scope): eerst `delete("spots", filters={"id": in_filter(PARITY_IDS)})`, dan `insert("spots", PARITY_ROWS)`, en na afloop dezelfde delete.
- Per `FILTER_CASES`: de filters plus `id` beperkt tot `in_filter(PARITY_IDS)` (als lijst gecombineerd als de case zelf al op `id` filtert). Daarna wordt de lijst ids uit de echte `select` vergeleken met `expected`.
- Een extra test leest via `select("spots", columns="id,updated_at", filters={"id": "eq.zzp-b"})` en controleert dat `datetime.fromisoformat(row["updated_at"]) == datetime(2026, 10, 14, 12, tzinfo=UTC)`. Zo is bekend in welke vorm de echte respons timestamps teruggeeft.

### `ingest/tests/test_migrations.py`
- `test_no_later_milestone_tables`: dezelfde regex als AC-6 (`create table[^;]*(sessions|rsvps|push_subscriptions|marine_hours)`, hoofdletterongevoelig) over alle bestanden in `supabase/migrations/` geeft geen treffers.
- `test_table_keys_match_migrations`: verzamelt de tabelnamen met `re.findall(r"create table (?:if not exists )?public\.(\w+)", sql, re.I)` over alle migraties en eist dat die verzameling gelijk is aan `set(TABLE_KEYS)`.
- `test_every_migration_table_enables_rls`: voor elke tabel uit de migraties staat ergens `alter table public.<t> enable row level security`.
- `test_migration_filenames`: elke bestandsnaam matcht `^\d{14}_[a-z0-9_]+\.sql$` en de namen zijn uniek.

### Toevoegingen aan `ingest/tests/test_repo_hygiene.py`
- In `test_ci_workflow_contract` komen de regels `db:` en `- run: supabase test db` erbij.
- `test_supabase_config_disables_auto_expose`: in `supabase/config.toml` staat tussen de regel `[api]` en de volgende regel die met `[` begint een regel die gestript exact `auto_expose_new_tables = false` is.

### `.github/workflows/ci.yml`: job `db` (toevoegen onder `jobs:`, na `ingest`)
```yaml
  db:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v7
      - uses: supabase/setup-cli@45a513f8c64c0bc8e0e3dfe572b5c95be85f6359 # v3.0.1
        with:
          version: 2.121.0
      - run: supabase start -x realtime,storage-api,imgproxy,mailpit,postgres-meta,studio,edge-runtime,logflare,vector,supavisor
      - run: supabase test db
```
Draait vanuit de repo-root, waar `supabase/` staat. Er zijn geen secrets nodig; ook PR's vanuit een fork slagen. De triggers, `permissions` en `concurrency` op workflowniveau blijven gelijk.

### `docs/RUNBOOK.md` (Nederlands)
- **Sectie 6 aanvullen:**
  - `supabase start` past de migraties toe;
  - `supabase db reset` bouwt de lokale database opnieuw op uit `supabase/migrations/`;
  - `supabase test db` draait de pgTAP-tests in `supabase/tests/`;
  - de optionele pariteitstest: neem de lokale secret key over uit `supabase status` en draai `SHAKKA_TEST_SUPABASE_URL=http://127.0.0.1:54321 SHAKKA_TEST_SUPABASE_SECRET_KEY=<lokale secret key> uv run pytest tests/test_fake_parity.py` vanuit `ingest/`. Die werkt alleen tegen localhost.
- **Nieuwe sectie 8 "Database en migraties":**
  1. Migraties staan in `supabase/migrations/` en worden nooit achteraf gewijzigd. Een wijziging is altijd een nieuw bestand.
  2. Elke nieuwe tabel krijgt in dezelfde migratie `enable row level security`, `revoke all … from public, anon, authenticated, service_role`, expliciete grants (ook aan `service_role`, anders kan de ingest er niet bij) en policies. De tabel komt ook in `TABLE_KEYS` in `ingest/src/shakka/db.py`; `test_table_keys_match_migrations` bewaakt dat.
  3. **Naar het remote project na de merge naar `develop` (Lars):**
     - `supabase link --project-ref <ref>` (eenmalig);
     - `supabase db push --dry-run` om te zien welke migraties meegaan;
     - `supabase db push`;
     - `supabase migration list --linked`: alle migraties staan als toegepast.
  4. Laat "Max rows" van de Data API op 1000. `SupabaseRest` vraagt pagina's van 1000; bij een lagere waarde blijft het resultaat compleet, maar kost het meer requests.
  5. `auto_expose_new_tables = false` in `config.toml` spiegelt de instelling van het remote project. Weigert een nieuwere CLI die sleutel, haal de regel dan weg. De migraties werken ook zonder, omdat ze zelf revoken en granten.
- **Sectie 7:** noemt de job `db` (`supabase start` en `supabase test db`).

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `alert_rules.dir_classes` met `offshore`, `side_offshore`, `null`-element of `{}` | CHECK geeft 23514 |
| E2 | `evaluations` met `dir_class = 'offshore'` en `verdict <> 'no_go'` | CHECK geeft 23514 |
| E3 | `weekdays` met 0, 8, `{}` of een null-element | CHECK geeft 23514 |
| E4 | `earliest_local >= latest_local`, `min_kn >= max_kn`, `default_min_kn >= default_max_kn` | CHECK geeft 23514 |
| E5 | `quiver_m2` met 2.5, 22, 11 kites of een null-element | CHECK geeft 23514 |
| E6 | `telegram_chat_id` met letters | CHECK geeft 23514. Als `authenticated` mag hij hoe dan ook niet wijzigen (42501). |
| E7 | `lat` zonder `lon` | CHECK geeft 23514 |
| E8 | `dir_deg = 360` | CHECK geeft 23514. WP-03 normaliseert `% 360`. |
| E9 | Favoriet verwijderen | De `alert_rules`-rij gaat mee (FK cascade), ook in de fake. |
| E10 | Auth-user verwijderen | `profiles`, `favorites`, `alert_rules` en `alert_state` van die user gaan mee (voorbereiding op WP-23). |
| E11 | `handle_new_user` voor een user die al een profiel heeft | `on conflict do nothing`, de signup blijft werken |
| E12 | `authenticated` stuurt `updated_at` of `telegram_chat_id` mee in een PATCH | 42501 op de hele update. De PWA (WP-16) stuurt alleen de vijf toegestane kolommen. |
| E13 | Insert in `alert_rules` voor een spot die geen favoriet is | FK-fout 23503 |
| E14 | A probeert een favoriet of regel voor B in te voegen | RLS WITH CHECK geeft 42501 |
| E15 | A update of verwijdert rijen van B | 0 rijen geraakt, geen fout, data van B ongewijzigd |
| E16 | `select` zonder `order` op een tabel buiten `TABLE_KEYS` | `ValueError` vóór een request |
| E17 | Precies 1000 of 2000 rijen, of minder dan 1000 | Altijd beëindigt een extra request die 0 rijen geeft de lus. Het resultaat is compleet. |
| E17b | Server geeft minder rijen per pagina dan gevraagd ("Max rows" < 1000) | De lus gaat door met `offset += len(page)` tot een lege pagina. Het resultaat is compleet. |
| E17c | Eigen `order` op een niet-unieke kolom (`valid_at` op `forecast_hours`) | PK-kolommen worden als tiebreaker toegevoegd. Pagina's overlappen niet en slaan niets over. |
| E17d | Twee rijen met dezelfde PK in één upsert | Echt: 21000 (HTTP 400). Fake: `DatabaseError(code="21000")`, batch niet opgeslagen. |
| E17e | Filterkolom `order`, `select`, `limit`, … | `ValueError`, geen request |
| E18 | `limit=1500` | Requests met `limit` 1000 en 500, offsets 0 en 1000 |
| E19 | Upsert van 0 rijen | Geen request, resultaat 0, geen entry in `writes` |
| E20 | Rijen met verschillende sleutels in één upsert of insert | `ValueError`, geen request |
| E21 | Naive datetime, NaN of `inf` in een rij | `ValueError`, geen request |
| E22 | Filterwaarde met `+00:00` | httpx codeert `+` als `%2B`. De server ontvangt `+00:00`, niet een spatie (test). |
| E23 | `in`-waarde met een komma | `in_filter` zet aanhalingstekens. Een waarde met `"` of `\` geeft `ValueError`. |
| E24 | Operator `like`, `not.is.null`, `cs`, enzovoort | `ValueError` in de client én in de fake, zodat een latere WP een uitbreiding expliciet doet |
| E25 | 4xx of 5xx met PostgREST-JSON | `DatabaseError` met `status` en `code`. De melding is ingekort en de secret geredigeerd. |
| E26 | 5xx met een HTML- of tekstbody | `DatabaseError` met alleen de status, geen body |
| E27 | 3xx | `DatabaseError` (redirects worden niet gevolgd). De key gaat niet naar een andere host. |
| E28 | Connectiefout of timeout | `DatabaseError("<op> <table>: ConnectError")` zonder `__cause__` en zonder URL of key |
| E29 | Tabelnaam `spots?x=1`, `../auth` of `Spots` | `ValueError` |
| E30 | `rpc` geeft 204 of een lege body | `None` |
| E31 | Een latere batch van een upsert faalt | `DatabaseError`. De eerdere batches zijn al opgeslagen; upserts zijn idempotent (staat in de docstring). |
| E32 | Insert in `ingest_runs` met een expliciete `id` | Echt: fout (`generated always`). Fake: `DatabaseError(code="428C9")`. |
| E33 | Pariteitstest met een remote URL in de env | `skip`, er wordt niets geschreven |
| E34 | Een toekomstige CLI kent `auto_expose_new_tables` niet meer | Regel verwijderen (RUNBOOK). Grants blijven correct door de expliciete revoke en grant. |

## Testplan
Tests eerst. De pgTAP-tests schrijft de builder vóór de migraties (rood), en de Python-tests vóór `db.py` en `fakes.py`.

**Patroon voor pgTAP-bestanden:** `begin;`, `create extension if not exists pgtap with schema extensions;`, `select plan(N);` (N exact), de asserts, `select * from finish();` en `rollback;`. Vaste test-uuid's:
- A = `11111111-1111-1111-1111-111111111111`;
- B = `22222222-2222-2222-2222-222222222222`.

Users maken: `insert into auth.users (id, email) values (A, 'a@example.test'), (B, 'b@example.test');`. Rol wisselen:
```sql
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
-- asserts as A
reset role;
```
Voor `anon` is het `set local role anon;` (geen claims). Voor `service_role` is het `set local role service_role;`. Controles na een "stille" update of delete gebeuren na `reset role` (als `postgres`, de eigenaar). Foutcodes worden getoetst met `throws_ok(sql, '<code>', null, '<beschrijving>')`.

**Typering van pgTAP-aanroepen (verplicht).** Ongetypeerde literals kunnen naar een verkeerde overload resolven. Daarom:
- arrays altijd casten: `'{}'::name[]`, `array['SELECT','UPDATE']::name[]`;
- bij `table_privs_are`, `column_privs_are`, `function_privs_are`, `policies_are` en `has_trigger` altijd de variant mét schema én mét beschrijving gebruiken, en de schema-, tabel-, rol- en triggernamen als `::name` casten. Concreet:
  - `table_privs_are('public'::name, '<t>'::name, '<rol>'::name, array[...]::name[], '<beschrijving>')`;
  - `column_privs_are('public'::name, 'profiles'::name, '<kolom>'::name, 'authenticated'::name, array[...]::name[], '<beschrijving>')`;
  - `function_privs_are('public'::name, 'handle_new_user'::name, '{}'::name[], '<rol>'::name, '{}'::name[], '<beschrijving>')` (idem `set_updated_at`);
  - `policies_are('public'::name, '<t>'::name, array[...]::name[], '<beschrijving>')`, ook voor de lege set (`'{}'::name[]`);
  - `has_trigger('auth'::name, 'users'::name, 'on_auth_user_created'::name, '<beschrijving>')`, en zo ook voor de vier `*_set_updated_at`-triggers in `public`.
- In de FK-`set_eq` is `confdeltype` van type `"char"`: selecteer `confdeltype::text`.

**Aantal asserts per bestand** (`select plan(N);`):

| Bestand | N | Opbouw |
|---|---|---|
| `01_schema.test.sql` | 71 (in stap 2: 70, zonder de RLS-assert) | `tables_are` 1, `columns_are` 10, kolom-`set_eq` 1, `col_is_pk` 10, FK-`set_eq` 1, RLS-`is_empty` 1, `has_trigger` 5, CHECK-`throws_ok` 40, `lives_ok` 2 |
| `02_privileges.test.sql` | 55 | `table_privs_are` 30, `column_privs_are` 9, `function_privs_are` 6, `policies_are` 10 |
| `03_rls_anon.test.sql` | 22 | leestabellen lezen 4, schrijven geweigerd 12, privé-tabellen geweigerd 6 |
| `04_rls_users.test.sql` | 42 | zie de genummerde volgorde onder (d)–(h) |

**AC-1** (`supabase db reset` foutloos)
- Builder en verifier draaien lokaal `supabase db reset`: exitcode 0, geen `ERROR` in de uitvoer.
- In CI past `supabase start` dezelfde migraties toe op een lege stack. De job `db` faalt als dat niet lukt.

**AC-2** (`supabase test db` groen, onderdelen a–h)
- (a) `01_schema.test.sql`:
  - `tables_are('public', array[10 tabellen])`. Dat bewijst ook dat er geen latere tabellen zijn.
  - `columns_are` per tabel (10 asserts).
  - Eén `set_eq` op `(relname, attname, format_type(atttypid, atttypmod), not attnotnull)` uit `pg_attribute` (schema `public`, `relkind = 'r'`, `attnum > 0`, `not attisdropped`) tegen een `values`-lijst van alle 86 kolommen. De types volgen exact de DDL: `text`, `double precision`, `smallint`, `jsonb`, `integer`, `boolean`, `timestamp with time zone`, `real`, `text[]`, `uuid`, `real[]`, `smallint[]`, `time without time zone`, `numeric(10,2)`, `bigint` en `date`. Nullable volgt de contracttabel.
  - `col_is_pk` per tabel (10).
  - Eén `set_eq` op `pg_constraint` (`contype = 'f'`): `(conrelid::regclass::text, confrelid::regclass::text, confdeltype)` is gelijk aan
    - `('forecast_hours','spots','c')`, `('evaluations','spots','c')`;
    - `('profiles','auth.users','c')`;
    - `('favorites','auth.users','c')`, `('favorites','spots','c')`;
    - `('alert_rules','favorites','c')`;
    - `('alert_state','auth.users','c')`, `('alert_state','spots','c')`.
  - `is_empty` op de tabellen in `public` met `relkind = 'r' and not relrowsecurity` (RLS aan op alles).
  - `has_trigger` voor `spots_set_updated_at`, `profiles_set_updated_at`, `alert_rules_set_updated_at`, `alert_state_set_updated_at` en (`auth`, `users`, `on_auth_user_created`).
  - CHECK-tests als `postgres`: één `throws_ok … '23514'` per invoer in de tabel hieronder (40 asserts). De fixture bevat spot `pgtap-spot`, user A (via `auth.users`) en favoriet (A, `pgtap-spot`).

    | Tabel | Ongeldige invoer | Aantal |
    |---|---|---|
    | spots | id `Bad Id`; `tide_sensitive='sometimes'`; `status='open'`; `level='pro'`; `shore_normal_deg=360`; `lat=52` zonder `lon`; `default_min_kn=4` | 7 |
    | forecast_hours | `model='gem'`; `dir_deg=360`; `wind_kn=-1`; `gust_kn=-1` | 4 |
    | tide_extremes | `kind='mid'` | 1 |
    | evaluations | `verdict='maybe'`; `dir_class='cross'`; `confidence='certain'`; `reasons='{unknown_code}'`; `dir_class='offshore'` met `verdict='go'`; `dir_class='side_offshore'` met `verdict='marginal'` | 6 |
    | profiles (update van A) | `weight_kg=29`; `weight_kg=201`; `level='pro'`; `quiver_m2='{2.5}'`; `quiver_m2` met 11 elementen; `telegram_chat_id='abc'`; `default_min_kn=20, default_max_kn=15` | 7 |
    | alert_rules (insert op (A, `pgtap-spot`)) | `weekdays='{0}'`; `weekdays='{8}'`; `weekdays='{}'`; `weekdays='{1,NULL}'`; `earliest_local='18:00', latest_local='17:00'`; `min_kn=20, max_kn=15`; `min_go_hours=0`; `days_ahead=8`; `min_kn=4` | 9 |
    | alert_state | `status='open'`; `last_event='moved'`; `window_end = window_start` | 3 |
    | api_usage | `source='windguru'`; `calls=-1` | 2 |
    | ingest_runs | `status='done'` | 1 |

    De `alert_rules`-inserts gebruiken alleen kolommen `user_id`, `spot_id` en de te toetsen kolom(men). In `01` bestaat nog geen regel voor (A, `pgtap-spot`), en de CHECK gaat in Postgres vóór de FK-controle; de fout is dus altijd 23514.

    Plus positieve gevallen met `lives_ok` (2 asserts): een evaluatie `dir_class='offshore'` met `verdict='no_go'`, en een spot met alleen `id` en `name`.
- (b) `03_rls_anon.test.sql`. Fixture als `postgres`: 1 spot en per leestabel 1 rij. Als `anon`:
  - `results_eq` geeft voor elk van de 4 leestabellen precies de fixture-rij (via `count(*)`, 4 asserts);
  - `throws_ok … '42501'` voor `insert`, `update` en `delete` op elk van de 4 leestabellen (12 asserts).

  `02_privileges.test.sql` toetst daarnaast dat `authenticated` op de leestabellen alleen `SELECT` heeft.
- (c) `03_rls_anon.test.sql`: als `anon` geeft `throws_ok('select * from public.<t>', '42501', …)` voor `profiles`, `favorites`, `alert_rules`, `alert_state`, `api_usage` en `ingest_runs` (6 asserts). Zie A3: er wordt geen enkele rij gelezen.
- (d) tot en met (h), plus de `service_role`-extra's: `04_rls_users.test.sql`, `plan(42)`, in exact deze volgorde. De volgorde is bindend: latere secties hangen af van de toestand na eerdere (bijv. B wordt pas als laatste verwijderd). "A" en "B" staan voor de vaste uuid's, in SQL als `'1111…'::uuid`.

  **Stap 0, fixture als `postgres` (geen asserts):** `insert into auth.users (id, email)` voor A en B (profielen via de trigger).

  **Sectie (f), trigger, als `postgres`:**
  1. `results_eq('select count(*)::int from public.profiles where user_id in (A, B)', array[2], …)`;
  2. `is((select quiver_m2 from public.profiles where user_id = A), '{}'::real[], …)`.

  **Fixture vervolg als `postgres` (geen asserts):**
  - spots `pgtap-spot` en `pgtap-spot-2` (alleen `id` en `name`);
  - favorieten (A, `pgtap-spot`) en (B, `pgtap-spot`);
  - regels (A, `pgtap-spot`, `min_kn` 12) en (B, `pgtap-spot`, `min_kn` 20);
  - `alert_state` voor A en voor B, elk op `pgtap-spot`, met `window_start = '2026-10-14T10:00:00Z'`, `window_end = '2026-10-14T14:00:00Z'`, `status = 'active'`, `snapshot = '{}'`.

  **Sectie (d), als A:**
  3–6. `profiles`, `favorites`, `alert_rules` en `alert_state` tonen elk precies 1 rij, met `user_id = A` (`results_eq('select user_id from public.<t>', $$values ('A'::uuid)$$, …)`);
  7–10. `is_empty('select 1 from public.<t> where user_id = B', …)` voor dezelfde 4 tabellen;
  11–14. `lives_ok` op `update public.profiles set weight_kg = 99 where user_id = B`, `update public.alert_rules set min_kn = 6 where user_id = B`, `delete from public.favorites where user_id = B` en `delete from public.alert_rules where user_id = B`;
  15–16. `throws_ok … '42501'` op `insert into public.favorites (user_id, spot_id) values (B, 'pgtap-spot-2')` en op `insert into public.alert_rules (user_id, spot_id) values (B, 'pgtap-spot')`.

  Dan `reset role`, als `postgres`:
  17–20. B's `weight_kg` is nog null, B's `min_kn` is nog 20, B's favoriet bestaat nog, B's regel bestaat nog.

  **Sectie (e), kolomprivilege en `updated_at`-trigger.** Voorbereiding als `postgres` (exact; maakt de test onafhankelijk van de klok, want `now()` is binnen de transactie constant):
  ```sql
  alter table public.profiles disable trigger profiles_set_updated_at;
  update public.profiles set updated_at = '2000-01-01T00:00:00Z' where user_id = '11111111-1111-1111-1111-111111111111';
  alter table public.profiles enable trigger profiles_set_updated_at;
  ```
  21. `is((select updated_at from public.profiles where user_id = A), '2000-01-01T00:00:00Z'::timestamptz, 'precondition: updated_at backdated')`. Zonder deze preconditie zou assert 26 ook slagen als het terugzetten niet werkte.

  Als A:
  22. `throws_ok($$update public.profiles set telegram_chat_id = '123' where user_id = '1111…'$$, '42501', null, …)`;
  23. `lives_ok($$update public.profiles set weight_kg = 80 where user_id = '1111…'$$, …)`.

  Dan `reset role`, als `postgres`:
  24. `is(weight_kg, 80::smallint)` voor A;
  25. `is(telegram_chat_id, null::text)` voor A;
  26. `is((select updated_at from public.profiles where user_id = A), now(), …)`. De trigger heeft dus gevuurd tijdens de update door `authenticated`, zonder EXECUTE-recht op `set_updated_at()` (A7).

  **Sectie (g), `dir_classes`.** Eerst als `postgres` (geen assert): `insert into public.favorites (user_id, spot_id) values (A, 'pgtap-spot-2')`. Alle inserts in deze sectie gebruiken de sleutel (A, `pgtap-spot-2`), waarvoor nog geen regel bestaat.
  27–31. Als `postgres`: `throws_ok … '23514'` op `insert into public.alert_rules (user_id, spot_id, dir_classes) values (A, 'pgtap-spot-2', <waarde>)` met `'{side_offshore}'`, `'{offshore}'`, `'{onshore,offshore}'`, `'{}'` en `'{onshore,NULL}'`;
  32. Als A: dezelfde insert met `'{offshore}'` geeft `23514`. Daarna `reset role`;
  33. Als `postgres`: `lives_ok` op dezelfde insert met `'{onshore,side_onshore,sideshore}'`.

  **`service_role`-extra's**, als `service_role` (vóór sectie (h), want die verwijdert B):
  34. `lives_ok` op `insert into public.ingest_runs (started_at, status) values (now(), 'running')` (A6);
  35. `lives_ok` op `insert into public.api_usage (day, source, calls, requests) values ('2026-10-14', 'rws', 1, 1)`;
  36. `results_eq('select user_id from public.alert_state order by user_id', $$values (A::uuid), (B::uuid)$$, …)` (BYPASSRLS).

  Dan `reset role`.

  **Sectie (h), cascades:**
  37. Als A: `lives_ok` op `delete from public.favorites where user_id = A and spot_id = 'pgtap-spot'`. Dan `reset role`;
  38. Als `postgres`: `is_empty` op `alert_rules` voor (A, `pgtap-spot`);
  Als `postgres` (geen assert): `delete from auth.users where id = B`;
  39–42. `is_empty` op `profiles`, `favorites`, `alert_rules` en `alert_state` voor B (E10).
- `02_privileges.test.sql` (`plan(55)`), met de typering uit "Typering van pgTAP-aanroepen":
  - `table_privs_are` voor alle 10 tabellen × (`anon`, `authenticated`, `service_role`), volgens de rechtenmatrix: 30 asserts. Een lege set is `'{}'::name[]`.
  - `column_privs_are` op `profiles` voor `authenticated`: `weight_kg`, `level`, `quiver_m2`, `default_min_kn` en `default_max_kn` hebben `array['SELECT','UPDATE']::name[]`; `telegram_chat_id`, `user_id`, `created_at` en `updated_at` hebben `array['SELECT']::name[]` (9 asserts).
  - `function_privs_are` met `'{}'::name[]` als argumenten en als privileges, voor `handle_new_user` en `set_updated_at`, voor `anon`, `authenticated` en `service_role` (6 asserts).
  - `policies_are` per tabel met exact de policynamen uit de security-migratie. Voor `api_usage` en `ingest_runs` is dat `'{}'::name[]` (10 asserts).

**AC-3** (`uv run pytest tests/test_db.py`, `httpx.MockTransport`). De client wordt gemaakt met `SupabaseRest("https://testref.supabase.co", "sb_secret_TESTVALUE", client=httpx.Client(transport=MockTransport(handler)))`. Een recorder bewaart de requests.

| Test | Wat hij toont |
|---|---|
| `test_key_in_header_not_url` | Voor `select`, `upsert`, `insert`, `update`, `delete` en `rpc`: header `apikey` == secret, geen `authorization`-header, en de secret staat niet in `str(request.url)`. |
| `test_select_serializes_filters` | `filters={"spot_id": "eq.wijk-aan-zee", "valid_at": ["gte.2026-10-14T00:00:00Z", "lt.2026-10-15T00:00:00+00:00"]}`. `request.url.params.multi_items()` bevat `("spot_id","eq.wijk-aan-zee")` en beide `valid_at`-paren, de `+` komt terug als `+` (E22), en verder `select=*`, `limit=1000` en `offset=0`. Pad: `/rest/v1/forecast_hours`. |
| `test_select_default_order` | Geparametriseerd over (tabel, `order`) → verstuurde `order`: (`forecast_hours`, None) → `spot_id,model,valid_at`; (`forecast_hours`, `valid_at.desc`) → `valid_at.desc,spot_id,model`; (`forecast_hours`, `model,valid_at.desc`) → `model,valid_at.desc,spot_id`; (`forecast_hours`, `spot_id.desc,model,valid_at`) → ongewijzigd; (`spots`, `lat.asc,id.desc`) → ongewijzigd; (`unknown_table`, `x.desc`) → `x.desc` (ongewijzigd). Een onbekende tabel zonder `order` geeft `ValueError` en 0 requests. |
| `test_effective_order` | Dezelfde paren direct op `effective_order`, plus `order="valid_at.sideways"` → `ValueError`. |
| `test_select_paginates` | Een handler die 2500 rijen op `limit`/`offset` serveert geeft 4 requests (offsets 0, 1000, 2000, 2500; de laatste levert 0) en 2500 rijen, in volgorde. |
| `test_select_exact_page_multiple` | 2000 rijen geeft 3 requests (de laatste levert 0) en 2000 rijen (E17). 0 rijen geeft 1 request en `[]`. |
| `test_select_short_pages` | Een handler die per request hoogstens 400 rijen teruggeeft (ongeacht `limit`), over 1000 rijen: offsets 0, 400, 800, 1000; resultaat alle 1000 rijen in volgorde (E17b). |
| `test_select_limit` | `limit=1500` over 3000 rijen geeft limits 1000 en 500 (E18) en 1500 rijen. `limit=5` over 10 rijen geeft 1 request en 5 rijen. `limit=0` geeft `ValueError`. |
| `test_upsert_on_conflict_and_prefer` | `POST`, parameter `on_conflict=spot_id,model,valid_at`. De `Prefer`-tokens (split op `,`, gestript) zijn `{"resolution=merge-duplicates","return=minimal"}`. Content-Type is JSON. De body is een JSON-lijst. Een tz-aware datetime in een rij staat als `…Z` in de body. |
| `test_upsert_batches` | 1201 rijen geeft 3 requests met 500, 500 en 201 rijen. Resultaat 1201. |
| `test_upsert_empty_no_request` | Resultaat 0 en 0 requests. |
| `test_upsert_mismatched_keys` | `ValueError` en 0 requests. Ook bij een `on_conflict`-kolom die niet in de rijen staat. |
| `test_insert_returning` | Met `returning=True` is `Prefer` `return=representation` en komen de rijen terug. Zonder is het `return=minimal` en het resultaat `[]`. |
| `test_update_and_delete_require_filters` | `filters=None`, `{}` en `{"id": []}` geven elk `ValueError` voor `update` en `delete`, met 0 requests. `update` met lege `values` geeft ook `ValueError`. |
| `test_update_counts_rows` | `PATCH`, `Prefer: return=representation`, `select=id` voor `ingest_runs`. Een respons met 2 rijen geeft 2. |
| `test_delete_counts_rows` | `DELETE` met filter `valid_at=lt.…` en `select=spot_id,model,valid_at`. Een respons met 3 rijen geeft 3. |
| `test_rpc` | `POST /rest/v1/rpc/db_usage` met body `{}`, resultaat de geparste JSON. Een 204 geeft `None`. |
| `test_http_error_becomes_database_error` | 409 met `{"code":"23505","message":"duplicate key value"}` geeft `DatabaseError` met `status == 409` en `code == "23505"`, en de melding bevat `HTTP 409 23505`. Een 401-body die de secret echoot geeft een melding zonder de secret. Een 500 met HTML-body geeft een melding zonder HTML. Een 302 geeft `DatabaseError`. |
| `test_transport_error` | De handler gooit `httpx.ConnectError("boom testref")`. Gevolg: `DatabaseError`, met `ConnectError` in de melding en zonder `boom`, `testref` of de secret. `exc.__cause__ is None`. |
| `test_validation_errors` | Geparametriseerd, elk een `ValueError` met 0 requests: tabel `spots?x=1`, `../auth` en `Spots`; kolommen `id; drop`; order `id.sideways`; filtersleutel `a b`; filtersleutels `order`, `select`, `limit`, `offset`, `on_conflict`, `columns`, `or`, `and` en `not` (elk met waarde `eq.1`); operatoren `like.*x*`, `not.is.null`, `is.true` en `in.a,b`. |
| `test_to_json` | Een naive datetime, NaN en `inf` geven `ValueError`. `datetime(2026,10,14,14,0,tzinfo=ZoneInfo("Europe/Amsterdam"))` geeft `"2026-10-14T12:00:00Z"`. Een `date`, `time(17,0)` en `frozenset({"b","a"})` worden `"2026-10-14"`, `"17:00:00"` en `["a","b"]`. |
| `test_in_filter` | `["a","b"]` geeft `in.(a,b)`. `["noord, holland","oost"]` geeft `in.("noord, holland",oost)`. `[]` geeft `ValueError`, en een waarde met `"` ook. |
| `test_repr_hides_secret_and_url` | `repr(db)` bevat geen `sb_secret_TESTVALUE` en geen `testref`. |
| `test_from_settings_uses_make_client` | Na een monkeypatch van `shakka.db.make_client` naar een recorder-client gaat een `select` naar `https://testref.supabase.co/rest/v1/spots` met de secret uit `Settings`. `close()` sluit de eigen client. |

**AC-4** (`uv run pytest tests/test_fakes.py`)

| Test | Wat hij toont |
|---|---|
| `test_filter_cases` | Geparametriseerd over `FILTER_CASES`, op `FakeSupabase` met `seed("spots", PARITY_ROWS)`. De ids zijn gelijk aan `expected`. Dit dekt `eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `in.(..)` en `is.null`, plus `order` en `limit`, inclusief de null- en timestampsemantiek van PostgREST en SQL. |
| `test_select_columns_projection` | `columns="id,region"` geeft alleen die sleutels terug. |
| `test_writes_recorded` | `seed` en `select` laten `writes` en `upserts` leeg. Daarna `upsert`, `insert`, `update` en `delete` op `spots` geeft `writes == [("upsert","spots"),("insert","spots"),("update","spots"),("delete","spots")]` en `upserts == [("spots","id")]`. Een lege upsert voegt aan geen van beide iets toe. `rpc` voegt niets toe aan `writes`, wel aan `rpc_calls`. |
| `test_upsert_merges_columns` | Een bestaande spot met `region="x"`, `notes="n"`, ge-upsert met `{id, name, region="y"}`, heeft daarna `region == "y"` en `notes == "n"`, en `updated_at` is gelijk aan de clock. Een nieuwe rij krijgt de defaults (`verified False`, `season []`). `on_conflict="name"` geeft `DatabaseError(code="42P10")`. |
| `test_upsert_duplicate_pk_in_batch` | Een upsert op `forecast_hours` met twee rijen met dezelfde (`spot_id`, `model`, `valid_at`) (één met `Z`, één met `+00:00`; als tijdstip gelijk) geeft `DatabaseError` met `code == "21000"` en `status == 400`, en de tabel blijft leeg (E17d). |
| `test_order_tiebreak_matches_client` | Op `forecast_hours` met 3 spots × 2 modellen op hetzelfde `valid_at`, geseed in willekeurige volgorde: `select(order="valid_at.desc")` geeft de rijen gesorteerd op (`spot_id`, `model`) oplopend (E17c). |
| `test_insert_duplicate_pk_is_atomic` | Een batch met een bestaande PK geeft `DatabaseError(code="23505")`, en de andere rijen uit die batch zijn niet ingevoegd. |
| `test_generated_defaults` | `insert("ingest_runs", [{started_at, status}], returning=True)` geeft `id == 1`, de tweede keer 2. Met een expliciete `id` volgt 428C9. `alert_state` krijgt een uuid-vormige `id`. |
| `test_update_sets_updated_at` | Met een clock die verschuift is `updated_at` na een `update` op `profiles` gelijk aan de nieuwe clockwaarde. Het resultaat telt de geraakte rijen. |
| `test_cascades` | Een favoriet verwijderen verwijdert de bijbehorende `alert_rules`-rij. Een spot verwijderen verwijdert `forecast_hours`, `evaluations`, `favorites`, `alert_rules` en `alert_state` van die spot, en laat andere spots ongemoeid. In `writes` staat alleen `("delete", …)` van de primaire actie. |
| `test_same_validation_as_client` | Lege filters bij `update` of `delete`, een onbekende operator, een naive datetime en `limit=0` geven `ValueError`, net als in de echte client. |
| `test_rpc` | Met `register_rpc("purge", fn)` geeft `rpc("purge", {"x": 1})` het resultaat van `fn({"x": 1})`. Een onbekende naam geeft `DatabaseError(code="PGRST202")`. |
| `test_signatures_match_client` | Voor `select`, `upsert`, `insert`, `update`, `delete`, `rpc` en `close` zijn de parameters van `inspect.signature` (naam, soort, default) gelijk tussen `FakeSupabase` en `SupabaseRest`. |

Pariteit met echt PostgREST: `test_fake_parity.py`, op dezelfde `FILTER_CASES`. De verifier draait deze test als Docker beschikbaar is. Anders noteert hij de test als niet uitgevoerd; AC-4 steunt dan op de handmatig afgeleide verwachtingen in `fake_cases.py`.

**AC-5** (CI-job `db` groen)
- `test_repo_hygiene.py::test_ci_workflow_contract` bevat `db:` en `- run: supabase test db`.
- De groene run zelf: `gh run list --branch wp/WP-01 --limit 1` (verifier), of `NEEDS_LARS` als er niet gepusht is.

**AC-6** (geen latere tabellen)
- `test_migrations.py::test_no_later_milestone_tables`.
- `tables_are` in `01_schema.test.sql`.
- De verifier draait ook het letterlijke `grep`-commando uit AC-6.

**AC-7** (remote toegepast): `NEEDS_LARS`. Lars volgt RUNBOOK sectie 8.3, en daarna toont `supabase migration list --linked` beide migraties als toegepast.

**Regressie:** de volledige suite (`uv run pytest`) blijft groen, inclusief `test_domain_purity.py` (`shakka.db` valt niet onder het domein) en `test_repo_hygiene.py` (er staan geen echte sleutels in tests; de lokale secret key wordt alleen via env meegegeven).

## Externe afhankelijkheden

Geen nieuwe Python-packages. `httpx` (0.28) en `pydantic-settings` zijn er al sinds WP-00.

| Afhankelijkheid | Versie / waarde | Reden | Gecontroleerd |
|---|---|---|---|
| Supabase CLI | 2.121.0 (npm `latest`, gelijk aan `supabase/.temp/cli-latest`) | `start`, `db reset`, `test db`, `db push` en `migration list` | https://registry.npmjs.org/supabase/latest |
| `supabase/setup-cli` | v3.0.1, SHA `45a513f8c64c0bc8e0e3dfe572b5c95be85f6359`, input `version` | CLI in CI | https://github.com/supabase/setup-cli, https://api.github.com/repos/supabase/setup-cli/tags |
| `supabase start -x` | uitgesloten: `realtime,storage-api,imgproxy,mailpit,postgres-meta,studio,edge-runtime,logflare,vector,supavisor` (alle uit de toegestane lijst) | Snellere en minder foutgevoelige CI | https://supabase.com/docs/reference/cli/supabase-test-db |
| `supabase test db` | Vereist een lokale stack. Draait pgTAP op de bestanden in `supabase/tests/` | AC-2, AC-5 | https://supabase.com/docs/reference/cli/supabase-test-db, https://supabase.com/docs/guides/local-development/testing/overview |
| `supabase db push` | `--dry-run`, `--linked`. `migration list --linked` | RUNBOOK, AC-7 | https://supabase.com/docs/reference/cli/supabase-db-push |
| `[api] auto_expose_new_tables` | `false`. Sinds CLI v2.102, gepland voor verwijdering op 2026-10-30. De standaardwaarde is in de bronnen tegenstrijdig. | Lokaal gelijk aan remote | https://github.com/orgs/supabase/discussions/45329, https://github.com/supabase/cli/releases/tag/v2.106.0, commentaar in `supabase/config.toml` (CLI 2.121.0) |
| Expliciete grants | Per tabel voor `anon`, `authenticated` en `service_role`. RLS staat los van grants. Over sequence-grants voor identity-kolommen zijn de Supabase-bronnen tegenstrijdig; het ontwerp leunt op Postgres-gedrag (identity-default zonder rechtencheck) en op de pgTAP-test (A6). | Migratie 2 | https://github.com/orgs/supabase/discussions/45329 |
| pgTAP | `tables_are`, `columns_are`, `set_eq`, `results_eq`, `is`, `is_empty`, `throws_ok(sql, errcode, NULL, desc)`, `lives_ok`, `col_is_pk`. Overloads gecontroleerd in de broncode: `has_trigger(NAME, NAME, NAME, TEXT)`, `table_privs_are(NAME, NAME, NAME, NAME[], TEXT)`, `column_privs_are(NAME, NAME, NAME, NAME, NAME[], TEXT)`, `function_privs_are(NAME, NAME, NAME[], NAME, NAME[], TEXT)`, `policies_are(NAME, NAME, NAME[], TEXT)`. Extensie via `create extension if not exists pgtap with schema extensions`. Rollen wisselen met `set local role` en `request.jwt.claims`. | AC-2 | https://pgtap.org/documentation.html, https://raw.githubusercontent.com/theory/pgtap/master/sql/pgtap.sql.in, https://supabase.com/docs/guides/local-development/testing/overview, https://supabase.com/docs/guides/local-development/testing/pgtap-extended |
| PostgREST-foutstatussen | 23503/23505 → 409; 42501 → 401/403; 21000, 23502, 42P10, 428C9 vallen onder "overige" → 400 | Statussen in `FakeSupabase` | https://raw.githubusercontent.com/PostgREST/postgrest/main/docs/references/errors.rst |
| `profiles`-trigger | `security definer set search_path = ''`, `after insert on auth.users`. Een falende trigger blokkeert de signup. | Migratie 1 | https://supabase.com/docs/guides/auth/managing-user-data |
| Kolomprivileges | `revoke update` op de tabel, daarna `grant update (kolommen)` | `telegram_chat_id` afschermen | https://supabase.com/docs/guides/database/postgres/column-level-security |
| Supabase API-sleutels | `sb_secret_…` alleen in de `apikey`-header, niet als Bearer. Werkt als `service_role` (BYPASSRLS). 401 bij een browser-achtige User-Agent. | `SupabaseRest`-headers | https://supabase.com/docs/guides/api/api-keys |
| PostgREST | Operatoren `eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `in.(…)` (waarden met gereserveerde tekens tussen dubbele aanhalingstekens), `is.null`. `order=a.desc,b.asc[.nullsfirst\|.nullslast]`, standaard asc. `limit` en `offset` (de server kan minder geven). Upsert: `POST` + `Prefer: resolution=merge-duplicates` + `on_conflict`. Bulk insert: "array of objects having all-matching keys". `return=minimal` is de standaard voor schrijfacties. `return=representation` mag met `select`. | `SupabaseRest` en `FakeSupabase` | https://github.com/PostgREST/postgrest/blob/main/docs/references/api/tables_views.rst, https://github.com/PostgREST/postgrest/blob/main/docs/references/api/preferences.rst, https://github.com/PostgREST/postgrest/blob/main/docs/references/api/pagination_count.rst |
| Herhaalde filterparameter | Dezelfde kolom twee keer (`a=gte.x&a=lt.y`). postgrest-js doet `searchParams.append` voor `gte`, `lt` en `in`, en citeert `in`-waarden met `[,()]`. | `Filters` met lijsten, `in_filter` | https://github.com/supabase/postgrest-js/blob/master/src/PostgrestFilterBuilder.ts |

Geen betaalde diensten. CI draait op gratis GitHub Actions in een publieke repo. De lokale stack draait in Docker.

## Risico's
- **R1. `auto_expose_new_tables` verdwijnt of verandert van betekenis.** Rond 2026-10-30 kan een nieuwere CLI de sleutel weigeren. Mitigatie: CI pint CLI 2.121.0. De migraties revoken en granten zelf, en `table_privs_are` legt de uitkomst vast. Bij een fout op de sleutel wordt de regel verwijderd (RUNBOOK); het ontwerp verandert daar niet door.
- **R2. `supabase start -x …` faalt in CI.** Dat kan als een uitgesloten dienst toch nodig blijkt. Dan haalt de builder de uitsluitingen weg (gewoon `supabase start`) en noteert dat in `deviations.md`. Het ontwerp verandert daar niet door.
- **R3. Paginering en "Max rows".** Afgevangen: de lus stopt pas bij een lege pagina, dus ook bij "Max rows" < 1000 is het resultaat compleet (`test_select_short_pages`). Prijs: één extra request per `select`. De RUNBOOK raadt nog steeds aan "Max rows" op 1000 te laten, omdat het anders meer requests kost.
- **R3b. Paginering terwijl de tabel verandert.** `limit`/`offset` kan rijen overslaan of dubbel geven als er tussen twee pagina's rijen bijkomen of verdwijnen. De PK-tiebreaker lost alleen het probleem van gelijke sorteerwaarden op. Voor M1 aanvaardbaar: er draait één ingest-job per uur, en die is de enige schrijver op de grote tabellen.
- **R4. De fake wijkt af van PostgREST.** Mitigatie: gedeelde validatie- en parseerhelpers, de pariteitstest tegen de lokale stack, en een expliciete lijst van wat níet wordt nagebootst (FK, CHECK, collatie, afronding van numeric). Jobtests van latere WP's die op constraints leunen, horen bij hun AC tegen de lokale stack.
- **R5. De CHECK op `evaluations.reasons` koppelt WP-05 aan een migratie.** Dat is bewust: de lijst ligt vast in WORK_PACKAGES, en een onbekende code in de database zou de PWA een ruwe code laten tonen (WP-14 AC-2). Een nieuwe code betekent een kleine migratie.
- **R6. Insert in `auth.users` met alleen (`id`, `email`).** Hangt af van de kolomdefaults van GoTrue. Basejump-helpers doen hetzelfde. Faalt het, dan voegt de builder `raw_user_meta_data '{}'` en `aud 'authenticated'` toe en noteert dat in `deviations.md` (geen ontwerpwijziging).
- **R7. Het remote project heeft al tabellen of migraties.** In strijd met A2. Dan toont `supabase db push --dry-run` dat en stopt Lars. De RUNBOOK noemt de dry-run als eerste stap.
- **R8. Kolom-UPDATE en upsert vanuit de PWA.** Een upsert op `profiles` door `authenticated` faalt, want er is geen INSERT. WP-16 moet `update` gebruiken; het profiel bestaat altijd dankzij de trigger.

## Buiten scope
- `marine_hours` (WP-12), `push_subscriptions` (WP-17), `sessions` en `rsvps` (WP-19), RPC's zoals `db_usage` (WP-22) en `delete_my_account` (WP-23).
- Tabellen vullen: spots (WP-02), forecasts (WP-03), getij (WP-04), evaluaties en alert_state (WP-10), ingest_runs (WP-11).
- Een atomaire increment-RPC voor `api_usage`. WP-03 kiest de aanpak; er draait één job per uur.
- Retries en backoff voor databasecalls (WP-22, `with_retries`).
- Opruimen van oude rijen (WP-03, WP-04, WP-10, WP-11). Hier zijn alleen de indexen voorbereid.
- `shakka doctor` aanpassen (WP-00 R1 blijft open; doctor werkt).
- Seeddata (`supabase/seed.sql`), Supabase-typegeneratie voor de PWA (WP-13 en WP-14), en Auth-configuratie (SMTP, redirect-URL's; WP-13 en WP-22).
- Zelf `supabase db push` draaien. Dat doet Lars na de merge.

## Stappenplan voor de builder
Werk op branch `wp/WP-01` in de worktree. Lees of print `.env` nooit. Na elke Python-stap: `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .`. Na elke databasestap: `supabase db reset && supabase test db` vanuit de repo-root, met de lokale stack draaiend via `supabase start`. Eén commit per stap, commitberichten in het Engels.

1. **Config en hygiëne.**
   - Zet `auto_expose_new_tables = false` in `[api]` van `supabase/config.toml`.
   - Voeg `test_supabase_config_disables_auto_expose` toe aan `test_repo_hygiene.py`.
   - Start de lokale stack (`supabase start`) en controleer dat `supabase db reset` zonder migraties slaagt.

   Commit: `chore(supabase): disable auto-expose of new tables locally`.
2. **Schema, eerst de test.**
   - Schrijf `supabase/tests/01_schema.test.sql` volledig.
   - `supabase test db` faalt (rood).
   - Schrijf `supabase/migrations/20261015090000_m1_schema.sql` exact volgens Interfaces.
   - Controleer `supabase db reset` en `supabase test db`: groen. De RLS-assert (`relrowsecurity`) staat in stap 2 nog niet in `01` (`plan(70)`); die komt er in stap 3 bij (`plan(71)`), zodat elke commit groen is.

   Commit: `feat(db): add M1 schema migration with pgTAP schema tests`.
3. **Beveiliging, eerst de tests.**
   - Schrijf `02_privileges.test.sql`, `03_rls_anon.test.sql` en `04_rls_users.test.sql`, en voeg de RLS-assert toe aan `01`.
   - Rood.
   - Schrijf `supabase/migrations/20261015090100_m1_security.sql`.
   - `supabase db reset && supabase test db` is groen.
   - Draai ook het letterlijke `grep`-commando uit AC-6.

   Commit: `feat(db): add RLS, grants and policies for M1 tables`.
4. **CI-job `db`.**
   - Voeg de job toe aan `.github/workflows/ci.yml` (exact).
   - Breid `test_ci_workflow_contract` uit.

   Commit: `ci: run pgTAP database tests`.
5. **Migratietests.** Schrijf `ingest/tests/test_migrations.py`. Die verwijst al naar `shakka.db.TABLE_KEYS`, dus maak eerst `shakka/db.py` met alleen `TABLE_KEYS` en de constanten.

   Commit: `test(ingest): guard migrations against later-milestone tables`.
6. **`SupabaseRest`, eerst de tests.**
   - Schrijf `ingest/tests/test_db.py` volledig. Rood.
   - Implementeer in `shakka/db.py`:
     - `DatabaseError`, `OrderTerm`;
     - de constante `RESERVED_PARAMS` en de helpers (`iso_utc`, `in_filter`, `to_json`, `validate_table`, `parse_columns`, `parse_order`, `default_order`, `effective_order`, `filter_params`);
     - `SupabaseRest`.
   - Groen.
   - Controleer dat `httpx.Client(` alleen in `shakka/http.py` staat (`grep -rn "httpx.Client(" ingest/src`).

   Commit: `feat(ingest): add Supabase REST client with pagination and batching`.
7. **`FakeSupabase`, eerst de tests.**
   - Schrijf `ingest/tests/fake_cases.py` en `ingest/tests/test_fakes.py`. Rood.
   - Implementeer `ingest/tests/fakes.py`. Groen.
   - Schrijf `ingest/tests/test_fake_parity.py`. Draai die lokaal tegen de stack, met de lokale secret key uit `supabase status` via de twee `SHAKKA_TEST_*`-variabelen (niet in een bestand zetten). Wijkt een case af, dan is `fake_cases.py` of de fake fout, niet de test. Pas aan tot ook de pariteit groen is.
   - Zonder env wordt de pariteitstest overgeslagen.

   Commit: `test(ingest): add in-memory FakeSupabase with PostgREST semantics`.
8. **RUNBOOK.** Vul sectie 6 aan, voeg sectie 8 toe en werk sectie 7 bij (Nederlands, zonder secrets).

   Commit: `docs: document migrations, local db tests and db push`.
9. **Eindcontrole.**
   - `supabase db reset` en `supabase test db` (lokaal).
   - `cd ingest && uv sync && uv run pytest && uv run ruff check . && uv run ruff format --check .`
   - Het letterlijke `grep` van AC-6, en `git grep --untracked -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'`: geen treffers.
   - Push `wp/WP-01` alleen met uitdrukkelijke toestemming. Daarna `gh run list --branch wp/WP-01 --limit 1`: jobs `ingest` en `db` zijn groen.
   - Niet zelf `supabase db push` naar het remote project draaien (AC-7 is voor Lars).

## Verwerking review

Review ronde 1 (`docs/wp/WP-01/review.md`), oordeel CHANGES_REQUIRED.

**Blokkerend**

| Punt | Verwerking |
|---|---|
| B-1: `updated_at`-test in AC-2(e) faalt altijd (`now()` constant in de transactie) | Overgenomen met de variant uit de review. Testplan (e) zet als `postgres` eerst `updated_at` op `2000-01-01T00:00:00Z` met de trigger tijdelijk uit (`alter table … disable/enable trigger profiles_set_updated_at`; exacte SQL staat erbij). Een preconditie-assert (21) bewijst dat het terugzetten werkte; na de update als A toetst `is(updated_at, now())` (26) dat de trigger vuurde. Geen afhankelijkheid van de klok, en de DDL van `set_updated_at()` blijft ongewijzigd. Gekozen boven `session_replication_role`, omdat dat superuser-rechten vraagt en `postgres` in Supabase geen superuser is. `04_rls_users.test.sql` is volledig genummerd uitgeschreven met `plan(42)`; ook de andere bestanden hebben nu een vast `plan(N)`. |
| B-2: paginering niet deterministisch bij een niet-unieke `order` | Overgenomen. Nieuwe helper `effective_order(table, order)` in `shakka.db`: voor tabellen in `TABLE_KEYS` komen de ontbrekende PK-kolommen als tiebreaker achter de opgegeven `order` (`valid_at.desc` → `valid_at.desc,spot_id,model`); een onbekende tabel met eigen `order` blijft ongewijzigd (docstring). `SupabaseRest.select` en `FakeSupabase.select` gebruiken allebei deze helper. `test_select_default_order` is aangepast, `test_effective_order` en `test_order_tiebreak_matches_client` zijn nieuw, en `FILTER_CASES` heeft twee cases met gelijke sorteerwaarden (`order_ties_pk_tiebreak`, `order_ties_bool`), zodat de pariteitstest de tiebreak ook tegen echt PostgREST toetst. Edge case E17c. |

**Niet-blokkerend**

| Punt | Verwerking |
|---|---|
| N-1 | Overgenomen: sectie (g) voegt als `postgres` eerst favoriet (A, `pgtap-spot-2`) toe; alle `dir_classes`-inserts, ook de positieve, gebruiken die sleutel. |
| N-2 | Overgenomen: rij `alert_rules` in de CHECK-tabel van `01` (9 invoeren, inclusief `weekdays='{1,NULL}'`), plus `forecast_hours.gust_kn=-1`. `tide_extremes` blijft bij één invoer. |
| N-3 | Overgenomen: paragraaf "Typering van pgTAP-aanroepen" met verplichte casts, beschrijvingen en de exacte vormen per functie; overloads gecontroleerd in `pgtap.sql.in`. `confdeltype::text` in de FK-`set_eq`. |
| N-4 | Overgenomen: A3 vraagt de orchestrator dit in de verificatieopdracht te noemen. |
| N-5 | Overgenomen: `FakeSupabase.upsert` geeft `DatabaseError(code="21000", status=400)` bij een dubbele PK binnen één batch (status volgens de PostgREST-foutentabel). Test `test_upsert_duplicate_pk_in_batch`, edge case E17d, en een regel bij "Gevolgen voor latere WP's". PK-vergelijking in de fake behandelt timestamps als tijdstip. |
| N-6 | Overgenomen in "Wat de fake níet nabootst", met de parseerregel; ook bij "Gevolgen voor latere WP's". |
| N-7 | Overgenomen in "Gevolgen voor latere WP's" (WP-02 `name`, WP-07/WP-10 `weekdays`, `dir_classes`, tijdvenster en `min_kn < max_kn`, WP-10 `telegram_chat_id`-formaat). |
| N-8 | Overgenomen: backfill-insert direct na de trigger in migratie 1; toelichting in Ontwerp. |
| N-9 | Overgenomen: `RESERVED_PARAMS` en de weigering in `filter_params`; cases in `test_validation_errors`, edge case E17e. |
| N-10 | Overgenomen: stopcriterium is een lege pagina. `test_select_paginates` verwacht nu 4 requests, nieuwe test `test_select_short_pages`, A5, R3 en RUNBOOK 8.4 bijgewerkt. |
| N-11 | Overgenomen: A6 en de rij "Expliciete grants" onderbouwen het met Postgres-gedrag plus de pgTAP-test, en noemen de tegenstrijdige Supabase-bronnen expliciet. |
| N-12 | Overgenomen: `FakeSupabase.upserts: list[tuple[str, str]]` (tabel, `on_conflict`), getoetst in `test_writes_recorded`. |
