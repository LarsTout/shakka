-- M1 schema: tables, constraints, indexes, triggers. Security lives in *_m1_security.sql.

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create table public.spots (
  id text primary key
    constraint spots_id_slug check (id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  name text not null constraint spots_name_not_blank check (btrim(name) <> ''),
  region text null,
  lat double precision null constraint spots_lat_range check (lat between -90 and 90),
  lon double precision null constraint spots_lon_range check (lon between -180 and 180),
  shore_normal_deg smallint null
    constraint spots_shore_normal_range check (shore_normal_deg between 0 and 359),
  ridable_dirs jsonb null
    constraint spots_ridable_dirs_array check (ridable_dirs is null or jsonb_typeof(ridable_dirs) = 'array'),
  hazards text null,
  tide_sensitive text not null default 'none'
    constraint spots_tide_sensitive_enum
    check (tide_sensitive in ('none', 'prefer_low', 'prefer_high', 'avoid_low')),
  tide_min_level_cm integer null
    constraint spots_tide_min_level_range check (tide_min_level_cm between -300 and 300),
  rws_station text null,
  season jsonb not null default '[]'::jsonb
    constraint spots_season_array check (jsonb_typeof(season) = 'array'),
  status text null constraint spots_status_enum check (status in ('allowed', 'limited', 'forbidden')),
  level text null
    constraint spots_level_enum check (level in ('beginner', 'intermediate', 'advanced')),
  default_min_kn smallint null
    constraint spots_default_min_kn_range check (default_min_kn between 5 and 40),
  notes text null,
  verified boolean not null default false,
  updated_at timestamptz not null default now(),
  constraint spots_lat_lon_together check ((lat is null) = (lon is null))
);

create table public.forecast_hours (
  spot_id text not null references public.spots (id) on delete cascade,
  model text not null constraint forecast_hours_model_enum check (model in ('knmi', 'icon', 'ecmwf', 'gfs')),
  valid_at timestamptz not null,
  wind_kn real null constraint forecast_hours_wind_nonneg check (wind_kn >= 0),
  gust_kn real null constraint forecast_hours_gust_nonneg check (gust_kn >= 0),
  dir_deg smallint null constraint forecast_hours_dir_range check (dir_deg between 0 and 359),
  fetched_at timestamptz not null,
  primary key (spot_id, model, valid_at)
);
create index forecast_hours_valid_at_idx on public.forecast_hours (valid_at);

create table public.tide_extremes (
  station text not null,
  at timestamptz not null,
  kind text not null constraint tide_extremes_kind_enum check (kind in ('high', 'low')),
  level_cm integer not null,
  fetched_at timestamptz not null,
  primary key (station, at)
);
create index tide_extremes_at_idx on public.tide_extremes (at);

create table public.evaluations (
  spot_id text not null references public.spots (id) on delete cascade,
  valid_at timestamptz not null,
  verdict text not null constraint evaluations_verdict_enum check (verdict in ('go', 'marginal', 'no_go')),
  reasons text[] not null default '{}'
    constraint evaluations_reasons_enum check (
      array_position(reasons, null) is null
      and reasons <@ array[
        'no_data', 'wind_too_light', 'wind_too_strong', 'wind_borderline', 'too_gusty', 'gusty',
        'offshore', 'side_offshore', 'direction_unknown', 'direction_not_ridable', 'dark',
        'season_closed', 'spot_forbidden', 'spot_limited', 'status_unknown', 'tide_too_low',
        'tide_unfavorable', 'tide_unknown', 'low_confidence'
      ]::text[]
    ),
  wind_kn real null,
  gust_kn real null,
  dir_deg smallint null constraint evaluations_dir_range check (dir_deg between 0 and 359),
  dir_class text null constraint evaluations_dir_class_enum
    check (dir_class in ('onshore', 'side_onshore', 'sideshore', 'side_offshore', 'offshore')),
  confidence text null
    constraint evaluations_confidence_enum check (confidence in ('high', 'medium', 'low')),
  tide_level_cm integer null,
  evaluated_at timestamptz not null,
  primary key (spot_id, valid_at),
  -- Hard rule: offshore and side-offshore are never ridable.
  constraint evaluations_offshore_is_no_go
    check (dir_class is null or dir_class not in ('offshore', 'side_offshore') or verdict = 'no_go')
);
create index evaluations_valid_at_idx on public.evaluations (valid_at);

create table public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  weight_kg smallint null constraint profiles_weight_range check (weight_kg between 30 and 200),
  level text null
    constraint profiles_level_enum check (level in ('beginner', 'intermediate', 'advanced')),
  quiver_m2 real[] not null default '{}'
    constraint profiles_quiver_valid check (
      cardinality(quiver_m2) <= 10
      and array_position(quiver_m2, null) is null
      and 3 <= all (quiver_m2)
      and 21 >= all (quiver_m2)
    ),
  default_min_kn smallint null constraint profiles_min_kn_range check (default_min_kn between 5 and 60),
  default_max_kn smallint null constraint profiles_max_kn_range check (default_max_kn between 5 and 60),
  telegram_chat_id text null
    constraint profiles_telegram_chat_id_format check (telegram_chat_id ~ '^-?[0-9]{1,20}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_min_lt_max
    check (default_min_kn is null or default_max_kn is null or default_min_kn < default_max_kn)
);

create table public.favorites (
  user_id uuid not null references auth.users (id) on delete cascade,
  spot_id text not null references public.spots (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, spot_id)
);
create index favorites_spot_id_idx on public.favorites (spot_id);

create table public.alert_rules (
  user_id uuid not null,
  spot_id text not null,
  enabled boolean not null default true,
  min_kn smallint null constraint alert_rules_min_kn_range check (min_kn between 5 and 60),
  max_kn smallint null constraint alert_rules_max_kn_range check (max_kn between 5 and 60),
  -- Hard rule: only ridable direction classes can be selected.
  dir_classes text[] null constraint alert_rules_dir_classes_ridable check (
    dir_classes is null or (
      cardinality(dir_classes) >= 1
      and array_position(dir_classes, null) is null
      and dir_classes <@ array['onshore', 'side_onshore', 'sideshore']::text[]
    )
  ),
  weekdays smallint[] null constraint alert_rules_weekdays_iso check (
    weekdays is null or (
      cardinality(weekdays) >= 1
      and array_position(weekdays, null) is null
      and weekdays <@ array[1, 2, 3, 4, 5, 6, 7]::smallint[]
    )
  ),
  earliest_local time null,
  latest_local time null,
  min_go_hours smallint null constraint alert_rules_min_go_hours_range check (min_go_hours between 1 and 24),
  days_ahead smallint null constraint alert_rules_days_ahead_range check (days_ahead between 0 and 7),
  updated_at timestamptz not null default now(),
  primary key (user_id, spot_id),
  foreign key (user_id, spot_id) references public.favorites (user_id, spot_id) on delete cascade,
  constraint alert_rules_min_lt_max check (min_kn is null or max_kn is null or min_kn < max_kn),
  constraint alert_rules_time_window
    check (earliest_local is null or latest_local is null or earliest_local < latest_local)
);

create table public.alert_state (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  spot_id text not null references public.spots (id) on delete cascade,
  window_start timestamptz not null,
  window_end timestamptz not null,
  status text not null
    constraint alert_state_status_enum check (status in ('active', 'cancelled', 'expired')),
  snapshot jsonb not null constraint alert_state_snapshot_object check (jsonb_typeof(snapshot) = 'object'),
  last_event text null constraint alert_state_last_event_enum
    check (last_event in ('new', 'improved', 'worsened', 'cancelled')),
  last_notified_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint alert_state_window_order check (window_end > window_start)
);
create index alert_state_user_spot_idx on public.alert_state (user_id, spot_id);
create index alert_state_spot_id_idx on public.alert_state (spot_id);
create index alert_state_window_end_idx on public.alert_state (window_end);

create table public.api_usage (
  day date not null,
  source text not null
    constraint api_usage_source_enum check (source in ('open_meteo_forecast', 'open_meteo_marine', 'rws')),
  calls numeric(10, 2) not null default 0 constraint api_usage_calls_nonneg check (calls >= 0),
  requests integer not null default 0 constraint api_usage_requests_nonneg check (requests >= 0),
  primary key (day, source)
);

create table public.ingest_runs (
  id bigint generated always as identity primary key,
  started_at timestamptz not null,
  finished_at timestamptz null,
  status text not null
    constraint ingest_runs_status_enum check (status in ('running', 'ok', 'partial', 'failed')),
  steps jsonb not null default '[]'::jsonb constraint ingest_runs_steps_array check (jsonb_typeof(steps) = 'array'),
  error_summary text null,
  constraint ingest_runs_finished_after_start check (finished_at is null or finished_at >= started_at)
);
create index ingest_runs_started_at_idx on public.ingest_runs (started_at desc);

create trigger spots_set_updated_at before update on public.spots
  for each row execute function public.set_updated_at();
create trigger profiles_set_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();
create trigger alert_rules_set_updated_at before update on public.alert_rules
  for each row execute function public.set_updated_at();
create trigger alert_state_set_updated_at before update on public.alert_state
  for each row execute function public.set_updated_at();

-- Create a profile row for every new auth user (pattern from Supabase docs).
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (user_id) values (new.id) on conflict (user_id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- Backfill: users that existed before this migration also get a profile (no-op on a fresh stack).
insert into public.profiles (user_id)
select id from auth.users
on conflict (user_id) do nothing;
