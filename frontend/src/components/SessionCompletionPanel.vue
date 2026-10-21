<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import {
  completeSession,
  SessionCompletionApiError,
} from '@/services/session-completion'

import type { ProgrammingLanguage } from '@/types/programming-language'
import {
  JUDGE_VERDICT_LABELS,
  type CompletionMode,
  type JudgeVerdict,
  type SessionCompletionOutcome,
  type SessionCompletionRequest,
} from '@/types/session-completion'

const props = defineProps<{
  sessionId: string
  problemText: string
  currentCode: string
  language: ProgrammingLanguage
  currentRevision: number
}>()

const emit = defineEmits<{
  completed: [outcome: SessionCompletionOutcome]
}>()

const isOpen = ref(false)
const isSubmitting = ref(false)
const errorMessage = ref('')

const completionMode = ref<CompletionMode | ''>('')
const selectedVerdict = ref<JudgeVerdict | ''>('')
const notes = ref('')

// Keep the exact request for safe retries after network errors.
const retryRequest = ref<SessionCompletionRequest | null>(null)

let requestController: AbortController | null = null

const verdictOptions = (
  Object.entries(JUDGE_VERDICT_LABELS) as [JudgeVerdict, string][]
).map(([value, label]) => ({
  value,
  label,
}))

const canSubmit = computed(() => {
  if (isSubmitting.value || retryRequest.value !== null) {
    return false
  }

  if (!props.problemText.trim() || !completionMode.value) {
    return false
  }

  if (completionMode.value === 'EXTERNAL_JUDGE') {
    return (
      selectedVerdict.value !== '' &&
      props.currentCode.trim().length > 0
    )
  }

  return completionMode.value === 'WITHOUT_SUBMISSION'
})

function openDialog() {
  isOpen.value = true
  errorMessage.value = ''
}

function closeDialog() {
  if (isSubmitting.value) {
    return
  }

  isOpen.value = false
}

function prepareNewRequest() {
  if (isSubmitting.value) {
    return
  }

  retryRequest.value = null
  errorMessage.value = ''
}

function buildRequest(): SessionCompletionRequest {
  const mode = completionMode.value

  if (!mode) {
    throw new Error('풀이 종료 방식을 선택해 주세요.')
  }

  if (
    mode === 'EXTERNAL_JUDGE' &&
    (!selectedVerdict.value || !props.currentCode.trim())
  ) {
    throw new Error(
      '외부 채점 결과와 제출한 코드를 확인해 주세요.',
    )
  }

  return {
    session_id: props.sessionId,
    code_revision: props.currentRevision,
    problem_text: props.problemText,
    final_code: props.currentCode,
    language: props.language,
    completion_mode: mode,
    judge_verdict: (
      mode === 'EXTERNAL_JUDGE'
        ? selectedVerdict.value as JudgeVerdict
        : null
    ),
    notes: notes.value.trim() || null,
  }
}

async function sendCompletion(
  request: SessionCompletionRequest,
) {
  if (isSubmitting.value) {
    return
  }

  const controller = new AbortController()

  requestController = controller
  retryRequest.value = request
  isSubmitting.value = true
  errorMessage.value = ''

  try {
    const outcome = await completeSession(
      request,
      controller.signal,
    )

    if (
      controller.signal.aborted ||
      requestController !== controller
    ) {
      return
    }

    retryRequest.value = null
    emit('completed', outcome)
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
        ' 서버가 기존 기록을 보유하고 있을 수 있습니다.'
    }
  } finally {
    if (requestController === controller) {
      requestController = null
      isSubmitting.value = false
    }
  }
}

function submitCompletion() {
  if (!canSubmit.value) {
    return
  }

  const request = buildRequest()
  void sendCompletion(request)
}

function retryCompletion() {
  if (isSubmitting.value || retryRequest.value === null) {
    return
  }

  // Retry the identical request, not a newly edited code snapshot.
  void sendCompletion(retryRequest.value)
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
            <span class="eyebrow">SESSION COMPLETION</span>
            <h2 id="completion-title">풀이 종료</h2>
          </div>

          <button
            type="button"
            class="close-button"
            :disabled="isSubmitting"
            aria-label="닫기"
            @click="closeDialog"
          >
            ×
          </button>
        </header>

        <p class="dialog-intro">
          외부 코딩테스트 사이트에서 확인한 채점 결과를
          직접 기록하거나, 제출하지 않고 풀이를 종료할 수 있습니다.
        </p>

        <form @submit.prevent="submitCompletion">
          <fieldset
            class="form-fields"
            :disabled="isSubmitting || retryRequest !== null"
          >
            <div class="field-group">
              <label for="completion-mode">종료 방식</label>

              <select
                id="completion-mode"
                v-model="completionMode"
                required
              >
                <option value="" disabled>
                  종료 방식 선택
                </option>
                <option value="EXTERNAL_JUDGE">
                  외부 채점 결과 기록
                </option>
                <option value="WITHOUT_SUBMISSION">
                  제출 없이 종료
                </option>
              </select>
            </div>

            <div
              v-if="completionMode === 'EXTERNAL_JUDGE'"
              class="field-group"
            >
              <label for="judge-verdict">
                외부 사이트의 채점 결과
              </label>

              <select
                id="judge-verdict"
                v-model="selectedVerdict"
                required
              >
                <option value="" disabled>
                  채점 결과 선택
                </option>

                <option
                  v-for="option in verdictOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>

              <p class="field-help">
                AlgoCoach의 AI 점검 결과가 아니라,
                실제 외부 사이트에서 확인한 판정을 선택하세요.
              </p>

              <p
                v-if="!currentCode.trim()"
                class="field-error"
              >
                외부 채점 결과를 기록하려면 최종 코드가 필요합니다.
              </p>
            </div>

            <div
              v-if="completionMode === 'WITHOUT_SUBMISSION'"
              class="mode-notice"
            >
              외부 채점 결과 없이 종료합니다.
              코드가 비어 있어도 종료할 수 있습니다.
            </div>

            <div class="field-group">
              <label for="completion-notes">
                메모 (선택)
              </label>

              <textarea
                id="completion-notes"
                v-model="notes"
                rows="3"
                maxlength="2000"
                placeholder="어려웠던 점이나 종료 사유를 기록하세요."
              />

              <span class="character-count">
                {{ notes.length }} / 2,000
              </span>
            </div>
          </fieldset>

          <div class="snapshot-info">
            <strong>종료할 코드 스냅샷</strong>
            <span>
              {{ language.toUpperCase() }}
              · Revision {{ currentRevision }}
            </span>
          </div>

          <div
            v-if="retryRequest"
            class="retry-info"
          >
            <strong>이전 종료 요청이 확정되지 않았습니다.</strong>

            <p>
              네트워크 오류라면 서버에서 이미 종료 처리가
              완료됐을 수 있습니다. 아래 재시도 버튼은
              처음 전송했던 요청을 동일하게 재전송합니다.
            </p>

            <p>
              재시도 대상:
              {{ retryRequest.language.toUpperCase() }}
              · Revision {{ retryRequest.code_revision }}
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

            <template v-if="retryRequest">
              <button
                type="button"
                class="secondary-button"
                :disabled="isSubmitting"
                @click="prepareNewRequest"
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
                    : '동일한 요청 재시도'
                }}
              </button>
            </template>

            <button
              v-else
              type="submit"
              class="submit-button"
              :disabled="!canSubmit"
            >
              {{
                isSubmitting
                  ? '종료 처리 중...'
                  : '풀이 종료 확정'
              }}
            </button>
          </div>
        </form>

        <p class="disclaimer">
          종료 처리 후에는 같은 세션의 결과를 변경할 수 없습니다.
          외부 채점 결과는 사용자가 직접 보고한 정보로 저장됩니다.
        </p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.open-button {
  padding: 10px 16px;
  border: 1px solid #dc2626;
  border-radius: 8px;
  background: white;
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
  padding: 20px;
  background: rgb(15 23 42 / 58%);
}

.completion-dialog {
  width: min(100%, 520px);
  max-height: 90vh;
  overflow-y: auto;
  padding: 28px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: white;
  box-shadow: 0 20px 60px rgb(0 0 0 / 20%);
}

.dialog-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
}

.eyebrow {
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.dialog-header h2 {
  margin: 8px 0 0;
  color: #0f172a;
  font-size: 23px;
}

.close-button {
  border: 0;
  background: transparent;
  color: #64748b;
  font-size: 27px;
  cursor: pointer;
}

.dialog-intro {
  margin: 18px 0;
  color: #475569;
  font-size: 13px;
  line-height: 1.8;
}

.form-fields {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-group label {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}

.field-group select,
.field-group textarea {
  width: 100%;
  padding: 11px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: white;
  color: #0f172a;
  font: inherit;
  font-size: 13px;
}

.field-group textarea {
  line-height: 1.7;
  resize: vertical;
}

.field-help,
.field-error,
.character-count {
  margin: 0;
  font-size: 11px;
  line-height: 1.6;
}

.field-help,
.character-count {
  color: #64748b;
}

.field-error,
.error-message {
  color: #dc2626;
}

.character-count {
  text-align: right;
}

.mode-notice,
.snapshot-info,
.retry-info {
  padding: 12px;
  border-radius: 8px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  line-height: 1.8;
}

.snapshot-info {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}

.retry-info {
  margin-top: 12px;
  background: #fffbeb;
}

.retry-info p {
  margin: 8px 0 0;
}

.error-message {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.7;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
}

.dialog-actions button {
  padding: 11px 14px;
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
.secondary-button {
  border: 1px solid #cbd5e1;
  background: white;
  color: #334155;
}

.submit-button {
  border: 1px solid #2563eb;
  background: #2563eb;
  color: white;
}

.disclaimer {
  margin: 20px 0 0;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.7;
}

@media (max-width: 600px) {
  .completion-dialog {
    padding: 18px;
  }

  .dialog-actions {
    flex-direction: column;
  }

  .dialog-actions button {
    width: 100%;
  }
}
</style>
