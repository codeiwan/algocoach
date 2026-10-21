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
}

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

  if (!text || isSending.value) return

  // Snapshot: the question must be associated
  // with the code that existed when it was sent.
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

  const active = new AbortController()

  controller = active
  isSending.value = true
  errorMessage.value = ''

  try {
    const result = await askCoachingQuestion(
      request,
      active.signal,
    )

    if (
      active.signal.aborted ||
      controller !== active
    ) {
      return
    }

    exchanges.value = [
      {
        id: ++nextExchangeId,
        question: text,
        answer: result.answer,
        answeredRevision: result.answered_revision,
      },
      ...exchanges.value,
    ].slice(0, 20)

    if (question.value.trim() === text) {
      question.value = ''
    }
  } catch (error) {
    if (
      active.signal.aborted ||
      controller !== active
    ) {
      return
    }

    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'AI에게 질문하는 중 오류가 발생했습니다.'
  } finally {
    if (controller === active) {
      controller = null
      isSending.value = false
    }
  }
}

onBeforeUnmount(() => {
  controller?.abort()
  controller = null
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
        문제나 현재 코드, 이전 코칭 내용에 관해 질문해 보세요.
        답변은 질문 당시 코드 기준으로 작성됩니다.
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
              ? '답변 생성 중...'
              : '질문 보내기'
          }}
        </button>
      </form>

      <p
        v-if="isSending"
        class="waiting"
        role="status"
      >
        AI가 현재 코드와 질문 내용을 확인하고 있습니다.
      </p>

      <p
        v-if="errorMessage"
        class="error"
        role="alert"
      >
        {{ errorMessage }}
      </p>

      <div
        v-if="exchanges.length"
        class="conversation"
        aria-live="polite"
      >
        <h3>질문과 답변</h3>

        <article
          v-for="entry in exchanges"
          :key="entry.id"
          class="exchange"
        >
          <p class="user-question">
            <strong>질문</strong>
            {{ entry.question }}
          </p>

          <div class="agent-answer">
            <strong>
              AlgoCoach · Revision {{ entry.answeredRevision }}
            </strong>

            <p>{{ entry.answer }}</p>

            <p
              v-if="entry.answeredRevision !== currentRevision"
              class="outdated-note"
            >
              이후 코드가 변경됐습니다.
              이 답변은 현재 코드의 재검증 결과가 아닙니다.
            </p>
          </div>
        </article>
      </div>
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

.helper-text {
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

.question-form label,
.conversation h3 {
  margin: 0;
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
}

.error {
  margin: 0;
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.7;
}

.conversation {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.exchange {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 9px;
  background: #f8fafc;
}

.user-question,
.agent-answer p {
  margin: 0;
  color: #334155;
  font-size: 12px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.agent-answer {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 10px;
  padding: 11px;
  border-radius: 8px;
  background: #eff6ff;
}

.agent-answer strong {
  color: #1e40af;
  font-size: 11px;
}

.agent-answer .outdated-note {
  color: #92400e;
  font-size: 11px;
}
</style>