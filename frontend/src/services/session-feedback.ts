export type MainChallenge =
  | 'UNDERSTANDING'
  | 'ALGORITHM'
  | 'IMPLEMENTATION'
  | 'DEBUGGING'
  | 'COMPLEXITY'
  | 'OTHER'

export interface SessionFeedbackRequest {
  session_id: string
  difficulty_rating: number
  intervention_timing_rating: number | null
  hint_helpfulness_rating: number | null
  review_helpfulness_rating: number | null
  main_challenge: MainChallenge | null
  comment: string | null
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
    let message = `설문 저장에 실패했습니다. (HTTP ${response.status})`

    if (response.status === 409) {
      message =
        '이미 다른 설문이 기록됐거나, 완료된 풀이 세션을 찾을 수 없습니다.'
    } else if (response.status === 422) {
      message = '설문 입력값을 확인해 주세요.'
    }

    throw new SessionFeedbackApiError(message, response.status)
  }

  if (response.status !== 200 && response.status !== 201) {
    throw new Error(
      `예상하지 못한 설문 응답입니다. (HTTP ${response.status})`,
    )
  }

  const receipt =
    (await response.json()) as SessionFeedbackReceipt

  if (
    receipt.session_id !== request.session_id ||
    receipt.status !== 'RECORDED'
  ) {
    throw new Error(
      '설문 저장 확인서가 요청한 세션과 일치하지 않습니다.',
    )
  }

  return receipt
}
