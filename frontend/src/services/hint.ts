import type {
  HintResult,
  NextHintRequest,
} from '@/types/hint'

export class HintApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = 'HintApiError'
  }
}

export async function requestNextHint(
  request: NextHintRequest,
  signal?: AbortSignal,
): Promise<HintResult> {
  const response = await fetch('/api/v1/dev/hints/next', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    let message = `힌트 요청에 실패했습니다. (HTTP ${response.status})`

    if (response.status === 409) {
      message = '이 풀이 세션에서는 3단계 힌트를 모두 제공했습니다.'
    }

    throw new HintApiError(message, response.status)
  }

  return (await response.json()) as HintResult
}
