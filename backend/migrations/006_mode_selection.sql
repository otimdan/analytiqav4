-- ============================================================
-- Analytika — Migration 006: explicit task mode (explore | guided)
-- Run in the Supabase SQL editor. Requires 001..005 first.
--
-- Replaces per-message mode inference with an explicit mode chosen once, up
-- front, and fixed immutably on the task at creation. Two modes:
--   'explore' — free-form chat with the data (no step rail)
--   'guided'  — staged quantitative pipeline (left step rail)
--
-- The legacy booleans `suggestion_mode` / `hypothesis_on_record` are NOT dropped
-- here (that would be a destructive change). They are simply no longer read or
-- written by the app after this ships; a later cleanup migration can remove them.
-- ============================================================

-- NOTE: `mode` is a Postgres ordered-set aggregate function name. It works fine
-- as a column, and `select *` returns it, but do NOT reference a bare `mode`
-- token in an explicit PostgREST select list (e.g. select=id,mode) — PostgREST
-- parses it as the aggregate and the request 400s. Read it via `select *`.
alter table sessions
  add column if not exists mode text not null default 'explore'
  check (mode in ('explore', 'guided'));

-- Backfill existing sessions: anything that already had a research question on
-- record was effectively "guided" (its step rail was showing), so keep it in
-- guided. Everything else becomes free-form 'explore' (the default), which
-- matches how those sessions already behaved.
update sessions set mode = 'guided' where hypothesis_on_record = true;
