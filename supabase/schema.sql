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
-- Make yourself an admin. Change the address to your own account first; it is
-- the one you created under Authentication -> Users.
-- --------------------------------------------------------------------------
-- insert into public.admins (user_id)
-- select id from auth.users where email = 'matt@users.setara.ai'
-- on conflict (user_id) do nothing;

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
