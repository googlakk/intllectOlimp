-- GoTrue inserts auth.users before applying Admin API app metadata and email
-- confirmation. Permit only the platform's non-routable identities here.
-- Application access still requires an active, backend-created public.profile.

create or replace function private.enforce_intellect_auth_provisioning()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.email like '%@users.intellect.local'
     and coalesce(new.raw_user_meta_data ->> 'login_name', '') <> ''
     and coalesce(new.raw_user_meta_data ->> 'display_name', '') <> ''
     and coalesce(new.raw_user_meta_data ->> 'role', '') in ('admin', 'teacher', 'student') then
    return new;
  end if;

  raise exception 'Public registration is disabled for this project'
    using errcode = '42501';
end;
$$;

revoke all on function private.enforce_intellect_auth_provisioning() from public, anon, authenticated;
