/**
 * Local observation policy for optional coaching offers.
 * This does not diagnose whether the learner is stuck
 * and does not call any LLM.
 */

export const PROACTIVE_POLL_MS = 5_000
export const PROACTIVE_IDLE_MS = 90_000
export const PROACTIVE_EMPTY_IDLE_MS = 120_000
export const PROACTIVE_REOFFER_MS = 90_000
export const PROACTIVE_DECLINE_MS = 180_000
export const PROACTIVE_REPEAT_WINDOW_MS = 120_000

export interface StableEdit {
  atMs: number
  codeLength: number
}

export type OfferReason = 'idle' | 'repeated_edits'

export interface ProactiveCheck {
  nowMs: number
  startedAtMs: number
  lastEditedAtMs: number
  currentRevision: number
  hasCode: boolean
  autoEnabled: boolean
  busy: boolean
  offerPending: boolean
  hintCount: number
  lastOfferAtMs: number | null
  lastOfferRevision: number | null
  lastOfferHintCount: number | null
  lastDeclineAtMs: number | null
  lastDeclinedRevision: number | null
  stableEdits: readonly StableEdit[]
}

/**
 * Returns an opportunity to OFFER help, never
 * a conclusion that the learner is struggling.
 */
export function evaluateProactiveOffer(input: ProactiveCheck): OfferReason | null {
  if (!input.autoEnabled || input.busy || input.offerPending || input.hintCount >= 3) {
    return null
  }

  if (input.nowMs - input.startedAtMs < 45_000) {
    return null
  }

  if (input.lastOfferAtMs !== null && input.nowMs - input.lastOfferAtMs < PROACTIVE_REOFFER_MS) {
    return null
  }

  if (
    input.lastDeclineAtMs !== null &&
    input.nowMs - input.lastDeclineAtMs < PROACTIVE_DECLINE_MS
  ) {
    return null
  }

  if (input.lastDeclinedRevision === input.currentRevision) {
    return null
  }

  // Do not repeat the same offer for the same code
  // and the same already-provided hint level.
  if (
    input.lastOfferRevision === input.currentRevision &&
    input.lastOfferHintCount === input.hintCount
  ) {
    return null
  }

  const recent = input.stableEdits.filter(
    (entry) => input.nowMs - entry.atMs <= PROACTIVE_REPEAT_WINDOW_MS,
  )

  if (recent.length >= 4 && input.nowMs - input.lastEditedAtMs >= 15_000) {
    const lengths = recent.map((entry) => entry.codeLength)
    const oldest = recent[0]

    if (
      oldest &&
      input.nowMs - oldest.atMs >= 45_000 &&
      Math.max(...lengths) - Math.min(...lengths) <= 24
    ) {
      return 'repeated_edits'
    }
  }

  const idleMs = input.nowMs - input.lastEditedAtMs

  const threshold = input.hasCode ? PROACTIVE_IDLE_MS : PROACTIVE_EMPTY_IDLE_MS

  return idleMs >= threshold ? 'idle' : null
}
