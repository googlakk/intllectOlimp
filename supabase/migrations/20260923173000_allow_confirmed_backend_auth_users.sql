-- GoTrue's Admin API may populate app metadata after auth.users BEFORE INSERT
-- triggers run. Keep public signup closed while allowing the backend's confirmed,
-- private-domain accounts to be provisioned through the Admin API.

create or replace function private.enforce_intellect_auth_provisioning()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if coalesce(new.raw_app_meta_data ->> 'provisioned_by', '') = 'intellect-backend' then
    return new;
  end if;

  if new.email like '%@users.intellect.local'
     and new.email_confirmed_at is not null
     and coalesce(new.raw_user_meta_data ->> 'login_name', '') <> '' then
    return new;
  end if;

  raise exception 'Public registration is disabled for this project'
    using errcode = '42501';
end;
$$;

revoke all on function private.enforce_intellect_auth_provisioning() from public, anon, authenticated;
