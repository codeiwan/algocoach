<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  ref,
  shallowRef,
  watch,
} from 'vue'

import {
  INTERVENTION_COOLDOWN_MS,
  evaluateIntervention,
  type DeliveredIntervention,
  type InterventionCandidate,
  type InterventionReason,
} from '@/services/intervention-policy'

import type { AnalysisResult } from '@/types/analysis'
import type { IssueRecoveryNotice } from '@/services/analysis-trigger'

const props = defineProps<{
  analysisResult: AnalysisResult | null
  currentRevision: number
  issueRecovery?: IssueRecoveryNotice | null
}>()

type FeedbackSource = 'auto' | 'simulation'
type DemoScenario =
  | 'warning'
  | 'critical'
  | 'praise'
  | 'no_signal'
  | 'stale'

interface CoachMessage {
  id: number
  source: FeedbackSource
  revision: number
  candidate: InterventionCandidate
}

// --------------------------------------------------
// Coaching history
// --------------------------------------------------

const messages = ref<CoachMessage[]>([])

const lastAutoDelivered = ref<DeliveredIntervention | null>(null)
const lastDemoDelivered = ref<DeliveredIntervention | null>(null)

const lastAutoReason = ref<InterventionReason | null>(null)
const lastDemoReason = ref<InterventionReason | null>(null)

let nextMessageId = 0

// --------------------------------------------------
// Pending intervention handling
// --------------------------------------------------

const pendingAutoResult = shallowRef<AnalysisResult | null>(null)
const pendingDemoResult = shallowRef<AnalysisResult | null>(null)

const pendingTimers: Record<
  FeedbackSource,
  ReturnType<typeof setTimeout> | null
> = {
  auto: null,
  simulation: null,
}

function getPendingSlot(source: FeedbackSource) {
  return source === 'auto'
    ? pendingAutoResult
    : pendingDemoResult
}

function clearPending(source: FeedbackSource) {
  const timer = pendingTimers[source]

  if (timer !== null) {
    clearTimeout(timer)
  }

  pendingTimers[source] = null
  getPendingSlot(source).value = null
}

function schedulePending(
  result: AnalysisResult,
  source: FeedbackSource,
  remainingMs: number,
) {
  const pendingSlot = getPendingSlot(source)

  pendingSlot.value = result

  pendingTimers[source] = setTimeout(() => {
    pendingTimers[source] = null

    if (pendingSlot.value !== result) {
      return
    }

    pendingSlot.value = null

    if (result.analyzed_revision !== props.currentRevision) {
      return
    }

    if (
      source === 'auto' &&
      props.analysisResult !== result
    ) {
      return
    }

    processAnalysis(result, source)
  }, remainingMs)
}

// --------------------------------------------------
// Existing intervention policy
// --------------------------------------------------

function processAnalysis(
  result: AnalysisResult,
  source: FeedbackSource,
) {
  clearPending(source)

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

  if (!decision.eligible || !decision.candidate) {
    if (
      decision.reason === 'COOLDOWN' &&
      lastDelivered !== null
    ) {
      const elapsedMs =
        nowMs - lastDelivered.deliveredAtMs

      const remainingMs = Math.max(
        1,
        INTERVENTION_COOLDOWN_MS - elapsedMs,
      )

      schedulePending(result, source, remainingMs)
    }

    return
  }

  const candidate = decision.candidate

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

// --------------------------------------------------
// Watch actual AI analysis
// --------------------------------------------------

watch(
  () => props.analysisResult,
  (result) => {
    clearPending('auto')

    if (result !== null) {
      processAnalysis(result, 'auto')
    }
  },
)

watch(
  () => props.currentRevision,
  () => {
    clearPending('auto')
    clearPending('simulation')
  },
)

// --------------------------------------------------
// Agent presentation
// --------------------------------------------------

const recoveryDisplay = computed(() => {
  switch (props.issueRecovery?.phase) {
    case 'pending':
      return {
        tone: 'pending',
        title: '수정한 코드를 확인할 준비가 됐어요',
        description:
          '이전에 지적한 코드 줄이 변경됐습니다. ' +
          '재분석하기 전까지는 오류가 해결됐다고 판단하지 않겠습니다.',
      }

    case 'checking':
      return {
        tone: 'checking',
        title: '수정한 코드를 다시 검토하고 있어요',
        description:
          '현재 코드 Revision에 대한 AI 분석 결과를 기다리고 있습니다.',
      }

    case 'cleared':
      return {
        tone: 'cleared',
        title: '이전 경고가 최신 분석에서 재발견되지 않았어요',
        description:
          '수정한 코드의 최신 AI 분석에서는 이전 문제가 보고되지 않았습니다. ' +
          '다만 실제 정답 판정이나 코드 실행을 의미하지는 않습니다.',
      }

    case 'issues_found':
      return {
        tone: 'issues_found',
        title: '수정한 코드에서 확인할 부분이 남아 있어요',
        description:
          '최신 분석에 문제가 보고되었습니다. ' +
          '이전 오류와 동일한 원인인지는 단정하지 않겠습니다.',
      }

    case 'failed':
      return {
        tone: 'failed',
        title: '코드 재검증을 완료하지 못했어요',
        description:
          '이번 수정이 오류를 해결했는지는 아직 확인하지 못했습니다. ' +
          '필요하면 현재 코드에 대한 피드백을 다시 요청해 주세요.',
      }

    default:
      return null
  }
})

const latestMessage = computed<CoachMessage | null>(() => {
  // A recovery event is more recent than the old intervention.
  // Show it first, and move previous messages to history.
  if (recoveryDisplay.value !== null) {
    return null
  }

  return messages.value[0] ?? null
})

const previousMessages = computed(() => {
  return recoveryDisplay.value !== null
    ? messages.value
    : messages.value.slice(1)
})

const agentStatus = computed(() => {
  if (props.issueRecovery?.phase === 'checking') {
    return '수정한 코드의 AI 분석 응답을 기다리는 중'
  }

  if (props.issueRecovery?.phase === 'pending') {
    return '코드 수정 감지 · 재검증 대기'
  }

  if (props.issueRecovery?.phase === 'failed') {
    return '재검증 실패 · 다시 시도 가능'
  }

  if (props.issueRecovery?.phase === 'cleared') {
    return '최신 코드 재검증 완료'
  }

  if (pendingAutoResult.value !== null) {
    return '다음 코칭 개입 시점 대기 중'
  }

  const newest = messages.value[0]

  if (
    newest !== undefined &&
    newest.revision !== props.currentRevision
  ) {
    return '코드 변경 확인 · 새 분석 결과 대기'
  }

  if (props.analysisResult !== null) {
    return '최근 AI 분석 결과 확인 완료'
  }

  return '코칭 준비 · 새 분석 결과 대기'
})

const hasVisibleFeedback = computed(() => {
  return (
    recoveryDisplay.value !== null ||
    latestMessage.value !== null
  )
})

// --------------------------------------------------
// Developer-only simulation
// --------------------------------------------------

const showDeveloperTools =
  import.meta.env.DEV &&
  new URLSearchParams(window.location.search).get(
    'debugCoach',
  ) === '1'

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
          evidence: '테스트용 일반 경고입니다.',
          line_start: 5,
          line_end: 5,
        },
      ]
      break

    case 'critical':
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
          evidence: '테스트용 심각한 경고입니다.',
          line_start: 8,
          line_end: 8,
        },
      ]
      break

    case 'praise':
      result.positive_observation =
        '중복 계산을 줄이는 효율적인 접근을 사용했습니다.'
      break

    case 'no_signal':
      break

    case 'stale':
      result.analyzed_revision = props.currentRevision + 1
      result.positive_observation =
        '오래된 분석 결과는 전달되면 안 됩니다.'
      break
  }

  processAnalysis(result, 'simulation')
}

function resetSimulation() {
  clearPending('simulation')

  lastDemoDelivered.value = null
  lastDemoReason.value = null

  messages.value = messages.value.filter(
    (message) => message.source !== 'simulation',
  )
}

onBeforeUnmount(() => {
  clearPending('auto')
  clearPending('simulation')
})
</script>

<template>
  <section
    class="coach-feedback"
    aria-label="AlgoCoach 에이전트 피드"
  >
    <!-- Agent identity -->
    <header class="agent-header">
      <div class="agent-avatar" aria-hidden="true">
        <div class="avatar-face">
          <span class="avatar-eye" />
          <span class="avatar-eye" />
        </div>
      </div>

      <div class="agent-identity">
        <strong>AlgoCoach</strong>
        <span>AI CODING AGENT</span>
      </div>

      <span class="agent-dot" aria-hidden="true" />
    </header>

    <!-- Actual state, not fabricated chain-of-thought -->
    <div
      class="agent-status"
      role="status"
      aria-live="polite"
    >
      <span class="status-pulse" aria-hidden="true" />
      <span>{{ agentStatus }}</span>
    </div>

    <!-- Latest message directly below the agent -->
    <div class="latest-section" aria-live="polite">
      <div class="section-heading">
        <strong>최신 코칭</strong>
        <span>
          Revision {{ currentRevision }}
        </span>
      </div>

      <article
        v-if="recoveryDisplay"
        class="latest-card recovery-card"
        :class="`recovery-${recoveryDisplay.tone}`"
      >
        <span class="message-label">
          코드 수정 재검증
        </span>

        <h3>{{ recoveryDisplay.title }}</h3>
        <p>{{ recoveryDisplay.description }}</p>
      </article>

      <article
        v-else-if="latestMessage"
        class="latest-card"
        :class="latestMessage.candidate.kind"
      >
        <div class="latest-meta">
          <span class="message-label">
            {{
              latestMessage.candidate.kind === 'issue'
                ? '코드에서 확인할 부분'
                : '긍정적 코칭'
            }}
          </span>

          <span class="message-revision">
            Revision {{ latestMessage.revision }}
          </span>
        </div>

        <p class="message-body">
          {{ latestMessage.candidate.message }}
        </p>

        <p
          v-if="latestMessage.revision !== currentRevision"
          class="historical-note"
        >
          현재 코드가 아닌 이전 Revision에 대한 의견입니다.
        </p>
      </article>

      <div
        v-else
        class="empty-coaching"
      >
        <strong>지금은 전달할 코칭이 없습니다.</strong>
        <p>
          분석에서 구체적인 지도 근거가 확인되면
          가장 최근 코칭을 이곳에 보여드립니다.
        </p>
      </div>
    </div>

    <!-- Previous coaching appears below latest -->
    <section
      v-if="previousMessages.length > 0"
      class="history-section"
    >
      <div class="section-heading">
        <strong>이전 코칭</strong>
        <span>{{ previousMessages.length }}개</span>
      </div>

      <div class="history-list">
        <article
          v-for="message in previousMessages"
          :key="message.id"
          class="history-card"
          :class="message.candidate.kind"
        >
          <div class="history-meta">
            <strong>
              {{
                message.candidate.kind === 'issue'
                  ? '코드 점검'
                  : '긍정적 피드백'
              }}
            </strong>

            <span>
              Revision {{ message.revision }}
            </span>
          </div>

          <p class="message-body">
            {{ message.candidate.message }}
          </p>

          <p
            v-if="
              message.source === 'auto' &&
              message.candidate.kind === 'issue' &&
              issueRecovery?.originRevision === message.revision
            "
            class="historical-note"
          >
            {{
              issueRecovery?.phase === 'cleared'
                ? '최신 분석에서는 이 경고가 재발견되지 않았습니다.'
                : '이전에 지적된 내용입니다. 현재 코드에서 다시 확인해 주세요.'
            }}
          </p>

          <p
            v-else-if="message.revision !== currentRevision"
            class="historical-note"
          >
            이전 코드 Revision에서 받은 피드백입니다.
          </p>
        </article>
      </div>
    </section>

    <p
      v-if="!hasVisibleFeedback && lastAutoReason === 'NO_SIGNAL'"
      class="quiet-note"
    >
      현재 분석에서 별도로 개입할 근거가 확인되지 않았습니다.
    </p>

    <!-- Hidden on the normal user screen -->
    <details
      v-if="showDeveloperTools"
      class="developer-tools"
    >
      <summary>개발용 코칭 시뮬레이션</summary>

      <p>
        실제 LLM을 호출하지 않고 개입 정책만 검증합니다.
      </p>

      <div class="simulation-buttons">
        <button
          type="button"
          @click="simulateScenario('warning')"
        >
          일반 경고
        </button>

        <button
          type="button"
          @click="simulateScenario('critical')"
        >
          심각한 경고
        </button>

        <button
          type="button"
          @click="simulateScenario('praise')"
        >
          칭찬
        </button>

        <button
          type="button"
          @click="simulateScenario('no_signal')"
        >
          신호 없음
        </button>

        <button
          type="button"
          @click="simulateScenario('stale')"
        >
          오래된 결과
        </button>

        <button
          type="button"
          @click="resetSimulation"
        >
          테스트 초기화
        </button>
      </div>

      <p v-if="pendingDemoResult">
        시뮬레이션 개입 후보 대기 중
      </p>

      <p v-if="lastDemoReason">
        마지막 시뮬레이션 판단: {{ lastDemoReason }}
      </p>
    </details>
  </section>
</template>

<style scoped>
.coach-feedback {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.agent-header {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 17px 15px;
  border: 1px solid #c7d2fe;
  border-radius: 14px;
  background: linear-gradient(
    135deg,
    #eff6ff 0%,
    #eef2ff 100%
  );
}

.agent-avatar {
  display: flex;
  width: 60px;
  height: 60px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: linear-gradient(
    135deg,
    #2563eb,
    #4f46e5
  );
  box-shadow: 0 6px 18px rgb(37 99 235 / 20%);
}

.avatar-face {
  display: flex;
  width: 39px;
  height: 28px;
  align-items: center;
  justify-content: space-evenly;
  border-radius: 10px;
  background: white;
}

.avatar-eye {
  width: 7px;
  height: 9px;
  border-radius: 5px;
  background: #2563eb;
}

.agent-identity {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 5px;
}

.agent-identity strong {
  color: #0f172a;
  font-size: 18px;
  letter-spacing: -0.025em;
}

.agent-identity span {
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.agent-dot {
  width: 9px;
  height: 9px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #16a34a;
}

.agent-status {
  display: flex;
  min-height: 36px;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 9px;
  background: #f1f5f9;
  color: #475569;
  font-size: 11px;
  line-height: 1.6;
}

.status-pulse {
  width: 7px;
  height: 7px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #64748b;
}

.latest-section,
.history-section {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.section-heading,
.latest-meta,
.history-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.section-heading {
  padding: 0 2px;
}

.section-heading strong {
  color: #334155;
  font-size: 12px;
}

.section-heading span,
.message-revision,
.history-meta span {
  color: #94a3b8;
  font-size: 10px;
}

.latest-card,
.empty-coaching {
  min-width: 0;
  padding: 16px;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: #eff6ff;
}

.latest-card.issue {
  border-color: #fed7aa;
  background: #fff7ed;
}

.latest-card.praise,
.latest-card.recovery-cleared {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.latest-card.recovery-issues_found,
.latest-card.recovery-failed {
  border-color: #fed7aa;
  background: #fff7ed;
}

.latest-card.recovery-checking,
.latest-card.recovery-pending {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.message-label {
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 700;
}

.latest-card.issue .message-label,
.latest-card.recovery-issues_found .message-label,
.latest-card.recovery-failed .message-label {
  color: #9a3412;
}

.latest-card.praise .message-label,
.latest-card.recovery-cleared .message-label {
  color: #166534;
}

.latest-card h3 {
  margin: 10px 0 7px;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.5;
}

.latest-card p,
.history-card p {
  margin: 8px 0 0;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.message-body {
  color: #334155;
  font-size: 13px;
  white-space: pre-wrap;
}

.recovery-card > p {
  color: #475569;
  font-size: 12px;
}

.empty-coaching strong {
  color: #1e40af;
  font-size: 13px;
}

.empty-coaching p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.history-card {
  min-width: 0;
  padding: 13px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.history-card .message-body {
  color: #475569;
  font-size: 12px;
}

.historical-note {
  padding-top: 8px;
  border-top: 1px solid rgb(148 163 184 / 25%);
  color: #64748b !important;
  font-size: 11px !important;
}

.quiet-note {
  margin: 0;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.6;
}

.developer-tools {
  padding: 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 9px;
  color: #64748b;
  font-size: 11px;
}

.developer-tools summary {
  cursor: pointer;
}

.developer-tools p {
  line-height: 1.7;
}

.simulation-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.simulation-buttons button {
  padding: 7px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: white;
  color: #334155;
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

@media (prefers-reduced-motion: reduce) {
  .agent-avatar {
    transition: none;
  }
}
</style>