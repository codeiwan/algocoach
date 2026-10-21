import type { ProgrammingLanguage } from '@/types/programming-language'

export type HintLevel =
  | 'DIRECTION'
  | 'ALGORITHM'
  | 'IMPLEMENTATION'

export interface NextHintRequest {
  session_id: string
  code_revision: number
  problem_text: string
  current_code: string
  language: ProgrammingLanguage
}

export interface HintResult {
  hinted_revision: number
  level: HintLevel
  message: string
  code_reference: string | null
}
