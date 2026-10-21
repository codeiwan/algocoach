<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import {
  completeSession,
  SessionCompletionApiError,
} from '@/services/session-completion'

import type { ProgrammingLanguage } from '@/types/programming-language'
import type {
  CoachingOutcome,
  SessionFeedbackRequest,
} from '@/services/session-feedback'
import type {
  JudgeVerdict,
  SessionCompletionOutcome,
  SessionCompletionRequest,
} from '@/types/session-completion'

const props = defineProps<{
  sessionId: string
  problemText: string
  currentCode: string
  language: ProgrammingLanguage
  currentRevision: number
}>()

const emit = defineEmits<{
  completed: [
    outcome: SessionCompletionOutcome,
    feedback: SessionFeedbackRequest | null,
  ]
}>()

type CompletionChoice = JudgeVerdict | 'WITHOUT_SUBMISSION'

interface CompletionOption {
  value: CompletionChoice
  label: string
  description: string
}

interface CoachingOption {
  value: CoachingOutcome
  label: string
}

interface PendingCompletion {
  completion: SessionCompletionRequest
  feedback: SessionFeedbackRequest | null
}

const primaryResults: CompletionOption[] = [
  {
    value: 'ACCEPTED',
    label: '정답',
    description: 'Accepted',
  },
  {
    value: 'WRONG_ANSWER',
    label: '오답',
    description: 'Wrong Answer',
  },
  {
    value: 'TIME_LIMIT_EXCEEDED',
    label: '시간 초과',
    description: 'Time Limit Exceeded',
  },
  {
    value: 'WITHOUT_SUBMISSION',
    label: '미제출',
    description: '채점 없이 종료',
  },
]

const otherResults: CompletionOption[] = [
  {
    value: 'MEMORY_LIMIT_EXCEEDED',
    label: '메모리 초과',
    description: 'Memory Limit Exceeded',
  },
  {
    value: 'RUNTIME_ERROR',
    label: '런타임 오류',
    description: 'Runtime Error',
  },
  {
    value: 'COMPILATION_ERROR',
    label: '컴파일 오류',
    description: 'Compilation Error',
  },
  {
    value: 'PRESENTATION_ERROR',
    label: '출력 형식 오류',
    description: 'Presentation Error',
  },
  {
    value: 'OUTPUT_LIMIT_EXCEEDED',
    label: '출력 초과',
    description: 'Output Limit Exceeded',
  },
  {
    value: 'OTHER',
    label: '기타 판정',
    description: 'Other',
  },
]

const coachingOptions: CoachingOption[] = [
  {
    value: 'ACCURATE_AND_HELPFUL',
    label: '정확했고 문제 해결에 도움이 됐어요',
  },
  {
    value: 'ACCURATE_BUT_NOT_HELPFUL',
    label: '방향은 맞았지만 해결에 큰 도움은 없었어요',
  },
  {
    value: 'MISLEADING_OR_INCORRECT',
    label: '잘못된 설명이나 코칭 오류가 있었어요',
  },
  {
    value: 'NOT_USED',
    label: 'AI 코칭을 사용하지 않았어요',
  },
  {
    value: 'UNABLE_TO_ASSESS',
    label: '사용했지만 정확성을 판단하기 어려워요',
  },
]

const isOpen = ref(false)
const isSubmitting = ref(false)
const errorMessage = ref('')

const selectedResult = ref<CompletionChoice | null>(null)
const coachingOutcome = ref<CoachingOutcome | null>(null)
const coachingComment = ref('')

const pendingCompletion = ref<PendingCompletion | null>(null)

let requestController: AbortController | null = null

const isExternalSubmission = computed(
  () =>
    selectedResult.value !== null &&
    selectedResult.value !== 'WITHOUT_SUBMISSION',
)

const canSubmit = computed(() => {
  if (
    isSubmitting.value ||
    pendingCompletion.value !== null ||
    selectedResult.value === null
  ) {
    return false
  }

  if (!props.problemText.trim()) {
    return false
  }

  if (
    isExternalSubmission.value &&
    !props.currentCode.trim()
  ) {
    return false
  }

  return true
})

function selectResult(value: CompletionChoice) {
  selectedResult.value = value
  errorMessage.value = ''
}

function selectCoaching(value: CoachingOutcome) {
  coachingOutcome.value =
    coachingOutcome.value === value ? null : value

  if (coachingOutcome.value === null) {
    coachingComment.value = ''
  }
}

function openDialog() {
  isOpen.value = true
}

function closeDialog() {
  if (isSubmitting.value) {
    return
  }

  isOpen.value = false
}

function discardPendingRequest() {
  if (isSubmitting.value) {
    return
  }

  pendingCompletion.value = null
  errorMessage.value = ''
}

function buildPendingCompletion(): PendingCompletion {
  const result = selectedResult.value

  if (result === null) {
    throw new Error('외부 채점 결과 또는 미제출을 선택해 주세요.')
  }

  const completionMode =
    result === 'WITHOUT_SUBMISSION'
      ? 'WITHOUT_SUBMISSION'
      : 'EXTERNAL_JUDGE'

  if (
    completionMode === 'EXTERNAL_JUDGE' &&
    !props.currentCode.trim()
  ) {
    throw new Error(
      '외부 채점 결과를 기록하려면 최종 코드가 필요합니다.',
    )
  }

  const completion: SessionCompletionRequest = {
    session_id: props.sessionId,
    code_revision: props.currentRevision,
    problem_text: props.problemText,
    final_code: props.currentCode,
    language: props.language,
    completion_mode: completionMode,
    judge_verdict: (
      completionMode === 'EXTERNAL_JUDGE'
        ? result as JudgeVerdict
        : null
    ),
    notes: null,
  }

  const feedback: SessionFeedbackRequest | null =
    coachingOutcome.value === null
      ? null
      : {
          session_id: props.sessionId,
          coaching_outcome: coachingOutcome.value,
          comment: coachingComment.value.trim() || null,
        }

  return {
    completion,
    feedback,
  }
}

async function sendCompletion(
  pending: PendingCompletion,
) {
  if (isSubmitting.value) {
    return
  }

  const controller = new AbortController()

  requestController = controller
  pendingCompletion.value = pending
  isSubmitting.value = true
  errorMessage.value = ''

  try {
    const outcome = await completeSession(
      pending.completion,
      controller.signal,
    )

    if (
      controller.signal.aborted ||
      requestController !== controller
    ) {
      return
    }

    requestController = null
    pendingCompletion.value = null

    // The parent owns feedback persistence after completion.
    // This prevents a feedback error from undoing a completed session.
    emit('completed', outcome, pending.feedback)
  } catch (error) {
    if (
      controller.signal.aborted ||
      requestController !== controller
    ) {
      return
    }

    errorMessage.value =
      error instanceof Error
        ? error.message
        : '풀이 종료 중 알 수 없는 오류가 발생했습니다.'

    if (
      error instanceof SessionCompletionApiError &&
      error.status === 409
    ) {
      errorMessage.value +=
        ' 서버의 기존 종료 기록과 충돌할 수 있습니다.'
    }
  } finally {
    if (requestController === controller) {
      requestController = null
    }

    isSubmitting.value = false
  }
}

function submitCompletion() {
  if (!canSubmit.value) {
    return
  }

  try {
    const pending = buildPendingCompletion()
    void sendCompletion(pending)
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : '종료 요청을 작성하지 못했습니다.'
  }
}

function retryCompletion() {
  if (
    isSubmitting.value ||
    pendingCompletion.value === null
  ) {
    return
  }

  // The same completion and coaching snapshot is reused.
  void sendCompletion(pendingCompletion.value)
}

onBeforeUnmount(() => {
  requestController?.abort()
  requestController = null
})
</script>

<template>
  <div class="completion-control">
    <button
      type="button"
      class="open-button"
      @click="openDialog"
    >
      풀이 종료
    </button>

    <div
      v-if="isOpen"
      class="modal-backdrop"
    >
      <section
        class="completion-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="completion-title"
        @keydown.esc="closeDialog"
      >
        <header class="dialog-header">
          <div>
            <span class="eyebrow">FINISH SESSION</span>
            <h2 id="completion-title">풀이 종료</h2>
          </div>

          <button
            type="button"
            class="close-button"
            :disabled="isSubmitting"
            aria-label="풀이 종료 창 닫기"
            @click="closeDialog"
          >
            ×
          </button>
        </header>

        <p class="dialog-description">
          결과를 선택하고, AI 코칭을 사용했다면
          정확성과 도움 정도를 알려주세요.
        </p>

        <fieldset
          class="completion-fields"
          :disabled="isSubmitting || pendingCompletion !== null"
        >
          <div class="question">
            <div class="question-header">
              <h3>1. 풀이 결과</h3>
              <span class="required">필수</span>
            </div>

            <div class="result-grid">
              <button
                v-for="option in primaryResults"
                :key="option.value"
                type="button"
                class="result-button"
                :class="{
                  selected: selectedResult === option.value,
                }"
                :aria-pressed="selectedResult === option.value"
                @click="selectResult(option.value)"
              >
                <strong>{{ option.label }}</strong>
                <span>{{ option.description }}</span>
              </button>
            </div>

            <details class="more-results">
              <summary>다른 채점 결과 선택</summary>

              <div class="other-result-grid">
                <button
                  v-for="option in otherResults"
                  :key="option.value"
                  type="button"
                  class="result-button secondary-result"
                  :class="{
                    selected: selectedResult === option.value,
                  }"
                  :aria-pressed="selectedResult === option.value"
                  @click="selectResult(option.value)"
                >
                  <strong>{{ option.label }}</strong>
                  <span>{{ option.description }}</span>
                </button>
              </div>
            </details>

            <p class="question-hint">
              외부 채점 사이트에서 확인한 결과를 선택하세요.
              제출하지 않았다면 '미제출'을 선택하세요.
            </p>

            <p
              v-if="isExternalSubmission && !currentCode.trim()"
              class="field-error"
            >
              외부 채점 결과를 기록하려면 코드를 먼저 작성해야 합니다.
            </p>
          </div>

          <div class="question">
            <div class="question-header">
              <h3>2. AI 코칭은 어떠했나요?</h3>
              <span class="optional">선택</span>
            </div>

            <div class="coaching-options">
              <button
                v-for="option in coachingOptions"
                :key="option.value"
                type="button"
                class="coaching-button"
                :class="{
                  selected: coachingOutcome === option.value,
                }"
                :aria-pressed="coachingOutcome === option.value"
                @click="selectCoaching(option.value)"
              >
                <span class="selection-dot" aria-hidden="true" />
                <span>{{ option.label }}</span>
              </button>
            </div>

            <p class="question-hint">
              평가하지 않아도 풀이를 종료할 수 있습니다.
              선택한 버튼을 다시 누르면 해제됩니다.
            </p>

            <div
              v-if="coachingOutcome !== null"
              class="comment-group"
            >
              <label for="coaching-comment">
                오류 내용 또는 개선 의견 (선택)
              </label>

              <textarea
                id="coaching-comment"
                v-model="coachingComment"
                rows="2"
                maxlength="1000"
                placeholder="예: 적절하지 않은 알고리즘을 추천했습니다."
              />

              <span class="comment-count">
                {{ coachingComment.length }} / 1,000
              </span>
            </div>
          </div>
        </fieldset>

        <div class="snapshot-info">
          <strong>종료 대상</strong>
          <span>
            {{ language.toUpperCase() }}
            · Revision {{ currentRevision }}
          </span>
        </div>

        <div
          v-if="pendingCompletion"
          class="retry-info"
        >
          <strong>이전 종료 요청의 응답을 확인하지 못했습니다.</strong>

          <p>
            서버가 이미 종료를 처리했을 수 있습니다.
            동일한 요청을 재전송하는 것이 가장 안전합니다.
          </p>

          <p>
            재전송 코드:
            {{ pendingCompletion.completion.language.toUpperCase() }}
            · Revision
            {{ pendingCompletion.completion.code_revision }}
          </p>
        </div>

        <p
          v-if="errorMessage"
          class="error-message"
          role="alert"
        >
          {{ errorMessage }}
        </p>

        <div class="dialog-actions">
          <button
            type="button"
            class="cancel-button"
            :disabled="isSubmitting"
            @click="closeDialog"
          >
            취소
          </button>

          <template v-if="pendingCompletion">
            <button
              type="button"
              class="reset-button"
              :disabled="isSubmitting"
              @click="discardPendingRequest"
            >
              새 요청 작성
            </button>

            <button
              type="button"
              class="submit-button"
              :disabled="isSubmitting"
              @click="retryCompletion"
            >
              {{
                isSubmitting
                  ? '처리 중...'
                  : '동일 요청 재시도'
              }}
            </button>
          </template>

          <button
            v-else
            type="button"
            class="submit-button"
            :disabled="!canSubmit"
            @click="submitCompletion"
          >
            {{
              isSubmitting
                ? '종료 처리 중...'
                : '풀이 종료 확정'
            }}
          </button>
        </div>

        <p class="disclaimer">
          외부 판정과 AI 코칭 평가는 사용자 보고 정보입니다.
          AlgoCoach가 직접 코드를 채점한 결과가 아닙니다.
        </p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.open-button {
  min-height: 42px;
  padding: 10px 18px;
  border: 1px solid #dc2626;
  border-radius: 9px;
  background: #fff;
  color: #b91c1c;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.open-button:hover {
  background: #fef2f2;
}

.modal-backdrop {
  position: fixed;
  z-index: 2000;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgb(15 23 42 / 58%);
}

.completion-dialog {
  box-sizing: border-box;
  width: min(100%, 580px);
  max-height: 92vh;
  overflow-y: auto;
  padding: 24px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 20px 60px rgb(0 0 0 / 20%);
}

.dialog-header,
.question-header,
.snapshot-info,
.dialog-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dialog-header {
  align-items: flex-start;
}

.eyebrow {
  color: #2563eb;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.dialog-header h2 {
  margin: 5px 0 0;
  color: #0f172a;
  font-size: 23px;
}

.close-button {
  border: 0;
  background: transparent;
  color: #64748b;
  font-size: 28px;
  cursor: pointer;
}

.dialog-description {
  margin: 12px 0 20px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.8;
}

.completion-fields {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.question {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.question-header {
  justify-content: flex-start;
}

.question h3 {
  margin: 0;
  color: #0f172a;
  font-size: 14px;
}

.required,
.optional {
  font-size: 11px;
  font-weight: 600;
}

.required {
  color: #2563eb;
}

.optional {
  color: #94a3b8;
}

.result-grid,
.other-result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
}

.result-button {
  display: flex;
  min-height: 80px;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  background: #f8fafc;
  color: #334155;
  font: inherit;
  cursor: pointer;
}

.result-button strong {
  font-size: 17px;
}

.result-button span {
  color: #64748b;
  font-size: 11px;
  text-align: center;
  overflow-wrap: anywhere;
}

.result-button.selected,
.coaching-button.selected {
  border: 2px solid #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
}

.result-button.selected span {
  color: #1d4ed8;
}

.more-results {
  padding: 2px 0;
}

.more-results summary {
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.other-result-grid {
  margin-top: 12px;
}

.secondary-result {
  min-height: 64px;
}

.secondary-result strong {
  font-size: 13px;
}

.coaching-options {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.coaching-button {
  display: flex;
  min-height: 48px;
  align-items: center;
  gap: 12px;
  padding: 11px 13px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  color: #334155;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  line-height: 1.6;
  cursor: pointer;
}

.selection-dot {
  box-sizing: border-box;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border: 2px solid #94a3b8;
  border-radius: 50%;
  background: #fff;
}

.coaching-button.selected .selection-dot {
  border: 5px solid #2563eb;
}

.result-button:hover:not(:disabled),
.coaching-button:hover:not(:disabled) {
  border-color: #93c5fd;
  background: #eff6ff;
}

.question-hint {
  margin: 0;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.6;
}

.field-error,
.error-message {
  margin: 0;
  color: #dc2626;
  font-size: 12px;
  line-height: 1.7;
}

.comment-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.comment-group label {
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.comment-group textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 11px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  color: #0f172a;
  font: inherit;
  font-size: 12px;
  line-height: 1.7;
  resize: vertical;
}

.comment-count {
  color: #94a3b8;
  font-size: 11px;
  text-align: right;
}

.snapshot-info {
  flex-wrap: wrap;
  margin-top: 20px;
  padding: 12px;
  border-radius: 8px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
}

.retry-info {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: #fffbeb;
  color: #92400e;
  font-size: 12px;
  line-height: 1.7;
}

.retry-info p {
  margin: 7px 0 0;
}

.error-message {
  margin-top: 12px;
}

.dialog-actions {
  justify-content: flex-end;
  flex-wrap: wrap;
  margin-top: 22px;
}

.dialog-actions button {
  min-height: 44px;
  padding: 11px 15px;
  border-radius: 8px;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.dialog-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cancel-button,
.reset-button {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
}

.submit-button {
  border: 1px solid #2563eb;
  background: #2563eb;
  color: #fff;
}

.disclaimer {
  margin: 14px 0 0;
  color: #94a3b8;
  font-size: 10px;
  line-height: 1.7;
}

@media (max-width: 600px) {
  .completion-dialog {
    padding: 18px;
  }

  .result-button {
    min-height: 72px;
    padding: 8px;
  }

  .result-button strong {
    font-size: 15px;
  }

  .dialog-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .dialog-actions button {
    width: 100%;
  }
}
</style>