-- WP-30: quiet hours columns on profiles: CHECK, column privileges, user A against user B.
begin;
create extension if not exists pgtap with schema extensions;

select plan(15);

insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'a@example.test'),
  ('22222222-2222-2222-2222-222222222222', 'b@example.test');

select ok(
  exists (select 1 from pg_constraint where conname = 'profiles_quiet_hours_valid' and contype = 'c' and conrelid = 'public.profiles'::regclass),
  'CHECK profiles_quiet_hours_valid exists'
);

select column_privs_are('public'::name, 'profiles'::name, 'quiet_from'::name, 'authenticated'::name, array['SELECT', 'UPDATE']::name[], 'authenticated may select and update profiles.quiet_from');
select column_privs_are('public'::name, 'profiles'::name, 'quiet_until'::name, 'authenticated'::name, array['SELECT', 'UPDATE']::name[], 'authenticated may select and update profiles.quiet_until');
select column_privs_are('public'::name, 'profiles'::name, 'quiet_from'::name, 'anon'::name, array[]::name[], 'anon has no privileges on profiles.quiet_from');

select throws_ok($$update public.profiles set quiet_from = '22:00' where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'only quiet_from set is rejected');
select throws_ok($$update public.profiles set quiet_until = '07:00' where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'only quiet_until set is rejected');
select throws_ok($$update public.profiles set quiet_from = '22:00', quiet_until = '22:00' where user_id = '11111111-1111-1111-1111-111111111111'$$, '23514', null, 'equal times are rejected');

select lives_ok($$update public.profiles set quiet_from = '22:00', quiet_until = '07:00' where user_id = '11111111-1111-1111-1111-111111111111'$$, 'a valid pair is accepted');
select lives_ok($$update public.profiles set quiet_from = null, quiet_until = null where user_id = '11111111-1111-1111-1111-111111111111'$$, 'both null is accepted');

set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111","role":"authenticated"}', true);

select lives_ok($$update public.profiles set quiet_from = '22:00', quiet_until = '07:00' where user_id = '11111111-1111-1111-1111-111111111111'$$, 'A sets own quiet hours');
select is((select quiet_from from public.profiles where user_id = '11111111-1111-1111-1111-111111111111'), '22:00'::time, 'A reads own quiet_from');
select is((select quiet_until from public.profiles where user_id = '11111111-1111-1111-1111-111111111111'), '07:00'::time, 'A reads own quiet_until');
select lives_ok($$update public.profiles set quiet_from = '23:00', quiet_until = '06:00' where user_id = '22222222-2222-2222-2222-222222222222'$$, 'A updating quiet hours of B touches 0 rows');

reset role;

select is((select quiet_from from public.profiles where user_id = '22222222-2222-2222-2222-222222222222'), null::time, 'quiet_from of B is unchanged');
select is((select quiet_until from public.profiles where user_id = '22222222-2222-2222-2222-222222222222'), null::time, 'quiet_until of B is unchanged');

select * from finish();
rollback;
