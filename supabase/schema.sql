-- ===========================================================================
-- Setara Production Budget — Supabase schema
--
-- Paste this whole file into the Supabase SQL editor and run it. It is
-- idempotent: running it twice changes nothing, so it is safe against the
-- tables that already exist.
--
-- Kept in the repo because until now this schema lived only in the dashboard.
-- A Supabase project that is ever recreated, or a second environment, had
-- nothing to rebuild from.
-- ===========================================================================

-- --------------------------------------------------------------------------
-- Productions: one row per saved budget. `snapshot` is exactly what the app's
-- snapshot() returns, so the client and the column never drift apart.
-- --------------------------------------------------------------------------
create table if not exists public.productions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  name        text not null default 'Untitled production',
  snapshot    jsonb not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- The app reads "my productions, newest first" and nothing else.
create index if not exists productions_user_updated_idx
  on public.productions (user_id, updated_at desc);

-- The app never sends updated_at, and pullProductions orders by it - without
-- this the "most recent" list is really "oldest created" and never changes.
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists productions_touch on public.productions;
create trigger productions_touch
  before update on public.productions
  for each row execute function public.touch_updated_at();

-- --------------------------------------------------------------------------
-- Admins: the accounts that may READ everything.
--
-- Read only, deliberately. Oversight is being able to see what a client has;
-- it is not being able to alter their budget without them knowing. Write
-- policies stay owner-only, so an admin can never quietly change a number in
-- somebody's bid.
-- --------------------------------------------------------------------------
create table if not exists public.admins (
  user_id  uuid primary key references auth.users(id) on delete cascade,
  added_at timestamptz not null default now()
);
alter table public.admins enable row level security;

-- Nobody queries this table from the browser; is_admin() below is the only
-- reader that matters, and it is SECURITY DEFINER so an ordinary account can
-- be *checked* against the list without being able to *read* the list.
drop policy if exists "admins see their own row" on public.admins;
create policy "admins see their own row" on public.admins
  for select to authenticated using (user_id = auth.uid());

create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.admins a where a.user_id = auth.uid());
$$;
revoke all on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

-- --------------------------------------------------------------------------
-- Row-level security.
--
-- This is what makes the app safe to ship with a key in the page: the anon key
-- identifies the project, it does not grant anything. Every rule below is
-- enforced by Postgres, so a signed-out visitor is refused by the DATABASE and
-- not merely by a screen the browser could be told to skip.
-- --------------------------------------------------------------------------
alter table public.productions enable row level security;

drop policy if exists "read own productions"   on public.productions;
drop policy if exists "insert own productions" on public.productions;
drop policy if exists "update own productions" on public.productions;
drop policy if exists "delete own productions" on public.productions;

-- Read: your own, plus everything if you are an admin.
create policy "read own productions" on public.productions
  for select to authenticated
  using (user_id = auth.uid() or public.is_admin());

-- Write: yours alone, admin or not.
create policy "insert own productions" on public.productions
  for insert to authenticated
  with check (user_id = auth.uid());

create policy "update own productions" on public.productions
  for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy "delete own productions" on public.productions
  for delete to authenticated
  using (user_id = auth.uid());

-- --------------------------------------------------------------------------
-- Make yourself an admin.
--
-- There is no such thing as an admin ACCOUNT here - only an admin row pointing
-- at an ordinary one. Promote the login you already use; nothing about it
-- changes, it simply gains read access to everything. Demote by deleting the
-- row. Nobody has to make a second account, and nobody should: a login you use
-- daily is a login you notice losing.
--
-- 1. See what accounts exist and pick yours.
-- select id, email, created_at, last_sign_in_at
--   from auth.users order by created_at;

-- 2. Promote it. Put YOUR address in - whatever you actually signed up with,
--    which may not be the example this file shipped with. Matching is
--    case-insensitive because the address you type is rarely the case it was
--    stored in.
-- insert into public.admins (user_id)
-- select id from auth.users where lower(email) = lower('admin@users.setara.ai')
-- on conflict (user_id) do nothing;

-- 3. Confirm it took. Zero rows back means step 2 matched no account - almost
--    always the address, occasionally an account that was never created.
-- select u.email, a.added_at
--   from public.admins a join auth.users u on u.id = a.user_id;

-- To demote:
-- delete from public.admins
--  where user_id = (select id from auth.users where lower(email) = lower('admin@users.setara.ai'));

-- --------------------------------------------------------------------------
-- The original screenplay files live in Storage, and their setup is in its own
-- file: supabase/storage.sql. It is separate because creating a policy on
-- storage.objects can be refused depending on the project (that table is owned
-- by supabase_storage_admin), and when it is, it aborts the rest of the run -
-- which is exactly how the bucket came to be missing while everything above it
-- had been created. Run this file first, then that one.
-- --------------------------------------------------------------------------

-- ===========================================================================
-- CHECK IT WORKED. Run this block after the one above; it changes nothing.
-- ===========================================================================

-- 1. Both new objects should be listed.
-- select 'admins table' as thing, to_regclass('public.admins') is not null as ok
-- union all
-- select 'is_admin()', to_regproc('public.is_admin') is not null;

-- 2. Every policy on productions. If a policy you made earlier is still here
--    under a DIFFERENT name, it is still in force - policies are OR'd together,
--    so an old permissive one is not replaced by the strict one above, it is
--    added to it. Drop anything here you did not intend.
-- select policyname, cmd, qual, with_check
--   from pg_policies where schemaname = 'public' and tablename = 'productions'
--  order by cmd, policyname;

-- 3. Are you actually an admin? Run while signed in as yourself.
-- select public.is_admin();

-- --------------------------------------------------------------------------
-- WHO IS USING IT. No new tables needed - Supabase already records this.
-- --------------------------------------------------------------------------
-- select u.email                as client,
--        u.created_at           as joined,
--        u.last_sign_in_at      as last_seen,
--        count(p.id)            as productions,
--        max(p.updated_at)      as last_worked
--   from auth.users u
--   left join public.productions p on p.user_id = u.id
--  group by u.id, u.email, u.created_at, u.last_sign_in_at
--  order by last_seen desc nulls last;

-- --------------------------------------------------------------------------
-- Every stored document, with whose it is and which production it belongs to.
-- The Storage browser in the dashboard also shows all of these directly - it
-- runs as the service role, so it ignores the policies above entirely.
-- --------------------------------------------------------------------------
-- select u.email                      as client,
--        p.name                       as production,
--        p.snapshot ->> 'sourceName'  as filename,
--        o.name                       as storage_path,
--        pg_size_pretty((o.metadata ->> 'size')::bigint) as size,
--        o.created_at
--   from public.productions p
--   join auth.users u on u.id = p.user_id
--   left join storage.objects o
--          on o.bucket_id = 'scripts' and o.name = p.snapshot ->> 'sourceFile'
--  where p.snapshot ->> 'sourceFile' is not null
--  order by o.created_at desc;

-- --------------------------------------------------------------------------
-- What an admin can see, once enrolled. Paste into the SQL editor.
-- --------------------------------------------------------------------------
-- select u.email                                   as client,
--        p.name                                    as production,
--        p.snapshot -> 'sourceName'                as script,
--        length(p.snapshot ->> 'scriptText')       as script_chars,
--        p.updated_at
--   from public.productions p
--   join auth.users u on u.id = p.user_id
--  order by p.updated_at desc;
