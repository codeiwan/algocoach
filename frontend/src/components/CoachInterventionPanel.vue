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
  type InterventionReason,
} from '@/services/intervention-policy'

import type {
  AnalysisResult,
  CodeIssue,
} from '@/types/analysis'

import type {
  IssueRecoveryNotice,
} from '@/services/analysis-trigger'

interface QuestionExchange {
  id: number
  question: string
  answer: string
  answeredRevision: number
  atMs: number
}

const props = defineProps<{
  analysisResult: AnalysisResult | null
  manualAnalysisResult?: AnalysisResult | null
  currentRevision: number
  issueRecovery?: IssueRecoveryNotice | null
  autoEnabled?: boolean
  isAutoAnalyzing?: boolean
  isManualAnalyzing?: boolean
  questionExchanges?: readonly QuestionExchange[]
}>()

type MessageSource = 'auto' | 'manual' | 'simulation'
type PolicySource = 'auto' | 'simulation'
type MessageTone = 'issue' | 'praise' | 'neutral'

type DemoScenario =
  | 'warning'
  | 'critical'
  | 'praise'
  | 'no_signal'
  | 'stale'

interface CoachMessage {
  id: number
  source: MessageSource
  revision: number
  tone: MessageTone
  text: string
  atMs: number
}

interface CoachingTimelineEntry extends CoachMessage {
  kind: 'coaching'
  key: string
}

interface QuestionTimelineEntry extends QuestionExchange {
  kind: 'question'
  key: string
  revision: number
}

type TimelineEntry =
  | CoachingTimelineEntry
  | QuestionTimelineEntry

// --------------------------------------------------
// Coaching history
// --------------------------------------------------

const messages = ref<CoachMessage[]>([])

const lastAutoDelivered = ref<DeliveredIntervention | null>(null)
const lastDemoDelivered = ref<DeliveredIntervention | null>(null)

const lastAutoReason = ref<InterventionReason | null>(null)
const lastDemoReason = ref<InterventionReason | null>(null)

let nextMessageId = 0

function appendMessage(
  source: MessageSource,
  revision: number,
  tone: MessageTone,
  content: string,
) {
  if (!content.trim()) {
    return
  }

  messages.value = [
    {
      id: ++nextMessageId,
      source,
      revision,
      tone,
      text: content,
      atMs: Date.now(),
    },
    ...messages.value,
  ].slice(0, 20)
}

// --------------------------------------------------
// Existing automatic intervention policy
// --------------------------------------------------

const pendingAutoResult = shallowRef<AnalysisResult | null>(null)
const pendingDemoResult = shallowRef<AnalysisResult | null>(null)

const pendingTimers: Record<
  PolicySource,
  ReturnType<typeof setTimeout> | null
> = {
  auto: null,
  simulation: null,
}

function getPendingSlot(source: PolicySource) {
  return source === 'auto'
    ? pendingAutoResult
    : pendingDemoResult
}

function clearPending(source: PolicySource) {
  const timer = pendingTimers[source]

  if (timer !== null) {
    clearTimeout(timer)
  }

  pendingTimers[source] = null
  getPendingSlot(source).value = null
}

function schedulePending(
  result: AnalysisResult,
  source: PolicySource,
  remainingMs: number,
) {
  const slot = getPendingSlot(source)
  slot.value = result

  pendingTimers[source] = setTimeout(() => {
    pendingTimers[source] = null

    if (slot.value !== result) {
      return
    }

    slot.value = null

    if (result.analyzed_revision !== props.currentRevision) {
      return
    }

    if (
      source === 'auto' &&
      (
        props.analysisResult !== result ||
        !props.autoEnabled
      )
    ) {
      return
    }

    processPolicyResult(result, source)
  }, remainingMs)
}

function processPolicyResult(
  result: AnalysisResult,
  source: PolicySource,
) {
  clearPending(source)

  const lastDelivered =
    source === 'auto'
      ? lastAutoDelivered.value
      : lastDemoDelivered.value

  const nowMs = Date.now()

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
      const elapsed = nowMs - lastDelivered.deliveredAtMs

      schedulePending(
        result,
        source,
        Math.max(1, INTERVENTION_COOLDOWN_MS - elapsed),
      )
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

  appendMessage(
    source,
    result.analyzed_revision,
    candidate.kind,
    candidate.message,
  )
}

// --------------------------------------------------
// Manual feedback is immediate
// --------------------------------------------------

function selectImportantIssue(
  result: AnalysisResult,
): CodeIssue | null {
  return (
    result.issues.find(
      (item) => item.severity === 'CRITICAL',
    ) ??
    result.issues.find(
      (item) => item.severity === 'WARNING',
    ) ??
    result.issues[0] ??
    null
  )
}

function publishManualAnalysis(result: AnalysisResult) {
  if (result.analyzed_revision !== props.currentRevision) {
    return
  }

  const issue = selectImportantIssue(result)
  const parts: string[] = []

  if (result.summary.trim()) {
    parts.push(result.summary.trim())
  }

  if (issue !== null) {
    parts.push(`검토할 부분: ${issue.description}`)

    if (issue.evidence.trim()) {
      parts.push(`근거: ${issue.evidence}`)
    }
  } else if (result.positive_observation?.trim()) {
    parts.push(result.positive_observation.trim())
  }

  const tone: MessageTone =
    issue !== null
      ? 'issue'
      : result.positive_observation?.trim()
        ? 'praise'
        : 'neutral'

  appendMessage(
    'manual',
    result.analyzed_revision,
    tone,
    parts.join('\n\n') ||
      '분석을 완료했습니다. 추가로 확인할 내용이 없습니다.',
  )
}

watch(
  () => props.analysisResult,
  (result) => {
    clearPending('auto')

    if (result !== null && props.autoEnabled) {
      processPolicyResult(result, 'auto')
    }
  },
)

watch(
  () => props.manualAnalysisResult,
  (result) => {
    if (result !== undefined && result !== null) {
      publishManualAnalysis(result)
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

watch(
  () => props.autoEnabled,
  (enabled) => {
    if (!enabled) {
      clearPending('auto')
    }
  },
)

// --------------------------------------------------
// Unified timeline: coaching + questions
// --------------------------------------------------

const timeline = computed<TimelineEntry[]>(() => {
  const coaching: CoachingTimelineEntry[] =
    messages.value.map((message) => ({
      ...message,
      kind: 'coaching',
      key: `coaching-${message.id}`,
    }))

  const questions: QuestionTimelineEntry[] =
    (props.questionExchanges ?? []).map((exchange) => ({
      ...exchange,
      kind: 'question',
      key: `question-${exchange.id}`,
      revision: exchange.answeredRevision,
    }))

  return [...coaching, ...questions]
    .sort((a, b) => b.atMs - a.atMs)
    .slice(0, 30)
})

// --------------------------------------------------
// Issue recovery notice
// --------------------------------------------------

const recoveryDisplay = computed(() => {
  switch (props.issueRecovery?.phase) {
    case 'pending':
      return {
        tone: 'pending',
        title: '수정한 코드를 다시 확인해야 해요',
        description:
          '이전에 지적한 코드가 변경됐습니다. ' +
          '아직 오류 해결 여부는 판단하지 않았습니다.',
      }

    case 'checking':
      return {
        tone: 'checking',
        title: '수정한 코드를 다시 분석하고 있어요',
        description:
          '현재 코드에 대한 AI 분석 결과를 기다리고 있습니다.',
      }

    case 'cleared':
      return {
        tone: 'cleared',
        title: '이전 경고가 최신 분석에서 재발견되지 않았어요',
        description:
          '새 분석에서 이전 문제가 보고되지 않았습니다. ' +
          '실제 코드 실행이나 정답 판정은 아닙니다.',
      }

    case 'issues_found':
      return {
        tone: 'issues_found',
        title: '수정한 코드에서 검토할 내용이 남아 있어요',
        description:
          '최신 분석 결과에 문제가 보고됐습니다.',
      }

    case 'failed':
      return {
        tone: 'failed',
        title: '수정한 코드의 재검증에 실패했어요',
        description:
          '현재 코드의 피드백을 다시 요청할 수 있습니다.',
      }

    default:
      return null
  }
})

const recoveryTakesPriority = computed(() => {
  const notice = props.issueRecovery

  if (!notice || !recoveryDisplay.value) {
    return false
  }

  if (
    notice.phase === 'pending' ||
    notice.phase === 'checking' ||
    notice.phase === 'failed'
  ) {
    return true
  }

  const newest = timeline.value[0]

  return (
    newest === undefined ||
    newest.revision !== props.currentRevision
  )
})

const latestEntry = computed<TimelineEntry | null>(() => {
  if (recoveryTakesPriority.value) {
    return null
  }

  return timeline.value[0] ?? null
})

const previousEntries = computed<TimelineEntry[]>(() => {
  return recoveryTakesPriority.value
    ? timeline.value
    : timeline.value.slice(1)
})

// --------------------------------------------------
// Agent status
// --------------------------------------------------

const agentStatus = computed(() => {
  if (props.isManualAnalyzing) {
    return '요청한 코드 피드백을 생성하고 있습니다.'
  }

  if (props.isAutoAnalyzing) {
    return '현재 코드의 자동 AI 분석 응답을 기다리고 있습니다.'
  }

  if (props.issueRecovery?.phase === 'checking') {
    return '수정한 코드의 재검증 결과를 기다리고 있습니다.'
  }

  if (props.issueRecovery?.phase === 'pending') {
    return '코드 수정 확인 · 재검증 대기'
  }

  if (props.issueRecovery?.phase === 'failed') {
    return '재검증 실패 · 다시 시도 가능'
  }

  if (props.issueRecovery?.phase === 'cleared') {
    return '최신 코드 재검증 완료'
  }

  if (!props.autoEnabled) {
    return '자동 코칭 OFF · 수동 피드백 이용 가능'
  }

  if (pendingAutoResult.value !== null) {
    return '다음 자동 코칭 개입 조건을 확인하고 있습니다.'
  }

  const newest = timeline.value[0]

  if (
    newest &&
    newest.revision !== props.currentRevision
  ) {
    return '코드가 변경되어 새 분석 결과를 기다립니다.'
  }

  return '코드를 관찰하고 있습니다.'
})

// --------------------------------------------------
// Developer-only simulation
// --------------------------------------------------

const showDeveloperTools =
  import.meta.env.DEV &&
  new URLSearchParams(window.location.search)
    .get('debugCoach') === '1'

function simulateScenario(scenario: DemoScenario) {
  const result: AnalysisResult = {
    analyzed_revision: props.currentRevision,
    algorithm: null,
    progress_status: 'IMPLEMENTING',
    summary: '개발용 코칭 시뮬레이션',
    positive_observation: null,
    complexity_estimate: null,
    issues: [],
  }

  switch (scenario) {
    case 'warning':
      result.issues = [{
        category: 'logic',
        severity: 'WARNING',
        description: '방문 처리 누락 가능성이 있습니다.',
        evidence: '개발용 테스트 경고입니다.',
        line_start: 5,
        line_end: 5,
      }]
      break

    case 'critical':
      result.issues = [{
        category: 'logic',
        severity: 'CRITICAL',
        description: '무한 루프가 발생할 수 있습니다.',
        evidence: '개발용 테스트 경고입니다.',
        line_start: 8,
        line_end: 8,
      }]
      break

    case 'praise':
      result.positive_observation =
        '중복 계산을 줄이는 접근이 확인됐습니다.'
      break

    case 'no_signal':
      break

    case 'stale':
      result.analyzed_revision =
        props.currentRevision + 1
      result.positive_observation =
        '현재 Revision에 표시되면 안 되는 메시지입니다.'
      break
  }

  processPolicyResult(result, 'simulation')
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

      <span
        class="agent-dot"
        :class="{ paused: !autoEnabled }"
        aria-hidden="true"
      />
    </header>

    <div
      class="agent-status"
      role="status"
      aria-live="polite"
    >
      <span
        class="status-pulse"
        :class="{
          busy: isManualAnalyzing || isAutoAnalyzing,
        }"
        aria-hidden="true"
      />

      <span>{{ agentStatus }}</span>
    </div>

    <div class="feed-scroll">
      <div class="latest-section">
        <div class="section-heading">
          <strong>최신 대화</strong>
          <span>Revision {{ currentRevision }}</span>
        </div>

        <!-- Recovery takes priority while verification is pending -->
        <article
          v-if="recoveryTakesPriority && recoveryDisplay"
          class="latest-card recovery-card"
          :class="`recovery-${recoveryDisplay.tone}`"
        >
          <span class="message-label">
            코드 수정 재검증
          </span>

          <h3>{{ recoveryDisplay.title }}</h3>
          <p>{{ recoveryDisplay.description }}</p>
        </article>

        <!-- Latest question and answer -->
        <article
          v-else-if="latestEntry?.kind === 'question'"
          class="latest-card conversation-card"
        >
          <div class="latest-meta">
            <span class="message-label">
              AI 질문 응답
            </span>

            <span class="message-revision">
              Revision {{ latestEntry.answeredRevision }}
            </span>
          </div>

          <div class="user-message">
            <strong>나</strong>
            <p>{{ latestEntry.question }}</p>
          </div>

          <div class="assistant-message">
            <strong>AlgoCoach</strong>
            <p>{{ latestEntry.answer }}</p>
          </div>

          <p
            v-if="latestEntry.revision !== currentRevision"
            class="historical-note"
          >
            이 답변은 이전 코드 Revision을 기준으로 작성됐습니다.
          </p>
        </article>

        <!-- Latest automatic or manual feedback -->
        <article
          v-else-if="latestEntry?.kind === 'coaching'"
          class="latest-card"
          :class="latestEntry.tone"
        >
          <div class="latest-meta">
            <span class="message-label">
              {{
                latestEntry.source === 'manual'
                  ? '요청한 코드 피드백'
                  : latestEntry.source === 'simulation'
                    ? '개발용 시뮬레이션'
                    : '자동 코칭'
              }}
            </span>

            <span class="message-revision">
              Revision {{ latestEntry.revision }}
            </span>
          </div>

          <p class="message-body">
            {{ latestEntry.text }}
          </p>

          <p
            v-if="
              issueRecovery?.phase === 'cleared' &&
              issueRecovery.checkedRevision === latestEntry.revision
            "
            class="historical-note"
          >
            이전 경고는 최신 분석에서 재발견되지 않았습니다.
          </p>

          <p
            v-if="latestEntry.revision !== currentRevision"
            class="historical-note"
          >
            이전 코드에 대한 피드백입니다.
          </p>
        </article>

        <article
          v-else-if="recoveryDisplay"
          class="latest-card recovery-card"
          :class="`recovery-${recoveryDisplay.tone}`"
        >
          <span class="message-label">재검증 결과</span>
          <h3>{{ recoveryDisplay.title }}</h3>
          <p>{{ recoveryDisplay.description }}</p>
        </article>

        <div
          v-else
          class="empty-coaching"
        >
          <strong>아직 전달할 코칭이 없습니다.</strong>

          <p>
            자동 분석, 수동 피드백 또는 질문에 대한
            AI 응답이 이곳에 표시됩니다.
          </p>
        </div>
      </div>

      <!-- Older coaching and conversations -->
      <section
        v-if="previousEntries.length > 0"
        class="history-section"
      >
        <div class="section-heading">
          <strong>이전 기록</strong>
          <span>{{ previousEntries.length }}개</span>
        </div>

        <div class="history-list">
          <article
            v-for="entry in previousEntries"
            :key="entry.key"
            class="history-card"
            :class="entry.kind === 'coaching' ? entry.tone : 'question'"
          >
            <template v-if="entry.kind === 'question'">
              <div class="history-meta">
                <strong>AI 질문 응답</strong>

                <span>
                  Revision {{ entry.answeredRevision }}
                </span>
              </div>

              <p class="history-question">
                <strong>나:</strong> {{ entry.question }}
              </p>

              <p class="message-body">
                <strong>AlgoCoach:</strong> {{ entry.answer }}
              </p>
            </template>

            <template v-else>
              <div class="history-meta">
                <strong>
                  {{
                    entry.source === 'manual'
                      ? '요청한 피드백'
                      : entry.source === 'simulation'
                        ? '개발용 시뮬레이션'
                        : '자동 코칭'
                  }}
                </strong>

                <span>Revision {{ entry.revision }}</span>
              </div>

              <p class="message-body">
                {{ entry.text }}
              </p>

              <p
                v-if="
                  entry.tone === 'issue' &&
                  issueRecovery?.originRevision === entry.revision &&
                  issueRecovery.phase === 'cleared'
                "
                class="historical-note"
              >
                최신 분석에서는 이 경고가 재발견되지 않았습니다.
              </p>
            </template>

            <p
              v-if="entry.revision !== currentRevision"
              class="historical-note"
            >
              이전 코드 Revision의 기록입니다.
            </p>
          </article>
        </div>
      </section>

      <details
        v-if="showDeveloperTools"
        class="developer-tools"
      >
        <summary>개발용 코칭 시뮬레이션</summary>

        <p>실제 LLM을 호출하지 않습니다.</p>

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
            초기화
          </button>
        </div>

        <p v-if="pendingDemoResult">
          시뮬레이션 개입 후보 대기 중
        </p>

        <p v-if="lastDemoReason">
          마지막 판단: {{ lastDemoReason }}
        </p>
      </details>
    </div>
  </section>
</template>

<style scoped>
.coach-feedback {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.agent-header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 13px;
  padding: 16px 14px;
  border: 1px solid #c7d2fe;
  border-radius: 14px;
  background: linear-gradient(135deg, #eff6ff, #eef2ff);
}

.agent-avatar {
  display: flex;
  width: 58px;
  height: 58px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
}

.avatar-face {
  display: flex;
  width: 38px;
  height: 27px;
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
  flex: 1;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.agent-identity strong {
  color: #0f172a;
  font-size: 18px;
}

.agent-identity span {
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.agent-dot,
.status-pulse {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #16a34a;
}

.agent-dot.paused {
  background: #94a3b8;
}

.agent-status {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 10px;
  min-height: 36px;
  padding: 9px 12px;
  border-radius: 9px;
  background: #f1f5f9;
  color: #475569;
  font-size: 11px;
  line-height: 1.6;
}

.status-pulse {
  background: #64748b;
}

.status-pulse.busy {
  background: #2563eb;
  animation: pulse 1s ease-in-out infinite alternate;
}

@keyframes pulse {
  to {
    opacity: 0.25;
  }
}

.feed-scroll {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  min-height: 0;
  padding-right: 3px;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
}

.latest-section,
.history-section,
.history-list {
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
  padding: 15px;
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

.conversation-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.user-message,
.assistant-message {
  padding: 11px;
  border-radius: 9px;
}

.user-message {
  background: white;
  border: 1px solid #dbeafe;
}

.assistant-message {
  background: #dbeafe;
}

.user-message strong,
.assistant-message strong {
  color: #1e40af;
  font-size: 11px;
}

.user-message p,
.assistant-message p {
  margin: 6px 0 0;
  color: #334155;
  font-size: 12px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.message-label {
  color: #1d4ed8;
  font-size: 11px;
  font-weight: 700;
}

.latest-card.issue .message-label {
  color: #9a3412;
}

.latest-card.praise .message-label,
.latest-card.recovery-cleared .message-label {
  color: #166534;
}

.latest-card h3 {
  margin: 9px 0 6px;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.5;
}

.message-body {
  margin: 9px 0 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.latest-card.recovery-card p,
.empty-coaching p {
  margin: 8px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.7;
}

.empty-coaching strong {
  color: #1e40af;
  font-size: 13px;
}

.history-card {
  padding: 13px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.history-card .message-body {
  color: #475569;
  font-size: 12px;
}

.history-question {
  margin: 10px 0 0;
  color: #334155;
  font-size: 12px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.historical-note {
  margin: 9px 0 0;
  padding-top: 8px;
  border-top: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 11px;
  line-height: 1.6;
}

.developer-tools {
  padding: 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 9px;
  font-size: 11px;
}

.developer-tools summary {
  cursor: pointer;
}

.simulation-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 10px;
}

.simulation-buttons button {
  padding: 7px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: white;
  color: #334155;
  font: inherit;
  cursor: pointer;
}

@media (prefers-reduced-motion: reduce) {
  .status-pulse.busy {
    animation: none;
  }
}
</style>