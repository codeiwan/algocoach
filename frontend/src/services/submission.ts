import type {
  SubmissionReviewRequest,
  SubmissionReviewResult,
} from '@/types/submission'

export class SubmissionReviewApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = 'SubmissionReviewApiError'
  }
}

export async function reviewSubmission(
  request: SubmissionReviewRequest,
  signal?: AbortSignal,
): Promise<SubmissionReviewResult> {
  const response = await fetch('/api/v1/dev/submission/review', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    let message = `제출 전 점검에 실패했습니다. (HTTP ${response.status})`

    if (response.status === 422) {
      message =
        '점검 요청 데이터가 올바르지 않습니다. 문제와 코드를 확인해 주세요.'
    } else if (response.status === 502) {
      message =
        'AI 점검 서버에서 응답을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'
    }

    throw new SubmissionReviewApiError(
      message,
      response.status,
    )
  }

  return (await response.json()) as SubmissionReviewResult
}
