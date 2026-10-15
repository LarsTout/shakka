-- Sessions and RSVPs (WP-19): shape, privileges, functions, constraints, RLS and cascades.
begin;
create extension if not exists pgtap with schema extensions;

select plan(112);

-- Fixture (postgres): users A and B, one spot, a session of B with one RSVP, and an old session of A.
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'a@example.test'),
  ('22222222-2222-2222-2222-222222222222', 'b@example.test');
insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot');
insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values
  ('b0000000-0000-4000-8000-000000000001', 'pgtap-b-session-01', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob',
   now() + interval '1 day', now() + interval '1 day 3 hours');
insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, created_at) values
  ('a0000000-0000-4000-8000-000000000001', 'pgtap-a-old-00001', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Anna',
   now() - interval '26 hours', now() - interval '25 hours', now() - interval '25 hours');
insert into public.rsvps (id, session_id, first_name, ride, seats_offered, edit_token_hash) values
  ('c0000000-0000-4000-8000-000000000001', 'b0000000-0000-4000-8000-000000000001', 'Eva', 'offers_ride', 2,
   encode(sha256(convert_to(repeat('D', 43), 'UTF8')), 'hex'));

-- Shape (1-11).
select columns_are('public'::name, 'sessions'::name, array['id', 'slug', 'spot_id', 'organizer_id', 'organizer_name', 'starts_at', 'ends_at', 'note', 'seats_free', 'departure_point', 'tikkie_url', 'cancelled_at', 'recent_rsvp_creates', 'created_at', 'updated_at']::name[], 'sessions columns');
select columns_are('public'::name, 'rsvps'::name, array['id', 'session_id', 'first_name', 'ride', 'seats_offered', 'rides_with', 'edit_token_hash', 'created_at', 'updated_at']::name[], 'rsvps columns');
select col_is_pk('public'::name, 'sessions'::name, array['id']::name[], 'sessions primary key');
select col_is_pk('public'::name, 'rsvps'::name, array['id']::name[], 'rsvps primary key');
select has_index('public'::name, 'sessions'::name, 'sessions_organizer_created_idx'::name, 'sessions_organizer_created_idx exists');
select has_index('public'::name, 'sessions'::name, 'sessions_ends_at_idx'::name, 'sessions_ends_at_idx exists');
select has_index('public'::name, 'sessions'::name, 'sessions_spot_id_idx'::name, 'sessions_spot_id_idx exists');
select has_index('public'::name, 'rsvps'::name, 'rsvps_rides_with_idx'::name, 'rsvps_rides_with_idx exists');
select has_trigger('public'::name, 'sessions'::name, 'sessions_prepare_insert'::name, 'sessions_prepare_insert exists');
select has_trigger('public'::name, 'sessions'::name, 'sessions_set_updated_at'::name, 'sessions_set_updated_at exists');
select has_trigger('public'::name, 'rsvps'::name, 'rsvps_set_updated_at'::name, 'rsvps_set_updated_at exists');

-- Privileges (12-34).
select table_privs_are('public'::name, 'sessions'::name, 'anon'::name, array[]::name[], 'anon has no privileges on sessions');
select table_privs_are('public'::name, 'sessions'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated may only select on table level');
select table_privs_are('public'::name, 'sessions'::name, 'service_role'::name, array[]::name[], 'service_role has no privileges on sessions');
select table_privs_are('public'::name, 'rsvps'::name, 'anon'::name, array[]::name[], 'anon has no privileges on rsvps');
select table_privs_are('public'::name, 'rsvps'::name, 'authenticated'::name, array[]::name[], 'authenticated has no privileges on rsvps');
select table_privs_are('public'::name, 'rsvps'::name, 'service_role'::name, array[]::name[], 'service_role has no privileges on rsvps');
select column_privs_are('public'::name, 'sessions'::name, 'id'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated column privileges on sessions.id');
select column_privs_are('public'::name, 'sessions'::name, 'slug'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated column privileges on sessions.slug');
select column_privs_are('public'::name, 'sessions'::name, 'spot_id'::name, 'authenticated'::name, array['INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated column privileges on sessions.spot_id');
select column_privs_are('public'::name, 'sessions'::name, 'organizer_id'::name, 'authenticated'::name, array['INSERT', 'SELECT']::name[], 'authenticated column privileges on sessions.organizer_id');
select column_privs_are('public'::name, 'sessions'::name, 'organizer_name'::name, 'authenticated'::name, array['INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated column privileges on sessions.organizer_name');
select column_privs_are('public'::name, 'sessions'::name, 'starts_at'::name, 'authenticated'::name, array['INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated column privileges on sessions.starts_at');
select column_privs_are('public'::name, 'sessions'::name, 'ends_at'::name, 'authenticated'::name, array['INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated column privileges on sessions.ends_at');
select column_privs_are('public'::name, 'sessions'::name, 'note'::name, 'authenticated'::name, array['INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated column privileges on sessions.note');
select column_privs_are('public'::name, 'sessions'::name, 'seats_free'::name, 'authenticated'::name, array['INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated column privileges on sessions.seats_free');
select column_privs_are('public'::name, 'sessions'::name, 'departure_point'::name, 'authenticated'::name, array['INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated column privileges on sessions.departure_point');
select column_privs_are('public'::name, 'sessions'::name, 'tikkie_url'::name, 'authenticated'::name, array['INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated column privileges on sessions.tikkie_url');
select column_privs_are('public'::name, 'sessions'::name, 'cancelled_at'::name, 'authenticated'::name, array['SELECT', 'UPDATE']::name[], 'authenticated column privileges on sessions.cancelled_at');
select column_privs_are('public'::name, 'sessions'::name, 'recent_rsvp_creates'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated column privileges on sessions.recent_rsvp_creates');
select column_privs_are('public'::name, 'sessions'::name, 'created_at'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated column privileges on sessions.created_at');
select column_privs_are('public'::name, 'sessions'::name, 'updated_at'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated column privileges on sessions.updated_at');
select policies_are('public'::name, 'sessions'::name, array['sessions_select_own', 'sessions_insert_own', 'sessions_update_own']::name[], 'sessions policies');
select policies_are('public'::name, 'rsvps'::name, array[]::name[], 'rsvps has no policies');

-- Functions (35-44).
select has_function('public'::name, 'get_public_session'::name, array['text']::name[], 'get_public_session exists');
select has_function('public'::name, 'rsvp_create'::name, array['text','text','text','integer']::name[], 'rsvp_create exists');
select has_function('public'::name, 'rsvp_update'::name, array['text','text','text','integer','uuid']::name[], 'rsvp_update exists');
select has_function('public'::name, 'rsvp_delete'::name, array['text']::name[], 'rsvp_delete exists');
select has_function('public'::name, 'purge_expired_sessions'::name, array['timestamp with time zone']::name[], 'purge_expired_sessions exists');
select set_eq($$select p.proname::text from pg_proc p where p.pronamespace = 'public'::regnamespace and has_function_privilege('anon', p.oid, 'EXECUTE')$$, $$values ('get_public_session'), ('rsvp_create'), ('rsvp_update'), ('rsvp_delete')$$, 'anon can execute exactly the four public RPCs');
select set_eq($$select p.proname::text from pg_proc p where p.pronamespace = 'public'::regnamespace and has_function_privilege('authenticated', p.oid, 'EXECUTE')$$, $$values ('get_public_session'), ('rsvp_create'), ('rsvp_update'), ('rsvp_delete')$$, 'authenticated can execute exactly the four public RPCs');
select set_eq($$select p.proname::text from pg_proc p where p.pronamespace = 'public'::regnamespace and has_function_privilege('service_role', p.oid, 'EXECUTE')$$, $$values ('purge_expired_sessions')$$, 'service_role can execute exactly purge_expired_sessions');
select set_eq($$select p.proname::text from pg_proc p where p.pronamespace = 'public'::regnamespace and p.prosecdef$$, $$values ('handle_new_user'), ('get_public_session'), ('rsvp_create'), ('rsvp_update'), ('rsvp_delete'), ('purge_expired_sessions')$$, 'security definer functions in public');
select is_empty($$select p.proname from pg_proc p where p.pronamespace = 'public'::regnamespace and p.prosecdef and not coalesce(p.proconfig @> array['search_path=""'], false)$$, 'every security definer function pins search_path');

-- Constraints on sessions (45-61), as postgres.
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', '', now() + interval '1 day', now() + interval '1 day 3 hours')$$, '23514', null, 'organizer_name must not be empty');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', repeat('x', 31), now() + interval '1 day', now() + interval '1 day 3 hours')$$, '23514', null, 'organizer_name has at most 30 characters');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', ' Lars', now() + interval '1 day', now() + interval '1 day 3 hours')$$, '23514', null, 'organizer_name must be trimmed');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', E'La\nrs', now() + interval '1 day', now() + interval '1 day 3 hours')$$, '23514', null, 'organizer_name has no control characters');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day')$$, '23514', null, 'ends_at must be after starts_at');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 17 hours')$$, '23514', null, 'a session lasts at most 16 hours');
select lives_ok($$insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('b0000000-0000-4000-8000-000000000016', 'pgtap-16h-000001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 16 hours')$$, 'a session of exactly 16 hours is accepted');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, note) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours', repeat('x', 281))$$, '23514', null, 'note has at most 280 characters');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, seats_free) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours', 9)$$, '23514', null, 'seats_free <= 8');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, seats_free) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours', -1)$$, '23514', null, 'seats_free >= 0');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, departure_point) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours', repeat('x', 81))$$, '23514', null, 'departure_point has at most 80 characters');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, tikkie_url) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours', 'http://tikkie.me/pay/x')$$, '23514', null, 'tikkie_url must be https');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, tikkie_url) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours', 'https://tikkie.me/pay/a b')$$, '23514', null, 'tikkie_url has no whitespace');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, tikkie_url) values ('pgtap-check-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours', 'https://' || repeat('a', 193))$$, '23514', null, 'tikkie_url has at most 200 characters');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('short', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours')$$, '23514', null, 'slug has at least 10 characters');
select throws_ok($$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('pgtap-check-0001', 'pgtap-unknown', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours')$$, '23503', null, 'spot must exist');
select lives_ok($$insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, tikkie_url) values ('b0000000-0000-4000-8000-000000000017', 'pgtap-tikkie-0001', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours', 'https://tikkie.me/pay/abc')$$, 'a valid https tikkie_url is accepted');

-- Constraints on rsvps (62-71), as postgres.
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash) values ('b0000000-0000-4000-8000-000000000001', '', 'own', encode(sha256(convert_to('t1', 'UTF8')), 'hex'))$$, '23514', null, 'first_name must not be empty');
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash) values ('b0000000-0000-4000-8000-000000000001', repeat('x', 31), 'own', encode(sha256(convert_to('t2', 'UTF8')), 'hex'))$$, '23514', null, 'first_name has at most 30 characters');
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash) values ('b0000000-0000-4000-8000-000000000001', 'Eva', 'walk', encode(sha256(convert_to('t3', 'UTF8')), 'hex'))$$, '23514', null, 'ride enum');
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash, seats_offered) values ('b0000000-0000-4000-8000-000000000001', 'Eva', 'own', encode(sha256(convert_to('t4', 'UTF8')), 'hex'), 2)$$, '23514', null, 'seats only with offers_ride');
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash, seats_offered) values ('b0000000-0000-4000-8000-000000000001', 'Eva', 'offers_ride', encode(sha256(convert_to('t5', 'UTF8')), 'hex'), 9)$$, '23514', null, 'seats_offered <= 8');
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash) values ('b0000000-0000-4000-8000-000000000001', 'Eva', 'own', 'abc')$$, '23514', null, 'edit_token_hash is a sha256 hex string');
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash, id, rides_with) values ('b0000000-0000-4000-8000-000000000001', 'Eva', 'needs_ride', encode(sha256(convert_to('t7', 'UTF8')), 'hex'), 'c0000000-0000-4000-8000-000000000068', 'c0000000-0000-4000-8000-000000000068')$$, '23514', null, 'rides_with cannot point to itself');
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash, rides_with) values ('b0000000-0000-4000-8000-000000000001', 'Eva', 'own', encode(sha256(convert_to('t8', 'UTF8')), 'hex'), 'c0000000-0000-4000-8000-000000000001')$$, '23514', null, 'rides_with only with needs_ride');
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash, rides_with) values ('b0000000-0000-4000-8000-000000000016', 'Eva', 'needs_ride', encode(sha256(convert_to('t9', 'UTF8')), 'hex'), 'c0000000-0000-4000-8000-000000000001')$$, '23503', null, 'rides_with must point to an RSVP of the same session');
select throws_ok($$insert into public.rsvps (session_id, first_name, ride, edit_token_hash) values ('b0000000-0000-4000-8000-000000000001', 'Eva', 'own', encode(sha256(convert_to(repeat('D', 43), 'UTF8')), 'hex'))$$, '23505', null, 'edit_token_hash is unique');

-- Slug generation (72-73), as postgres.
select lives_ok($$insert into public.sessions (id, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('b0000000-0000-4000-8000-000000000018', 'pgtap-spot', '22222222-2222-2222-2222-222222222222', 'Bob', now() + interval '1 day', now() + interval '1 day 3 hours')$$, 'a session without slug gets one');
select ok((select slug ~ '^[A-Za-z0-9_-]{22}$' from public.sessions where id = 'b0000000-0000-4000-8000-000000000018'), 'generated slug is 22 base64url characters');

-- A as authenticated (74-92).
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select lives_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at, note) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours', 'pgtap-a-1')$$, 'A creates a session without slug and organizer_id');
select is_empty($$select 1 from public.sessions where organizer_id = '22222222-2222-2222-2222-222222222222'$$, 'A sees no sessions of B');
select ok((select slug ~ '^[A-Za-z0-9_-]{10,}$' from public.sessions where note = 'pgtap-a-1'), 'the slug is generated server-side');
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at, organizer_id) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours', '22222222-2222-2222-2222-222222222222')$$, '42501', null, 'A cannot create a session for B');
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at, slug) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours', 'pgtap-own-slug-1')$$, '42501', null, 'A cannot choose the slug');
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at, cancelled_at) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours', now())$$, '42501', null, 'A cannot set cancelled_at on insert');
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at, recent_rsvp_creates) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours', '{}')$$, '42501', null, 'A cannot set recent_rsvp_creates on insert');
select lives_ok($$update public.sessions set organizer_name = 'Hacked' where id = 'b0000000-0000-4000-8000-000000000001'$$, 'A updating a session of B touches 0 rows');
select lives_ok($$update public.sessions set cancelled_at = now() where note = 'pgtap-a-1'$$, 'A cancels an own session');
select throws_ok($$update public.sessions set organizer_id = '22222222-2222-2222-2222-222222222222' where note = 'pgtap-a-1'$$, '42501', null, 'A cannot change organizer_id');
select throws_ok($$update public.sessions set slug = 'pgtap-new-slug-01' where note = 'pgtap-a-1'$$, '42501', null, 'A cannot change the slug');
select throws_ok($$update public.sessions set recent_rsvp_creates = '{}' where note = 'pgtap-a-1'$$, '42501', null, 'A cannot change recent_rsvp_creates');
select throws_ok($$delete from public.sessions where note = 'pgtap-a-1'$$, '42501', null, 'A cannot delete sessions');
select throws_ok('select 1 from public.rsvps', '42501', null, 'authenticated cannot select rsvps');
select throws_ok($$insert into public.rsvps (session_id, first_name, edit_token_hash) values ('b0000000-0000-4000-8000-000000000001', 'x', repeat('a', 64))$$, '42501', null, 'authenticated cannot insert rsvps');
select throws_ok($$update public.rsvps set first_name = 'x'$$, '42501', null, 'authenticated cannot update rsvps');
select throws_ok($$delete from public.rsvps$$, '42501', null, 'authenticated cannot delete rsvps');
select lives_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at) select 'pgtap-spot', 'Anna', now() + interval '2 days', now() + interval '2 days 2 hours' from generate_series(1, 9)$$, 'A reaches 10 sessions in 24 hours (the 25 hour old one does not count)');
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours')$$, 'PT400', 'rate_limited', 'the 11th session within 24 hours is rate limited');
-- Extra (N-5): created_at and id are not writable, so the limit cannot be dodged.
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at, created_at) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours', now() - interval '3 days')$$, '42501', null, 'A cannot set created_at on insert');
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at, id) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours', gen_random_uuid())$$, '42501', null, 'A cannot set id on insert');
reset role;

-- As postgres (93-94).
select is((select organizer_name from public.sessions where id = 'b0000000-0000-4000-8000-000000000001'), 'Bob', 'the session of B is unchanged');
select ok((select cancelled_at is not null from public.sessions where note = 'pgtap-a-1'), 'the session of A is cancelled');

-- anon (95-102).
set local role anon;
select throws_ok('select 1 from public.sessions', '42501', null, 'anon cannot select sessions');
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at) values ('pgtap-spot', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours')$$, '42501', null, 'anon cannot insert sessions');
select throws_ok($$update public.sessions set organizer_name = 'x'$$, '42501', null, 'anon cannot update sessions');
select throws_ok('delete from public.sessions', '42501', null, 'anon cannot delete sessions');
select throws_ok('select 1 from public.rsvps', '42501', null, 'anon cannot select rsvps');
select throws_ok($$insert into public.rsvps (session_id, first_name, edit_token_hash) values ('b0000000-0000-4000-8000-000000000001', 'x', repeat('a', 64))$$, '42501', null, 'anon cannot insert rsvps');
select throws_ok($$update public.rsvps set first_name = 'x'$$, '42501', null, 'anon cannot update rsvps');
select throws_ok('delete from public.rsvps', '42501', null, 'anon cannot delete rsvps');
reset role;

-- service_role (103-104).
set local role service_role;
select throws_ok('select 1 from public.sessions', '42501', null, 'service_role cannot select sessions');
select throws_ok('select 1 from public.rsvps', '42501', null, 'service_role cannot select rsvps');
reset role;

-- Extra (N-5): a multi-row insert over the limit, as B (B already has 4 sessions from the fixture).
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"22222222-2222-2222-2222-222222222222","role":"authenticated"}', true);
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at) select 'pgtap-spot', 'Bob', now() + interval '3 days', now() + interval '3 days 2 hours' from generate_series(1, 7)$$, 'PT400', 'rate_limited', 'a multi-row insert crossing the limit is rejected as a whole');
select lives_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at) select 'pgtap-spot', 'Bob', now() + interval '3 days', now() + interval '3 days 2 hours' from generate_series(1, 6)$$, 'a multi-row insert up to the limit is accepted');
select throws_ok($$insert into public.sessions (spot_id, organizer_name, starts_at, ends_at) values ('pgtap-spot', 'Bob', now() + interval '3 days', now() + interval '3 days 2 hours')$$, 'PT400', 'rate_limited', 'B is now at the limit as well');
reset role;

-- Cascades (105-107), as postgres.
delete from public.sessions where id = 'b0000000-0000-4000-8000-000000000001';
select is_empty($$select 1 from public.rsvps where session_id = 'b0000000-0000-4000-8000-000000000001'$$, 'deleting a session removes its rsvps');
delete from auth.users where id = '11111111-1111-1111-1111-111111111111';
select is_empty($$select 1 from public.sessions where organizer_id = '11111111-1111-1111-1111-111111111111'$$, 'deleting a user removes the sessions');
select throws_ok($$delete from public.spots where id = 'pgtap-spot'$$, '23001', null, 'a spot with sessions cannot be deleted (restrict)');

select * from finish();
rollback;
