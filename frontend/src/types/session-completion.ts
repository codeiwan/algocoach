import type { ProgrammingLanguage } from '@/types/programming-language'

export type CompletionMode =
  | 'EXTERNAL_JUDGE'
  | 'WITHOUT_SUBMISSION'

export type JudgeVerdict =
  | 'ACCEPTED'
  | 'WRONG_ANSWER'
  | 'TIME_LIMIT_EXCEEDED'
  | 'MEMORY_LIMIT_EXCEEDED'
  | 'RUNTIME_ERROR'
  | 'COMPILATION_ERROR'
  | 'PRESENTATION_ERROR'
  | 'OUTPUT_LIMIT_EXCEEDED'
  | 'OTHER'

export const JUDGE_VERDICT_LABELS: Record<JudgeVerdict, string> = {
  ACCEPTED: '정답 (Accepted)',
  WRONG_ANSWER: '오답 (Wrong Answer)',
  TIME_LIMIT_EXCEEDED: '시간 초과 (TLE)',
  MEMORY_LIMIT_EXCEEDED: '메모리 초과 (MLE)',
  RUNTIME_ERROR: '런타임 오류',
  COMPILATION_ERROR: '컴파일 오류',
  PRESENTATION_ERROR: '출력 형식 오류',
  OUTPUT_LIMIT_EXCEEDED: '출력 초과',
  OTHER: '기타 판정',
}

export interface SessionCompletionRequest {
  session_id: string
  code_revision: number
  problem_text: string
  final_code: string
  language: ProgrammingLanguage
  completion_mode: CompletionMode
  judge_verdict: JudgeVerdict | null
  notes: string | null
}

export interface SessionCompletionReceipt {
  session_id: string
  code_revision: number
  completion_mode: CompletionMode
  judge_verdict: JudgeVerdict | null
  verdict_source: 'USER_REPORTED' | null
  completed_at: string
}

export interface SessionCompletionOutcome {
  request: SessionCompletionRequest
  receipt: SessionCompletionReceipt
  created: boolean
}
