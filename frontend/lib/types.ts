export interface SessionState {
  session_id: string
  hypothesis_on_record: boolean
  suggestion_mode: boolean
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
}

export type MessageRole = "user" | "assistant"

export type ChunkType =
  | "text" | "image" | "disambiguation" | "confirmation_prompt"
  | "guidance_suggestion" | "cached_artifact" | "report"
  | "meta" | "error" | "done" | "code_execution"

export interface CodeExecution {
  code: string
  output: string
}

export interface StreamChunk {
  type: ChunkType
  content?: string
  regime?: string
  artifact_id?: string
  show_feedback?: boolean
  code?: string
  output?: string
  message_id?: string
  prompt?: { question: string; options: string[] }
  is_hypothesis_candidate?: boolean
  report?: { markdown: string; filename: string; artifact_count: number; stages_covered: string[] }
  route_to?: string
  shortcut?: "profile" | "cached_artifact"
}

export interface Message {
  id: string
  role: MessageRole
  content: string
  images: string[]
  regime?: string
  artifact_id?: string
  show_feedback?: boolean
  disambiguation?: { question: string; options: string[] }
  confirmation_prompt?: string
  guidance_suggestion?: string
  is_hypothesis_candidate?: boolean
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
  created_at: string | null
}

export type ArtifactStage =
  | "data_preparation" | "descriptive" | "inferential"
  | "visualisation" | "interpretation"

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
  hypothesis_on_record: boolean
  suggestion_mode: boolean
  hypothesis_text: string | null
}

export interface RailStage {
  key: ArtifactStage
  label: string
  completed: boolean
}

export const RAIL_STAGES: RailStage[] = [
  { key: "data_preparation", label: "Data Preparation", completed: false },
  { key: "descriptive", label: "Descriptive Stats", completed: false },
  { key: "inferential", label: "Inferential Analysis", completed: false },
  { key: "visualisation", label: "Visualisation", completed: false },
  { key: "interpretation", label: "Interpretation", completed: false },
]

export interface FeedbackRequest {
  session_id: string
  message_id: string
  rating: number
  comment?: string
}
