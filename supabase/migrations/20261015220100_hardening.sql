-- WP-22: database usage for the weekly report (service role only), at most 20 push
-- subscriptions per user, and an upper bound on how far ahead a session can start.

create function public.db_usage()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select pg_catalog.jsonb_build_object(
    'database_bytes',
    (select coalesce(sum(pg_catalog.pg_database_size(d.oid)), 0)::bigint
       from pg_catalog.pg_database d
      where pg_catalog.has_database_privilege(d.oid, 'CONNECT')),
    'tables',
    pg_catalog.jsonb_build_object(
      'spots', (select count(*) from public.spots),
      'forecast_hours', (select count(*) from public.forecast_hours),
      'marine_hours', (select count(*) from public.marine_hours),
      'tide_extremes', (select count(*) from public.tide_extremes),
      'evaluations', (select count(*) from public.evaluations),
      'profiles', (select count(*) from public.profiles),
      'favorites', (select count(*) from public.favorites),
      'alert_rules', (select count(*) from public.alert_rules),
      'alert_state', (select count(*) from public.alert_state),
      'push_subscriptions', (select count(*) from public.push_subscriptions),
      'sessions', (select count(*) from public.sessions),
      'rsvps', (select count(*) from public.rsvps),
      'api_usage', (select count(*) from public.api_usage),
      'ingest_runs', (select count(*) from public.ingest_runs)
    )
  );
$$;

revoke all on function public.db_usage() from public, anon, authenticated, service_role;
grant execute on function public.db_usage() to service_role;

-- Security invoker on purpose: under RLS an authenticated caller only counts own rows.
create function public.push_subscriptions_limit()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_count integer;
begin
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('shakka.push_subscriptions:' || new.user_id::text, 0)
  );
  select count(*) into v_count from public.push_subscriptions p where p.user_id = new.user_id;
  if v_count >= 20 then
    raise sqlstate 'PT400' using message = 'too_many_subscriptions';
  end if;
  return new;
end;
$$;

create trigger push_subscriptions_limit before insert on public.push_subscriptions
  for each row execute function public.push_subscriptions_limit();

revoke all on function public.push_subscriptions_limit()
  from public, anon, authenticated, service_role;

-- Upper bound on how far ahead a session may start. A CHECK cannot use now(), so a trigger.
-- The app allows up to 365 days ahead, on create and on edit. On update the bound only applies
-- when starts_at actually changes, so an older row stays editable. Security invoker.
create function public.sessions_starts_at_horizon()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' then
    if new.starts_at is not distinct from old.starts_at then
      return new;
    end if;
  end if;
  if new.starts_at > now() + interval '370 days' then
    raise sqlstate '23514' using message = 'starts_at_too_far_ahead';
  end if;
  return new;
end;
$$;

create trigger sessions_starts_at_horizon before insert or update of starts_at on public.sessions
  for each row execute function public.sessions_starts_at_horizon();

revoke all on function public.sessions_starts_at_horizon()
  from public, anon, authenticated, service_role;
