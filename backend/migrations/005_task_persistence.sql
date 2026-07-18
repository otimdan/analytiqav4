-- ============================================================
-- Analytika — Migration 005: task persistence
-- Run in the Supabase SQL editor. Requires 001..004 first.
--
-- Makes each session a durable "task": messages persist their run-code
-- (executions) AND their charts (images), and sessions carry a title so the
-- left-nav "recents" list can name them.
-- ============================================================

-- Chart images shown in a message, persisted so the conversation restores its
-- visuals on reload. Shape: [{ "src": "<base64 png>", "caption": "..." }, ...]
alter table messages add column if not exists images jsonb;

-- Run-code / output blocks (may already exist from an earlier hotfix).
alter table messages add column if not exists executions jsonb;

-- Human-friendly task title for the sidebar (defaults to the dataset filename).
alter table sessions add column if not exists title text;

-- Backfill titles for existing sessions from their dataset filename.
update sessions set title = dataset_filename where title is null;
