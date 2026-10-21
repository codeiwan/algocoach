/**
 * Suppress unsolicited offers after a positive static review.
 * This is a UX decision only, not a correctness or acceptance verdict.
 */

export function substantiallyChangedSinceReview(
  reviewedCode: string,
  currentCode: string,
): boolean {
  // Ignore whitespace-only edits when estimating change size.
  const before = reviewedCode.replace(/\s+/g, '')
  const after = currentCode.replace(/\s+/g, '')

  if (before === after) return false

  let prefix = 0
  const commonLength = Math.min(before.length, after.length)
  while (prefix < commonLength && before[prefix] === after[prefix]) {
    prefix += 1
  }

  let suffix = 0
  while (
    suffix < commonLength - prefix &&
    before[before.length - 1 - suffix] === after[after.length - 1 - suffix]
  ) {
    suffix += 1
  }

  const removed = before.length - prefix - suffix
  const added = after.length - prefix - suffix
  const changedSpan = Math.max(removed, added)
  const threshold = Math.max(24, Math.ceil(before.length * 0.15))

  return changedSpan >= threshold
}
