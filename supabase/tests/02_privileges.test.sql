-- Exact privileges per table and role, column privileges on profiles, function privileges, policies.
begin;
create extension if not exists pgtap with schema extensions;

select plan(54);

select table_privs_are('public'::name, 'spots'::name, 'anon'::name, array['SELECT']::name[], 'anon privileges on spots');
select table_privs_are('public'::name, 'spots'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated privileges on spots');
select table_privs_are('public'::name, 'spots'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on spots');

select table_privs_are('public'::name, 'forecast_hours'::name, 'anon'::name, array['SELECT']::name[], 'anon privileges on forecast_hours');
select table_privs_are('public'::name, 'forecast_hours'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated privileges on forecast_hours');
select table_privs_are('public'::name, 'forecast_hours'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on forecast_hours');

select table_privs_are('public'::name, 'tide_extremes'::name, 'anon'::name, array['SELECT']::name[], 'anon privileges on tide_extremes');
select table_privs_are('public'::name, 'tide_extremes'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated privileges on tide_extremes');
select table_privs_are('public'::name, 'tide_extremes'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on tide_extremes');

select table_privs_are('public'::name, 'evaluations'::name, 'anon'::name, array['SELECT']::name[], 'anon privileges on evaluations');
select table_privs_are('public'::name, 'evaluations'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated privileges on evaluations');
select table_privs_are('public'::name, 'evaluations'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on evaluations');

select table_privs_are('public'::name, 'profiles'::name, 'anon'::name, '{}'::name[], 'anon privileges on profiles');
select table_privs_are('public'::name, 'profiles'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated privileges on profiles');
select table_privs_are('public'::name, 'profiles'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on profiles');

select table_privs_are('public'::name, 'favorites'::name, 'anon'::name, '{}'::name[], 'anon privileges on favorites');
select table_privs_are('public'::name, 'favorites'::name, 'authenticated'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated privileges on favorites');
select table_privs_are('public'::name, 'favorites'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on favorites');

select table_privs_are('public'::name, 'alert_rules'::name, 'anon'::name, '{}'::name[], 'anon privileges on alert_rules');
select table_privs_are('public'::name, 'alert_rules'::name, 'authenticated'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'authenticated privileges on alert_rules');
select table_privs_are('public'::name, 'alert_rules'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on alert_rules');

select table_privs_are('public'::name, 'alert_state'::name, 'anon'::name, '{}'::name[], 'anon privileges on alert_state');
select table_privs_are('public'::name, 'alert_state'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated privileges on alert_state');
select table_privs_are('public'::name, 'alert_state'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on alert_state');

select table_privs_are('public'::name, 'api_usage'::name, 'anon'::name, '{}'::name[], 'anon privileges on api_usage');
select table_privs_are('public'::name, 'api_usage'::name, 'authenticated'::name, '{}'::name[], 'authenticated privileges on api_usage');
select table_privs_are('public'::name, 'api_usage'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on api_usage');

select table_privs_are('public'::name, 'ingest_runs'::name, 'anon'::name, '{}'::name[], 'anon privileges on ingest_runs');
select table_privs_are('public'::name, 'ingest_runs'::name, 'authenticated'::name, '{}'::name[], 'authenticated privileges on ingest_runs');
select table_privs_are('public'::name, 'ingest_runs'::name, 'service_role'::name, array['DELETE', 'INSERT', 'SELECT', 'UPDATE']::name[], 'service_role privileges on ingest_runs');

select column_privs_are('public'::name, 'profiles'::name, 'weight_kg'::name, 'authenticated'::name, array['SELECT', 'UPDATE']::name[], 'authenticated may select and update profiles.weight_kg');
select column_privs_are('public'::name, 'profiles'::name, 'level'::name, 'authenticated'::name, array['SELECT', 'UPDATE']::name[], 'authenticated may select and update profiles.level');
select column_privs_are('public'::name, 'profiles'::name, 'quiver_m2'::name, 'authenticated'::name, array['SELECT', 'UPDATE']::name[], 'authenticated may select and update profiles.quiver_m2');
select column_privs_are('public'::name, 'profiles'::name, 'default_min_kn'::name, 'authenticated'::name, array['SELECT', 'UPDATE']::name[], 'authenticated may select and update profiles.default_min_kn');
select column_privs_are('public'::name, 'profiles'::name, 'default_max_kn'::name, 'authenticated'::name, array['SELECT', 'UPDATE']::name[], 'authenticated may select and update profiles.default_max_kn');
select column_privs_are('public'::name, 'profiles'::name, 'user_id'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated may only select profiles.user_id');
select column_privs_are('public'::name, 'profiles'::name, 'created_at'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated may only select profiles.created_at');
select column_privs_are('public'::name, 'profiles'::name, 'updated_at'::name, 'authenticated'::name, array['SELECT']::name[], 'authenticated may only select profiles.updated_at');

select function_privs_are('public'::name, 'handle_new_user'::name, '{}'::name[], 'anon'::name, '{}'::name[], 'anon cannot execute handle_new_user');
select function_privs_are('public'::name, 'handle_new_user'::name, '{}'::name[], 'authenticated'::name, '{}'::name[], 'authenticated cannot execute handle_new_user');
select function_privs_are('public'::name, 'handle_new_user'::name, '{}'::name[], 'service_role'::name, '{}'::name[], 'service_role cannot execute handle_new_user');
select function_privs_are('public'::name, 'set_updated_at'::name, '{}'::name[], 'anon'::name, '{}'::name[], 'anon cannot execute set_updated_at');
select function_privs_are('public'::name, 'set_updated_at'::name, '{}'::name[], 'authenticated'::name, '{}'::name[], 'authenticated cannot execute set_updated_at');
select function_privs_are('public'::name, 'set_updated_at'::name, '{}'::name[], 'service_role'::name, '{}'::name[], 'service_role cannot execute set_updated_at');

select policies_are('public'::name, 'spots'::name, array['spots_read']::name[], 'policies on spots');
select policies_are('public'::name, 'forecast_hours'::name, array['forecast_hours_read']::name[], 'policies on forecast_hours');
select policies_are('public'::name, 'tide_extremes'::name, array['tide_extremes_read']::name[], 'policies on tide_extremes');
select policies_are('public'::name, 'evaluations'::name, array['evaluations_read']::name[], 'policies on evaluations');
select policies_are('public'::name, 'profiles'::name, array['profiles_select_own', 'profiles_update_own']::name[], 'policies on profiles');
select policies_are('public'::name, 'favorites'::name, array['favorites_select_own', 'favorites_insert_own', 'favorites_update_own', 'favorites_delete_own']::name[], 'policies on favorites');
select policies_are('public'::name, 'alert_rules'::name, array['alert_rules_select_own', 'alert_rules_insert_own', 'alert_rules_update_own', 'alert_rules_delete_own']::name[], 'policies on alert_rules');
select policies_are('public'::name, 'alert_state'::name, array['alert_state_select_own']::name[], 'policies on alert_state');
select policies_are('public'::name, 'api_usage'::name, '{}'::name[], 'policies on api_usage');
select policies_are('public'::name, 'ingest_runs'::name, '{}'::name[], 'policies on ingest_runs');

select * from finish();
rollback;
