import type { AnalysisRequest, AnalysisResult } from '@/types/analysis'

export async function analyzeCode(
  request: AnalysisRequest,
  signal?: AbortSignal,
): Promise<AnalysisResult> {
  const response = await fetch('/api/v1/dev/analyze', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    throw new Error(`분석 요청 실패: HTTP ${response.status}`)
  }

  return (await response.json()) as AnalysisResult
}
