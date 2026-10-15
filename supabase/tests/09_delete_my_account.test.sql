-- delete_my_account (WP-23): privileges, authentication, and the cascade through every table of the account.
begin;
create extension if not exists pgtap with schema extensions;

select plan(23);

-- Fixture (postgres): users A and B (profiles come from the trigger), one spot, and per user a favorite,
-- an alert rule, an alert_state row, a push subscription and a session. Plus three RSVPs.
insert into auth.users (id, email) values
  ('aaaaaaaa-0000-4000-8000-00000000000a', 'a@example.test'),
  ('bbbbbbbb-0000-4000-8000-00000000000b', 'b@example.test');
insert into public.spots (id, name) values ('pgtap-del-spot', 'Pgtap Delete Spot');
insert into public.favorites (user_id, spot_id) values
  ('aaaaaaaa-0000-4000-8000-00000000000a', 'pgtap-del-spot'),
  ('bbbbbbbb-0000-4000-8000-00000000000b', 'pgtap-del-spot');
insert into public.alert_rules (user_id, spot_id, min_kn) values
  ('aaaaaaaa-0000-4000-8000-00000000000a', 'pgtap-del-spot', 12),
  ('bbbbbbbb-0000-4000-8000-00000000000b', 'pgtap-del-spot', 20);
insert into public.alert_state (user_id, spot_id, window_start, window_end, status, snapshot) values
  ('aaaaaaaa-0000-4000-8000-00000000000a', 'pgtap-del-spot', '2026-10-14T10:00:00Z', '2026-10-14T14:00:00Z', 'active', '{}'),
  ('bbbbbbbb-0000-4000-8000-00000000000b', 'pgtap-del-spot', '2026-10-14T10:00:00Z', '2026-10-14T14:00:00Z', 'active', '{}');
insert into public.push_subscriptions (user_id, endpoint, p256dh, auth) values
  ('aaaaaaaa-0000-4000-8000-00000000000a', 'https://push.example.test/a', 'BAAA', 'AAAA'),
  ('bbbbbbbb-0000-4000-8000-00000000000b', 'https://push.example.test/b', 'BAAA', 'AAAA');
insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values
  ('5a000000-0000-4000-8000-00000000000a', 'pgtap-del-sa-01', 'pgtap-del-spot', 'aaaaaaaa-0000-4000-8000-00000000000a', 'Anna', '2026-10-20T10:00:00Z', '2026-10-20T14:00:00Z'),
  ('5b000000-0000-4000-8000-00000000000b', 'pgtap-del-sb-01', 'pgtap-del-spot', 'bbbbbbbb-0000-4000-8000-00000000000b', 'Bram', '2026-10-20T10:00:00Z', '2026-10-20T14:00:00Z');
insert into public.rsvps (session_id, first_name, ride, edit_token_hash) values
  ('5a000000-0000-4000-8000-00000000000a', 'Bram', 'own', repeat('a', 64)),
  ('5b000000-0000-4000-8000-00000000000b', 'Anna', 'own', repeat('b', 64)),
  ('5b000000-0000-4000-8000-00000000000b', 'Cas', 'own', repeat('c', 64));

-- Shape and privileges (1-7).
select has_function('public'::name, 'delete_my_account'::name, '{}'::name[], 'delete_my_account exists');
select function_returns('public'::name, 'delete_my_account'::name, '{}'::name[], 'void', 'delete_my_account returns void');
select is_definer('public'::name, 'delete_my_account'::name, '{}'::name[], 'delete_my_account is security definer');
select ok(
  (select p.proconfig @> array['search_path=""'] from pg_proc p where p.pronamespace = 'public'::regnamespace and p.proname = 'delete_my_account'),
  'delete_my_account pins search_path'
);
select function_privs_are('public'::name, 'delete_my_account'::name, '{}'::name[], 'anon'::name, '{}'::name[], 'anon cannot execute delete_my_account');
select function_privs_are('public'::name, 'delete_my_account'::name, '{}'::name[], 'authenticated'::name, array['EXECUTE'], 'authenticated can execute delete_my_account');
select function_privs_are('public'::name, 'delete_my_account'::name, '{}'::name[], 'service_role'::name, '{}'::name[], 'service_role cannot execute delete_my_account');

-- Not signed in (8-9).
set local role anon;
select throws_ok('select public.delete_my_account()', '42501', null, 'anon is refused');
reset role;

set local role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated"}', true);
select throws_ok('select public.delete_my_account()', 'PT401', 'not_authenticated', 'a token without sub is refused');
reset role;

-- User A deletes the account (10).
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-4000-8000-00000000000a","role":"authenticated"}', true);
select lives_ok('select public.delete_my_account()', 'A deletes the own account');
reset role;

-- Everything of A is gone (11-18).
select is_empty($$select 1 from auth.users where id = 'aaaaaaaa-0000-4000-8000-00000000000a'$$, 'auth.users row of A is gone');
select is_empty($$select 1 from public.profiles where user_id = 'aaaaaaaa-0000-4000-8000-00000000000a'$$, 'profile of A is gone');
select is_empty($$select 1 from public.favorites where user_id = 'aaaaaaaa-0000-4000-8000-00000000000a'$$, 'favorites of A are gone');
select is_empty($$select 1 from public.alert_rules where user_id = 'aaaaaaaa-0000-4000-8000-00000000000a'$$, 'alert_rules of A are gone');
select is_empty($$select 1 from public.alert_state where user_id = 'aaaaaaaa-0000-4000-8000-00000000000a'$$, 'alert_state of A is gone');
select is_empty($$select 1 from public.push_subscriptions where user_id = 'aaaaaaaa-0000-4000-8000-00000000000a'$$, 'push_subscriptions of A are gone');
select is_empty($$select 1 from public.sessions where organizer_id = 'aaaaaaaa-0000-4000-8000-00000000000a'$$, 'sessions of A are gone');
select is_empty($$select 1 from public.rsvps where session_id = '5a000000-0000-4000-8000-00000000000a'$$, 'RSVPs on the sessions of A are gone');

-- B is untouched (19-21).
select isnt_empty($$select 1 from auth.users where id = 'bbbbbbbb-0000-4000-8000-00000000000b'$$, 'auth.users row of B remains');
select results_eq(
  $$select
      (select count(*) from public.profiles where user_id = 'bbbbbbbb-0000-4000-8000-00000000000b')::int,
      (select count(*) from public.favorites where user_id = 'bbbbbbbb-0000-4000-8000-00000000000b')::int,
      (select count(*) from public.alert_rules where user_id = 'bbbbbbbb-0000-4000-8000-00000000000b')::int,
      (select count(*) from public.alert_state where user_id = 'bbbbbbbb-0000-4000-8000-00000000000b')::int,
      (select count(*) from public.push_subscriptions where user_id = 'bbbbbbbb-0000-4000-8000-00000000000b')::int,
      (select count(*) from public.sessions where organizer_id = 'bbbbbbbb-0000-4000-8000-00000000000b')::int$$,
  $$values (1, 1, 1, 1, 1, 1)$$,
  'B keeps profile, favorite, rule, state, subscription and session'
);
select results_eq(
  $$select count(*)::int from public.rsvps where session_id = '5b000000-0000-4000-8000-00000000000b'$$,
  $$values (2)$$,
  'the anonymous RSVP of A on the session of B remains'
);

-- A second call by the already deleted user is a no-op (22-23).
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-4000-8000-00000000000a","role":"authenticated"}', true);
select lives_ok('select public.delete_my_account()', 'a second call by A is a no-op');
reset role;
select isnt_empty($$select 1 from auth.users where id = 'bbbbbbbb-0000-4000-8000-00000000000b'$$, 'B still exists after the second call');

select * from finish();
rollback;
