<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

import {
  askCoachingQuestion,
  type CoachingConversationTurn,
} from '@/services/coaching-question'

import type { ProgrammingLanguage } from '@/types/programming-language'

const props = defineProps<{
  sessionId: string
  problemText: string
  currentCode: string
  language: ProgrammingLanguage
  currentRevision: number
  latestCoaching: string | null
}>()

interface Exchange {
  id: number
  question: string
  answer: string
  answeredRevision: number
  atMs: number
}

const emit = defineEmits<{
  answered: [exchange: Exchange]
  activity: [isActive: boolean]
}>()

const isOpen = ref(false)
const isSending = ref(false)
const question = ref('')
const errorMessage = ref('')
const exchanges = ref<Exchange[]>([])

let nextExchangeId = 0
let controller: AbortController | null = null

function togglePanel() {
  isOpen.value = !isOpen.value
}

function recentHistory(): CoachingConversationTurn[] {
  return exchanges.value
    .slice(0, 3)
    .reverse()
    .flatMap((entry) => [
      {
        role: 'user' as const,
        content: entry.question.slice(0, 2000),
      },
      {
        role: 'assistant' as const,
        content: entry.answer.slice(0, 2000),
      },
    ])
}

async function submitQuestion() {
  const text = question.value.trim()

  if (!text || isSending.value) {
    return
  }

  const request = {
    session_id: props.sessionId,
    code_revision: props.currentRevision,
    problem_text: props.problemText,
    current_code: props.currentCode,
    language: props.language,
    question: text,
    latest_coaching: props.latestCoaching,
    history: recentHistory(),
  }

  const activeController = new AbortController()

  controller = activeController
  isSending.value = true
  errorMessage.value = ''

  // Reflect the actual request lifecycle in the agent header.
  emit('activity', true)

  try {
    const result = await askCoachingQuestion(
      request,
      activeController.signal,
    )

    if (
      activeController.signal.aborted ||
      controller !== activeController
    ) {
      return
    }

    const exchange: Exchange = {
      id: ++nextExchangeId,
      question: text,
      answer: result.answer,
      answeredRevision: result.answered_revision,
      atMs: Date.now(),
    }

    exchanges.value = [
      exchange,
      ...exchanges.value,
    ].slice(0, 20)

    emit('answered', exchange)

    if (question.value.trim() === text) {
      question.value = ''
    }
  } catch (error) {
    if (
      activeController.signal.aborted ||
      controller !== activeController
    ) {
      return
    }

    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'AI에게 질문하는 중 오류가 발생했습니다.'
  } finally {
    if (controller === activeController) {
      controller = null
      isSending.value = false
      emit('activity', false)
    }
  }
}

onBeforeUnmount(() => {
  controller?.abort()
  controller = null
  emit('activity', false)
})
</script>

<template>
  <section
    class="question-panel"
    aria-label="AI 코치에게 질문하기"
  >
    <button
      type="button"
      class="toggle-button"
      :aria-expanded="isOpen"
      @click="togglePanel"
    >
      <span>AI에게 질문하기</span>
      <span aria-hidden="true">{{ isOpen ? '−' : '+' }}</span>
    </button>

    <div
      v-if="isOpen"
      class="question-content"
    >
      <p class="helper-text">
        문제, 현재 코드, 이전 코칭에 관해 자유롭게 질문하세요.
        답변은 위쪽 AlgoCoach 대화 피드에 표시됩니다.
      </p>

      <form
        class="question-form"
        @submit.prevent="submitQuestion"
      >
        <label for="coach-question">
          코치에게 질문
        </label>

        <textarea
          id="coach-question"
          v-model="question"
          rows="3"
          maxlength="1000"
          :disabled="isSending"
          placeholder="예: 왜 반복문에서 i를 더해야 하나요?"
        />

        <button
          type="submit"
          class="send-button"
          :disabled="!question.trim() || isSending"
        >
          {{
            isSending
              ? 'AI 답변 생성 중...'
              : '질문 보내기'
          }}
        </button>
      </form>

      <p
        v-if="isSending"
        class="waiting"
        role="status"
      >
        현재 코드와 질문을 바탕으로 답변을 생성하고 있습니다.
      </p>

      <p
        v-if="errorMessage"
        class="error"
        role="alert"
      >
        {{ errorMessage }}
      </p>

      <p
        v-if="exchanges.length > 0"
        class="history-note"
      >
        질문 {{ exchanges.length }}건 · 답변은 위 대화 피드에서 확인
      </p>
    </div>
  </section>
</template>

<style scoped>
.question-panel {
  min-width: 0;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: #fff;
}

.toggle-button {
  display: flex;
  width: 100%;
  min-height: 46px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 0;
  border-radius: 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.question-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  padding: 14px;
}

.helper-text,
.history-note {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

.question-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.question-form label {
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

.question-form textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: white;
  color: #0f172a;
  font: inherit;
  font-size: 12px;
  line-height: 1.7;
  resize: vertical;
}

.send-button {
  min-height: 40px;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: white;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.send-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.waiting {
  margin: 0;
  color: #1d4ed8;
  font-size: 12px;
  line-height: 1.7;
}

.error {
  margin: 0;
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.7;
}
</style>