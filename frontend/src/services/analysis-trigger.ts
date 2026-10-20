import type { ProgrammingLanguage } from '@/types/programming-language'

export const MIN_CODE_LENGTH = 8
export const TRIGGER_COOLDOWN_MS = 10_000

export interface CodeSnapshot {
  language: ProgrammingLanguage
  code: string
  revision: number
}

export interface TriggerSuggestion {
  snapshot: CodeSnapshot
  suggestedAtMs: number
}

export type TriggerReason =
  | 'EMPTY_CODE'
  | 'SHORT_CODE'
  | 'UNCHANGED'
  | 'COOLDOWN'
  | 'ELIGIBLE'

export interface TriggerDecision {
  eligible: boolean
  reason: TriggerReason
  message: string
}

/**
 * Decide whether a stable code snapshot should become
 * an AI analysis candidate.
 *
 * This function does not call an LLM or mutate application state.
 */
export function evaluateAnalysisTrigger(
  snapshot: CodeSnapshot,
  lastSuggestion: TriggerSuggestion | null,
  nowMs: number,
): TriggerDecision {
  // 1. Ignore empty code.
  if (!snapshot.code.trim()) {
    return {
      eligible: false,
      reason: 'EMPTY_CODE',
      message: '작성된 코드가 없어 분석을 보류합니다.',
    }
  }

  // 2. Avoid triggering during very early typing.
  const codeLength = snapshot.code.replace(/\s/g, '').length

  if (codeLength < MIN_CODE_LENGTH) {
    return {
      eligible: false,
      reason: 'SHORT_CODE',
      message: '코드 작성 초기 단계이므로 조금 더 관찰합니다.',
    }
  }

  if (lastSuggestion !== null) {
    // 3. Avoid analyzing an identical candidate again.
    if (
      snapshot.language === lastSuggestion.snapshot.language &&
      snapshot.code === lastSuggestion.snapshot.code
    ) {
      return {
        eligible: false,
        reason: 'UNCHANGED',
        message: '이전에 선정한 분석 후보와 동일한 코드입니다.',
      }
    }

    // 4. Limit how frequently analysis candidates are selected.
    const elapsedMs = nowMs - lastSuggestion.suggestedAtMs

    if (elapsedMs < TRIGGER_COOLDOWN_MS) {
      return {
        eligible: false,
        reason: 'COOLDOWN',
        message: '분석 후보 선정 간격이 지나지 않아 관찰을 계속합니다.',
      }
    }
  }

  // 5. The snapshot is eligible for further analysis.
  return {
    eligible: true,
    reason: 'ELIGIBLE',
    message: '새로운 코드 변경이 확인되어 분석 후보로 선정했습니다.',
  }
}
