import type { ProgrammingLanguage } from '@/types/programming-language'

export type ReviewStatus =
  | 'RISK_FOUND'
  | 'NO_OBVIOUS_RISK'
  | 'UNCERTAIN'

export type ReviewCategory =
  | 'LOGIC'
  | 'EDGE_CASE'
  | 'COMPLEXITY'
  | 'INPUT_OUTPUT'
  | 'CONSTRAINT'
  | 'LANGUAGE'

export type ReviewSeverity =
  | 'HIGH'
  | 'MEDIUM'
  | 'LOW'

export interface SubmissionReviewRequest {
  session_id: string
  code_revision: number
  problem_text: string
  current_code: string
  language: ProgrammingLanguage
}

export interface ReviewFinding {
  category: ReviewCategory
  severity: ReviewSeverity
  description: string
  evidence: string
  line_start: number | null
  line_end: number | null
}

export interface SubmissionReviewResult {
  reviewed_revision: number
  status: ReviewStatus
  summary: string
  findings: ReviewFinding[]
  complexity_assessment: string | null
  suggested_checks: string[]
}
