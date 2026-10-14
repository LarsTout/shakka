-- RLS, explicit grants and policies. Independent of the "auto expose new tables" setting:
-- every table first loses all API privileges, then gets exactly what it needs.

alter table public.spots enable row level security;
alter table public.forecast_hours enable row level security;
alter table public.tide_extremes enable row level security;
alter table public.evaluations enable row level security;
alter table public.profiles enable row level security;
alter table public.favorites enable row level security;
alter table public.alert_rules enable row level security;
alter table public.alert_state enable row level security;
alter table public.api_usage enable row level security;
alter table public.ingest_runs enable row level security;

revoke all on table
  public.spots, public.forecast_hours, public.tide_extremes, public.evaluations,
  public.profiles, public.favorites, public.alert_rules, public.alert_state,
  public.api_usage, public.ingest_runs
from public, anon, authenticated, service_role;

-- Public read data.
grant select on table public.spots, public.forecast_hours, public.tide_extremes, public.evaluations
  to anon, authenticated;

-- Own profile: read, and update only user-editable columns (never telegram_chat_id).
grant select on table public.profiles to authenticated;
grant update (weight_kg, level, quiver_m2, default_min_kn, default_max_kn)
  on table public.profiles to authenticated;

-- Own favorites and alert rules: full CRUD (RLS restricts to own rows).
grant select, insert, update, delete on table public.favorites, public.alert_rules to authenticated;

-- Own alert state: read only.
grant select on table public.alert_state to authenticated;

-- Ingest (secret key -> service_role, BYPASSRLS).
grant select, insert, update, delete on table
  public.spots, public.forecast_hours, public.tide_extremes, public.evaluations,
  public.profiles, public.favorites, public.alert_rules, public.alert_state,
  public.api_usage, public.ingest_runs
to service_role;

-- Policies.
create policy spots_read on public.spots for select to anon, authenticated using (true);
create policy forecast_hours_read on public.forecast_hours for select to anon, authenticated using (true);
create policy tide_extremes_read on public.tide_extremes for select to anon, authenticated using (true);
create policy evaluations_read on public.evaluations for select to anon, authenticated using (true);

create policy profiles_select_own on public.profiles for select to authenticated
  using (user_id = (select auth.uid()));
create policy profiles_update_own on public.profiles for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

create policy favorites_select_own on public.favorites for select to authenticated
  using (user_id = (select auth.uid()));
create policy favorites_insert_own on public.favorites for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy favorites_update_own on public.favorites for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy favorites_delete_own on public.favorites for delete to authenticated
  using (user_id = (select auth.uid()));

create policy alert_rules_select_own on public.alert_rules for select to authenticated
  using (user_id = (select auth.uid()));
create policy alert_rules_insert_own on public.alert_rules for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy alert_rules_update_own on public.alert_rules for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy alert_rules_delete_own on public.alert_rules for delete to authenticated
  using (user_id = (select auth.uid()));

create policy alert_state_select_own on public.alert_state for select to authenticated
  using (user_id = (select auth.uid()));

-- api_usage, ingest_runs: no policies (service_role only).

-- Trigger functions are never callable through the API.
revoke all on function public.set_updated_at() from public, anon, authenticated, service_role;
revoke all on function public.handle_new_user() from public, anon, authenticated, service_role;
