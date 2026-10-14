-- What anon may and may not do. Private tables are not even readable (no grant -> 42501).
begin;
create extension if not exists pgtap with schema extensions;

select plan(22);

-- Fixture as postgres: one spot and one row per public read table.
insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot');
insert into public.forecast_hours (spot_id, model, valid_at, fetched_at)
  values ('pgtap-spot', 'knmi', '2026-10-14T12:00:00Z', '2026-10-14T11:00:00Z');
insert into public.tide_extremes (station, at, kind, level_cm, fetched_at)
  values ('pgtap-station', '2026-10-14T12:00:00Z', 'high', 100, '2026-10-14T11:00:00Z');
insert into public.evaluations (spot_id, valid_at, verdict, evaluated_at)
  values ('pgtap-spot', '2026-10-14T12:00:00Z', 'no_go', '2026-10-14T11:00:00Z');

set local role anon;

select results_eq('select count(*)::int from public.spots', array[1], 'anon reads spots');
select results_eq('select count(*)::int from public.forecast_hours', array[1], 'anon reads forecast_hours');
select results_eq('select count(*)::int from public.tide_extremes', array[1], 'anon reads tide_extremes');
select results_eq('select count(*)::int from public.evaluations', array[1], 'anon reads evaluations');

select throws_ok($$insert into public.spots (id, name) values ('pgtap-x', 'x')$$, '42501', null, 'anon cannot insert spots');
select throws_ok($$update public.spots set name = 'x'$$, '42501', null, 'anon cannot update spots');
select throws_ok($$delete from public.spots$$, '42501', null, 'anon cannot delete spots');

select throws_ok($$insert into public.forecast_hours (spot_id, model, valid_at, fetched_at) values ('pgtap-spot', 'icon', now(), now())$$, '42501', null, 'anon cannot insert forecast_hours');
select throws_ok($$update public.forecast_hours set wind_kn = 1$$, '42501', null, 'anon cannot update forecast_hours');
select throws_ok($$delete from public.forecast_hours$$, '42501', null, 'anon cannot delete forecast_hours');

select throws_ok($$insert into public.tide_extremes (station, at, kind, level_cm, fetched_at) values ('pgtap-station', now(), 'low', 0, now())$$, '42501', null, 'anon cannot insert tide_extremes');
select throws_ok($$update public.tide_extremes set level_cm = 1$$, '42501', null, 'anon cannot update tide_extremes');
select throws_ok($$delete from public.tide_extremes$$, '42501', null, 'anon cannot delete tide_extremes');

select throws_ok($$insert into public.evaluations (spot_id, valid_at, verdict, evaluated_at) values ('pgtap-spot', now(), 'go', now())$$, '42501', null, 'anon cannot insert evaluations');
select throws_ok($$update public.evaluations set verdict = 'go'$$, '42501', null, 'anon cannot update evaluations');
select throws_ok($$delete from public.evaluations$$, '42501', null, 'anon cannot delete evaluations');

select throws_ok('select * from public.profiles', '42501', null, 'anon cannot read profiles');
select throws_ok('select * from public.favorites', '42501', null, 'anon cannot read favorites');
select throws_ok('select * from public.alert_rules', '42501', null, 'anon cannot read alert_rules');
select throws_ok('select * from public.alert_state', '42501', null, 'anon cannot read alert_state');
select throws_ok('select * from public.api_usage', '42501', null, 'anon cannot read api_usage');
select throws_ok('select * from public.ingest_runs', '42501', null, 'anon cannot read ingest_runs');

reset role;
select * from finish();
rollback;
