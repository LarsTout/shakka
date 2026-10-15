-- push_subscriptions (WP-17): shape, privileges, constraints, RLS, cascade.
begin;
create extension if not exists pgtap with schema extensions;

select plan(32);

-- Fixture (postgres): two auth users and one subscription for B.
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'a@example.test'),
  ('22222222-2222-2222-2222-222222222222', 'b@example.test');
insert into public.push_subscriptions (user_id, endpoint, p256dh, auth)
  values ('22222222-2222-2222-2222-222222222222', 'https://push.example.test/b1', 'BBBB', 'bbbb');

select columns_are('public'::name, 'push_subscriptions'::name, array['id', 'user_id', 'endpoint', 'p256dh', 'auth', 'created_at', 'last_success_at']::name[], 'push_subscriptions columns');
select col_is_pk('public'::name, 'push_subscriptions'::name, array['id']::name[], 'push_subscriptions primary key');
select has_index('public'::name, 'push_subscriptions'::name, 'push_subscriptions_user_id_idx'::name, 'index on user_id');

select table_privs_are('public'::name, 'push_subscriptions'::name, 'anon'::name, array[]::name[], 'anon has no privileges on push_subscriptions');
select table_privs_are('public'::name, 'push_subscriptions'::name, 'authenticated'::name, array['DELETE', 'SELECT']::name[], 'authenticated privileges on push_subscriptions');
select table_privs_are('public'::name, 'push_subscriptions'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on push_subscriptions');

select column_privs_are('public'::name, 'push_subscriptions'::name, 'user_id'::name, 'authenticated'::name, array['INSERT', 'SELECT']::name[], 'authenticated column privileges on user_id');
select column_privs_are('public'::name, 'push_subscriptions'::name, 'endpoint'::name, 'authenticated'::name, array['INSERT', 'SELECT']::name[], 'authenticated column privileges on endpoint');
select column_privs_are('public'::name, 'push_subscriptions'::name, 'p256dh'::name, 'authenticated'::name, array['INSERT', 'SELECT']::name[], 'authenticated column privileges on p256dh');
select column_privs_are('public'::name, 'push_subscriptions'::name, 'auth'::name, 'authenticated'::name, array['INSERT', 'SELECT']::name[], 'authenticated column privileges on auth');
select column_privs_are('public'::name, 'push_subscriptions'::name, 'id'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated column privileges on id');
select column_privs_are('public'::name, 'push_subscriptions'::name, 'created_at'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated column privileges on created_at');
select column_privs_are('public'::name, 'push_subscriptions'::name, 'last_success_at'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated column privileges on last_success_at');

select policies_are('public'::name, 'push_subscriptions'::name, array['push_subscriptions_select_own', 'push_subscriptions_insert_own', 'push_subscriptions_delete_own']::name[], 'push_subscriptions policies');

-- Constraints (postgres; user_id given explicitly so NOT NULL does not fire before the CHECK).
select throws_ok($$insert into public.push_subscriptions (user_id, endpoint, p256dh, auth) values ('11111111-1111-1111-1111-111111111111', 'http://push.example.test/x', 'AAAA', 'aaaa')$$, '23514', null, 'endpoint must be https');
select throws_ok($$insert into public.push_subscriptions (user_id, endpoint, p256dh, auth) values ('11111111-1111-1111-1111-111111111111', 'https://push.example.test/a b', 'AAAA', 'aaaa')$$, '23514', null, 'endpoint has no whitespace');
select throws_ok($$insert into public.push_subscriptions (user_id, endpoint, p256dh, auth) values ('11111111-1111-1111-1111-111111111111', 'https://push.example.test/a2', 'ab cd', 'aaaa')$$, '23514', null, 'p256dh is base64url');
select throws_ok($$insert into public.push_subscriptions (user_id, endpoint, p256dh, auth) values ('11111111-1111-1111-1111-111111111111', 'https://push.example.test/a3', 'AAAA', 'a+b')$$, '23514', null, 'auth is base64url');
select throws_ok($$insert into public.push_subscriptions (user_id, endpoint, p256dh, auth) values ('11111111-1111-1111-1111-111111111111', 'https://push.example.test/b1', 'AAAA', 'aaaa')$$, '23505', null, 'endpoint is unique');

-- A as authenticated.
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);

select lives_ok($$insert into public.push_subscriptions (endpoint, p256dh, auth) values ('https://push.example.test/a1', 'AAAA', 'aaaa')$$, 'A adds a subscription without user_id');
select results_eq('select user_id from public.push_subscriptions', $$values ('11111111-1111-1111-1111-111111111111'::uuid)$$, 'A sees only own subscription, user_id from auth.uid()');
select throws_ok($$insert into public.push_subscriptions (user_id, endpoint, p256dh, auth) values ('22222222-2222-2222-2222-222222222222', 'https://push.example.test/a4', 'AAAA', 'aaaa')$$, '42501', null, 'A cannot add a subscription for B');
select throws_ok($$insert into public.push_subscriptions (endpoint, p256dh, auth, last_success_at) values ('https://push.example.test/a5', 'AAAA', 'aaaa', now())$$, '42501', null, 'A cannot set last_success_at');
select throws_ok($$update public.push_subscriptions set last_success_at = now()$$, '42501', null, 'A cannot update');
select lives_ok($$delete from public.push_subscriptions where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A deleting subscriptions of B touches 0 rows');
select lives_ok($$delete from public.push_subscriptions where endpoint = 'https://push.example.test/a1'$$, 'A deletes own subscription');

reset role;

select isnt_empty($$select 1 from public.push_subscriptions where user_id = '22222222-2222-2222-2222-222222222222'$$, 'subscription of B still exists');
select is_empty($$select 1 from public.push_subscriptions where endpoint = 'https://push.example.test/a1'$$, 'subscription a1 is gone');

-- anon.
set local role anon;
select throws_ok('select 1 from public.push_subscriptions', '42501', null, 'anon cannot select');
select throws_ok($$insert into public.push_subscriptions (user_id, endpoint, p256dh, auth) values ('11111111-1111-1111-1111-111111111111', 'https://push.example.test/a6', 'AAAA', 'aaaa')$$, '42501', null, 'anon cannot insert');
reset role;

-- service_role.
set local role service_role;
select lives_ok($$update public.push_subscriptions set last_success_at = now() where user_id = '22222222-2222-2222-2222-222222222222'$$, 'service_role updates last_success_at');
reset role;

-- Cascade.
delete from auth.users where id = '22222222-2222-2222-2222-222222222222';
select is_empty($$select 1 from public.push_subscriptions where user_id = '22222222-2222-2222-2222-222222222222'$$, 'deleting a user removes the subscriptions');

select * from finish();
rollback;
