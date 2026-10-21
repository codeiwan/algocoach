/**
 * Automatic analysis scheduling policy.
 *
 * This is a client-side request controller,
 * not a backend-enforced billing or security limit.
 */

export const AUTO_STABLE_MS = 2_000
export const AUTO_REFLECTION_MS = 6_000

export const AUTO_MIN_INTERVAL_MS = 25_000
export const AUTO_RECHECK_INTERVAL_MS = 12_000

export const AUTO_WINDOW_MS = 10 * 60_000
export const AUTO_MAX_PER_WINDOW = 8
export const AUTO_MAX_PER_SESSION = 24

export type AutoAnalysisBudgetReason =
  | 'READY'
  | 'MIN_INTERVAL'
  | 'WINDOW_BUDGET'
  | 'SESSION_BUDGET'

export interface AutoAnalysisBudgetDecision {
  allowed: boolean
  waitMs: number
  reason: AutoAnalysisBudgetReason
}

/**
 * Evaluate whether another automatic AI request
 * may begin.
 *
 * Requests already sent count toward the budget,
 * even if the browser later aborts them.
 *
 * No timers, HTTP calls, or state mutations
 * occur in this function.
 */
export function evaluateAutoAnalysisBudget(
  nowMs: number,
  requestTimes: readonly number[],
  totalRequests: number,
  priorityRecheck = false,
): AutoAnalysisBudgetDecision {
  if (totalRequests >= AUTO_MAX_PER_SESSION) {
    return {
      allowed: false,
      waitMs: 0,
      reason: 'SESSION_BUDGET',
    }
  }

  const recent = requestTimes
    .filter(
      (time) =>
        time <= nowMs &&
        nowMs - time < AUTO_WINDOW_MS,
    )
    .sort((a, b) => a - b)

  if (recent.length >= AUTO_MAX_PER_WINDOW) {
    const oldest =
      recent[recent.length - AUTO_MAX_PER_WINDOW]

    return {
      allowed: false,
      waitMs: Math.max(
        1,
        (oldest ?? nowMs) + AUTO_WINDOW_MS - nowMs,
      ),
      reason: 'WINDOW_BUDGET',
    }
  }

  const lastRequest =
    requestTimes.length > 0
      ? Math.max(...requestTimes)
      : null

  if (lastRequest !== null) {
    const requiredGap = priorityRecheck
      ? AUTO_RECHECK_INTERVAL_MS
      : AUTO_MIN_INTERVAL_MS

    const waitMs =
      lastRequest + requiredGap - nowMs

    if (waitMs > 0) {
      return {
        allowed: false,
        waitMs,
        reason: 'MIN_INTERVAL',
      }
    }
  }

  return {
    allowed: true,
    waitMs: 0,
    reason: 'READY',
  }
}
