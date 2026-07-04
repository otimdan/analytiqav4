-- ============================================================================
-- Migration 002 — Auth: associate data with users + row-level security.
-- Run in Supabase → SQL Editor. Safe to run once.
--
-- IMPORTANT: The backend must connect with the **service_role** key
-- (SUPABASE_KEY in backend/.env). The service role bypasses RLS, so Part B does
-- NOT break the backend — it only guards against direct anon-key access. If your
-- SUPABASE_KEY is the *anon* key, run Part A only and switch the backend to the
-- service_role key before enabling Part B.
-- ============================================================================

-- ── Part A (REQUIRED): link sessions to auth.users ──────────────────────────
alter table public.sessions
  add column if not exists user_id uuid references auth.users(id) on delete cascade;

create index if not exists sessions_user_id_idx on public.sessions(user_id);


-- ── Part B (RECOMMENDED): row-level security, defense-in-depth ──────────────
alter table public.sessions               enable row level security;
alter table public.messages               enable row level security;
alter table public.artifacts              enable row level security;
alter table public.feedback               enable row level security;
alter table public.hypothesis_candidates  enable row level security;

drop policy if exists "own sessions" on public.sessions;
create policy "own sessions" on public.sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own messages" on public.messages;
create policy "own messages" on public.messages
  for all using (exists (
    select 1 from public.sessions s where s.id = messages.session_id and s.user_id = auth.uid()
  ));

drop policy if exists "own artifacts" on public.artifacts;
create policy "own artifacts" on public.artifacts
  for all using (exists (
    select 1 from public.sessions s where s.id = artifacts.session_id and s.user_id = auth.uid()
  ));

drop policy if exists "own feedback" on public.feedback;
create policy "own feedback" on public.feedback
  for all using (exists (
    select 1 from public.sessions s where s.id = feedback.session_id and s.user_id = auth.uid()
  ));

drop policy if exists "own candidates" on public.hypothesis_candidates;
create policy "own candidates" on public.hypothesis_candidates
  for all using (exists (
    select 1 from public.sessions s where s.id = hypothesis_candidates.session_id and s.user_id = auth.uid()
  ));
