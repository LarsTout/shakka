-- Self-service account deletion (WP-23). Deleting the auth.users row removes every row that belongs
-- to the account through the existing on-delete-cascade foreign keys: profiles, favorites (and with
-- them alert_rules), alert_state, push_subscriptions, and the sessions the user organizes together
-- with the RSVPs on those sessions. Anonymous RSVPs the user made elsewhere are not linked to the
-- account and are not touched.

create function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
begin
  if v_uid is null then
    raise sqlstate 'PT401' using message = 'not_authenticated';
  end if;
  delete from auth.users where id = v_uid;
end;
$$;

revoke all on function public.delete_my_account() from public, anon, authenticated, service_role;
grant execute on function public.delete_my_account() to authenticated;
