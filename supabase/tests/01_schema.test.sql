-- Schema shape: tables, columns, keys, constraints, triggers. Runs as postgres.
begin;
create extension if not exists pgtap with schema extensions;

select plan(71);

select tables_are('public'::name, array['spots', 'forecast_hours', 'tide_extremes', 'evaluations', 'profiles', 'favorites', 'alert_rules', 'alert_state', 'api_usage', 'ingest_runs']::name[], 'public has exactly the M1 tables');

select columns_are('public'::name, 'spots'::name, array['id', 'name', 'region', 'lat', 'lon', 'shore_normal_deg', 'ridable_dirs', 'hazards', 'tide_sensitive', 'tide_min_level_cm', 'rws_station', 'season', 'status', 'level', 'default_min_kn', 'notes', 'verified', 'updated_at']::name[], 'spots columns');
select columns_are('public'::name, 'forecast_hours'::name, array['spot_id', 'model', 'valid_at', 'wind_kn', 'gust_kn', 'dir_deg', 'fetched_at']::name[], 'forecast_hours columns');
select columns_are('public'::name, 'tide_extremes'::name, array['station', 'at', 'kind', 'level_cm', 'fetched_at']::name[], 'tide_extremes columns');
select columns_are('public'::name, 'evaluations'::name, array['spot_id', 'valid_at', 'verdict', 'reasons', 'wind_kn', 'gust_kn', 'dir_deg', 'dir_class', 'confidence', 'tide_level_cm', 'evaluated_at']::name[], 'evaluations columns');
select columns_are('public'::name, 'profiles'::name, array['user_id', 'weight_kg', 'level', 'quiver_m2', 'default_min_kn', 'default_max_kn', 'telegram_chat_id', 'created_at', 'updated_at']::name[], 'profiles columns');
select columns_are('public'::name, 'favorites'::name, array['user_id', 'spot_id', 'created_at']::name[], 'favorites columns');
select columns_are('public'::name, 'alert_rules'::name, array['user_id', 'spot_id', 'enabled', 'min_kn', 'max_kn', 'dir_classes', 'weekdays', 'earliest_local', 'latest_local', 'min_go_hours', 'days_ahead', 'updated_at']::name[], 'alert_rules columns');
select columns_are('public'::name, 'alert_state'::name, array['id', 'user_id', 'spot_id', 'window_start', 'window_end', 'status', 'snapshot', 'last_event', 'last_notified_at', 'created_at', 'updated_at']::name[], 'alert_state columns');
select columns_are('public'::name, 'api_usage'::name, array['day', 'source', 'calls', 'requests']::name[], 'api_usage columns');
select columns_are('public'::name, 'ingest_runs'::name, array['id', 'started_at', 'finished_at', 'status', 'steps', 'error_summary']::name[], 'ingest_runs columns');

select set_eq(
  $q$select c.relname::text, a.attname::text, format_type(a.atttypid, a.atttypmod)::text,
            not a.attnotnull
       from pg_attribute a
       join pg_class c on c.oid = a.attrelid
       join pg_namespace n on n.oid = c.relnamespace
      where n.nspname = 'public' and c.relkind = 'r' and a.attnum > 0 and not a.attisdropped$q$,
  $q$values
    ('spots', 'id', 'text', false),
    ('spots', 'name', 'text', false),
    ('spots', 'region', 'text', true),
    ('spots', 'lat', 'double precision', true),
    ('spots', 'lon', 'double precision', true),
    ('spots', 'shore_normal_deg', 'smallint', true),
    ('spots', 'ridable_dirs', 'jsonb', true),
    ('spots', 'hazards', 'text', true),
    ('spots', 'tide_sensitive', 'text', false),
    ('spots', 'tide_min_level_cm', 'integer', true),
    ('spots', 'rws_station', 'text', true),
    ('spots', 'season', 'jsonb', false),
    ('spots', 'status', 'text', true),
    ('spots', 'level', 'text', true),
    ('spots', 'default_min_kn', 'smallint', true),
    ('spots', 'notes', 'text', true),
    ('spots', 'verified', 'boolean', false),
    ('spots', 'updated_at', 'timestamp with time zone', false),
    ('forecast_hours', 'spot_id', 'text', false),
    ('forecast_hours', 'model', 'text', false),
    ('forecast_hours', 'valid_at', 'timestamp with time zone', false),
    ('forecast_hours', 'wind_kn', 'real', true),
    ('forecast_hours', 'gust_kn', 'real', true),
    ('forecast_hours', 'dir_deg', 'smallint', true),
    ('forecast_hours', 'fetched_at', 'timestamp with time zone', false),
    ('tide_extremes', 'station', 'text', false),
    ('tide_extremes', 'at', 'timestamp with time zone', false),
    ('tide_extremes', 'kind', 'text', false),
    ('tide_extremes', 'level_cm', 'integer', false),
    ('tide_extremes', 'fetched_at', 'timestamp with time zone', false),
    ('evaluations', 'spot_id', 'text', false),
    ('evaluations', 'valid_at', 'timestamp with time zone', false),
    ('evaluations', 'verdict', 'text', false),
    ('evaluations', 'reasons', 'text[]', false),
    ('evaluations', 'wind_kn', 'real', true),
    ('evaluations', 'gust_kn', 'real', true),
    ('evaluations', 'dir_deg', 'smallint', true),
    ('evaluations', 'dir_class', 'text', true),
    ('evaluations', 'confidence', 'text', true),
    ('evaluations', 'tide_level_cm', 'integer', true),
    ('evaluations', 'evaluated_at', 'timestamp with time zone', false),
    ('profiles', 'user_id', 'uuid', false),
    ('profiles', 'weight_kg', 'smallint', true),
    ('profiles', 'level', 'text', true),
    ('profiles', 'quiver_m2', 'real[]', false),
    ('profiles', 'default_min_kn', 'smallint', true),
    ('profiles', 'default_max_kn', 'smallint', true),
    ('profiles', 'telegram_chat_id', 'text', true),
    ('profiles', 'created_at', 'timestamp with time zone', false),
    ('profiles', 'updated_at', 'timestamp with time zone', false),
    ('favorites', 'user_id', 'uuid', false),
    ('favorites', 'spot_id', 'text', false),
    ('favorites', 'created_at', 'timestamp with time zone', false),
    ('alert_rules', 'user_id', 'uuid', false),
    ('alert_rules', 'spot_id', 'text', false),
    ('alert_rules', 'enabled', 'boolean', false),
    ('alert_rules', 'min_kn', 'smallint', true),
    ('alert_rules', 'max_kn', 'smallint', true),
    ('alert_rules', 'dir_classes', 'text[]', true),
    ('alert_rules', 'weekdays', 'smallint[]', true),
    ('alert_rules', 'earliest_local', 'time without time zone', true),
    ('alert_rules', 'latest_local', 'time without time zone', true),
    ('alert_rules', 'min_go_hours', 'smallint', true),
    ('alert_rules', 'days_ahead', 'smallint', true),
    ('alert_rules', 'updated_at', 'timestamp with time zone', false),
    ('alert_state', 'id', 'uuid', false),
    ('alert_state', 'user_id', 'uuid', false),
    ('alert_state', 'spot_id', 'text', false),
    ('alert_state', 'window_start', 'timestamp with time zone', false),
    ('alert_state', 'window_end', 'timestamp with time zone', false),
    ('alert_state', 'status', 'text', false),
    ('alert_state', 'snapshot', 'jsonb', false),
    ('alert_state', 'last_event', 'text', true),
    ('alert_state', 'last_notified_at', 'timestamp with time zone', true),
    ('alert_state', 'created_at', 'timestamp with time zone', false),
    ('alert_state', 'updated_at', 'timestamp with time zone', false),
    ('api_usage', 'day', 'date', false),
    ('api_usage', 'source', 'text', false),
    ('api_usage', 'calls', 'numeric(10,2)', false),
    ('api_usage', 'requests', 'integer', false),
    ('ingest_runs', 'id', 'bigint', false),
    ('ingest_runs', 'started_at', 'timestamp with time zone', false),
    ('ingest_runs', 'finished_at', 'timestamp with time zone', true),
    ('ingest_runs', 'status', 'text', false),
    ('ingest_runs', 'steps', 'jsonb', false),
    ('ingest_runs', 'error_summary', 'text', true)
  $q$,
  'column types and nullability');

select col_is_pk('public'::name, 'spots'::name, array['id']::name[], 'spots primary key');
select col_is_pk('public'::name, 'forecast_hours'::name, array['spot_id', 'model', 'valid_at']::name[], 'forecast_hours primary key');
select col_is_pk('public'::name, 'tide_extremes'::name, array['station', 'at']::name[], 'tide_extremes primary key');
select col_is_pk('public'::name, 'evaluations'::name, array['spot_id', 'valid_at']::name[], 'evaluations primary key');
select col_is_pk('public'::name, 'profiles'::name, array['user_id']::name[], 'profiles primary key');
select col_is_pk('public'::name, 'favorites'::name, array['user_id', 'spot_id']::name[], 'favorites primary key');
select col_is_pk('public'::name, 'alert_rules'::name, array['user_id', 'spot_id']::name[], 'alert_rules primary key');
select col_is_pk('public'::name, 'alert_state'::name, array['id']::name[], 'alert_state primary key');
select col_is_pk('public'::name, 'api_usage'::name, array['day', 'source']::name[], 'api_usage primary key');
select col_is_pk('public'::name, 'ingest_runs'::name, array['id']::name[], 'ingest_runs primary key');

select set_eq(
  $q$select conrelid::regclass::text, confrelid::regclass::text, confdeltype::text
       from pg_constraint where contype = 'f' and connamespace = 'public'::regnamespace$q$,
  $q$values
    ('forecast_hours', 'spots', 'c'), ('evaluations', 'spots', 'c'),
    ('profiles', 'auth.users', 'c'),
    ('favorites', 'auth.users', 'c'), ('favorites', 'spots', 'c'),
    ('alert_rules', 'favorites', 'c'),
    ('alert_state', 'auth.users', 'c'), ('alert_state', 'spots', 'c')
  $q$,
  'foreign keys cascade on delete');

select is_empty(
  $q$select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
      where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity$q$,
  'row level security is enabled on every public table');

select has_trigger('public'::name, 'spots'::name, 'spots_set_updated_at'::name, 'spots_set_updated_at exists');
select has_trigger('public'::name, 'profiles'::name, 'profiles_set_updated_at'::name, 'profiles_set_updated_at exists');
select has_trigger('public'::name, 'alert_rules'::name, 'alert_rules_set_updated_at'::name, 'alert_rules_set_updated_at exists');
select has_trigger('public'::name, 'alert_state'::name, 'alert_state_set_updated_at'::name, 'alert_state_set_updated_at exists');
select has_trigger('auth'::name, 'users'::name, 'on_auth_user_created'::name, 'on_auth_user_created exists');

-- Fixture: one spot, user A (profile via trigger) and a favorite.
insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot');
insert into auth.users (id, email) values ('11111111-1111-1111-1111-111111111111', 'a@example.test');
insert into public.favorites (user_id, spot_id) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot');

select throws_ok($$insert into public.spots (id, name) values ('Bad Id', 'x')$$, '23514', null, 'spots: id must be a slug');
select throws_ok($$insert into public.spots (id, name, tide_sensitive) values ('pgtap-a', 'x', 'sometimes')$$, '23514', null, 'spots: tide_sensitive enum');
select throws_ok($$insert into public.spots (id, name, status) values ('pgtap-a', 'x', 'open')$$, '23514', null, 'spots: status enum');
select throws_ok($$insert into public.spots (id, name, level) values ('pgtap-a', 'x', 'pro')$$, '23514', null, 'spots: level enum');
select throws_ok($$insert into public.spots (id, name, shore_normal_deg) values ('pgtap-a', 'x', 360)$$, '23514', null, 'spots: shore_normal_deg < 360');
select throws_ok($$insert into public.spots (id, name, lat) values ('pgtap-a', 'x', 52)$$, '23514', null, 'spots: lat without lon');
select throws_ok($$insert into public.spots (id, name, default_min_kn) values ('pgtap-a', 'x', 4)$$, '23514', null, 'spots: default_min_kn >= 5');

select throws_ok($$insert into public.forecast_hours (spot_id, model, valid_at, fetched_at) values ('pgtap-spot', 'gem', now(), now())$$, '23514', null, 'forecast_hours: model enum');
select throws_ok($$insert into public.forecast_hours (spot_id, model, valid_at, fetched_at, dir_deg) values ('pgtap-spot', 'knmi', now(), now(), 360)$$, '23514', null, 'forecast_hours: dir_deg < 360');
select throws_ok($$insert into public.forecast_hours (spot_id, model, valid_at, fetched_at, wind_kn) values ('pgtap-spot', 'knmi', now(), now(), -1)$$, '23514', null, 'forecast_hours: wind_kn >= 0');
select throws_ok($$insert into public.forecast_hours (spot_id, model, valid_at, fetched_at, gust_kn) values ('pgtap-spot', 'knmi', now(), now(), -1)$$, '23514', null, 'forecast_hours: gust_kn >= 0');
select throws_ok($$insert into public.tide_extremes (station, at, kind, level_cm, fetched_at) values ('hoekvanholland', now(), 'mid', 0, now())$$, '23514', null, 'tide_extremes: kind enum');

select throws_ok($$insert into public.evaluations (spot_id, valid_at, verdict, evaluated_at) values ('pgtap-spot', now(), 'maybe', now())$$, '23514', null, 'evaluations: verdict enum');
select throws_ok($$insert into public.evaluations (spot_id, valid_at, verdict, evaluated_at, dir_class) values ('pgtap-spot', now(), 'no_go', now(), 'cross')$$, '23514', null, 'evaluations: dir_class enum');
select throws_ok($$insert into public.evaluations (spot_id, valid_at, verdict, evaluated_at, confidence) values ('pgtap-spot', now(), 'no_go', now(), 'certain')$$, '23514', null, 'evaluations: confidence enum');
select throws_ok($$insert into public.evaluations (spot_id, valid_at, verdict, evaluated_at, reasons) values ('pgtap-spot', now(), 'no_go', now(), '{unknown_code}')$$, '23514', null, 'evaluations: reasons whitelist');
select throws_ok($$insert into public.evaluations (spot_id, valid_at, verdict, dir_class, evaluated_at) values ('pgtap-spot', now(), 'go', 'offshore', now())$$, '23514', null, 'evaluations: offshore must be no_go');
select throws_ok($$insert into public.evaluations (spot_id, valid_at, verdict, dir_class, evaluated_at) values ('pgtap-spot', now(), 'marginal', 'side_offshore', now())$$, '23514', null, 'evaluations: side_offshore must be no_go');

select throws_ok($$update public.profiles set weight_kg = 29 where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'profiles: weight_kg >= 30');
select throws_ok($$update public.profiles set weight_kg = 201 where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'profiles: weight_kg <= 200');
select throws_ok($$update public.profiles set level = 'pro' where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'profiles: level enum');
select throws_ok($$update public.profiles set quiver_m2 = '{2.5}' where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'profiles: quiver_m2 >= 3');
select throws_ok($$update public.profiles set quiver_m2 = '{3,4,5,6,7,8,9,10,11,12,13}' where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'profiles: quiver_m2 has at most 10 kites');
select throws_ok($$update public.profiles set telegram_chat_id = 'abc' where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'profiles: telegram_chat_id is numeric');
select throws_ok($$update public.profiles set default_min_kn = 20, default_max_kn = 15 where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'profiles: min < max');

select throws_ok($$insert into public.alert_rules (user_id, spot_id, weekdays) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', '{0}')$$, '23514', null, 'alert_rules: weekday 0');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, weekdays) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', '{8}')$$, '23514', null, 'alert_rules: weekday 8');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, weekdays) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', '{}')$$, '23514', null, 'alert_rules: weekdays not empty');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, weekdays) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', '{1,NULL}')$$, '23514', null, 'alert_rules: weekdays no nulls');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, earliest_local, latest_local) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', '18:00', '17:00')$$, '23514', null, 'alert_rules: time window order');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, min_kn, max_kn) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', 20, 15)$$, '23514', null, 'alert_rules: min < max');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, min_go_hours) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', 0)$$, '23514', null, 'alert_rules: min_go_hours >= 1');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, days_ahead) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', 8)$$, '23514', null, 'alert_rules: days_ahead <= 7');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, min_kn) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', 4)$$, '23514', null, 'alert_rules: min_kn >= 5');

select throws_ok($$insert into public.alert_state (user_id, spot_id, snapshot, window_start, window_end, status) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', '{}', '2026-10-14T10:00:00Z', '2026-10-14T14:00:00Z', 'open')$$, '23514', null, 'alert_state: status enum');
select throws_ok($$insert into public.alert_state (user_id, spot_id, snapshot, window_start, window_end, status, last_event) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', '{}', '2026-10-14T10:00:00Z', '2026-10-14T14:00:00Z', 'active', 'moved')$$, '23514', null, 'alert_state: last_event enum');
select throws_ok($$insert into public.alert_state (user_id, spot_id, snapshot, window_start, window_end, status) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', '{}', '2026-10-14T10:00:00Z', '2026-10-14T10:00:00Z', 'active')$$, '23514', null, 'alert_state: window_end > window_start');
select throws_ok($$insert into public.api_usage (day, source) values ('2026-10-14', 'windguru')$$, '23514', null, 'api_usage: source enum');
select throws_ok($$insert into public.api_usage (day, source, calls) values ('2026-10-14', 'rws', -1)$$, '23514', null, 'api_usage: calls >= 0');
select throws_ok($$insert into public.ingest_runs (started_at, status) values (now(), 'done')$$, '23514', null, 'ingest_runs: status enum');

select lives_ok($$insert into public.evaluations (spot_id, valid_at, verdict, dir_class, evaluated_at) values ('pgtap-spot', now(), 'no_go', 'offshore', now())$$, 'evaluations: offshore with no_go is accepted');
select lives_ok($$insert into public.spots (id, name) values ('pgtap-min', 'Minimal')$$, 'spots: only id and name are required');

select * from finish();
rollback;
