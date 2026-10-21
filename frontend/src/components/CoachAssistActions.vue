<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import { HintApiError, requestNextHint } from '@/services/hint'
import { reviewSubmission } from '@/services/submission'

import type {
  CoachingAssistanceActivity,
  CoachingAssistanceEvent,
} from '@/types/coaching-assistance'

import type { HintLevel, HintResult } from '@/types/hint'
import type { ProgrammingLanguage } from '@/types/programming-language'
import type { SubmissionReviewResult } from '@/types/submission'

const props = defineProps<{
  sessionId: string
  problemText: string
  currentCode: string
  language: ProgrammingLanguage
  currentRevision: number
  disabled?: boolean
}>()

const emit = defineEmits<{
  delivered: [event: CoachingAssistanceEvent]
  activity: [state: CoachingAssistanceActivity]
}>()

// --------------------------------------------------
// Hint progression
// --------------------------------------------------

const LEVELS: HintLevel[] = [
  'DIRECTION',
  'ALGORITHM',
  'IMPLEMENTATION',
]

const LABELS: Record<HintLevel, string> = {
  DIRECTION: '방향',
  ALGORITHM: '알고리즘',
  IMPLEMENTATION: '구현',
}

const hintCount = ref(0)
const hintLimitReached = ref(false)

// --------------------------------------------------
// Request state
// --------------------------------------------------

const activity = ref<CoachingAssistanceActivity>(null)
const errorMessage = ref('')

let controller: AbortController | null = null
let nextEventId = 0
let lastEventTime = 0

const hintExhausted = computed(
  () =>
    hintLimitReached.value ||
    hintCount.value >= LEVELS.length,
)

const nextHintLabel = computed(() => {
  if (hintExhausted.value) {
    return '힌트 3/3 완료'
  }

  const next = LEVELS[hintCount.value]

  return next
    ? `${hintCount.value + 1}단계 ${LABELS[next]} 힌트`
    : '다음 힌트'
})

const busy = computed(
  () => activity.value !== null || !!props.disabled,
)

// --------------------------------------------------
// Snapshot and agent events
// --------------------------------------------------

function makeSnapshot() {
  return {
    session_id: props.sessionId,
    code_revision: props.currentRevision,
    problem_text: props.problemText,
    current_code: props.currentCode,
    language: props.language,
  }
}

function publish(
  event: Omit<CoachingAssistanceEvent, 'id' | 'atMs'>,
) {
  lastEventTime = Math.max(Date.now(), lastEventTime + 1)

  emit('delivered', {
    ...event,
    id: ++nextEventId,
    atMs: lastEventTime,
  })
}

function setActivity(next: CoachingAssistanceActivity) {
  activity.value = next
  emit('activity', next)
}

// --------------------------------------------------
// Format results for the existing Markdown renderer
// --------------------------------------------------

function formatHint(result: HintResult): string {
  const parts = [result.message]

  if (result.code_reference?.trim()) {
    parts.push(
      `관련 코드:\n${result.code_reference.trim()}`,
    )
  }

  return parts.join('\n\n')
}

function formatReview(
  result: SubmissionReviewResult,
): string {
  const parts = [result.summary]

  const categoryLabels: Record<string, string> = {
    LOGIC: '논리',
    EDGE_CASE: '경계 조건',
    COMPLEXITY: '복잡도',
    INPUT_OUTPUT: '입출력',
    CONSTRAINT: '제약 조건',
    LANGUAGE: '언어',
  }

  for (const finding of result.findings) {
    const category =
      categoryLabels[finding.category] ?? finding.category

    const location =
      finding.line_start === null
        ? ''
        : ` (${finding.line_start}${
            finding.line_end !== null &&
            finding.line_end !== finding.line_start
              ? `~${finding.line_end}`
              : ''
          }행)`

    parts.push(
      `**${category} · ${finding.severity}${location}**\n` +
        `${finding.description}\n` +
        `근거: ${finding.evidence}`,
    )
  }

  if (result.complexity_assessment?.trim()) {
    parts.push(
      `**복잡도 검토**\n${result.complexity_assessment}`,
    )
  }

  if (result.suggested_checks.length > 0) {
    parts.push(
      '**추가 확인 사항**\n' +
        result.suggested_checks
          .map((check, index) => `${index + 1}. ${check}`)
          .join('\n'),
    )
  }

  parts.push(
    '이 내용은 AI 정적 검토이며 코드 실행, 테스트 통과 ' +
      '또는 정답 판정이 아닙니다.',
  )

  return parts.filter(Boolean).join('\n\n')
}

// --------------------------------------------------
// Progressive hints
// --------------------------------------------------

async function requestHint() {
  if (busy.value || hintExhausted.value) {
    return
  }

  const snapshot = makeSnapshot()
  const active = new AbortController()

  controller = active
  errorMessage.value = ''
  setActivity('hint')

  try {
    const result = await requestNextHint(
      snapshot,
      active.signal,
    )

    if (active.signal.aborted || controller !== active) {
      return
    }

    if (result.hinted_revision !== snapshot.code_revision) {
      throw new Error(
        '요청한 Revision과 힌트 결과가 일치하지 않습니다.',
      )
    }

    const expected = LEVELS[hintCount.value]

    if (result.level !== expected) {
      throw new Error(
        '서버 힌트 단계가 현재 화면의 진행 단계와 다릅니다.',
      )
    }

    hintCount.value += 1

    publish({
      source: 'hint',
      title: `${hintCount.value}단계 · ${LABELS[result.level]} 힌트`,
      revision: result.hinted_revision,
      text: formatHint(result),
      tone: 'neutral',
    })
  } catch (error) {
    if (active.signal.aborted || controller !== active) {
      return
    }

    if (
      error instanceof HintApiError &&
      error.status === 409
    ) {
      hintLimitReached.value = true
    }

    errorMessage.value =
      error instanceof Error
        ? error.message
        : '힌트 요청 중 오류가 발생했습니다.'
  } finally {
    if (controller === active) {
      controller = null
      setActivity(null)
    }
  }
}

// --------------------------------------------------
// Submission review
// --------------------------------------------------

async function requestReview() {
  if (busy.value || !props.currentCode.trim()) {
    return
  }

  const snapshot = makeSnapshot()
  const active = new AbortController()

  controller = active
  errorMessage.value = ''
  setActivity('review')

  try {
    const result = await reviewSubmission(
      snapshot,
      active.signal,
    )

    if (active.signal.aborted || controller !== active) {
      return
    }

    if (result.reviewed_revision !== snapshot.code_revision) {
      throw new Error(
        '요청한 Revision과 제출 전 점검 결과가 일치하지 않습니다.',
      )
    }

    const statusLabel = {
      RISK_FOUND: '잠재적 위험 발견',
      NO_OBVIOUS_RISK: '뚜렷한 위험 미발견',
      UNCERTAIN: '판단 보류',
    }[result.status]

    publish({
      source: 'review',
      title: `제출 전 AI 점검 · ${statusLabel}`,
      revision: result.reviewed_revision,
      text: formatReview(result),
      tone:
        result.status === 'RISK_FOUND'
          ? 'issue'
          : 'neutral',
    })
  } catch (error) {
    if (active.signal.aborted || controller !== active) {
      return
    }

    errorMessage.value =
      error instanceof Error
        ? error.message
        : '제출 전 점검 중 오류가 발생했습니다.'
  } finally {
    if (controller === active) {
      controller = null
      setActivity(null)
    }
  }
}

// --------------------------------------------------
// Cleanup
// --------------------------------------------------

onBeforeUnmount(() => {
  controller?.abort()
  controller = null
  setActivity(null)
})
</script>

<template>
  <section
    class="coach-assist-actions"
    aria-label="추가 AI 코칭 요청"
  >
    <div class="assist-buttons">
      <button
        type="button"
        class="assist-button"
        :disabled="busy || hintExhausted"
        @click="requestHint"
      >
        {{
          activity === 'hint'
            ? '힌트 생성 중...'
            : nextHintLabel
        }}
      </button>

      <button
        type="button"
        class="assist-button"
        :disabled="busy || !currentCode.trim()"
        @click="requestReview"
      >
        {{
          activity === 'review'
            ? '제출 전 점검 중...'
            : '제출 전 점검'
        }}
      </button>
    </div>

    <p
      v-if="activity"
      class="assist-status"
      role="status"
    >
      {{
        activity === 'hint'
          ? '현재 풀이에 맞는 다음 힌트를 요청했습니다.'
          : '현재 코드의 제출 전 정적 검토를 요청했습니다.'
      }}
    </p>

    <p
      v-if="errorMessage"
      class="assist-error"
      role="alert"
    >
      {{ errorMessage }}
    </p>

    <p
      v-if="hintExhausted"
      class="assist-note"
    >
      이 세션의 3단계 힌트를 모두 사용했습니다.
    </p>
  </section>
</template>

<style scoped>
.coach-assist-actions {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.assist-buttons {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.assist-button {
  min-width: 0;
  min-height: 38px;
  padding: 9px 8px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.assist-button:hover:not(:disabled) {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}

.assist-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.assist-status,
.assist-error,
.assist-note {
  margin: 0;
  font-size: 11px;
  line-height: 1.6;
}

.assist-status {
  color: #1d4ed8;
}

.assist-error {
  color: #b91c1c;
}

.assist-note {
  color: #64748b;
}
</style>