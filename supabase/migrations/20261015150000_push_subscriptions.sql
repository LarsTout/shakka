-- Web Push subscriptions (WP-17). One row per browser or device. Written by the PWA (WP-18),
-- read and cleaned up by the ingest (secret key -> service_role). The endpoint is a capability
-- URL: never log it.

create table public.push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  endpoint text not null
    constraint push_subscriptions_endpoint_unique unique
    constraint push_subscriptions_endpoint_https
    check (endpoint ~ '^https://[^[:space:]]+$' and char_length(endpoint) <= 2048),
  p256dh text not null constraint push_subscriptions_p256dh_format
    check (p256dh ~ '^[A-Za-z0-9_-]+={0,2}$' and char_length(p256dh) <= 256),
  auth text not null constraint push_subscriptions_auth_format
    check (auth ~ '^[A-Za-z0-9_-]+={0,2}$' and char_length(auth) <= 64),
  created_at timestamptz not null default now(),
  last_success_at timestamptz null
);
create index push_subscriptions_user_id_idx on public.push_subscriptions (user_id);

alter table public.push_subscriptions enable row level security;

revoke all on table public.push_subscriptions from public, anon, authenticated, service_role;

-- Own subscriptions: read, add (only these columns) and remove. No update.
grant select, delete on table public.push_subscriptions to authenticated;
grant insert (user_id, endpoint, p256dh, auth) on table public.push_subscriptions to authenticated;

-- Ingest.
grant select, insert, update, delete on table public.push_subscriptions to service_role;

create policy push_subscriptions_select_own on public.push_subscriptions for select to authenticated
  using (user_id = (select auth.uid()));
create policy push_subscriptions_insert_own on public.push_subscriptions for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy push_subscriptions_delete_own on public.push_subscriptions for delete to authenticated
  using (user_id = (select auth.uid()));
