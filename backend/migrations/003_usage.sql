-- ============================================================================
-- Migration 003 — Usage metering & plans (for tiered caps).
-- Run in Supabase → SQL Editor. Safe to run once.
-- Requires migration 002 (auth) first. Backend uses service_role (bypasses RLS).
-- ============================================================================

-- ── profiles: one row per user, holds their plan ────────────────────────────
create table if not exists public.profiles (
  id         uuid primary key references auth.users(id) on delete cascade,
  plan       text not null default 'free',
  created_at timestamptz not null default now()
);

-- ── usage_events: append-only, one row per metered analysis ─────────────────
create table if not exists public.usage_events (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  kind       text not null,                    -- e.g. 'exploratory' | 'confirmatory'
  created_at timestamptz not null default now()
);
create index if not exists usage_events_user_created_idx
  on public.usage_events(user_id, created_at);

-- ── auto-create a profile on signup ─────────────────────────────────────────
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id) values (new.id) on conflict (id) do nothing;
  return new;
end; $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── backfill profiles for users who signed up before this migration ─────────
insert into public.profiles (id)
  select id from auth.users on conflict (id) do nothing;

-- ── RLS (defense-in-depth; backend service_role bypasses it) ────────────────
alter table public.profiles     enable row level security;
alter table public.usage_events enable row level security;

drop policy if exists "own profile" on public.profiles;
create policy "own profile" on public.profiles
  for select using (auth.uid() = id);

drop policy if exists "own usage" on public.usage_events;
create policy "own usage" on public.usage_events
  for select using (auth.uid() = user_id);
