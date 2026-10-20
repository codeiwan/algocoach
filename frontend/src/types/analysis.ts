export type ProgressStatus =
  | 'UNDERSTANDING'
  | 'IMPLEMENTING'
  | 'DEBUGGING'
  | 'STUCK_SUSPECTED'
  | 'REVIEWING'

export type IssueSeverity = 'INFO' | 'WARNING' | 'CRITICAL'

export interface AnalysisRequest {
  session_id: string
  code_revision: number
  problem_text: string
  current_code: string
  previous_code?: string | null
}

export interface CodeIssue {
  category: 'logic' | 'complexity' | 'edge_case' | 'constraint'
  severity: IssueSeverity
  description: string
  evidence: string
  line_start: number | null
  line_end: number | null
}

export interface AnalysisResult {
  analyzed_revision: number
  algorithm: string | null
  progress_status: ProgressStatus
  summary: string
  positive_observation: string | null
  complexity_estimate: string | null
  issues: CodeIssue[]
}
