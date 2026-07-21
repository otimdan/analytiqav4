export type TaskMode = "explore" | "guided"

export interface SessionState {
  session_id: string
  mode: TaskMode
  hypothesis_text: string | null
  dataset_filename: string | null
  profile_summary: ProfileSummary | null
  artifact_count: number
  dataset_ready: boolean
}

export interface ProfileSummary {
  row_count: number
  column_count: number
  summary: string
}

export interface UploadResponse {
  session_id: string
  filename: string
  rows: number
  columns: number
  column_names: string[]
  profile_summary: ProfileSummary
  // What ingestion had to infer or change (a guessed encoding, dropped
  // merged-cell header rows). Optional: older backends omit the field.
  ingest_notes?: string[]
}

export type NudgeStyle = "directive" | "soft"

export type MessageRole = "user" | "assistant"

export type ChunkType =
  | "text" | "image" | "disambiguation" | "confirmation_prompt"
  | "guidance_suggestion" | "cached_artifact" | "report"
  | "meta" | "error" | "done" | "code_execution" | "verification"

export interface CodeExecution {
  code: string
  output: string
}

export interface ChartImage {
  src: string
  caption?: string
}

export interface NextAction {
  label: string
  query: string
}

export interface UsageSummary {
  plan: string
  used: number
  limit: number
  remaining: number
}

export interface Plan {
  id: string
  name: string
  price_usd: number
  monthly_analyses: number
  is_paid: boolean
  current: boolean
}

export interface StreamChunk {
  type: ChunkType
  content?: string
  caption?: string
  regime?: string
  artifact_id?: string
  show_feedback?: boolean
  code?: string
  output?: string
  message_id?: string
  prompt?: { question: string; options: string[] }
  is_hypothesis_candidate?: boolean
  next_action?: NextAction | null
  nudge_style?: NudgeStyle
  engine_verified?: boolean
  test_display_name?: string
  report?: { markdown: string; filename: string; artifact_count: number; stages_covered: string[]; latex?: string; latex_filename?: string }
  route_to?: string
  shortcut?: "profile" | "cached_artifact"
}

export interface Message {
  id: string
  role: MessageRole
  content: string
  images: ChartImage[]
  regime?: string
  artifact_id?: string
  show_feedback?: boolean
  // `original_message` is the question that triggered the prompt. The answer is
  // sent as a new message, so without it "Run a test" arrives naming no columns.
  disambiguation?: { question: string; options: string[]; original_message?: string }
  confirmation_prompt?: string
  guidance_suggestion?: string
  guidance_next_action?: NextAction | null
  guidance_style?: NudgeStyle
  is_hypothesis_candidate?: boolean
  // Verification badge for a statistical result: true = verified test library,
  // false = LLM-assisted (unverified). undefined = not a test result.
  engine_verified?: boolean
  verified_test_name?: string
  report?: StreamChunk["report"]
  executions?: CodeExecution[]
  server_message_id?: string
  created_at: Date
}

export interface MessageHistoryItem {
  id: string
  role: MessageRole
  content: string
  regime?: string | null
  executions?: CodeExecution[]
  images?: ChartImage[]
  created_at: string | null
}

export interface TaskSummary {
  id: string
  title: string
  dataset_filename: string | null
  created_at: string | null
  last_active_at: string | null
  dataset_ready: boolean
}

export type ArtifactStage =
  | "data_preparation" | "descriptive" | "inferential"
  | "visualisation" | "interpretation" | "assumption_checks"

export type ArtifactType =
  | "chart" | "table" | "test_result" | "cleaned_dataset"
  | "summary" | "derived_column" | "report"

export interface Artifact {
  id: string
  session_id: string
  message_id: string | null
  created_at: string
  stage: ArtifactStage
  artifact_type: ArtifactType
  content: Record<string, unknown>
  code_used: string | null
  superseded: boolean
  superseded_by: string | null
  variables_involved: string[] | null
}

export interface GuidanceState {
  mode: TaskMode
  is_guided: boolean
  hypothesis_text: string | null
}

// ── Guided-mode step rail ────────────────────────────────────────────────────
// The seven pipeline stages shown in the guided rail. Completion is derived
// purely from artifact existence + session state (no parallel progress store).
export type GuidedStageKey =
  | "dataset" | "variable_typing" | "assumption_checks"
  | "test_selection" | "run" | "interpret" | "report"

export const GUIDED_STAGES: { key: GuidedStageKey; label: string }[] = [
  { key: "dataset", label: "Dataset" },
  { key: "variable_typing", label: "Variable Typing" },
  { key: "assumption_checks", label: "Assumption Checks" },
  { key: "test_selection", label: "Test Selection" },
  { key: "run", label: "Run Test" },
  { key: "interpret", label: "Interpret" },
  { key: "report", label: "Report" },
]

export interface GuidedProgressInputs {
  hasDataset: boolean
  hasProfile: boolean
  completedStages: Set<ArtifactStage>
  hasReport: boolean
}

// Map the artifact-derived signals onto the seven rail steps. Some steps share a
// signal (a single confirmatory run produces the assumption-check + test-result
// artifacts together), so the rail can advance more than one node per turn —
// consistent with "completion derives from artifacts".
export function deriveGuidedProgress(i: GuidedProgressInputs): Set<GuidedStageKey> {
  const done = new Set<GuidedStageKey>()
  if (i.hasDataset) done.add("dataset")
  if (i.hasProfile) done.add("variable_typing")
  const assumptionsDone = i.completedStages.has("assumption_checks") || i.completedStages.has("inferential")
  if (assumptionsDone) {
    done.add("assumption_checks")
    done.add("test_selection")
  }
  if (i.completedStages.has("inferential")) {
    done.add("run")
    done.add("interpret")
  }
  if (i.hasReport) done.add("report")
  return done
}

export interface FeedbackRequest {
  session_id: string
  message_id: string
  rating: number
  comment?: string
}
