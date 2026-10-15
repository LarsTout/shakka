-- marine_hours (WP-12): shape, privileges, constraints, RLS, cascade.
-- Asserts on rows filter on 'pgtap-spot' so they do not depend on an empty table.
begin;
create extension if not exists pgtap with schema extensions;

select plan(20);

-- Fixture (postgres).
insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot');
insert into public.marine_hours (spot_id, valid_at, wave_height_m, wave_period_s, wave_dir_deg, fetched_at)
  values ('pgtap-spot', '2026-10-14T12:00:00Z', 1.2, 5.0, 250, '2026-10-14T11:00:00Z');

select columns_are('public'::name, 'marine_hours'::name, array['spot_id', 'valid_at', 'wave_height_m', 'wave_period_s', 'wave_dir_deg', 'fetched_at']::name[], 'marine_hours columns');
select col_is_pk('public'::name, 'marine_hours'::name, array['spot_id', 'valid_at']::name[], 'marine_hours primary key');
select has_index('public'::name, 'marine_hours'::name, 'marine_hours_valid_at_idx'::name, 'index on valid_at');

select table_privs_are('public'::name, 'marine_hours'::name, 'anon'::name, array['SELECT']::name[], 'anon privileges on marine_hours');
select table_privs_are('public'::name, 'marine_hours'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated privileges on marine_hours');
select table_privs_are('public'::name, 'marine_hours'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on marine_hours');

select policies_are('public'::name, 'marine_hours'::name, array['marine_hours_read']::name[], 'marine_hours policies');

-- Constraints (postgres).
select throws_ok($$insert into public.marine_hours (spot_id, valid_at, wave_height_m, fetched_at) values ('pgtap-spot', '2026-10-14T13:00:00Z', -0.1, now())$$, '23514', null, 'wave height >= 0');
select throws_ok($$insert into public.marine_hours (spot_id, valid_at, wave_period_s, fetched_at) values ('pgtap-spot', '2026-10-14T13:00:00Z', -1, now())$$, '23514', null, 'wave period >= 0');
select throws_ok($$insert into public.marine_hours (spot_id, valid_at, wave_dir_deg, fetched_at) values ('pgtap-spot', '2026-10-14T13:00:00Z', 360, now())$$, '23514', null, 'wave direction < 360');
select throws_ok($$insert into public.marine_hours (spot_id, valid_at, fetched_at) values ('pgtap-spot', '2026-10-14T13:00:00Z', now())$$, '23514', null, 'at least one value');
select throws_ok($$insert into public.marine_hours (spot_id, valid_at, wave_height_m, fetched_at) values ('pgtap-unknown', '2026-10-14T13:00:00Z', 1, now())$$, '23503', null, 'spot must exist');
select lives_ok($$insert into public.marine_hours (spot_id, valid_at, wave_height_m, fetched_at) values ('pgtap-spot', '2026-10-14T14:00:00Z', 0.8, now())$$, 'row with only a height');

-- anon.
set local role anon;
select results_eq($$select count(*)::int from public.marine_hours where spot_id = 'pgtap-spot'$$, array[2], 'anon reads marine_hours');
select throws_ok($$insert into public.marine_hours (spot_id, valid_at, wave_height_m, fetched_at) values ('pgtap-spot', '2026-10-14T15:00:00Z', 1, now())$$, '42501', null, 'anon cannot insert');
select throws_ok($$update public.marine_hours set wave_height_m = 1$$, '42501', null, 'anon cannot update');
select throws_ok($$delete from public.marine_hours$$, '42501', null, 'anon cannot delete');
reset role;

-- authenticated.
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select results_eq($$select count(*)::int from public.marine_hours where spot_id = 'pgtap-spot'$$, array[2], 'authenticated reads marine_hours');
select throws_ok($$insert into public.marine_hours (spot_id, valid_at, wave_height_m, fetched_at) values ('pgtap-spot', '2026-10-14T15:00:00Z', 1, now())$$, '42501', null, 'authenticated cannot insert');
reset role;

-- Cascade.
delete from public.spots where id = 'pgtap-spot';
select is_empty($$select 1 from public.marine_hours where spot_id = 'pgtap-spot'$$, 'marine_hours rows are removed with the spot');

select * from finish();
rollback;
