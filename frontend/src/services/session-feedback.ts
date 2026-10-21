export type CoachingOutcome =
  | 'ACCURATE_AND_HELPFUL'
  | 'ACCURATE_BUT_NOT_HELPFUL'
  | 'MISLEADING_OR_INCORRECT'
  | 'NOT_USED'
  | 'UNABLE_TO_ASSESS'

// Legacy type retained until old survey component cleanup.
export type MainChallenge =
  | 'UNDERSTANDING'
  | 'ALGORITHM'
  | 'IMPLEMENTATION'
  | 'DEBUGGING'
  | 'COMPLEXITY'
  | 'OTHER'

export interface SessionFeedbackRequest {
  session_id: string

  // New primary feedback field.
  coaching_outcome?: CoachingOutcome | null
  comment: string | null

  // Legacy fields are optional for backward compatibility.
  difficulty_rating?: number | null
  intervention_timing_rating?: number | null
  hint_helpfulness_rating?: number | null
  review_helpfulness_rating?: number | null
  main_challenge?: MainChallenge | null
}

export interface SessionFeedbackReceipt {
  session_id: string
  status: 'RECORDED'
  recorded_at: string
}

export class SessionFeedbackApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = 'SessionFeedbackApiError'
  }
}

export async function recordSessionFeedback(
  request: SessionFeedbackRequest,
  signal?: AbortSignal,
): Promise<SessionFeedbackReceipt> {
  const response = await fetch('/api/v1/dev/sessions/feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    let message = `AI 코칭 평가 저장에 실패했습니다. (HTTP ${response.status})`

    if (response.status === 409) {
      message =
        '이미 다른 평가가 저장됐거나 완료된 풀이 세션을 찾을 수 없습니다.'
    } else if (response.status === 422) {
      message =
        'AI 코칭 평가 데이터가 올바르지 않습니다.'
    }

    throw new SessionFeedbackApiError(
      message,
      response.status,
    )
  }

  if (response.status !== 200 && response.status !== 201) {
    throw new Error(
      `예상하지 못한 평가 저장 응답입니다. (HTTP ${response.status})`,
    )
  }

  const receipt =
    (await response.json()) as SessionFeedbackReceipt

  if (
    receipt.session_id !== request.session_id ||
    receipt.status !== 'RECORDED'
  ) {
    throw new Error(
      '코칭 평가 저장 확인서가 요청한 세션과 일치하지 않습니다.',
    )
  }

  return receipt
}
