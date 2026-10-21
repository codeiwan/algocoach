<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

import { reviewSubmission } from '@/services/submission'

import type { ProgrammingLanguage } from '@/types/programming-language'
import type {
  ReviewCategory,
  ReviewSeverity,
  ReviewStatus,
  SubmissionReviewResult,
} from '@/types/submission'

const props = defineProps<{
  sessionId: string
  problemText: string
  currentCode: string
  language: ProgrammingLanguage
  currentRevision: number
  disabled?: boolean
}>()

interface ReviewedSnapshot {
  sessionId: string
  revision: number
  code: string
  language: ProgrammingLanguage
}

const isLoading = ref(false)
const errorMessage = ref('')

const lastReview = ref<SubmissionReviewResult | null>(null)
const lastReviewedSnapshot = ref<ReviewedSnapshot | null>(null)

let reviewController: AbortController | null = null

const statusLabels: Record<ReviewStatus, string> = {
  RISK_FOUND: '잠재적 위험 발견',
  NO_OBVIOUS_RISK: '뚜렷한 위험 미발견',
  UNCERTAIN: '판단 보류',
}

const categoryLabels: Record<ReviewCategory, string> = {
  LOGIC: '논리 오류',
  EDGE_CASE: '경계 조건',
  COMPLEXITY: '복잡도',
  INPUT_OUTPUT: '입출력',
  CONSTRAINT: '제약 조건',
  LANGUAGE: '언어별 주의사항',
}

const severityLabels: Record<ReviewSeverity, string> = {
  HIGH: '높음',
  MEDIUM: '보통',
  LOW: '낮음',
}

const canReview = computed(() => {
  return (
    !isLoading.value &&
    !props.disabled &&
    props.problemText.trim().length > 0 &&
    props.currentCode.trim().length > 0
  )
})

const isCurrentReview = computed(() => {
  const snapshot = lastReviewedSnapshot.value

  if (lastReview.value === null || snapshot === null) {
    return false
  }

  return (
    snapshot.sessionId === props.sessionId &&
    snapshot.revision === props.currentRevision &&
    snapshot.language === props.language &&
    snapshot.code === props.currentCode
  )
})

async function runSubmissionReview() {
  if (!canReview.value) {
    return
  }

  const snapshot: ReviewedSnapshot = {
    sessionId: props.sessionId,
    revision: props.currentRevision,
    language: props.language,
    code: props.currentCode,
  }

  const controller = new AbortController()
  reviewController = controller

  isLoading.value = true
  errorMessage.value = ''

  try {
    const result = await reviewSubmission(
      {
        session_id: snapshot.sessionId,
        code_revision: snapshot.revision,
        problem_text: props.problemText,
        current_code: snapshot.code,
        language: snapshot.language,
      },
      controller.signal,
    )

    if (
      controller.signal.aborted ||
      reviewController !== controller
    ) {
      return
    }

    if (result.reviewed_revision !== snapshot.revision) {
      throw new Error(
        '점검 결과의 코드 Revision이 요청한 Revision과 일치하지 않습니다.',
      )
    }

    // Preserve the exact code snapshot that the AI reviewed.
    // If editing occurred during the request, the result is
    // displayed as an outdated review, not as a current verdict.
    lastReview.value = result
    lastReviewedSnapshot.value = snapshot
  } catch (error) {
    if (
      controller.signal.aborted ||
      reviewController !== controller
    ) {
      return
    }

    errorMessage.value =
      error instanceof Error
        ? error.message
        : '제출 전 AI 점검 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    if (reviewController === controller) {
      reviewController = null
      isLoading.value = false
    }
  }
}

onBeforeUnmount(() => {
  reviewController?.abort()
  reviewController = null
})
</script>

<template>
  <section class="submission-panel">
    <header class="submission-header">
      <h3>제출 전 AI 점검</h3>
      <span class="review-type">정적 검토</span>
    </header>

    <p class="submission-description">
      작성한 코드의 논리, 경계 조건, 입출력과 복잡도를
      제출 전에 검토합니다.
    </p>

    <button
      type="button"
      class="review-button"
      :disabled="!canReview"
      @click="runSubmissionReview"
    >
      {{
        isLoading
          ? 'AI가 제출 전 점검 중...'
          : '제출 전 AI 점검 실행'
      }}
    </button>

    <p
      v-if="!currentCode.trim()"
      class="helper-message"
    >
      점검할 코드를 먼저 작성해 주세요.
    </p>

    <p
      v-if="isLoading"
      class="loading-message"
      role="status"
    >
      현재 코드 스냅샷을 기준으로 정적 검토하고 있습니다.
      실제 실행이나 채점은 수행하지 않습니다.
    </p>

    <p
      v-if="errorMessage"
      class="error-message"
      role="alert"
    >
      {{ errorMessage }}
    </p>

    <div v-if="lastReview" class="review-result">
      <div class="result-heading">
        <span
          class="status-label"
          :class="{
            'status-risk': lastReview.status === 'RISK_FOUND',
            'status-clear': lastReview.status === 'NO_OBVIOUS_RISK',
            'status-uncertain': lastReview.status === 'UNCERTAIN',
          }"
        >
          {{ statusLabels[lastReview.status] }}
        </span>

        <span class="revision-label">
          Revision {{ lastReview.reviewed_revision }}
        </span>
      </div>

      <div
        v-if="!isCurrentReview"
        class="outdated-warning"
        role="status"
      >
        이 결과는 현재 코드와 다른 이전 스냅샷을 기준으로
        생성되었습니다. 현재 코드를 다시 점검하려면
        점검 버튼을 눌러 주세요.
      </div>

      <p class="result-summary">
        {{ lastReview.summary }}
      </p>

      <p
        v-if="lastReview.status === 'NO_OBVIOUS_RISK'"
        class="result-caution"
      >
        정적 검토에서 뚜렷한 위험을 발견하지 못했다는 뜻입니다.
        정답 판정이나 테스트 통과를 의미하지 않습니다.
      </p>

      <p
        v-if="lastReview.status === 'UNCERTAIN'"
        class="result-caution"
      >
        현재 정보만으로 신뢰할 만한 결론을 내리기 어렵습니다.
        이 결과를 제출 가능 판정으로 해석하지 마세요.
      </p>

      <!-- Findings -->
      <section
        v-if="lastReview.findings.length > 0"
        class="review-section"
      >
        <h4>
          발견된 위험
          <span>{{ lastReview.findings.length }}건</span>
        </h4>

        <article
          v-for="(finding, index) in lastReview.findings"
          :key="index"
          class="finding-card"
          :class="{
            'severity-high': finding.severity === 'HIGH',
            'severity-medium': finding.severity === 'MEDIUM',
            'severity-low': finding.severity === 'LOW',
          }"
        >
          <div class="finding-meta">
            <strong>
              {{ categoryLabels[finding.category] }}
            </strong>

            <span>
              위험도 {{ severityLabels[finding.severity] }}
            </span>
          </div>

          <p class="finding-description">
            {{ finding.description }}
          </p>

          <div class="finding-evidence">
            <strong>판단 근거</strong>
            <p>{{ finding.evidence }}</p>
          </div>

          <p
            v-if="finding.line_start !== null"
            class="finding-location"
          >
            관련 코드:
            {{
              finding.line_start === finding.line_end
                ? `${finding.line_start}행`
                : `${finding.line_start}~${finding.line_end}행`
            }}
          </p>
        </article>
      </section>

      <!-- Complexity -->
      <section
        v-if="lastReview.complexity_assessment"
        class="review-section"
      >
        <h4>복잡도 검토</h4>

        <p class="section-body">
          {{ lastReview.complexity_assessment }}
        </p>
      </section>

      <!-- Suggested manual checks -->
      <section
        v-if="lastReview.suggested_checks.length > 0"
        class="review-section"
      >
        <h4>추가 확인 사항</h4>

        <ul class="check-list">
          <li
            v-for="(check, index) in lastReview.suggested_checks"
            :key="index"
          >
            {{ check }}
          </li>
        </ul>
      </section>

      <div class="review-disclaimer">
        이 점검은 AI의 정적 추론 결과입니다.
        코드를 컴파일하거나 실행하지 않았으며,
        실제 채점 결과를 보장하지 않습니다.
      </div>
    </div>

    <p v-else-if="!isLoading" class="empty-message">
      아직 제출 전 점검을 수행하지 않았습니다.
    </p>

    <p class="api-notice">
      점검은 버튼을 누를 때만 수행됩니다.
      OpenAI 모드에서는 API 사용 요금이 발생할 수 있습니다.
    </p>
  </section>
</template>

<style scoped>
.submission-panel {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: white;
}

.submission-header,
.result-heading,
.finding-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.submission-header h3 {
  margin: 0;
  color: #0f172a;
  font-size: 14px;
}

.review-type {
  padding: 4px 7px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
}

.submission-description {
  margin: 12px 0 16px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

.review-button {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 8px;
  background: #0f172a;
  color: white;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.review-button:hover:not(:disabled) {
  background: #334155;
}

.review-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.helper-message,
.loading-message,
.error-message,
.empty-message,
.api-notice {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.7;
}

.helper-message,
.empty-message,
.api-notice {
  color: #94a3b8;
}

.loading-message {
  color: #2563eb;
}

.error-message {
  color: #dc2626;
}

.review-result {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #e2e8f0;
}

.status-label {
  padding: 6px 9px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
}

.status-risk {
  background: #fee2e2;
  color: #991b1b;
}

.status-clear {
  background: #dbeafe;
  color: #1d4ed8;
}

.status-uncertain {
  background: #fef3c7;
  color: #92400e;
}

.revision-label {
  color: #64748b;
  font-size: 11px;
}

.outdated-warning {
  padding: 12px;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  background: #fffbeb;
  color: #92400e;
  font-size: 12px;
  line-height: 1.7;
}

.result-summary {
  margin: 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.result-caution {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  line-height: 1.7;
}

.review-section {
  padding-top: 15px;
  border-top: 1px solid #e2e8f0;
}

.review-section h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  color: #0f172a;
  font-size: 13px;
}

.review-section h4 span {
  color: #64748b;
  font-size: 11px;
  font-weight: 400;
}

.finding-card {
  margin-top: 10px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #94a3b8;
  border-radius: 8px;
  background: #f8fafc;
}

.finding-card.severity-high {
  border-left-color: #dc2626;
}

.finding-card.severity-medium {
  border-left-color: #d97706;
}

.finding-card.severity-low {
  border-left-color: #64748b;
}

.finding-meta strong {
  color: #0f172a;
  font-size: 12px;
}

.finding-meta span {
  color: #64748b;
  font-size: 11px;
}

.finding-description,
.finding-evidence p,
.section-body {
  margin: 10px 0 0;
  color: #334155;
  font-size: 12px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.finding-evidence {
  margin-top: 12px;
  padding: 10px;
  border-radius: 6px;
  background: #e2e8f0;
}

.finding-evidence strong {
  color: #475569;
  font-size: 11px;
}

.finding-evidence p {
  margin-top: 5px;
}

.finding-location {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 11px;
}

.section-body {
  margin-top: 0;
}

.check-list {
  margin: 0;
  padding-left: 18px;
  color: #334155;
  font-size: 12px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}

.check-list li + li {
  margin-top: 6px;
}

.review-disclaimer {
  padding: 12px;
  border-radius: 8px;
  background: #f1f5f9;
  color: #475569;
  font-size: 11px;
  line-height: 1.8;
}
</style>