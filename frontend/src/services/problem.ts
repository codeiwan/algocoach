import type {
  ProblemStructureRequest,
  StructuredProblem,
} from '@/types/problem'

export async function structureProblem(
  request: ProblemStructureRequest,
  signal?: AbortSignal,
): Promise<StructuredProblem> {
  const response = await fetch('/api/v1/dev/problems/structure', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    throw new Error(
      `문제 구조화 요청에 실패했습니다. (HTTP ${response.status})`,
    )
  }

  return (await response.json()) as StructuredProblem
}
