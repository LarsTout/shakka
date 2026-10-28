-- WP-25: organizer moderation. organizer_delete_rsvp, rsvps_closed_at and the closed-sign-ups behaviour of the public RPCs.
begin;
create extension if not exists pgtap with schema extensions;

select plan(32);

-- Fixture (postgres): users A and B, one spot, a session of A (SA) and one of B (SO), three RSVPs on SA.
insert into auth.users (id, email) values
  ('aaaaaaaa-0000-4000-8000-00000000000a', 'a@example.test'),
  ('bbbbbbbb-0000-4000-8000-00000000000b', 'b@example.test');
insert into public.spots (id, name) values ('pgtap-mod-spot', 'Pgtap Moderation Spot');
insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values
  ('5a000000-0000-4000-8000-00000000000a', 'pgtap-mod-sa-01', 'pgtap-mod-spot', 'aaaaaaaa-0000-4000-8000-00000000000a', 'Anna', now() + interval '1 day', now() + interval '1 day 4 hours'),
  ('5b000000-0000-4000-8000-00000000000b', 'pgtap-mod-so-01', 'pgtap-mod-spot', 'bbbbbbbb-0000-4000-8000-00000000000b', 'Bram', now() + interval '1 day', now() + interval '1 day 4 hours');
insert into public.rsvps (id, session_id, first_name, ride, seats_offered, rides_with, edit_token_hash) values
  ('6a000000-0000-4000-8000-000000000001', '5a000000-0000-4000-8000-00000000000a', 'Eva', 'offers_ride', 2, null, encode(sha256(convert_to(repeat('E', 43), 'UTF8')), 'hex'));
insert into public.rsvps (id, session_id, first_name, ride, seats_offered, rides_with, edit_token_hash) values
  ('6a000000-0000-4000-8000-000000000002', '5a000000-0000-4000-8000-00000000000a', 'Bram', 'needs_ride', null, '6a000000-0000-4000-8000-000000000001', encode(sha256(convert_to(repeat('B', 43), 'UTF8')), 'hex')),
  ('6a000000-0000-4000-8000-000000000003', '5a000000-0000-4000-8000-00000000000a', 'Cas', 'own', null, null, encode(sha256(convert_to(repeat('K', 43), 'UTF8')), 'hex'));

-- Shape and privileges (1-7).
select has_function('public'::name, 'organizer_delete_rsvp'::name, array['uuid']::name[], 'organizer_delete_rsvp exists');
select function_returns('public'::name, 'organizer_delete_rsvp'::name, array['uuid']::name[], 'boolean', 'organizer_delete_rsvp returns boolean');
select is_definer('public'::name, 'organizer_delete_rsvp'::name, array['uuid']::name[], 'organizer_delete_rsvp is security definer');
select ok(
  (select p.proconfig @> array['search_path=""'] from pg_proc p where p.pronamespace = 'public'::regnamespace and p.proname = 'organizer_delete_rsvp'),
  'organizer_delete_rsvp pins search_path'
);
select function_privs_are('public'::name, 'organizer_delete_rsvp'::name, array['uuid']::name[], 'anon'::name, '{}'::name[], 'anon cannot execute organizer_delete_rsvp');
select function_privs_are('public'::name, 'organizer_delete_rsvp'::name, array['uuid']::name[], 'authenticated'::name, array['EXECUTE'], 'authenticated can execute organizer_delete_rsvp');
select function_privs_are('public'::name, 'organizer_delete_rsvp'::name, array['uuid']::name[], 'service_role'::name, '{}'::name[], 'service_role cannot execute organizer_delete_rsvp');

-- Deleting (8-17).
set local role anon;
select throws_ok($$select public.organizer_delete_rsvp('6a000000-0000-4000-8000-000000000001')$$, '42501', null, 'anon is refused');
reset role;

set local role authenticated;
select set_config('request.jwt.claims', '{"role":"authenticated"}', true);
select is(public.organizer_delete_rsvp('6a000000-0000-4000-8000-000000000001'), false, 'a token without sub gives false');
reset role;

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"bbbbbbbb-0000-4000-8000-00000000000b","role":"authenticated"}', true);
select is(public.organizer_delete_rsvp('6a000000-0000-4000-8000-000000000003'), false, 'B cannot delete an RSVP on the session of A');
reset role;
select isnt_empty($$select 1 from public.rsvps where id = '6a000000-0000-4000-8000-000000000003'$$, 'the RSVP of Cas still exists');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-4000-8000-00000000000a","role":"authenticated"}', true);
select is(public.organizer_delete_rsvp('6a000000-0000-4000-8000-0000000000ff'), false, 'an unknown id gives false');
select is(public.organizer_delete_rsvp(null), false, 'null gives false');
select is(public.organizer_delete_rsvp('6a000000-0000-4000-8000-000000000001'), true, 'A deletes the RSVP of Eva');
reset role;
select is_empty($$select 1 from public.rsvps where id = '6a000000-0000-4000-8000-000000000001'$$, 'the RSVP of Eva is gone');
select is((select rides_with from public.rsvps where id = '6a000000-0000-4000-8000-000000000002'), null::uuid, 'the rider of Eva is looking again');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-4000-8000-00000000000a","role":"authenticated"}', true);
select is(public.organizer_delete_rsvp('6a000000-0000-4000-8000-000000000001'), false, 'deleting again gives false');
reset role;

-- Closing (18-22).
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-4000-8000-00000000000a","role":"authenticated"}', true);
select throws_ok(
  $$insert into public.sessions (slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, rsvps_closed_at)
    values ('pgtap-mod-sx-01', 'pgtap-mod-spot', 'aaaaaaaa-0000-4000-8000-00000000000a', 'Anna', now() + interval '1 day', now() + interval '1 day 2 hours', now())$$,
  '42501', null, 'rsvps_closed_at cannot be set on insert'
);
reset role;

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"bbbbbbbb-0000-4000-8000-00000000000b","role":"authenticated"}', true);
select lives_ok($$update public.sessions set rsvps_closed_at = now() where id = '5a000000-0000-4000-8000-00000000000a'$$, 'B updating the session of A does not error');
reset role;
select is((select rsvps_closed_at from public.sessions where id = '5a000000-0000-4000-8000-00000000000a'), null::timestamptz, 'but the session of A stays open');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-4000-8000-00000000000a","role":"authenticated"}', true);
select lives_ok($$update public.sessions set rsvps_closed_at = now() where id = '5a000000-0000-4000-8000-00000000000a'$$, 'A closes the own session');
reset role;
select isnt((select rsvps_closed_at from public.sessions where id = '5a000000-0000-4000-8000-00000000000a'), null::timestamptz, 'rsvps_closed_at is set');

-- Public behaviour while closed (23-30).
set local role anon;
select is(public.get_public_session('pgtap-mod-sa-01')->'session'->>'rsvps_closed', 'true', 'the closed session is flagged');
select is(public.get_public_session('pgtap-mod-so-01')->'session'->>'rsvps_closed', 'false', 'the open session is not flagged');
select set_eq($$select k from jsonb_object_keys(public.get_public_session('pgtap-mod-sa-01')->'session') k$$, $$values ('slug'), ('spot_id'), ('spot_name'), ('organizer_name'), ('starts_at'), ('ends_at'), ('note'), ('seats_free'), ('departure_point'), ('tikkie_url'), ('cancelled'), ('rsvps_closed')$$, 'session keys');
select ok(public.get_public_session('pgtap-mod-sa-01')::text !~ '(organizer_id|edit_token|email|user_id|recent_rsvp_creates|rsvps_closed_at)', 'no private keys in the public view');
select throws_ok($$select public.rsvp_create('pgtap-mod-sa-01', 'Dirk', 'own', null)$$, 'PT400', 'session_closed', 'rsvp_create on a closed session');
select throws_ok($$select public.rsvp_create('pgtap-mod-sa-01', '  ', 'own', null)$$, 'PT400', 'invalid_input', 'invalid input is checked first');
select is((public.rsvp_update(repeat('K', 43), 'Cas2', 'own', null, null))->>'first_name', 'Cas2', 'a token holder can still edit');
select is(public.rsvp_delete(repeat('K', 43)), true, 'a token holder can still sign off');
reset role;

-- Reopening (31-32).
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-4000-8000-00000000000a","role":"authenticated"}', true);
select lives_ok($$update public.sessions set rsvps_closed_at = null where id = '5a000000-0000-4000-8000-00000000000a'$$, 'A reopens the session');
reset role;
set local role anon;
select ok((public.rsvp_create('pgtap-mod-sa-01', 'Dirk', 'own', null))->>'edit_token' ~ '^[A-Za-z0-9_-]{43}$', 'rsvp_create works again');
reset role;

select * from finish();
rollback;
