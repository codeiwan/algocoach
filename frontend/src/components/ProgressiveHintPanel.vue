<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import {
  HintApiError,
  requestNextHint,
} from '@/services/hint'
import type {
  HintLevel,
  HintResult,
} from '@/types/hint'
import type { ProgrammingLanguage } from '@/types/programming-language'

const props = defineProps<{
  sessionId: string
  problemText: string
  currentCode: string
  language: ProgrammingLanguage
  currentRevision: number
}>()

const HINT_LEVELS: HintLevel[] = [
  'DIRECTION',
  'ALGORITHM',
  'IMPLEMENTATION',
]

const HINT_LABELS: Record<HintLevel, string> = {
  DIRECTION: '방향 힌트',
  ALGORITHM: '알고리즘 힌트',
  IMPLEMENTATION: '구현 힌트',
}

const hints = ref<HintResult[]>([])
const isLoading = ref(false)
const errorMessage = ref('')
const limitReached = ref(false)

let requestController: AbortController | null = null

const deliveredCount = computed(() => hints.value.length)

const isComplete = computed(
  () => deliveredCount.value >= HINT_LEVELS.length || limitReached.value,
)

const nextLevel = computed(
  () => HINT_LEVELS[deliveredCount.value] ?? null,
)

const nextButtonLabel = computed(() => {
  if (isLoading.value) {
    return 'AI가 힌트를 생성하고 있습니다...'
  }

  if (isComplete.value) {
    return '모든 단계의 힌트를 확인했습니다'
  }

  return nextLevel.value
    ? `${HINT_LABELS[nextLevel.value]} 요청`
    : '힌트 요청'
})

async function requestHint() {
  if (isLoading.value || isComplete.value) {
    return
  }

  const controller = new AbortController()
  requestController = controller

  const revisionSnapshot = props.currentRevision

  isLoading.value = true
  errorMessage.value = ''

  try {
    const result = await requestNextHint(
      {
        session_id: props.sessionId,
        code_revision: revisionSnapshot,
        problem_text: props.problemText,
        current_code: props.currentCode,
        language: props.language,
      },
      controller.signal,
    )

    if (controller.signal.aborted) {
      return
    }

    // The backend owns hint progression.
    // Preserve delivered results even if the code changed meanwhile.
    if (hints.value.some((hint) => hint.level === result.level)) {
      errorMessage.value =
        '이미 표시된 힌트 단계가 다시 반환되었습니다. 서버 상태를 확인해 주세요.'
      return
    }

    hints.value.push(result)

    if (result.hinted_revision !== revisionSnapshot) {
      errorMessage.value =
        '서버가 요청한 코드 Revision과 다른 힌트를 반환했습니다.'
    }

    if (hints.value.length >= HINT_LEVELS.length) {
      limitReached.value = true
    }
  } catch (error) {
    if (controller.signal.aborted) {
      return
    }

    if (error instanceof HintApiError && error.status === 409) {
      limitReached.value = true
    }

    errorMessage.value =
      error instanceof Error
        ? error.message
        : '힌트 요청 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    if (requestController === controller) {
      requestController = null
      isLoading.value = false
    }
  }
}

onBeforeUnmount(() => {
  requestController?.abort()
  requestController = null
})
</script>

<template>
  <section class="hint-panel">
    <header class="hint-header">
      <h3>단계별 AI 힌트</h3>
      <span class="hint-progress">
        {{ deliveredCount }} / 3
      </span>
    </header>

    <p class="hint-description">
      정답을 바로 공개하지 않고, 방향부터 구현까지
      단계적으로 도움을 제공합니다.
    </p>

    <div class="hint-steps" aria-label="힌트 진행 단계">
      <div
        v-for="(level, index) in HINT_LEVELS"
        :key="level"
        class="hint-step"
        :class="{
          completed: deliveredCount > index,
          current: deliveredCount === index && !isComplete,
        }"
      >
        <span class="step-number">{{ index + 1 }}</span>
        <span>{{ HINT_LABELS[level] }}</span>
      </div>
    </div>

    <div
      v-if="hints.length > 0"
      class="hint-history"
      aria-live="polite"
    >
      <article
        v-for="(hint, index) in hints"
        :key="`${hint.level}-${index}`"
        class="hint-card"
      >
        <div class="hint-meta">
          <strong>
            {{ index + 1 }}단계 · {{ HINT_LABELS[hint.level] }}
          </strong>
          <span>Revision {{ hint.hinted_revision }}</span>
        </div>

        <p class="hint-message">
          {{ hint.message }}
        </p>

        <div
          v-if="hint.code_reference"
          class="code-reference"
        >
          <span>관련 코드</span>
          <pre>{{ hint.code_reference }}</pre>
        </div>

        <p
          v-if="hint.hinted_revision !== currentRevision"
          class="outdated-note"
        >
          이 힌트는 이전 코드 Revision을 기준으로 생성됐습니다.
          현재 코드에 그대로 적용하기 전에 변경사항을 확인하세요.
        </p>
      </article>
    </div>

    <p v-else class="empty-hints">
      아직 요청한 힌트가 없습니다.
      문제를 스스로 풀다가 도움이 필요할 때 사용하세요.
    </p>

    <button
      type="button"
      class="hint-button"
      :disabled="isLoading || isComplete"
      @click="requestHint"
    >
      {{ nextButtonLabel }}
    </button>

    <p
      v-if="isLoading"
      class="hint-status"
      role="status"
    >
      현재 코드와 문제를 분석하여 해당 단계의 힌트를 생성하고 있습니다.
    </p>

    <p
      v-if="errorMessage"
      class="hint-error"
      role="alert"
    >
      {{ errorMessage }}
    </p>

    <p
      v-if="isComplete"
      class="completion-message"
    >
      이 풀이 세션에 제공할 수 있는 힌트 단계를 모두 사용했습니다.
    </p>

    <p class="hint-notice">
      힌트는 버튼을 누를 때만 생성됩니다.
      OpenAI 모드에서는 요청마다 API 사용 요금이 발생할 수 있습니다.
    </p>
  </section>
</template>

<style scoped>
.hint-panel {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: white;
}

.hint-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.hint-header h3 {
  margin: 0;
  font-size: 14px;
}

.hint-progress {
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}

.hint-description {
  margin: 12px 0 16px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

.hint-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hint-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #64748b;
  font-size: 12px;
}

.step-number {
  display: flex;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #e2e8f0;
  font-weight: 700;
}

.hint-step.current {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}

.hint-step.completed {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #166534;
}

.hint-step.completed .step-number {
  background: #dcfce7;
}

.hint-history {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 18px 0;
}

.hint-card {
  padding: 14px;
  border: 1px solid #dbeafe;
  border-left: 3px solid #2563eb;
  border-radius: 8px;
  background: #f8fafc;
}

.hint-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.hint-meta strong {
  color: #1e40af;
  font-size: 12px;
}

.hint-meta span {
  color: #64748b;
  font-size: 11px;
}

.hint-message {
  margin: 12px 0 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.code-reference {
  margin-top: 12px;
}

.code-reference span {
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}

.code-reference pre {
  margin: 6px 0 0;
  padding: 10px;
  border-radius: 6px;
  background: #e2e8f0;
  color: #334155;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.outdated-note {
  margin: 12px 0 0;
  color: #92400e;
  font-size: 11px;
  line-height: 1.6;
}

.empty-hints {
  margin: 18px 0;
  padding: 14px;
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
  text-align: center;
}

.hint-button {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: white;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.hint-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.hint-status,
.hint-error,
.completion-message,
.hint-notice {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.7;
}

.hint-status {
  color: #2563eb;
}

.hint-error {
  color: #dc2626;
}

.completion-message {
  color: #166534;
}

.hint-notice {
  color: #94a3b8;
}
</style>