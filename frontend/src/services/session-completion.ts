import type {
  SessionCompletionOutcome,
  SessionCompletionRequest,
  SessionCompletionReceipt,
} from '@/types/session-completion'

export class SessionCompletionApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = 'SessionCompletionApiError'
  }
}

export async function completeSession(
  request: SessionCompletionRequest,
  signal?: AbortSignal,
): Promise<SessionCompletionOutcome> {
  const response = await fetch('/api/v1/dev/sessions/complete', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    let message = `풀이 종료 요청에 실패했습니다. (HTTP ${response.status})`

    if (response.status === 409) {
      message =
        '이 풀이 세션은 이미 다른 내용으로 종료되었습니다. ' +
        '기존 기록을 변경할 수 없습니다.'
    } else if (response.status === 422) {
      message =
        '종료 요청 데이터가 올바르지 않습니다. ' +
        '채점 결과와 최종 코드를 확인해 주세요.'
    }

    throw new SessionCompletionApiError(
      message,
      response.status,
    )
  }

  if (response.status !== 200 && response.status !== 201) {
    throw new Error(
      `예상하지 못한 종료 응답입니다. (HTTP ${response.status})`,
    )
  }

  const receipt = (await response.json()) as SessionCompletionReceipt

  if (
    receipt.session_id !== request.session_id ||
    receipt.code_revision !== request.code_revision ||
    receipt.completion_mode !== request.completion_mode ||
    receipt.judge_verdict !== request.judge_verdict
  ) {
    throw new Error(
      '서버가 반환한 풀이 종료 결과가 요청 내용과 일치하지 않습니다.',
    )
  }

  if (
    request.completion_mode === 'EXTERNAL_JUDGE' &&
    receipt.verdict_source !== 'USER_REPORTED'
  ) {
    throw new Error(
      '외부 채점 결과의 출처를 확인할 수 없습니다.',
    )
  }

  return {
    request,
    receipt,
    created: response.status === 201,
  }
}
