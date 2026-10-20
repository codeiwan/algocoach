
import { computed, shallowRef, watch, type Ref } from 'vue'

import type { CodeSnapshot } from '@/services/analysis-trigger'
import type { ProgrammingLanguage } from '@/types/programming-language'

export const MAX_CODE_HISTORY = 20

export interface CodeHistoryEntry {
  revision: number
  language: ProgrammingLanguage
  codeLength: number
  changedCharacters: number | null
  recordedAtMs: number
}

/**
 * Estimate the number of inserted and removed characters
 * between two code versions.
 *
 * This is not a semantic code comparison.
 */
export function countChangedCharacters(
  previous: string,
  current: string,
): number {
  let prefix = 0

  const minLength = Math.min(previous.length, current.length)

  while (
    prefix < minLength &&
    previous[prefix] === current[prefix]
  ) {
    prefix += 1
  }

  let previousEnd = previous.length
  let currentEnd = current.length

  while (
    previousEnd > prefix &&
    currentEnd > prefix &&
    previous[previousEnd - 1] === current[currentEnd - 1]
  ) {
    previousEnd -= 1
    currentEnd -= 1
  }

  // Sum the unmatched portions of both versions.
  return (previousEnd - prefix) + (currentEnd - prefix)
}

/**
 * Collect bounded metadata about stable code revisions.
 *
 * A new entry is recorded only when the code content
 * differs from the last recorded version of that language.
 */
export function useCodeHistory(
  stableSnapshot: Ref<CodeSnapshot | null>,
) {
  const history = shallowRef<CodeHistoryEntry[]>([])

  // Keep only the latest code for each language for comparison.
  const previousCodeByLanguage: Partial<
    Record<ProgrammingLanguage, string>
  > = {}

  watch(stableSnapshot, (snapshot) => {
    if (snapshot === null) {
      return
    }

    const previousCode = previousCodeByLanguage[snapshot.language]

    // Ignore an initially empty editor.
    if (
      previousCode === undefined &&
      !snapshot.code.trim()
    ) {
      return
    }

    // Switching back to unchanged code is not a new edit.
    if (previousCode === snapshot.code) {
      return
    }

    const changedCharacters =
      previousCode === undefined
        ? null
        : countChangedCharacters(previousCode, snapshot.code)

    const entry: CodeHistoryEntry = {
      revision: snapshot.revision,
      language: snapshot.language,
      codeLength: snapshot.code.length,
      changedCharacters,
      recordedAtMs: Date.now(),
    }

    previousCodeByLanguage[snapshot.language] = snapshot.code

    // Keep the newest entries only.
    history.value = [
      ...history.value,
      entry,
    ].slice(-MAX_CODE_HISTORY)
  })

  const latestEntry = computed(
    () => history.value[history.value.length - 1] ?? null,
  )

  return {
    history,
    latestEntry,
  }
}
