-- Wave forecasts per spot and hour (WP-12). Display only: never used in evaluations or alerts.
-- Written by the ingest (secret key -> service_role), read by the app (anon, authenticated).

create table public.marine_hours (
  spot_id text not null references public.spots (id) on delete cascade,
  valid_at timestamptz not null,
  wave_height_m real null constraint marine_hours_wave_height_nonneg check (wave_height_m >= 0),
  wave_period_s real null constraint marine_hours_wave_period_nonneg check (wave_period_s >= 0),
  wave_dir_deg smallint null
    constraint marine_hours_wave_dir_range check (wave_dir_deg between 0 and 359),
  fetched_at timestamptz not null,
  primary key (spot_id, valid_at),
  constraint marine_hours_has_value
    check (wave_height_m is not null or wave_period_s is not null or wave_dir_deg is not null)
);
create index marine_hours_valid_at_idx on public.marine_hours (valid_at);

alter table public.marine_hours enable row level security;

revoke all on table public.marine_hours from public, anon, authenticated, service_role;

-- Public read data.
grant select on table public.marine_hours to anon, authenticated;

-- Ingest.
grant select, insert, update, delete on table public.marine_hours to service_role;

create policy marine_hours_read on public.marine_hours for select to anon, authenticated using (true);
