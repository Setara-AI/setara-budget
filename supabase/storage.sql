-- ===========================================================================
-- Setara Production Budget - Storage for the original screenplay files
--
-- Run this AFTER schema.sql (it depends on public.is_admin()).
--
-- It is a separate file because creating a policy on storage.objects can be
-- refused - that table is owned by supabase_storage_admin, not by the role the
-- SQL editor uses - and a refusal aborts the whole run. On its own, a failure
-- here costs nothing that was already working.
--
-- If STEP 1 fails: make the bucket in the dashboard instead. Storage -> New
-- bucket, name it exactly `scripts`, leave Public OFF, set the size limit to
-- 25 MB. Then run STEP 2 on its own.
--
-- If STEP 2 fails with "must be owner of table objects": add the same four
-- policies through the dashboard instead - Storage -> Policies -> New policy
-- on storage.objects - using the USING / WITH CHECK expressions below verbatim.
-- ===========================================================================

-- --------------------------------------------------------------------------
-- STEP 1 - the bucket.
--
-- Private. Nothing in it is servable by URL: reading a file means asking for a
-- short-lived signed link, and only the owner or an admin may ask.
-- --------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit)
values ('scripts', 'scripts', false, 26214400)      -- 25 MB; a script PDF is 1-6
on conflict (id) do update
  set public = false, file_size_limit = excluded.file_size_limit;

-- --------------------------------------------------------------------------
-- STEP 2 - who may touch what.
--
-- The app writes files as `<user id>/<uuid>.<ext>`, so the first path segment
-- is the owner and that is what every policy below keys on.
-- --------------------------------------------------------------------------
drop policy if exists "read own scripts"   on storage.objects;
drop policy if exists "write own scripts"  on storage.objects;
drop policy if exists "delete own scripts" on storage.objects;

-- Read: your own, plus everything if you are an admin - the same rule the
-- productions table uses, so a file and its budget never disagree about who
-- may see them.
create policy "read own scripts" on storage.objects
  for select to authenticated
  using (bucket_id = 'scripts'
         and ((storage.foldername(name))[1] = auth.uid()::text or public.is_admin()));

-- Write and delete: yours alone, admin or not. An admin can read the document a
-- client bid against; an admin cannot replace it with a different one.
create policy "write own scripts" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'scripts'
              and (storage.foldername(name))[1] = auth.uid()::text);

create policy "delete own scripts" on storage.objects
  for delete to authenticated
  using (bucket_id = 'scripts'
         and (storage.foldername(name))[1] = auth.uid()::text);

-- ===========================================================================
-- CHECK IT WORKED. Read-only; changes nothing.
-- ===========================================================================

-- The bucket exists and is PRIVATE. public must be false - a public bucket
-- serves every screenplay in it to anyone holding the URL.
-- select id, public, file_size_limit from storage.buckets where id = 'scripts';

-- All three policies are present.
-- select policyname, cmd from pg_policies
--  where schemaname = 'storage' and tablename = 'objects'
--    and policyname like '%own scripts%' order by cmd;
