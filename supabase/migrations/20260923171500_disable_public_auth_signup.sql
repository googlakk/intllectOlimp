-- Defense in depth for the closed beta. Public Auth signup can populate user
-- metadata, but only the service-role Admin API can populate app metadata.

create or replace function private.enforce_intellect_auth_provisioning()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if coalesce(new.raw_app_meta_data ->> 'provisioned_by', '') <> 'intellect-backend' then
    raise exception 'Public registration is disabled for this project'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

drop trigger if exists enforce_intellect_auth_provisioning on auth.users;
create trigger enforce_intellect_auth_provisioning
before insert on auth.users
for each row execute function private.enforce_intellect_auth_provisioning();

revoke all on function private.enforce_intellect_auth_provisioning() from public, anon, authenticated;
