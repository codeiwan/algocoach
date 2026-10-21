import type { ProgrammingLanguage } from '@/types/programming-language'

export interface CoachingConversationTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface CoachingQuestionRequest {
  session_id: string
  code_revision: number
  problem_text: string
  current_code: string
  language: ProgrammingLanguage
  question: string
  latest_coaching: string | null
  history: CoachingConversationTurn[]
}

export interface CoachingQuestionResponse {
  session_id: string
  answered_revision: number
  answer: string
}

export class CoachingQuestionApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = 'CoachingQuestionApiError'
  }
}

export async function askCoachingQuestion(
  request: CoachingQuestionRequest,
  signal?: AbortSignal,
): Promise<CoachingQuestionResponse> {
  const response = await fetch('/api/v1/dev/coaching/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    const messages: Record<number, string> = {
      422: '질문 또는 대화 내역의 형식이 올바르지 않습니다.',
      502: 'AI가 올바른 답변을 반환하지 못했습니다.',
      504: 'AI 응답이 지연되어 요청이 종료됐습니다.',
    }

    throw new CoachingQuestionApiError(
      messages[response.status] ??
        `AI 질문 요청 실패: HTTP ${response.status}`,
      response.status,
    )
  }

  const result =
    (await response.json()) as CoachingQuestionResponse

  if (
    result.session_id !== request.session_id ||
    result.answered_revision !== request.code_revision ||
    typeof result.answer !== 'string' ||
    !result.answer.trim()
  ) {
    throw new Error(
      'AI 답변이 요청한 세션 또는 코드 Revision과 일치하지 않습니다.',
    )
  }

  return result
}
