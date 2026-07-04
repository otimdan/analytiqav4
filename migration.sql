-- ============================================================
-- Analytika — Supabase SQL Migration
-- Run this in the Supabase SQL editor in one go.
-- ============================================================

create extension if not exists "pgcrypto";

create table if not exists sessions (
  id                    uuid primary key default gen_random_uuid(),
  created_at            timestamptz not null default now(),
  last_active_at        timestamptz not null default now(),
  dataset_filename      text,
  dataset_csv           text,
  sandbox_id            text,
  profile               jsonb,
  hypothesis_text       text,
  hypothesis_columns    jsonb,
  pending_candidate     text,
  hypothesis_on_record  boolean not null default false,
  suggestion_mode       boolean not null default false,
  feedback_count        integer not null default 0
);

create index if not exists sessions_last_active_at_idx on sessions (last_active_at);

create table if not exists messages (
  id                          uuid primary key default gen_random_uuid(),
  session_id                  uuid not null references sessions(id) on delete cascade,
  created_at                  timestamptz not null default now(),
  role                        text not null check (role in ('user', 'assistant')),
  content                     text not null,
  regime                      text,
  classification_confidence   text,
  metadata                    jsonb
);

create index if not exists messages_session_id_created_at_idx on messages (session_id, created_at);

create table if not exists artifacts (
  id                  uuid primary key default gen_random_uuid(),
  session_id          uuid not null references sessions(id) on delete cascade,
  message_id          uuid references messages(id) on delete set null,
  created_at          timestamptz not null default now(),
  stage               text not null check (stage in ('data_preparation','descriptive','inferential','visualisation','interpretation')),
  artifact_type       text not null check (artifact_type in ('chart','table','test_result','cleaned_dataset','summary','derived_column','report')),
  content             jsonb not null default '{}',
  code_used           text,
  superseded          boolean not null default false,
  superseded_by       uuid references artifacts(id) on delete set null,
  variables_involved  jsonb
);

create index if not exists artifacts_session_stage_superseded_idx on artifacts (session_id, stage, superseded);
create index if not exists artifacts_session_type_superseded_idx on artifacts (session_id, artifact_type, superseded);
create index if not exists artifacts_session_created_at_idx on artifacts (session_id, created_at) where code_used is not null;

create table if not exists feedback (
  id            uuid primary key default gen_random_uuid(),
  session_id    uuid not null references sessions(id) on delete cascade,
  message_id    uuid not null references messages(id) on delete cascade,
  created_at    timestamptz not null default now(),
  rating        integer not null check (rating >= 1 and rating <= 5),
  comment       text
);

create index if not exists feedback_session_id_idx on feedback (session_id);

create table if not exists hypothesis_candidates (
  id                  uuid primary key default gen_random_uuid(),
  session_id          uuid not null references sessions(id) on delete cascade,
  created_at          timestamptz not null default now(),
  candidate_text      text not null,
  matched_columns     jsonb,
  source_message_id   uuid references messages(id) on delete set null,
  status              text not null default 'pending' check (status in ('pending', 'accepted', 'declined'))
);

create index if not exists hypothesis_candidates_session_status_idx on hypothesis_candidates (session_id, status);

alter table sessions               enable row level security;
alter table messages               enable row level security;
alter table artifacts              enable row level security;
alter table feedback               enable row level security;
alter table hypothesis_candidates  enable row level security;

create policy "service role full access on sessions" on sessions for all using (true) with check (true);
create policy "service role full access on messages" on messages for all using (true) with check (true);
create policy "service role full access on artifacts" on artifacts for all using (true) with check (true);
create policy "service role full access on feedback" on feedback for all using (true) with check (true);
create policy "service role full access on hypothesis_candidates" on hypothesis_candidates for all using (true) with check (true);

-- Verify: select table_name from information_schema.tables where table_schema = 'public' order by table_name;
