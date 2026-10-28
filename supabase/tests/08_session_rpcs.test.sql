-- Session RPCs (WP-19): get_public_session, rsvp_create, rsvp_update, rsvp_delete, purge_expired_sessions.
begin;
create extension if not exists pgtap with schema extensions;

select plan(71);

-- Fixture (postgres): organizer A, one spot, eight sessions and a few RSVPs.
insert into auth.users (id, email) values ('11111111-1111-1111-1111-111111111111', 'a@example.test');
insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot');
insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, note, seats_free, departure_point, tikkie_url, cancelled_at) values
  ('50000000-0000-4000-8000-000000000001', 'pgtap-open-0001', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() + interval '1 day', now() + interval '1 day 4 hours', 'Parkeren bij de strandopgang', 3, 'Utrecht CS', 'https://tikkie.me/pay/pgtap', null),
  ('50000000-0000-4000-8000-000000000002', 'pgtap-cancel-01', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() + interval '1 day', now() + interval '1 day 2 hours', null, null, null, null, now()),
  ('50000000-0000-4000-8000-000000000003', 'pgtap-ended-001', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() - interval '5 hours', now() - interval '1 hour', null, null, null, null, null),
  ('50000000-0000-4000-8000-000000000004', 'pgtap-full-0001', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() + interval '1 day', now() + interval '1 day 2 hours', null, null, null, null, null),
  ('50000000-0000-4000-8000-000000000005', 'pgtap-rate-0001', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() + interval '1 day', now() + interval '1 day 2 hours', null, null, null, null, null),
  ('50000000-0000-4000-8000-000000000006', 'pgtap-old-00001', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() - interval '8 days 3 hours', now() - interval '8 days', null, null, null, null, null),
  ('50000000-0000-4000-8000-000000000007', 'pgtap-edge-0001', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() - interval '7 days 2 hours', now() - interval '7 days', null, null, null, null, null),
  ('50000000-0000-4000-8000-000000000008', 'pgtap-recent-01', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() - interval '6 days 2 hours', now() - interval '6 days', null, null, null, null, null);
insert into public.rsvps (id, session_id, first_name, ride, seats_offered, edit_token_hash, created_at) values
  ('60000000-0000-4000-8000-000000000001', '50000000-0000-4000-8000-000000000001', 'Eva', 'offers_ride', 2, encode(sha256(convert_to(repeat('D', 43), 'UTF8')), 'hex'), now() - interval '2 hours');
insert into public.rsvps (id, session_id, first_name, ride, seats_offered, edit_token_hash) values
  ('60000000-0000-4000-8000-000000000002', '50000000-0000-4000-8000-000000000002', 'Tom', 'own', null, encode(sha256(convert_to(repeat('C', 43), 'UTF8')), 'hex')),
  ('60000000-0000-4000-8000-000000000003', '50000000-0000-4000-8000-000000000003', 'Piet', 'offers_ride', 1, encode(sha256(convert_to(repeat('E', 43), 'UTF8')), 'hex')),
  ('60000000-0000-4000-8000-000000000004', '50000000-0000-4000-8000-000000000006', 'Ida', 'own', null, encode(sha256(convert_to(repeat('O', 43), 'UTF8')), 'hex')),
  ('60000000-0000-4000-8000-000000000005', '50000000-0000-4000-8000-000000000006', 'Jan', 'own', null, encode(sha256(convert_to(repeat('P', 43), 'UTF8')), 'hex'));
insert into public.rsvps (id, session_id, first_name, ride, seats_offered, edit_token_hash, created_at)
  select gen_random_uuid(), '50000000-0000-4000-8000-000000000004', 'Gast ' || i, 'own', null, encode(sha256(convert_to('full-' || i, 'UTF8')), 'hex'), now() - interval '1 hour'
    from generate_series(1, 30) i;

set local role anon;

-- get_public_session (1-9).
select is(public.get_public_session('pgtap-unknown-01'), null::jsonb, 'unknown slug gives null');
select is(public.get_public_session('bad slug!'), null::jsonb, 'malformed slug gives null');
select set_eq($$select k from jsonb_object_keys(public.get_public_session('pgtap-open-0001')) k$$, $$values ('session'), ('rsvps')$$, 'top-level keys');
select set_eq($$select k from jsonb_object_keys(public.get_public_session('pgtap-open-0001')->'session') k$$, $$values ('slug'), ('spot_id'), ('spot_name'), ('organizer_name'), ('starts_at'), ('ends_at'), ('note'), ('seats_free'), ('departure_point'), ('tikkie_url'), ('cancelled'), ('rsvps_closed')$$, 'session keys');
select set_eq($$select k from jsonb_object_keys(public.get_public_session('pgtap-open-0001')->'rsvps'->0) k$$, $$values ('id'), ('first_name'), ('ride'), ('seats_offered'), ('rides_with'), ('created_at')$$, 'rsvp keys');
select ok(public.get_public_session('pgtap-open-0001')::text !~ '(organizer_id|edit_token|email|user_id|recent_rsvp_creates)', 'no private keys in the public view');
select is(public.get_public_session('pgtap-open-0001')->'session'->>'spot_name', 'Pgtap Spot', 'spot name is included');
select is(public.get_public_session('pgtap-open-0001')->'session'->>'cancelled', 'false', 'open session is not cancelled');
select is(public.get_public_session('pgtap-cancel-01')->'session'->>'cancelled', 'true', 'cancelled session is flagged');

-- rsvp_create and rsvp_update (10-20).
select ok((select set_config('pgtap.c1', public.rsvp_create('pgtap-open-0001', '  Sanne  ', 'needs_ride', null)::text, true))::jsonb->>'edit_token' ~ '^[A-Za-z0-9_-]{43}$', 'rsvp_create returns a 43 character token');
select set_eq($$select k from jsonb_object_keys(current_setting('pgtap.c1')::jsonb) k$$, $$values ('rsvp_id'), ('edit_token')$$, 'rsvp_create result keys');
select results_eq($$select e->>'first_name' from jsonb_array_elements(public.get_public_session('pgtap-open-0001')->'rsvps') with ordinality as t(e, n) order by n$$, $$values ('Eva'), ('Sanne')$$, 'the name is trimmed and listed in order');
select is(public.rsvp_update((current_setting('pgtap.c1')::jsonb->>'edit_token'), 'Sanne', 'needs_ride', null, '60000000-0000-4000-8000-000000000001')->>'rides_with', '60000000-0000-4000-8000-000000000001', 'Sanne rides with Eva');
select throws_ok($$select public.rsvp_update(repeat('Z', 43), 'X', 'own', null, null)$$, 'PT400', 'invalid_token', 'unknown token');
select throws_ok($$select public.rsvp_update('abc', 'X', 'own', null, null)$$, 'PT400', 'invalid_token', 'malformed token');
select throws_ok($$select public.rsvp_update((current_setting('pgtap.c1')::jsonb->>'edit_token'), 'Sanne', 'needs_ride', null, ((current_setting('pgtap.c1')::jsonb->>'rsvp_id')::uuid))$$, 'PT400', 'invalid_input', 'rides_with cannot point to oneself');
select throws_ok($$select public.rsvp_update((current_setting('pgtap.c1')::jsonb->>'edit_token'), 'Sanne', 'needs_ride', null, '60000000-0000-4000-8000-000000000003'::uuid)$$, 'PT400', 'invalid_input', 'rides_with cannot point to another session');
select throws_ok($$select public.rsvp_update((current_setting('pgtap.c1')::jsonb->>'edit_token'), 'Sanne', 'own', null, '60000000-0000-4000-8000-000000000001'::uuid)$$, 'PT400', 'invalid_input', 'rides_with needs needs_ride');
select throws_ok($$select public.rsvp_update(repeat('D', 43), 'Eva', 'needs_ride', null, ((current_setting('pgtap.c1')::jsonb->>'rsvp_id')::uuid))$$, 'PT400', 'invalid_input', 'rides_with must offer a ride');
select throws_ok($$select public.rsvp_update(repeat('C', 43), 'Tom', 'own', null, null)$$, 'PT400', 'session_closed', 'update on a cancelled session');

-- rsvp_create validation (21-30).
select throws_ok($$select public.rsvp_create('pgtap-open-0001', '', 'own', null)$$, 'PT400', 'invalid_input', 'empty name');
select throws_ok($$select public.rsvp_create('pgtap-open-0001', '   ', 'own', null)$$, 'PT400', 'invalid_input', 'blank name');
select throws_ok($$select public.rsvp_create('pgtap-open-0001', repeat('x', 31), 'own', null)$$, 'PT400', 'invalid_input', 'name of 31 characters');
select throws_ok($$select public.rsvp_create('pgtap-open-0001', null, 'own', null)$$, 'PT400', 'invalid_input', 'null name');
select throws_ok($$select public.rsvp_create('pgtap-open-0001', E'Sa\nnne', 'own', null)$$, 'PT400', 'invalid_input', 'name with a line break');
select throws_ok($$select public.rsvp_create('pgtap-open-0001', 'Ann', 'walk', null)$$, 'PT400', 'invalid_input', 'unknown ride');
select throws_ok($$select public.rsvp_create('pgtap-open-0001', 'Ann', null, null)$$, 'PT400', 'invalid_input', 'null ride');
select throws_ok($$select public.rsvp_create('pgtap-open-0001', 'Ann', 'offers_ride', 9)$$, 'PT400', 'invalid_input', 'more than 8 seats');
select throws_ok($$select public.rsvp_create('pgtap-open-0001', 'Ann', 'own', 2)$$, 'PT400', 'invalid_input', 'seats without offers_ride');
select lives_ok($$select public.rsvp_create('pgtap-open-0001', repeat('x', 30), 'offers_ride', 0)$$, 'name of exactly 30 characters and 0 seats');

-- closed, full, rate limit (31-39).
select throws_ok($$select public.rsvp_create('pgtap-cancel-01', 'Ann', 'own', null)$$, 'PT400', 'session_closed', 'rsvp_create on a cancelled session');
select throws_ok($$select public.rsvp_create('pgtap-ended-001', 'Ann', 'own', null)$$, 'PT400', 'session_closed', 'rsvp_create on a ended session');
select throws_ok($$select public.rsvp_create('pgtap-unknown-01', 'Ann', 'own', null)$$, 'PT400', 'session_closed', 'rsvp_create on a unknown session');
select throws_ok($$select public.rsvp_create('pgtap-full-0001', 'Ann', 'own', null)$$, 'PT400', 'session_full', 'rsvp_create on a full session');
select lives_ok($$select public.rsvp_create('pgtap-rate-0001', 'Gast', 'own', null) from generate_series(1, 10)$$, 'ten rsvp_create calls are accepted');
select throws_ok($$select public.rsvp_create('pgtap-rate-0001', 'Gast', 'own', null)$$, 'PT400', 'rate_limited', 'the 11th call within 10 minutes is rate limited');
reset role;
delete from public.rsvps where session_id = '50000000-0000-4000-8000-000000000005';
set local role anon;
select throws_ok($$select public.rsvp_create('pgtap-rate-0001', 'Gast', 'own', null)$$, 'PT400', 'rate_limited', 'removed rsvps still count');
reset role;
update public.sessions set recent_rsvp_creates = array_fill(now() - interval '11 minutes', array[10]) where id = '50000000-0000-4000-8000-000000000005';
set local role anon;
select lives_ok($$select public.rsvp_create('pgtap-rate-0001', 'Gast', 'own', null)$$, 'old calls expire after 10 minutes');
reset role;
select is((select cardinality(recent_rsvp_creates) from public.sessions where id = '50000000-0000-4000-8000-000000000005'), 1, 'expired timestamps are pruned');

-- carpool (40-44).
set local role anon;
select lives_ok($$select public.rsvp_update(repeat('D', 43), 'Eva', 'own', null, null)$$, 'the driver stops offering a ride');
reset role;
select is((select rides_with from public.rsvps where id = ((current_setting('pgtap.c1')::jsonb->>'rsvp_id')::uuid)), null::uuid, 'riders of a former driver are looking again');
set local role anon;
select ok((select set_config('pgtap.c2', public.rsvp_create('pgtap-open-0001', '  Noor ', 'needs_ride', null)::text, true)) is not null, 'Noor joins');
select lives_ok($$select public.rsvp_update(repeat('D', 43), 'Eva', 'offers_ride', 3, null)$$, 'Eva offers a ride again');
select lives_ok($$select public.rsvp_update((current_setting('pgtap.c2')::jsonb->>'edit_token'), 'Noor', 'needs_ride', null, '60000000-0000-4000-8000-000000000001'::uuid)$$, 'Noor rides with Eva');

-- rsvp_delete (45-53).
select is(public.rsvp_delete(repeat('Z', 43)), false, 'unknown token gives false');
select is(public.rsvp_delete('abc'), false, 'malformed token gives false');
select is(public.rsvp_delete((current_setting('pgtap.c1')::jsonb->>'edit_token')), true, 'Sanne can cancel');
select is(public.rsvp_delete((current_setting('pgtap.c1')::jsonb->>'edit_token')), false, 'the second cancel gives false');
select is(public.rsvp_delete(repeat('C', 43)), true, 'cancel on a cancelled session is allowed');
select is(public.rsvp_delete(repeat('D', 43)), true, 'Eva cancels');
reset role;
select is((select rides_with from public.rsvps where id = ((current_setting('pgtap.c2')::jsonb->>'rsvp_id')::uuid)), null::uuid, 'riders of a cancelled driver are looking again');
select is((select first_name from public.rsvps where id = ((current_setting('pgtap.c2')::jsonb->>'rsvp_id')::uuid)), 'Noor', 'Noor is still there, trimmed');
select ok((select edit_token_hash = encode(sha256(convert_to((current_setting('pgtap.c2')::jsonb->>'edit_token'), 'UTF8')), 'hex') and edit_token_hash <> (current_setting('pgtap.c2')::jsonb->>'edit_token') from public.rsvps where id = ((current_setting('pgtap.c2')::jsonb->>'rsvp_id')::uuid)), 'only the hash of the token is stored');

-- authenticated and the purge function (54-62).
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select ok(public.get_public_session('pgtap-open-0001') is not null, 'authenticated can read the public view');
select lives_ok($$select public.rsvp_create('pgtap-open-0001', 'Lars', 'offers_ride', 2)$$, 'authenticated can create an rsvp');
select throws_ok($$select public.purge_expired_sessions(now())$$, '42501', null, 'authenticated cannot purge');
reset role;
set local role anon;
select throws_ok($$select public.purge_expired_sessions(now())$$, '42501', null, 'anon cannot purge');
reset role;
set local role service_role;
select throws_ok($$select public.purge_expired_sessions(null)$$, 'PT400', 'invalid_input', 'purge needs p_now');
select is(public.purge_expired_sessions(now()), 1, 'only the session older than 7 days is purged');
reset role;
select is_empty($$select 1 from public.sessions where id = '50000000-0000-4000-8000-000000000006'$$, 'the old session is gone');
select is_empty($$select 1 from public.rsvps where session_id = '50000000-0000-4000-8000-000000000006'$$, 'its rsvps are gone (cascade)');
select results_eq($$select count(*)::int from public.sessions where id in ('50000000-0000-4000-8000-000000000007', '50000000-0000-4000-8000-000000000008', '50000000-0000-4000-8000-000000000003')$$, array[3], 'exactly 7 days old and newer sessions stay');

-- Extra (N-5): ended sessions, slug edge cases, negative seats, cascades with a driver and a rider.
set local role anon;
select throws_ok($$select public.rsvp_update(repeat('E', 43), 'Piet', 'offers_ride', 1, null)$$, 'PT400', 'session_closed', 'update on an ended session');
select is(public.rsvp_delete(repeat('E', 43)), true, 'cancel on an ended session is allowed');
select is(public.get_public_session(null), null::jsonb, 'null slug gives null');
select is(public.get_public_session('short'), null::jsonb, 'too short slug gives null');
select is(public.get_public_session(repeat('a', 65)), null::jsonb, 'too long slug gives null');
select throws_ok($$select public.rsvp_create('pgtap-open-0001', 'Ann', 'offers_ride', -1)$$, 'PT400', 'invalid_input', 'negative seats');
reset role;
insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values
  ('50000000-0000-4000-8000-000000000009', 'pgtap-casc-0001', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() + interval '1 day', now() + interval '1 day 2 hours'),
  ('50000000-0000-4000-8000-000000000010', 'pgtap-casc-0002', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Lars', now() - interval '9 days 2 hours', now() - interval '9 days');
insert into public.rsvps (id, session_id, first_name, ride, seats_offered, edit_token_hash) values
  ('60000000-0000-4000-8000-000000000021', '50000000-0000-4000-8000-000000000009', 'Driver', 'offers_ride', 2, encode(sha256(convert_to('casc-d1', 'UTF8')), 'hex')),
  ('60000000-0000-4000-8000-000000000023', '50000000-0000-4000-8000-000000000010', 'Driver', 'offers_ride', 2, encode(sha256(convert_to('casc-d2', 'UTF8')), 'hex'));
insert into public.rsvps (id, session_id, first_name, ride, rides_with, edit_token_hash) values
  ('60000000-0000-4000-8000-000000000022', '50000000-0000-4000-8000-000000000009', 'Rider', 'needs_ride', '60000000-0000-4000-8000-000000000021', encode(sha256(convert_to('casc-r1', 'UTF8')), 'hex')),
  ('60000000-0000-4000-8000-000000000024', '50000000-0000-4000-8000-000000000010', 'Rider', 'needs_ride', '60000000-0000-4000-8000-000000000023', encode(sha256(convert_to('casc-r2', 'UTF8')), 'hex'));
delete from public.sessions where id = '50000000-0000-4000-8000-000000000009';
select is_empty($$select 1 from public.rsvps where session_id = '50000000-0000-4000-8000-000000000009'$$, 'deleting a session with a driver and a rider removes both');
set local role service_role;
select is(public.purge_expired_sessions(now()), 1, 'purge removes the session with a driver and a rider');
reset role;
select is_empty($$select 1 from public.rsvps where session_id = '50000000-0000-4000-8000-000000000010'$$, 'the purge cascade removes driver and rider');

select * from finish();
rollback;
