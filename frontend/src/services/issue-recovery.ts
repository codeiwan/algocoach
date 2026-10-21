/**
 * Detect whether the learner edited a source line
 * previously identified by the AI as problematic.
 *
 * This is a recheck signal, NOT proof that the issue
 * has been fixed.
 */

export interface ReportedIssueLine {
  line_start: number | null
  line_end: number | null
}

export function hasEditedReportedIssueLine(
  analyzedCode: string,
  currentCode: string,
  issues: readonly ReportedIssueLine[],
): boolean {
  if (
    !analyzedCode.trim() ||
    !currentCode.trim() ||
    analyzedCode === currentCode ||
    issues.length === 0
  ) {
    return false
  }

  const previousLines = analyzedCode
    .replace(/\r\n/g, '\n')
    .split('\n')

  const currentLines = currentCode
    .replace(/\r\n/g, '\n')
    .split('\n')

  // Line positions cannot be compared reliably
  // when lines were added or removed.
  // Leave those edits to the existing trigger policy.
  if (previousLines.length !== currentLines.length) {
    return false
  }

  for (const issue of issues) {
    const start = issue.line_start

    if (
      start === null ||
      !Number.isInteger(start) ||
      start < 1 ||
      start > previousLines.length
    ) {
      continue
    }

    const end = issue.line_end ?? start

    if (
      !Number.isInteger(end) ||
      end < start ||
      end > previousLines.length
    ) {
      continue
    }

    for (let line = start; line <= end; line += 1) {
      if (
        previousLines[line - 1] !==
        currentLines[line - 1]
      ) {
        return true
      }
    }
  }

  return false
}
