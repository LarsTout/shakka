-- User A versus user B, telegram_chat_id protection, profile trigger, dir_classes, cascades, service_role.
-- The order of the sections is binding: later sections depend on the state left by earlier ones.
begin;
create extension if not exists pgtap with schema extensions;

select plan(42);

-- Step 0 fixture (postgres): two auth users; profiles are created by the trigger.
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'a@example.test'),
  ('22222222-2222-2222-2222-222222222222', 'b@example.test');

-- Section (f): profiles trigger.
select results_eq(
  $$select count(*)::int from public.profiles where user_id in ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222')$$,
  array[2],
  'a profile exists for every new auth user'
);
select is(
  (select quiver_m2 from public.profiles where user_id = '11111111-1111-1111-1111-111111111111'),
  '{}'::real[],
  'new profile has an empty quiver'
);

-- Fixture continued (postgres).
insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot'), ('pgtap-spot-2', 'Pgtap Spot 2');
insert into public.favorites (user_id, spot_id) values
  ('11111111-1111-1111-1111-111111111111', 'pgtap-spot'),
  ('22222222-2222-2222-2222-222222222222', 'pgtap-spot');
insert into public.alert_rules (user_id, spot_id, min_kn) values
  ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', 12),
  ('22222222-2222-2222-2222-222222222222', 'pgtap-spot', 20);
insert into public.alert_state (user_id, spot_id, window_start, window_end, status, snapshot) values
  ('11111111-1111-1111-1111-111111111111', 'pgtap-spot', '2026-10-14T10:00:00Z', '2026-10-14T14:00:00Z', 'active', '{}'),
  ('22222222-2222-2222-2222-222222222222', 'pgtap-spot', '2026-10-14T10:00:00Z', '2026-10-14T14:00:00Z', 'active', '{}');

-- Section (d): A against B.
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);

select results_eq('select user_id from public.profiles', $$values ('11111111-1111-1111-1111-111111111111'::uuid)$$, 'A sees only own profile');
select results_eq('select user_id from public.favorites', $$values ('11111111-1111-1111-1111-111111111111'::uuid)$$, 'A sees only own favorites');
select results_eq('select user_id from public.alert_rules', $$values ('11111111-1111-1111-1111-111111111111'::uuid)$$, 'A sees only own alert_rules');
select results_eq('select user_id from public.alert_state', $$values ('11111111-1111-1111-1111-111111111111'::uuid)$$, 'A sees only own alert_state');

select is_empty($$select 1 from public.profiles where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A cannot see profile of B');
select is_empty($$select 1 from public.favorites where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A cannot see favorites of B');
select is_empty($$select 1 from public.alert_rules where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A cannot see alert_rules of B');
select is_empty($$select 1 from public.alert_state where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A cannot see alert_state of B');

select lives_ok($$update public.profiles set weight_kg = 99 where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A updating profile of B touches 0 rows');
select lives_ok($$update public.alert_rules set min_kn = 6 where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A updating rule of B touches 0 rows');
select lives_ok($$delete from public.favorites where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A deleting favorite of B touches 0 rows');
select lives_ok($$delete from public.alert_rules where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A deleting rule of B touches 0 rows');

select throws_ok($$insert into public.favorites (user_id, spot_id) values ('22222222-2222-2222-2222-222222222222', 'pgtap-spot-2')$$, '42501', null, 'A cannot insert a favorite for B');
select throws_ok($$insert into public.alert_rules (user_id, spot_id) values ('22222222-2222-2222-2222-222222222222', 'pgtap-spot')$$, '42501', null, 'A cannot insert a rule for B');

reset role;

select is((select weight_kg from public.profiles where user_id = '22222222-2222-2222-2222-222222222222'), null::smallint, 'weight of B is unchanged');
select is((select min_kn from public.alert_rules where user_id = '22222222-2222-2222-2222-222222222222'), 20::smallint, 'rule of B is unchanged');
select isnt_empty($$select 1 from public.favorites where user_id = '22222222-2222-2222-2222-222222222222' and spot_id = 'pgtap-spot'$$, 'favorite of B still exists');
select isnt_empty($$select 1 from public.alert_rules where user_id = '22222222-2222-2222-2222-222222222222' and spot_id = 'pgtap-spot'$$, 'rule of B still exists');

-- Section (e): column privilege and updated_at trigger. Backdate updated_at (now() is constant in a transaction).
alter table public.profiles disable trigger profiles_set_updated_at;
update public.profiles set updated_at = '2000-01-01T00:00:00Z' where user_id = '11111111-1111-1111-1111-111111111111';
alter table public.profiles enable trigger profiles_set_updated_at;

select is(
  (select updated_at from public.profiles where user_id = '11111111-1111-1111-1111-111111111111'),
  '2000-01-01T00:00:00Z'::timestamptz,
  'precondition: updated_at backdated'
);

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);

select throws_ok($$update public.profiles set telegram_chat_id = '123' where user_id = '11111111-1111-1111-1111-111111111111'$$, '42501', null, 'A cannot change telegram_chat_id');
select lives_ok($$update public.profiles set weight_kg = 80 where user_id = '11111111-1111-1111-1111-111111111111'$$, 'A can change weight_kg');

reset role;

select is((select weight_kg from public.profiles where user_id = '11111111-1111-1111-1111-111111111111'), 80::smallint, 'weight of A is updated');
select is((select telegram_chat_id from public.profiles where user_id = '11111111-1111-1111-1111-111111111111'), null::text, 'telegram_chat_id of A is unchanged');
select is(
  (select updated_at from public.profiles where user_id = '11111111-1111-1111-1111-111111111111'),
  now(),
  'updated_at trigger fired during the update by authenticated'
);

-- Section (g): dir_classes. Favorite (A, pgtap-spot-2) has no rule yet.
insert into public.favorites (user_id, spot_id) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot-2');

select throws_ok($$insert into public.alert_rules (user_id, spot_id, dir_classes) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot-2', '{side_offshore}')$$, '23514', null, 'dir_classes rejects side_offshore');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, dir_classes) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot-2', '{offshore}')$$, '23514', null, 'dir_classes rejects offshore');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, dir_classes) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot-2', '{onshore,offshore}')$$, '23514', null, 'dir_classes rejects a mix with offshore');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, dir_classes) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot-2', '{}')$$, '23514', null, 'dir_classes rejects an empty array');
select throws_ok($$insert into public.alert_rules (user_id, spot_id, dir_classes) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot-2', '{onshore,NULL}')$$, '23514', null, 'dir_classes rejects a null element');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select throws_ok($$insert into public.alert_rules (user_id, spot_id, dir_classes) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot-2', '{offshore}')$$, '23514', null, 'dir_classes rejects offshore for authenticated too');
reset role;

select lives_ok($$insert into public.alert_rules (user_id, spot_id, dir_classes) values ('11111111-1111-1111-1111-111111111111', 'pgtap-spot-2', '{onshore,side_onshore,sideshore}')$$, 'dir_classes accepts the ridable classes');

-- service_role extras (before section (h), which removes B).
set local role service_role;

select lives_ok($$insert into public.ingest_runs (started_at, status) values (now(), 'running')$$, 'service_role inserts into ingest_runs without a sequence grant');
select lives_ok($$insert into public.api_usage (day, source, calls, requests) values ('2026-10-14', 'rws', 1, 1)$$, 'service_role inserts into api_usage');
select results_eq(
  'select user_id from public.alert_state order by user_id',
  $$values ('11111111-1111-1111-1111-111111111111'::uuid), ('22222222-2222-2222-2222-222222222222'::uuid)$$,
  'service_role bypasses RLS on alert_state'
);

reset role;

-- Section (h): cascades.
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select lives_ok($$delete from public.favorites where user_id = '11111111-1111-1111-1111-111111111111' and spot_id = 'pgtap-spot'$$, 'A deletes own favorite');
reset role;

select is_empty($$select 1 from public.alert_rules where user_id = '11111111-1111-1111-1111-111111111111' and spot_id = 'pgtap-spot'$$, 'deleting a favorite removes its rule');

delete from auth.users where id = '22222222-2222-2222-2222-222222222222';

select is_empty($$select 1 from public.profiles where user_id = '22222222-2222-2222-2222-222222222222'$$, 'deleting a user removes the profile');
select is_empty($$select 1 from public.favorites where user_id = '22222222-2222-2222-2222-222222222222'$$, 'deleting a user removes favorites');
select is_empty($$select 1 from public.alert_rules where user_id = '22222222-2222-2222-2222-222222222222'$$, 'deleting a user removes alert_rules');
select is_empty($$select 1 from public.alert_state where user_id = '22222222-2222-2222-2222-222222222222'$$, 'deleting a user removes alert_state');

select * from finish();
rollback;
