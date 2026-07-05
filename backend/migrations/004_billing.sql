-- ============================================================================
-- Migration 004 — Billing (Dodo Payments) fields on profiles.
-- Run in Supabase → SQL Editor. Requires migration 003. Safe to run once.
-- ============================================================================

alter table public.profiles
  add column if not exists dodo_customer_id      text,
  add column if not exists dodo_subscription_id  text,
  add column if not exists subscription_status   text;

create index if not exists profiles_dodo_subscription_idx
  on public.profiles(dodo_subscription_id);
create index if not exists profiles_dodo_customer_idx
  on public.profiles(dodo_customer_id);
