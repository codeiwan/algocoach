<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  ref,
} from 'vue'

import {
  recordSessionFeedback,
  type MainChallenge,
  type SessionFeedbackReceipt,
  type SessionFeedbackRequest,
} from '@/services/session-feedback'

const props = defineProps<{
  sessionId: string
}>()

interface RatingOption {
  value: number
  label: string
}

interface ChallengeOption {
  value: MainChallenge
  label: string
}

const difficultyOptions: RatingOption[] = [
  { value: 1, label: '매우 쉬움' },
  { value: 2, label: '쉬움' },
  { value: 3, label: '보통' },
  { value: 4, label: '어려움' },
  { value: 5, label: '매우 어려움' },
]

const helpfulnessOptions: RatingOption[] = [
  { value: 1, label: '전혀' },
  { value: 2, label: '조금' },
  { value: 3, label: '보통' },
  { value: 4, label: '도움됨' },
  { value: 5, label: '매우 도움' },
]

const challengeOptions: ChallengeOption[] = [
  { value: 'UNDERSTANDING', label: '문제 이해' },
  { value: 'ALGORITHM', label: '알고리즘 선택' },
  { value: 'IMPLEMENTATION', label: '코드 구현' },
  { value: 'DEBUGGING', label: '디버깅' },
  { value: 'COMPLEXITY', label: '시간·공간 복잡도' },
  { value: 'OTHER', label: '기타' },
]

const difficultyRating = ref<number | null>(null)
const mainChallenge = ref<MainChallenge | null>(null)
const hintHelpfulnessRating = ref<number | null>(null)
const comment = ref('')

const isSaving = ref(false)
const isSkipped = ref(false)
const skippedAfterError = ref(false)
const errorMessage = ref('')

const receipt = ref<SessionFeedbackReceipt | null>(null)

// Preserve the original payload when an HTTP response is uncertain.
const pendingRequest = ref<SessionFeedbackRequest | null>(null)

let requestController: AbortController | null = null

const isFinished = computed(
  () => receipt.value !== null || isSkipped.value,
)

const canSubmit = computed(
  () =>
    !isSaving.value &&
    !isFinished.value &&
    pendingRequest.value === null &&
    difficultyRating.value !== null,
)

function selectDifficulty(value: number) {
  difficultyRating.value = value
}

function selectChallenge(value: MainChallenge) {
  mainChallenge.value =
    mainChallenge.value === value ? null : value
}

function selectHintHelpfulness(value: number) {
  hintHelpfulnessRating.value =
    hintHelpfulnessRating.value === value ? null : value
}

function buildRequest(): SessionFeedbackRequest {
  if (difficultyRating.value === null) {
    throw new Error('체감 난이도를 선택해 주세요.')
  }

  return {
    session_id: props.sessionId,
    difficulty_rating: difficultyRating.value,
    intervention_timing_rating: null,
    hint_helpfulness_rating: hintHelpfulnessRating.value,
    review_helpfulness_rating: null,
    main_challenge: mainChallenge.value,
    comment: comment.value.trim() || null,
  }
}

async function sendFeedback(request: SessionFeedbackRequest) {
  if (isSaving.value || isFinished.value) {
    return
  }

  const controller = new AbortController()

  requestController = controller
  pendingRequest.value = request
  isSaving.value = true
  errorMessage.value = ''

  try {
    const result = await recordSessionFeedback(
      request,
      controller.signal,
    )

    if (
      controller.signal.aborted ||
      requestController !== controller
    ) {
      return
    }

    receipt.value = result
    pendingRequest.value = null
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
        : '설문 저장 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    if (requestController === controller) {
      requestController = null
      isSaving.value = false
    }
  }
}

function submitFeedback() {
  if (!canSubmit.value) {
    return
  }

  void sendFeedback(buildRequest())
}

function retryFeedback() {
  if (
    isSaving.value ||
    isFinished.value ||
    pendingRequest.value === null
  ) {
    return
  }

  // Retry exactly the same payload.
  // A different payload could conflict with an accepted request.
  void sendFeedback(pendingRequest.value)
}

function skipFeedback() {
  if (isSaving.value || isFinished.value) {
    return
  }

  skippedAfterError.value = pendingRequest.value !== null
  pendingRequest.value = null
  errorMessage.value = ''
  isSkipped.value = true
}

onBeforeUnmount(() => {
  requestController?.abort()
  requestController = null
})
</script>

<template>
  <section class="feedback-panel">
    <template v-if="receipt">
      <div class="feedback-finished">
        <span class="finished-icon" aria-hidden="true">✓</span>

        <div>
          <h2>학습 설문이 기록되었습니다.</h2>

          <p>
            남겨주신 응답은 향후 AI 코칭 품질을
            분석하고 개선하는 데 활용할 수 있습니다.
          </p>

          <p class="recorded-time">
            기록 시각:
            {{ new Date(receipt.recorded_at).toLocaleString('ko-KR') }}
          </p>
        </div>
      </div>
    </template>

    <template v-else-if="isSkipped">
      <div class="feedback-finished">
        <span class="finished-icon skipped" aria-hidden="true">
          —
        </span>

        <div>
          <h2>설문을 건너뛰었습니다.</h2>

          <p v-if="skippedAfterError">
            이전 저장 요청의 서버 처리 여부를 확인하지 못했습니다.
            별도의 설문 기록이 이미 존재할 수 있습니다.
          </p>

          <p v-else>
            설문을 남기지 않아도 풀이 종료는 정상적으로 완료됩니다.
          </p>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="feedback-header">
        <div>
          <span class="eyebrow">QUICK FEEDBACK</span>
          <h2>이번 풀이, 어떠셨나요?</h2>
        </div>

        <span class="optional-tag">짧은 설문</span>
      </div>

      <p class="intro">
        응답은 향후 AI 코칭 개선을 위한 참고 자료입니다.
        체감 난이도만 선택하면 제출할 수 있습니다.
      </p>

      <fieldset
        class="feedback-form"
        :disabled="isSaving || pendingRequest !== null"
      >
        <div class="question-block">
          <div class="question-heading">
            <h3>1. 문제는 얼마나 어려웠나요?</h3>
            <span class="required-label">필수</span>
          </div>

          <div
            class="rating-grid"
            role="group"
            aria-label="체감 난이도"
          >
            <button
              v-for="option in difficultyOptions"
              :key="option.value"
              type="button"
              class="rating-button"
              :class="{ selected: difficultyRating === option.value }"
              :aria-pressed="difficultyRating === option.value"
              @click="selectDifficulty(option.value)"
            >
              <strong>{{ option.value }}</strong>
              <span>{{ option.label }}</span>
            </button>
          </div>
        </div>

        <div class="question-block">
          <div class="question-heading">
            <h3>2. 가장 어려웠던 부분은?</h3>
            <span class="optional-label">선택</span>
          </div>

          <div
            class="challenge-grid"
            role="group"
            aria-label="가장 어려웠던 부분"
          >
            <button
              v-for="option in challengeOptions"
              :key="option.value"
              type="button"
              class="challenge-button"
              :class="{ selected: mainChallenge === option.value }"
              :aria-pressed="mainChallenge === option.value"
              @click="selectChallenge(option.value)"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <div class="question-block">
          <div class="question-heading">
            <h3>3. AI 힌트가 도움이 됐나요?</h3>
            <span class="optional-label">선택</span>
          </div>

          <p class="question-help">
            힌트를 사용하지 않았다면 선택하지 않아도 됩니다.
            선택한 버튼을 다시 누르면 선택이 해제됩니다.
          </p>

          <div
            class="rating-grid"
            role="group"
            aria-label="AI 힌트 도움 정도"
          >
            <button
              v-for="option in helpfulnessOptions"
              :key="option.value"
              type="button"
              class="rating-button"
              :class="{
                selected: hintHelpfulnessRating === option.value,
              }"
              :aria-pressed="hintHelpfulnessRating === option.value"
              @click="selectHintHelpfulness(option.value)"
            >
              <strong>{{ option.value }}</strong>
              <span>{{ option.label }}</span>
            </button>
          </div>
        </div>

        <details class="comment-details">
          <summary>추가 의견 남기기 (선택)</summary>

          <textarea
            v-model="comment"
            rows="3"
            maxlength="1000"
            placeholder="AI 코칭에서 개선되었으면 하는 점을 자유롭게 적어주세요."
          />

          <span class="comment-count">
            {{ comment.length }} / 1,000
          </span>
        </details>
      </fieldset>

      <div
        v-if="pendingRequest"
        class="retry-message"
      >
        <strong>이전 설문 요청의 처리 결과를 확인하지 못했습니다.</strong>

        <p>
          서버가 이미 기록했을 수 있으므로
          처음 전송한 설문을 그대로 재시도할 수 있습니다.
        </p>
      </div>

      <p
        v-if="errorMessage"
        class="error-message"
        role="alert"
      >
        {{ errorMessage }}
      </p>

      <div class="feedback-actions">
        <button
          type="button"
          class="skip-button"
          :disabled="isSaving"
          @click="skipFeedback"
        >
          건너뛰기
        </button>

        <button
          v-if="pendingRequest"
          type="button"
          class="submit-button"
          :disabled="isSaving"
          @click="retryFeedback"
        >
          {{
            isSaving
              ? '저장 중...'
              : '동일한 설문 재시도'
          }}
        </button>

        <button
          v-else
          type="button"
          class="submit-button"
          :disabled="!canSubmit"
          @click="submitFeedback"
        >
          {{
            isSaving
              ? '저장 중...'
              : '설문 제출'
          }}
        </button>
      </div>

      <p class="storage-notice">
        현재 개발 버전에서는 설문을 서버 메모리에 기록합니다.
        관리자 통계 및 영구 저장은 향후 확장 기능입니다.
      </p>
    </template>
  </section>
</template>

<style scoped>
.feedback-panel {
  padding: 24px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
}

.feedback-header {
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

.feedback-header h2 {
  margin: 8px 0 0;
  color: #0f172a;
  font-size: 21px;
}

.optional-tag {
  flex-shrink: 0;
  padding: 6px 9px;
  border-radius: 6px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 600;
}

.intro {
  margin: 12px 0 22px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.8;
}

.feedback-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.question-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.question-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.question-heading h3 {
  margin: 0;
  color: #0f172a;
  font-size: 14px;
}

.required-label,
.optional-label {
  font-size: 11px;
  font-weight: 600;
}

.required-label {
  color: #2563eb;
}

.optional-label {
  color: #94a3b8;
}

.rating-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.rating-button {
  display: flex;
  min-height: 70px;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 4px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  color: #334155;
  font: inherit;
  cursor: pointer;
  transition:
    background-color 120ms ease,
    border-color 120ms ease;
}

.rating-button strong {
  font-size: 20px;
}

.rating-button span {
  font-size: 11px;
  line-height: 1.3;
  text-align: center;
  overflow-wrap: anywhere;
}

.challenge-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.challenge-button {
  min-height: 52px;
  padding: 10px;
  border: 1px solid #cbd5e1;
  border-radius: 9px;
  background: #f8fafc;
  color: #334155;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.rating-button:hover:not(:disabled),
.challenge-button:hover:not(:disabled) {
  border-color: #93c5fd;
  background: #eff6ff;
}

.rating-button.selected,
.challenge-button.selected {
  border-color: #2563eb;
  background: #dbeafe;
  color: #1d4ed8;
}

.rating-button:focus-visible,
.challenge-button:focus-visible,
.feedback-actions button:focus-visible {
  outline: 3px solid #93c5fd;
  outline-offset: 2px;
}

.question-help {
  margin: 0;
  color: #64748b;
  font-size: 11px;
  line-height: 1.7;
}

.comment-details {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 9px;
}

.comment-details summary {
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.comment-details textarea {
  box-sizing: border-box;
  width: 100%;
  margin-top: 12px;
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
  display: block;
  margin-top: 4px;
  color: #94a3b8;
  font-size: 11px;
  text-align: right;
}

.feedback-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}

.feedback-actions button {
  min-width: 128px;
  min-height: 46px;
  padding: 11px 16px;
  border-radius: 9px;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.feedback-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.skip-button {
  border: 1px solid #cbd5e1;
  background: white;
  color: #475569;
}

.submit-button {
  border: 1px solid #2563eb;
  background: #2563eb;
  color: white;
}

.retry-message {
  margin-top: 20px;
  padding: 12px;
  border-radius: 8px;
  background: #fffbeb;
  color: #92400e;
  font-size: 12px;
  line-height: 1.7;
}

.retry-message p {
  margin: 6px 0 0;
}

.error-message {
  margin: 12px 0 0;
  color: #dc2626;
  font-size: 12px;
  line-height: 1.7;
}

.storage-notice {
  margin: 16px 0 0;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.7;
}

.feedback-finished {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.finished-icon {
  display: flex;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #dcfce7;
  color: #166534;
  font-size: 22px;
  font-weight: 700;
}

.finished-icon.skipped {
  background: #f1f5f9;
  color: #64748b;
}

.feedback-finished h2 {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 17px;
}

.feedback-finished p {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.8;
}

.feedback-finished .recorded-time {
  margin-top: 8px;
  font-size: 11px;
}

@media (max-width: 600px) {
  .feedback-panel {
    padding: 16px;
  }

  .challenge-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .rating-grid {
    gap: 5px;
  }

  .rating-button {
    min-height: 64px;
    padding: 7px 2px;
  }

  .rating-button span {
    font-size: 10px;
  }

  .feedback-actions {
    flex-direction: column;
  }

  .feedback-actions button {
    width: 100%;
  }
}
</style>