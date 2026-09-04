-- ===========================================================================
-- Setara Production Budget - the trail
--
-- Run AFTER schema.sql (it uses public.is_admin()).
--
-- productions holds one row per budget and UPDATES it, so it is always the
-- current state and never the story. This is the story: an append-only row
-- each time a bid meaningfully moves, so "Acme opened Sky's End at $340k,
-- pushed the ratio to 6:1, watched it reach $520k, settled at $410k" is a
-- query rather than a thing nobody can ever know.
--
-- The figures are copied in, not joined to. A bid is only meaningful next to
-- the rates and levers that produced it, and those change - a row that had to
-- join back to productions would report today's assumptions against last
-- week's number.
-- ===========================================================================

create table if not exists public.production_events (
  id               bigint generated always as identity primary key,
  user_id          uuid not null references auth.users(id) on delete cascade,

  -- SET NULL, not CASCADE. Deleting a production should not erase the record
  -- of what it once cost - that is exactly the moment the trail earns its
  -- keep. The name is copied for the same reason: it has to still read as
  -- something after the row it pointed at is gone.
  production_id    uuid references public.productions(id) on delete set null,
  production_name  text,

  at               timestamptz not null default now(),
  kind             text not null,          -- 'upload' | 'change' | 'export'

  -- what the bid was
  bid              numeric,
  crew             numeric,
  generation       numeric,
  contingency      numeric,
  runtime_minutes  numeric,
  weeks            numeric,

  -- and why it was that, so a jump has an explanation next to it
  levers           jsonb
);

create index if not exists production_events_user_at_idx
  on public.production_events (user_id, at desc);
create index if not exists production_events_production_idx
  on public.production_events (production_id, at);

alter table public.production_events enable row level security;

drop policy if exists "insert own events" on public.production_events;
drop policy if exists "read own events"   on public.production_events;

-- Append-only, deliberately. There is no update or delete policy at all, so
-- nothing reachable from the browser can rewrite or quietly prune the trail -
-- which is the one property that makes it worth having. Removing an account
-- still removes its rows, through the cascade above.
create policy "insert own events" on public.production_events
  for insert to authenticated
  with check (user_id = auth.uid());

create policy "read own events" on public.production_events
  for select to authenticated
  using (user_id = auth.uid() or public.is_admin());

-- ===========================================================================
-- READING IT. Uncomment what you need.
-- ===========================================================================

-- Everything that happened, newest first.
-- select u.email as client, e.production_name, e.kind, e.at,
--        e.bid, e.runtime_minutes, e.weeks, e.levers
--   from public.production_events e join auth.users u on u.id = e.user_id
--  order by e.at desc limit 200;

-- One production's bid, moving. This is the "numbers moving" view.
-- select e.at, e.kind, e.bid, e.runtime_minutes, e.weeks,
--        e.bid - lag(e.bid) over (order by e.at) as moved_by,
--        e.levers
--   from public.production_events e
--  where e.production_name = 'Sky''s End'
--  order by e.at;

-- Where each client landed, against where they started.
-- select u.email as client, e.production_name,
--        min(e.at) as first_seen, max(e.at) as last_seen, count(*) as events,
--        (array_agg(e.bid order by e.at))[1]              as opened_at,
--        (array_agg(e.bid order by e.at desc))[1]         as latest,
--        min(e.bid) as lowest, max(e.bid) as highest
--   from public.production_events e join auth.users u on u.id = e.user_id
--  group by u.email, e.production_name
--  order by max(e.at) desc;

-- How busy it has been, by day.
-- select date_trunc('day', at) as day, count(*) filter (where kind = 'upload') as uploads,
--        count(*) filter (where kind = 'change') as changes,
--        count(*) filter (where kind = 'export') as exports,
--        count(distinct user_id) as clients
--   from public.production_events group by 1 order by 1 desc;
