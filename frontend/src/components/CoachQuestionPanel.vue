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

// --------------------------------------------------
// Composer state
// --------------------------------------------------

const question = ref('')
const isSending = ref(false)
const errorMessage = ref('')

// Keep recent exchanges for contextual follow-up
// questions. The visible history belongs to the
// unified AlgoCoach feed, not this input component.
const exchanges = ref<Exchange[]>([])

let nextExchangeId = 0
let controller: AbortController | null = null

// --------------------------------------------------
// Conversation context
// --------------------------------------------------

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

// --------------------------------------------------
// Keyboard interaction
// --------------------------------------------------

function handleKeydown(event: KeyboardEvent) {
  if (
    event.key !== 'Enter' ||
    event.shiftKey ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey ||
    event.isComposing ||
    event.repeat
  ) {
    return
  }

  // Enter submits the question.
  // Shift+Enter retains native newline behavior.
  event.preventDefault()

  void submitQuestion()
}

// --------------------------------------------------
// Submit contextual coaching question
// --------------------------------------------------

async function submitQuestion() {
  const text = question.value.trim()

  if (
    !text ||
    isSending.value
  ) {
    return
  }

  // Preserve the code snapshot and Revision from
  // the instant the question is submitted.
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

  // Notify the agent that an actual API request
  // has started.
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

    // Retain a bounded local conversation history.
    exchanges.value = [
      exchange,
      ...exchanges.value,
    ].slice(0, 20)

    // Send the result to the unified agent feed.
    emit('answered', exchange)

    // Clear only after a successful response.
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

    // Keep the original question available
    // so the learner can retry without retyping.
    errorMessage.value =
      error instanceof Error
        ? error.message
        : 'AI 질문 요청 중 오류가 발생했습니다.'
  } finally {
    if (controller === activeController) {
      controller = null
      isSending.value = false

      emit('activity', false)
    }
  }
}

// --------------------------------------------------
// Cleanup
// --------------------------------------------------

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
    <form
      class="question-form"
      @submit.prevent="submitQuestion"
    >
      <label
        for="coach-question-input"
        class="composer-label"
      >
        AI에게 질문
      </label>

      <div
        class="composer"
        :class="{
          'composer-busy': isSending,
          'composer-error': !!errorMessage,
        }"
      >
        <textarea
          id="coach-question-input"
          v-model="question"
          class="composer-input"
          rows="2"
          maxlength="1000"
          :disabled="isSending"
          placeholder="현재 코드나 문제에 대해 질문하세요..."
          aria-label="AI 코치에게 질문할 내용"
          @keydown="handleKeydown"
        />

        <div class="composer-footer">
          <span class="keyboard-hint">
            Enter 전송 · Shift+Enter 줄바꿈
          </span>

          <button
            type="submit"
            class="send-button"
            :disabled="!question.trim() || isSending"
            :aria-label="
              isSending
                ? 'AI 답변 생성 중'
                : 'AI에게 질문 전송'
            "
          >
            <span>
              {{
                isSending
                  ? '응답 중'
                  : '전송'
              }}
            </span>

            <span
              v-if="!isSending"
              class="send-arrow"
              aria-hidden="true"
            >
              ↑
            </span>
          </button>
        </div>
      </div>
    </form>

    <p
      v-if="isSending"
      class="status-message"
      role="status"
    >
      현재 코드와 질문을 바탕으로 답변을 생성하고 있습니다.
    </p>

    <p
      v-if="errorMessage"
      class="error-message"
      role="alert"
    >
      {{ errorMessage }}
    </p>
  </section>
</template>

<style scoped>
/* --------------------------------------------------
   Question composer container
-------------------------------------------------- */

.question-panel {
  display: flex;
  flex-direction: column;
  gap: 7px;

  min-width: 0;

  border: none;
  border-radius: 10px;
  background: transparent;
}

.question-form {
  display: flex;
  flex-direction: column;
  gap: 7px;

  min-width: 0;
}

.composer-label {
  padding-left: 2px;

  color: #475569;
  font-size: 11px;
  font-weight: 700;
}

/* --------------------------------------------------
   Composer
-------------------------------------------------- */

.composer {
  display: flex;
  flex-direction: column;
  gap: 6px;

  min-width: 0;

  padding: 10px;

  border: 1px solid #cbd5e1;
  border-radius: 11px;

  background: #fff;

  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.composer:focus-within {
  border-color: #60a5fa;

  box-shadow:
    0 0 0 3px rgba(59, 130, 246, 0.1);
}

.composer-busy {
  background: #f8fafc;
}

.composer-error {
  border-color: #fca5a5;
}

.composer-input {
  box-sizing: border-box;

  display: block;
  width: 100%;
  min-height: 40px;
  max-height: 110px;

  padding: 1px 2px;

  border: none;
  border-radius: 0;
  outline: none;

  background: transparent;
  color: #0f172a;

  font: inherit;
  font-size: 12px;
  line-height: 1.65;

  resize: vertical;
}

.composer-input::placeholder {
  color: #94a3b8;
}

.composer-input:disabled {
  color: #64748b;
  cursor: wait;
}

/* --------------------------------------------------
   Bottom controls
-------------------------------------------------- */

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;

  min-width: 0;
}

.keyboard-hint {
  min-width: 0;

  color: #94a3b8;
  font-size: 10px;
  line-height: 1.4;
}

.send-button {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  gap: 6px;

  min-height: 31px;
  padding: 6px 11px;

  border: none;
  border-radius: 8px;

  background: #2563eb;
  color: #fff;

  font: inherit;
  font-size: 11px;
  font-weight: 700;

  cursor: pointer;
}

.send-button:hover:not(:disabled) {
  background: #1d4ed8;
}

.send-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.send-arrow {
  font-size: 15px;
  line-height: 1;
}

/* --------------------------------------------------
   Status and error messages
-------------------------------------------------- */

.status-message,
.error-message {
  margin: 0;
  padding: 0 2px;

  font-size: 11px;
  line-height: 1.6;
}

.status-message {
  color: #2563eb;
}

.error-message {
  color: #b91c1c;
}

/* --------------------------------------------------
   Narrow screen
-------------------------------------------------- */

@media (max-width: 420px) {
  .keyboard-hint {
    font-size: 9px;
  }

  .composer {
    padding: 8px;
  }

  .send-button {
    padding: 6px 9px;
  }
}
</style>