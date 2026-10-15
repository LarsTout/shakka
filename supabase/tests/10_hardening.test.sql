-- Hardening (WP-22): db_usage, the limit of 20 push subscriptions per user, and the sessions horizon.
begin;
create extension if not exists pgtap with schema extensions;

select plan(28);

-- Fixture (postgres): users A and B and one spot.
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'a@example.test'),
  ('22222222-2222-2222-2222-222222222222', 'b@example.test');
insert into public.spots (id, name) values ('pgtap-spot', 'Pgtap Spot');

-- db_usage (1-11).
select has_function('public'::name, 'db_usage'::name, array[]::name[], 'db_usage exists');
select is_definer('public'::name, 'db_usage'::name, array[]::name[], 'db_usage is security definer');
select function_privs_are('public'::name, 'db_usage'::name, array[]::name[], 'anon'::name, array[]::text[], 'anon cannot execute db_usage');
select function_privs_are('public'::name, 'db_usage'::name, array[]::name[], 'authenticated'::name, array[]::text[], 'authenticated cannot execute db_usage');
select function_privs_are('public'::name, 'db_usage'::name, array[]::name[], 'service_role'::name, array['EXECUTE']::text[], 'service_role can execute db_usage');

set local role anon;
select throws_ok('select public.db_usage()', '42501', null, 'anon cannot call db_usage');
reset role;

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select throws_ok('select public.db_usage()', '42501', null, 'authenticated cannot call db_usage');
reset role;

set local role service_role;
select lives_ok('select public.db_usage()', 'service_role can call db_usage');
reset role;

select set_eq($$select k from jsonb_object_keys(public.db_usage()->'tables') k$$, $$values ('spots'), ('forecast_hours'), ('marine_hours'), ('tide_extremes'), ('evaluations'), ('profiles'), ('favorites'), ('alert_rules'), ('alert_state'), ('push_subscriptions'), ('sessions'), ('rsvps'), ('api_usage'), ('ingest_runs')$$, 'db_usage counts the 14 tables');
select ok((public.db_usage()->>'database_bytes')::bigint > 0, 'db_usage reports a database size');
select is((public.db_usage()->'tables'->>'spots')::bigint, (select count(*) from public.spots), 'db_usage counts spots exactly');

-- push_subscriptions limit (12-18).
select has_trigger('public'::name, 'push_subscriptions'::name, 'push_subscriptions_limit'::name, 'push_subscriptions has the limit trigger');
select function_privs_are('public'::name, 'push_subscriptions_limit'::name, array[]::name[], 'authenticated'::name, array[]::text[], 'authenticated has no EXECUTE on the limit trigger function');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select lives_ok($$insert into public.push_subscriptions (endpoint, p256dh, auth) select 'https://fcm.googleapis.com/fcm/send/a' || g, 'AAAA', 'aaaa' from generate_series(1, 20) g$$, 'A can add 20 subscriptions');
select throws_ok($$insert into public.push_subscriptions (endpoint, p256dh, auth) values ('https://fcm.googleapis.com/fcm/send/a21', 'AAAA', 'aaaa')$$, 'PT400', 'too_many_subscriptions', 'the 21st subscription of A is refused');
select lives_ok($$delete from public.push_subscriptions where endpoint = 'https://fcm.googleapis.com/fcm/send/a1'$$, 'A removes one subscription');
select lives_ok($$insert into public.push_subscriptions (endpoint, p256dh, auth) values ('https://fcm.googleapis.com/fcm/send/a21', 'AAAA', 'aaaa')$$, 'A can add one again');
reset role;

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"22222222-2222-2222-2222-222222222222","role":"authenticated"}', true);
select lives_ok($$insert into public.push_subscriptions (endpoint, p256dh, auth) values ('https://fcm.googleapis.com/fcm/send/b1', 'AAAA', 'aaaa')$$, 'the limit is per user: B can add one');
reset role;

-- sessions horizon (19-28).
select has_trigger('public'::name, 'sessions'::name, 'sessions_starts_at_horizon'::name, 'sessions has the horizon trigger');
select function_privs_are('public'::name, 'sessions_starts_at_horizon'::name, array[]::name[], 'authenticated'::name, array[]::text[], 'authenticated has no EXECUTE on the horizon trigger function');
select isnt_definer('public'::name, 'sessions_starts_at_horizon'::name, array[]::name[], 'the horizon trigger function is security invoker');

select throws_ok($$insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('d0000000-0000-4000-8000-000000000009', 'pgtap-horizon-0009', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Anna', now() + interval '371 days', now() + interval '371 days 2 hours')$$, '23514', 'starts_at_too_far_ahead', 'a session 371 days ahead is refused');
select lives_ok($$insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at, created_at) values ('d0000000-0000-4000-8000-000000000001', 'pgtap-horizon-0001', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Anna', now() + interval '365 days', now() + interval '365 days 2 hours', now() - interval '10 days')$$, 'a session 365 days ahead is accepted');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select lives_ok($$update public.sessions set starts_at = now() + interval '369 days', ends_at = now() + interval '369 days 2 hours' where id = 'd0000000-0000-4000-8000-000000000001'$$, 'A can move a 10 day old session to 369 days ahead');
reset role;

select ok((select starts_at > now() + interval '368 days' from public.sessions where id = 'd0000000-0000-4000-8000-000000000001'), 'the move to 369 days ahead really happened');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select throws_ok($$update public.sessions set starts_at = now() + interval '371 days', ends_at = now() + interval '371 days 2 hours' where id = 'd0000000-0000-4000-8000-000000000001'$$, '23514', 'starts_at_too_far_ahead', 'moving a session to 371 days ahead is refused');
reset role;

-- A legacy row beyond the horizon (inserted with the trigger off) stays editable while starts_at is unchanged.
alter table public.sessions disable trigger sessions_starts_at_horizon;
insert into public.sessions (id, slug, spot_id, organizer_id, organizer_name, starts_at, ends_at) values ('d0000000-0000-4000-8000-000000000002', 'pgtap-horizon-0002', 'pgtap-spot', '11111111-1111-1111-1111-111111111111', 'Anna', now() + interval '400 days', now() + interval '400 days 2 hours');
alter table public.sessions enable trigger sessions_starts_at_horizon;

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);
select lives_ok($$update public.sessions set note = 'pgtap-legacy', starts_at = starts_at where id = 'd0000000-0000-4000-8000-000000000002'$$, 'a legacy row stays editable with an unchanged starts_at');
select throws_ok($$update public.sessions set starts_at = starts_at + interval '1 day', ends_at = ends_at + interval '1 day' where id = 'd0000000-0000-4000-8000-000000000002'$$, '23514', 'starts_at_too_far_ahead', 'changing starts_at of a legacy row is bounded');
reset role;

select * from finish();
rollback;
