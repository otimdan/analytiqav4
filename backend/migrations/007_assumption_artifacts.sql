-- ============================================================
-- Analytika — Migration 007: allow assumption-check artifacts
-- Run in the Supabase SQL editor. Requires 001..006 first.
--
-- Guided mode logs an assumption-check artifact (the PASS/FAIL table that backs
-- the "Assumption Checks" rail stage) before running a test. The artifacts table
-- CHECK constraints from migration 001 enumerated the allowed stage/type values
-- and did NOT include these, so the insert 400s and the guided pause produced an
-- empty reply. This widens both constraints.
-- ============================================================

alter table artifacts drop constraint if exists artifacts_stage_check;
alter table artifacts add constraint artifacts_stage_check
  check (stage in (
    'data_preparation','descriptive','inferential','visualisation',
    'interpretation','assumption_checks'
  ));

alter table artifacts drop constraint if exists artifacts_artifact_type_check;
alter table artifacts add constraint artifacts_artifact_type_check
  check (artifact_type in (
    'chart','table','test_result','cleaned_dataset','summary',
    'derived_column','report','assumption_check'
  ));
