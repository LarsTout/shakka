-- WP-30: quiet hours per user, local time (Europe/Amsterdam), every day. Both null = off.
-- start > end runs past midnight; the alert job holds back delivery and state inside [from, until).
alter table public.profiles add column quiet_from time null;
alter table public.profiles add column quiet_until time null;
alter table public.profiles add constraint profiles_quiet_hours_valid check (
  (quiet_from is null) = (quiet_until is null)
  and (quiet_from is null or quiet_from <> quiet_until)
);
grant update (quiet_from, quiet_until) on table public.profiles to authenticated;
