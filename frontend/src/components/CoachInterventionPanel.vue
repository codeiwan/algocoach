
<script setup lang="ts">
import { ref, watch } from 'vue'

import {
  evaluateIntervention,
  type DeliveredIntervention,
  type InterventionCandidate,
  type InterventionReason,
} from '@/services/intervention-policy'
import type { AnalysisResult } from '@/types/analysis'

const props = defineProps<{
  analysisResult: AnalysisResult | null
  currentRevision: number
}>()

type FeedbackSource = 'auto' | 'simulation'
type DemoScenario = 'warning' | 'critical' | 'praise' | 'no_signal' | 'stale'

interface CoachMessage {
  id: number
  source: FeedbackSource
  revision: number
  candidate: InterventionCandidate
}

const messages = ref<CoachMessage[]>([])

// Real analysis and test simulation have separate histories.
const lastAutoDelivered = ref<DeliveredIntervention | null>(null)
const lastDemoDelivered = ref<DeliveredIntervention | null>(null)

const lastAutoReason = ref<InterventionReason | null>(null)
const lastDemoReason = ref<InterventionReason | null>(null)

let nextMessageId = 0

const reasonLabels: Record<InterventionReason, string> = {
  STALE_REVISION: '오래된 코드 분석 결과이므로 개입하지 않습니다.',
  NO_SIGNAL: '코칭할 만한 구체적인 근거가 없어 관찰을 유지합니다.',
  DUPLICATE: '이전에 전달한 메시지와 동일하여 생략합니다.',
  COOLDOWN: '최근 코칭 이후 60초가 지나지 않아 개입을 보류합니다.',
  ELIGIBLE: '개입 정책을 통과하여 코칭 메시지를 전달했습니다.',
}

/**
 * Evaluate one analysis result and deliver a message only
 * when the Intervention Policy allows it.
 */
function processAnalysis(
  result: AnalysisResult,
  source: FeedbackSource,
) {
  const nowMs = Date.now()

  const lastDelivered =
    source === 'auto'
      ? lastAutoDelivered.value
      : lastDemoDelivered.value

  const decision = evaluateIntervention(
    result,
    props.currentRevision,
    lastDelivered,
    nowMs,
  )

  if (source === 'auto') {
    lastAutoReason.value = decision.reason
  } else {
    lastDemoReason.value = decision.reason
  }

  // A rejected decision must not change delivery history.
  if (!decision.eligible || !decision.candidate) {
    return
  }

  const candidate = decision.candidate

  // Record the intervention at the moment it is added to the feed.
  const delivered: DeliveredIntervention = {
    fingerprint: candidate.fingerprint,
    deliveredAtMs: nowMs,
  }

  if (source === 'auto') {
    lastAutoDelivered.value = delivered
  } else {
    lastDemoDelivered.value = delivered
  }

  messages.value = [
    {
      id: ++nextMessageId,
      source,
      revision: result.analyzed_revision,
      candidate,
    },
    ...messages.value,
  ].slice(0, 20)
}

// Observe results received from the actual LangGraph analysis API.
watch(
  () => props.analysisResult,
  (result) => {
    if (result !== null) {
      processAnalysis(result, 'auto')
    }
  },
)

/**
 * Developer-only scenarios.
 * These do not call an LLM or modify actual analysis history.
 */
function simulateScenario(scenario: DemoScenario) {
  const result: AnalysisResult = {
    analyzed_revision: props.currentRevision,
    algorithm: null,
    progress_status: 'IMPLEMENTING',
    summary: '개발용 코칭 시뮬레이션입니다.',
    positive_observation: null,
    complexity_estimate: null,
    issues: [],
  }

  switch (scenario) {
    case 'warning':
      result.issues = [
        {
          category: 'logic',
          severity: 'WARNING',
          description: '방문 처리 누락 가능성이 있습니다.',
          evidence: '테스트 상황에서 방문 상태 갱신이 누락됐다고 가정합니다.',
          line_start: 5,
          line_end: 5,
        },
      ]
      break

    case 'critical':
      // Include a warning to verify CRITICAL priority.
      result.issues = [
        {
          category: 'logic',
          severity: 'WARNING',
          description: '방문 처리 누락 가능성이 있습니다.',
          evidence: '테스트용 일반 경고입니다.',
          line_start: 5,
          line_end: 5,
        },
        {
          category: 'logic',
          severity: 'CRITICAL',
          description: '무한 루프가 발생할 가능성이 있습니다.',
          evidence: '테스트 상황에서 반복 종료 조건이 없다고 가정합니다.',
          line_start: 8,
          line_end: 8,
        },
      ]
      break

    case 'praise':
      result.positive_observation =
        '테스트용 칭찬: 중복 계산을 줄이는 효율적인 접근을 사용했습니다.'
      break

    case 'no_signal':
      // No issues or positive observations.
      break

    case 'stale':
      result.analyzed_revision = props.currentRevision + 1
      result.positive_observation =
        '오래된 분석 결과는 화면에 전달되면 안 됩니다.'
      break
  }

  processAnalysis(result, 'simulation')
}

function resetSimulation() {
  lastDemoDelivered.value = null
  lastDemoReason.value = null

  // Preserve real automatic coaching messages and their history.
  messages.value = messages.value.filter(
    (message) => message.source !== 'simulation',
  )
}
</script>

<template>
  <section class="coach-feedback">
    <header class="feedback-header">
      <h3>AI Coach 피드</h3>
      <span class="feed-caption">Intervention Policy</span>
    </header>

    <div class="policy-status">
      <strong>최근 자동 분석 판단</strong>
      <p>
        {{
          lastAutoReason
            ? reasonLabels[lastAutoReason]
            : '아직 자동 분석에 대한 개입 판단이 없습니다.'
        }}
      </p>
    </div>

    <div v-if="messages.length === 0" class="feed-empty">
      아직 전달된 코칭 메시지가 없습니다.
      <p>
        분석 근거가 부족하거나 개입 조건을 충족하지 않으면
        AI Coach는 조용히 관찰합니다.
      </p>
    </div>

    <div v-else class="message-list" aria-live="polite">
      <article
        v-for="message in messages"
        :key="message.id"
        class="coach-message"
        :class="message.candidate.kind"
      >
        <div class="message-meta">
          <strong>
            {{ message.candidate.kind === 'issue' ? '코드 점검' : '긍정적 피드백' }}
          </strong>

          <span>
            {{ message.source === 'simulation' ? '시뮬레이션' : '자동 분석' }}
            · Revision {{ message.revision }}
          </span>
        </div>

        <p class="message-text">
          {{ message.candidate.message }}
        </p>

        <p
          v-if="message.revision !== currentRevision"
          class="outdated-note"
        >
          이전 코드 Revision에서 전달된 메시지입니다.
        </p>
      </article>
    </div>

    <!-- Hidden by default: developer testing tools. -->
    <details class="demo-tools">
      <summary>개발용 코칭 시뮬레이션</summary>

      <p class="demo-description">
        아래 버튼은 실제 코드를 분석하지 않습니다.
        가상의 AI 분석 결과로 개입 정책을 검증합니다.
      </p>

      <div class="demo-buttons">
        <button type="button" @click="simulateScenario('warning')">
          일반 경고
        </button>

        <button type="button" @click="simulateScenario('critical')">
          심각한 경고
        </button>

        <button type="button" @click="simulateScenario('praise')">
          칭찬
        </button>

        <button type="button" @click="simulateScenario('no_signal')">
          신호 없음
        </button>

        <button type="button" @click="simulateScenario('stale')">
          오래된 결과
        </button>

        <button
          type="button"
          class="reset-button"
          @click="resetSimulation"
        >
          테스트 초기화
        </button>
      </div>

      <p v-if="lastDemoReason" class="demo-result">
        최근 테스트 판단:
        <strong>{{ lastDemoReason }}</strong>
      </p>
    </details>
  </section>
</template>

<style scoped>
.coach-feedback {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
}

.feedback-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 16px;
}

.feedback-header h3 {
  margin: 0;
  font-size: 14px;
}

.feed-caption {
  color: #64748b;
  font-size: 11px;
}

.policy-status {
  padding: 12px;
  border-radius: 8px;
  background: #f1f5f9;
}

.policy-status strong {
  font-size: 12px;
}

.policy-status p {
  margin: 6px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
}

.feed-empty {
  padding: 24px 4px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
  text-align: center;
}

.feed-empty p {
  margin: 8px 0 0;
  font-size: 12px;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.coach-message {
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #94a3b8;
  border-radius: 8px;
  background: #f8fafc;
}

.coach-message.issue {
  border-left-color: #d97706;
}

.coach-message.praise {
  border-left-color: #16a34a;
}

.message-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-meta strong {
  font-size: 13px;
}

.message-meta span {
  color: #64748b;
  font-size: 11px;
}

.message-text {
  margin: 12px 0 0;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.outdated-note {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 11px;
}

.demo-tools {
  margin-top: 20px;
  padding-top: 14px;
  border-top: 1px solid #e2e8f0;
}

.demo-tools summary {
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
}

.demo-description {
  margin: 12px 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.demo-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.demo-buttons button {
  padding: 7px 9px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #f8fafc;
  color: #334155;
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

.demo-buttons button:hover {
  background: #e2e8f0;
}

.demo-buttons .reset-button {
  border-color: #fca5a5;
  color: #b91c1c;
}

.demo-result {
  margin: 12px 0 0;
  color: #475569;
  font-size: 12px;
}
</style>
