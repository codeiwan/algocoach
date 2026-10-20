
import type { AnalysisResult, CodeIssue } from '@/types/analysis'

// Minimum time between delivered coaching messages.
export const INTERVENTION_COOLDOWN_MS = 60_000

export type InterventionKind = 'issue' | 'praise'

export type InterventionReason =
  | 'STALE_REVISION'
  | 'NO_SIGNAL'
  | 'DUPLICATE'
  | 'COOLDOWN'
  | 'ELIGIBLE'

export interface InterventionCandidate {
  kind: InterventionKind
  fingerprint: string
  message: string
  severity?: 'WARNING' | 'CRITICAL'
}

export interface DeliveredIntervention {
  fingerprint: string
  deliveredAtMs: number
}

export interface InterventionDecision {
  eligible: boolean
  reason: InterventionReason
  candidate: InterventionCandidate | null
}

/**
 * Select one potential coaching message from an analysis result.
 *
 * Priority:
 * 1. Critical issues
 * 2. Warning issues
 * 3. Positive observations
 */
function selectCandidate(
  result: AnalysisResult,
): InterventionCandidate | null {
  const hasEvidence = (issue: CodeIssue) =>
    issue.description.trim().length > 0 &&
    issue.evidence.trim().length > 0

  const issue =
    result.issues.find(
      (item) => item.severity === 'CRITICAL' && hasEvidence(item),
    ) ??
    result.issues.find(
      (item) => item.severity === 'WARNING' && hasEvidence(item),
    )

  if (issue && (issue.severity === 'WARNING' || issue.severity === 'CRITICAL')) {
    const description = issue.description.trim()
    const evidence = issue.evidence.trim()

    return {
      kind: 'issue',
      severity: issue.severity,
      fingerprint: JSON.stringify([
        'issue',
        issue.category,
        issue.severity,
        description,
        evidence,
      ]),
      message: `검토할 부분이 있습니다: ${description}\n근거: ${evidence}`,
    }
  }

  const observation = result.positive_observation?.trim()

  if (observation) {
    return {
      kind: 'praise',
      fingerprint: JSON.stringify(['praise', observation]),
      message: observation,
    }
  }

  return null
}

/**
 * Decide whether an analysis result deserves a coaching message.
 *
 * This function does not display messages, call an LLM,
 * or update intervention history.
 */
export function evaluateIntervention(
  result: AnalysisResult,
  currentRevision: number,
  lastDelivered: DeliveredIntervention | null,
  nowMs: number,
): InterventionDecision {
  // 1. Never intervene using an outdated analysis result.
  if (result.analyzed_revision !== currentRevision) {
    return {
      eligible: false,
      reason: 'STALE_REVISION',
      candidate: null,
    }
  }

  // 2. Identify a concrete coaching opportunity.
  const candidate = selectCandidate(result)

  if (!candidate) {
    return {
      eligible: false,
      reason: 'NO_SIGNAL',
      candidate: null,
    }
  }

  if (lastDelivered !== null) {
    // 3. Avoid repeating an identical coaching message.
    if (candidate.fingerprint === lastDelivered.fingerprint) {
      return {
        eligible: false,
        reason: 'DUPLICATE',
        candidate: null,
      }
    }

    // 4. Do not interrupt the user too frequently.
    const elapsedMs = nowMs - lastDelivered.deliveredAtMs

    if (elapsedMs < INTERVENTION_COOLDOWN_MS) {
      return {
        eligible: false,
        reason: 'COOLDOWN',
        candidate: null,
      }
    }
  }

  // 5. The analysis may be surfaced to the user.
  return {
    eligible: true,
    reason: 'ELIGIBLE',
    candidate,
  }
}
