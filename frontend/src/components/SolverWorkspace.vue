<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  reactive,
  ref,
  watch,
} from 'vue'

import CodeEditor from '@/components/CodeEditor.vue'
import CoachInterventionPanel from '@/components/CoachInterventionPanel.vue'
import CoachQuestionPanel from '@/components/CoachQuestionPanel.vue'
import ProblemReadingPanel from '@/components/ProblemReadingPanel.vue'
import ProgressiveHintPanel from '@/components/ProgressiveHintPanel.vue'
import SessionCompletionPanel from '@/components/SessionCompletionPanel.vue'
import SubmissionReviewPanel from '@/components/SubmissionReviewPanel.vue'

import { useCodeHistory } from '@/composables/useCodeHistory'
import { useIdleDetection } from '@/composables/useIdleDetection'
import { analyzeCode } from '@/services/analysis'
import { hasEditedReportedIssueLine } from '@/services/issue-recovery'

import {
  recordSessionFeedback,
  type SessionFeedbackReceipt,
  type SessionFeedbackRequest,
} from '@/services/session-feedback'

import {
  evaluateAnalysisTrigger,
  type CodeSnapshot,
  type TriggerDecision,
  type TriggerSuggestion,
  type IssueRecoveryNotice,
} from '@/services/analysis-trigger'

import type { AnalysisResult } from '@/types/analysis'
import type { StructuredProblem } from '@/types/problem'
import type { ProgrammingLanguage } from '@/types/programming-language'

import {
  JUDGE_VERDICT_LABELS,
  type SessionCompletionOutcome,
} from '@/types/session-completion'

const props = defineProps<{
  problemText: string
  structuredProblem: StructuredProblem | null
}>()

const emit = defineEmits<{
  back: []
}>()

// --------------------------------------------------
// Session
// --------------------------------------------------

const sessionId = crypto.randomUUID()

const completionOutcome = ref<SessionCompletionOutcome | null>(
  null,
)

// --------------------------------------------------
// Coaching feedback persistence
// --------------------------------------------------

type FeedbackSaveStatus =
  | 'none'
  | 'saving'
  | 'saved'
  | 'failed'

const feedbackSaveStatus = ref<FeedbackSaveStatus>('none')

const feedbackRequest = ref<SessionFeedbackRequest | null>(
  null,
)

const feedbackReceipt = ref<SessionFeedbackReceipt | null>(
  null,
)

const feedbackError = ref('')

let feedbackController: AbortController | null = null

const feedbackStatusLabel = computed(() => {
  switch (feedbackSaveStatus.value) {
    case 'saving':
      return 'AI 코칭 평가를 기록하고 있습니다.'

    case 'saved':
      return 'AI 코칭 평가가 기록되었습니다.'

    case 'failed':
      return '풀이 종료는 완료됐지만 AI 코칭 평가 저장에 실패했습니다.'

    default:
      return '별도의 AI 코칭 평가를 제출하지 않았습니다.'
  }
})

// --------------------------------------------------
// Editor state
// --------------------------------------------------

const selectedLanguage = ref<ProgrammingLanguage>('python')

const codeByLanguage = reactive<Record<ProgrammingLanguage, string>>({
  python: '',
  java: '',
  cpp: '',
  c: '',
})

const currentCode = computed({
  get: () => codeByLanguage[selectedLanguage.value],
  set: (value: string) => {
    codeByLanguage[selectedLanguage.value] = value
  },
})

const codeRevision = ref(0)

// --------------------------------------------------
// Manual analysis
// --------------------------------------------------

const isAnalyzing = ref(false)
const analysisResult = ref<AnalysisResult | null>(null)
const errorMessage = ref('')

// --------------------------------------------------
// Automatic analysis
// --------------------------------------------------

const MAX_AUTO_ANALYSES = 3

const autoAnalysisEnabled = ref(true)
const autoAnalysisCalls = ref(0)

const isAutoAnalyzing = ref(false)
const autoAnalysisResult = ref<AnalysisResult | null>(null)
const autoAnalysisError = ref('')

let autoAbortController: AbortController | null = null

const autoAnalysisLimitReached = computed(
  () => autoAnalysisCalls.value >= MAX_AUTO_ANALYSES,
)

// --------------------------------------------------
// AI question activity — Stage 5.8B
// --------------------------------------------------

/**
 * This reflects an actual question request lifecycle.
 * It is not inferred from the model's internal reasoning.
 */
const isQuestionAnswering = ref(false)

function handleQuestionActivity(isActive: boolean) {
  if (completionOutcome.value !== null) {
    return
  }

  isQuestionAnswering.value = isActive
}

// --------------------------------------------------
// Unified question history
// --------------------------------------------------

interface CoachingQuestionExchange {
  id: number
  question: string
  answer: string
  answeredRevision: number
  atMs: number
}

const questionExchanges = ref<CoachingQuestionExchange[]>([])

function handleQuestionAnswered(
  exchange: CoachingQuestionExchange,
) {
  if (completionOutcome.value !== null) {
    return
  }

  questionExchanges.value = [
    exchange,
    ...questionExchanges.value,
  ].slice(0, 20)
}

// --------------------------------------------------
// Code observation
// --------------------------------------------------

type ObservationPhase =
  | 'waiting'
  | 'editing'
  | 'settled'

const OBSERVATION_DELAY_MS = 800

const observationPhase = ref<ObservationPhase>('waiting')
const stableSnapshot = ref<CodeSnapshot | null>(null)

const triggerDecision = ref<TriggerDecision | null>(null)
const lastSuggestion = ref<TriggerSuggestion | null>(null)

interface ReportedIssueSnapshot {
  snapshot: CodeSnapshot
  issues: AnalysisResult['issues']
}

const lastReportedIssues = ref<ReportedIssueSnapshot | null>(
  null,
)

const issueRecovery = ref<IssueRecoveryNotice | null>(null)

function editedReportedIssue(snapshot: CodeSnapshot): boolean {
  const previous = lastReportedIssues.value

  return (
    previous !== null &&
    previous.snapshot.language === snapshot.language &&
    hasEditedReportedIssueLine(
      previous.snapshot.code,
      snapshot.code,
      previous.issues,
    )
  )
}

function observeIssueEdit(snapshot: CodeSnapshot) {
  const previous = lastReportedIssues.value

  if (previous !== null && editedReportedIssue(snapshot)) {
    issueRecovery.value = {
      originRevision: previous.snapshot.revision,
      checkedRevision: null,
      phase: 'pending',
    }

    return
  }

  issueRecovery.value = null
}

function markIssueChecking(snapshot: CodeSnapshot) {
  const previous = lastReportedIssues.value

  if (previous !== null && editedReportedIssue(snapshot)) {
    issueRecovery.value = {
      originRevision: previous.snapshot.revision,
      checkedRevision: null,
      phase: 'checking',
    }
  }
}

function markIssueCheckFailure(snapshot: CodeSnapshot) {
  const notice = issueRecovery.value

  if (
    notice !== null &&
    notice.phase === 'checking' &&
    snapshot.revision === codeRevision.value &&
    snapshot.language === selectedLanguage.value &&
    snapshot.code === currentCode.value
  ) {
    issueRecovery.value = {
      ...notice,
      phase: 'failed',
    }
  }
}

function acceptFreshAnalysis(
  snapshot: CodeSnapshot,
  result: AnalysisResult,
) {
  const previous = lastReportedIssues.value
  const notice = issueRecovery.value

  if (
    previous !== null &&
    notice !== null &&
    notice.originRevision === previous.snapshot.revision &&
    editedReportedIssue(snapshot)
  ) {
    issueRecovery.value = {
      originRevision: notice.originRevision,
      checkedRevision: snapshot.revision,
      phase:
        result.issues.length === 0
          ? 'cleared'
          : 'issues_found',
    }
  }

  lastReportedIssues.value =
    result.issues.length > 0
      ? {
          snapshot,
          issues: result.issues,
        }
      : null
}

let observationTimer: ReturnType<typeof setTimeout> | null = null

const observationStatusText = computed(() => {
  switch (observationPhase.value) {
    case 'editing':
      return '코드 편집 중'

    case 'settled':
      return '입력 안정'

    default:
      return '입력 대기'
  }
})

// --------------------------------------------------
// Existing observation and history
// --------------------------------------------------

const { isIdle, idleStatusText } = useIdleDetection(
  currentCode,
  selectedLanguage,
)

const { history, latestEntry } = useCodeHistory(
  stableSnapshot,
)

const showDeveloperMonitor =
  import.meta.env.DEV &&
  new URLSearchParams(window.location.search).get(
    'debugCoach',
  ) === '1'

// --------------------------------------------------
// Coaching context for questions
// --------------------------------------------------

const latestCoachingText = computed<string | null>(() => {
  if (
    analysisResult.value?.analyzed_revision ===
    codeRevision.value
  ) {
    return analysisResult.value.summary
  }

  if (
    autoAnalysisResult.value?.analyzed_revision ===
    codeRevision.value
  ) {
    return autoAnalysisResult.value.summary
  }

  return null
})

// --------------------------------------------------
// Automatic analysis eligibility
// --------------------------------------------------

function considerAutomaticAnalysis(
  snapshot: CodeSnapshot,
) {
  if (completionOutcome.value !== null) {
    return
  }

  const nowMs = Date.now()

  const decision = evaluateAnalysisTrigger(
    snapshot,
    lastSuggestion.value,
    nowMs,
    {
      recheckEditedIssue:
        issueRecovery.value?.phase === 'pending' &&
        editedReportedIssue(snapshot),
    },
  )

  triggerDecision.value = decision

  if (!decision.eligible) {
    return
  }

  if (!autoAnalysisEnabled.value) {
    return
  }

  if (
    isAnalyzing.value ||
    isAutoAnalyzing.value ||
    autoAnalysisLimitReached.value
  ) {
    return
  }

  lastSuggestion.value = {
    snapshot,
    suggestedAtMs: nowMs,
  }

  void runAutomaticAnalysis(snapshot)
}

// --------------------------------------------------
// Observe changes to code and language
// --------------------------------------------------

watch([selectedLanguage, currentCode], () => {
  if (completionOutcome.value !== null) {
    return
  }

  codeRevision.value += 1

  analysisResult.value = null
  errorMessage.value = ''

  autoAbortController?.abort()
  autoAbortController = null

  isAutoAnalyzing.value = false
  autoAnalysisResult.value = null
  autoAnalysisError.value = ''

  stableSnapshot.value = null
  triggerDecision.value = null
  observationPhase.value = 'editing'

  if (observationTimer !== null) {
    clearTimeout(observationTimer)
    observationTimer = null
  }

  const snapshot: CodeSnapshot = {
    language: selectedLanguage.value,
    code: currentCode.value,
    revision: codeRevision.value,
  }

  observeIssueEdit(snapshot)

  observationTimer = setTimeout(() => {
    observationTimer = null

    if (
      completionOutcome.value !== null ||
      snapshot.revision !== codeRevision.value ||
      snapshot.language !== selectedLanguage.value ||
      snapshot.code !== currentCode.value
    ) {
      return
    }

    stableSnapshot.value = snapshot
    observationPhase.value = 'settled'

    considerAutomaticAnalysis(snapshot)
  }, OBSERVATION_DELAY_MS)
})

// --------------------------------------------------
// Automatic coaching ON / OFF
// --------------------------------------------------

watch(autoAnalysisEnabled, (enabled) => {
  if (!enabled) {
    autoAbortController?.abort()
    autoAbortController = null

    isAutoAnalyzing.value = false
    autoAnalysisResult.value = null
    autoAnalysisError.value = ''

    if (issueRecovery.value?.phase === 'checking') {
      issueRecovery.value = {
        ...issueRecovery.value,
        phase: 'pending',
      }
    }

    return
  }

  if (completionOutcome.value !== null) {
    return
  }

  const snapshot = stableSnapshot.value

  if (
    snapshot !== null &&
    observationPhase.value === 'settled' &&
    snapshot.revision === codeRevision.value &&
    snapshot.language === selectedLanguage.value &&
    snapshot.code === currentCode.value
  ) {
    considerAutomaticAnalysis(snapshot)
  }
})

// --------------------------------------------------
// Manual code feedback
// --------------------------------------------------

async function runAnalysis() {
  if (
    completionOutcome.value !== null ||
    isAnalyzing.value ||
    isAutoAnalyzing.value ||
    !currentCode.value.trim()
  ) {
    return
  }

  const revision = codeRevision.value
  const codeSnapshot = currentCode.value
  const languageSnapshot = selectedLanguage.value

  const snapshot: CodeSnapshot = {
    language: languageSnapshot,
    code: codeSnapshot,
    revision,
  }

  markIssueChecking(snapshot)

  isAnalyzing.value = true
  analysisResult.value = null
  errorMessage.value = ''

  try {
    const result = await analyzeCode({
      session_id: sessionId,
      code_revision: revision,
      problem_text: props.problemText,
      current_code: codeSnapshot,
      language: languageSnapshot,
    })

    if (completionOutcome.value !== null) {
      return
    }

    if (
      revision !== codeRevision.value ||
      codeSnapshot !== currentCode.value ||
      languageSnapshot !== selectedLanguage.value
    ) {
      errorMessage.value =
        '분석 중 코드가 변경되었습니다. 현재 코드로 다시 요청해 주세요.'
      return
    }

    if (result.analyzed_revision !== revision) {
      throw new Error(
        '분석 결과의 코드 Revision이 일치하지 않습니다.',
      )
    }

    acceptFreshAnalysis(snapshot, result)
    analysisResult.value = result
  } catch (error) {
    markIssueCheckFailure(snapshot)

    if (completionOutcome.value !== null) {
      return
    }

    errorMessage.value =
      error instanceof Error
        ? error.message
        : '분석 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    isAnalyzing.value = false
  }
}

// --------------------------------------------------
// Automatic code analysis
// --------------------------------------------------

async function runAutomaticAnalysis(
  snapshot: CodeSnapshot,
) {
  if (
    completionOutcome.value !== null ||
    !autoAnalysisEnabled.value ||
    isAnalyzing.value ||
    isAutoAnalyzing.value ||
    autoAnalysisLimitReached.value
  ) {
    return
  }

  autoAbortController?.abort()

  const controller = new AbortController()
  autoAbortController = controller

  autoAnalysisCalls.value += 1

  markIssueChecking(snapshot)
  isAutoAnalyzing.value = true
  autoAnalysisResult.value = null
  autoAnalysisError.value = ''

  try {
    const result = await analyzeCode(
      {
        session_id: sessionId,
        code_revision: snapshot.revision,
        problem_text: props.problemText,
        current_code: snapshot.code,
        language: snapshot.language,
      },
      controller.signal,
    )

    if (
      completionOutcome.value !== null ||
      controller.signal.aborted ||
      autoAbortController !== controller ||
      !autoAnalysisEnabled.value
    ) {
      return
    }

    if (
      snapshot.revision !== codeRevision.value ||
      snapshot.language !== selectedLanguage.value ||
      snapshot.code !== currentCode.value
    ) {
      return
    }

    if (result.analyzed_revision !== snapshot.revision) {
      throw new Error(
        '자동 분석 결과의 코드 Revision이 일치하지 않습니다.',
      )
    }

    acceptFreshAnalysis(snapshot, result)
    autoAnalysisResult.value = result
  } catch (error) {
    if (
      completionOutcome.value !== null ||
      controller.signal.aborted ||
      autoAbortController !== controller
    ) {
      return
    }

    if (lastSuggestion.value?.snapshot === snapshot) {
      lastSuggestion.value = null
    }

    markIssueCheckFailure(snapshot)

    autoAnalysisError.value =
      error instanceof Error
        ? error.message
        : '자동 분석 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    if (autoAbortController === controller) {
      autoAbortController = null
      isAutoAnalyzing.value = false
    }
  }
}

// --------------------------------------------------
// Feedback persistence
// --------------------------------------------------

async function saveCoachingFeedback(
  request: SessionFeedbackRequest,
) {
  if (feedbackSaveStatus.value === 'saving') {
    return
  }

  const controller = new AbortController()

  feedbackController = controller
  feedbackSaveStatus.value = 'saving'
  feedbackError.value = ''

  let timedOut = false

  const timeoutId = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, 15_000)

  try {
    const receipt = await recordSessionFeedback(
      request,
      controller.signal,
    )

    if (
      controller.signal.aborted ||
      feedbackController !== controller
    ) {
      return
    }

    feedbackReceipt.value = receipt
    feedbackSaveStatus.value = 'saved'
  } catch (error) {
    if (feedbackController !== controller) {
      return
    }

    feedbackSaveStatus.value = 'failed'

    feedbackError.value = timedOut
      ? '평가 저장 응답이 지연되었습니다. 동일한 요청으로 재시도할 수 있습니다.'
      : (
            error instanceof Error
              ? error.message
              : '코칭 평가 저장 중 오류가 발생했습니다.'
        )
  } finally {
    clearTimeout(timeoutId)

    if (feedbackController === controller) {
      feedbackController = null
    }
  }
}

function retryCoachingFeedback() {
  if (
    feedbackSaveStatus.value !== 'failed' ||
    feedbackRequest.value === null
  ) {
    return
  }

  void saveCoachingFeedback(feedbackRequest.value)
}

// --------------------------------------------------
// Complete session
// --------------------------------------------------

function handleSessionCompleted(
  outcome: SessionCompletionOutcome,
  feedback: SessionFeedbackRequest | null,
) {
  if (completionOutcome.value !== null) {
    return
  }

  autoAnalysisEnabled.value = false

  autoAbortController?.abort()
  autoAbortController = null

  isAutoAnalyzing.value = false
  isQuestionAnswering.value = false

  if (observationTimer !== null) {
    clearTimeout(observationTimer)
    observationTimer = null
  }

  completionOutcome.value = outcome

  if (feedback === null) {
    feedbackSaveStatus.value = 'none'
    return
  }

  feedbackRequest.value = { ...feedback }

  void saveCoachingFeedback(feedbackRequest.value)
}

// --------------------------------------------------
// Cleanup and navigation
// --------------------------------------------------

onBeforeUnmount(() => {
  if (observationTimer !== null) {
    clearTimeout(observationTimer)
    observationTimer = null
  }

  autoAbortController?.abort()
  autoAbortController = null

  feedbackController?.abort()
  feedbackController = null

  isQuestionAnswering.value = false
})

function returnToProblemInput() {
  if (feedbackSaveStatus.value === 'saving') {
    return
  }

  emit('back')
}
</script>

<template>
  <!-- Completed session -->
  <div
    v-if="completionOutcome"
    class="completion-page"
  >
    <div class="completion-summary">
      <span class="completion-eyebrow">
        SESSION COMPLETED
      </span>

      <h1>풀이를 종료했습니다.</h1>

      <p class="completion-description">
        풀이 종료 기록이 서버에 접수됐습니다.
        다음 정보는 사용자가 입력한 외부 채점 결과와
        종료 당시 코드입니다.
      </p>

      <div class="completion-meta">
        <div class="completion-meta-item">
          <span>종료 방식</span>
          <strong>
            {{
              completionOutcome.receipt.completion_mode ===
              'EXTERNAL_JUDGE'
                ? '외부 채점 결과 기록'
                : '제출 없이 종료'
            }}
          </strong>
        </div>

        <div class="completion-meta-item">
          <span>외부 채점 결과</span>
          <strong>
            {{
              completionOutcome.receipt.judge_verdict
                ? JUDGE_VERDICT_LABELS[
                    completionOutcome.receipt.judge_verdict
                  ]
                : '기록 없음'
            }}
          </strong>
        </div>

        <div class="completion-meta-item">
          <span>프로그래밍 언어</span>
          <strong>
            {{ completionOutcome.request.language.toUpperCase() }}
          </strong>
        </div>

        <div class="completion-meta-item">
          <span>최종 코드 Revision</span>
          <strong>
            {{ completionOutcome.receipt.code_revision }}
          </strong>
        </div>

        <div class="completion-meta-item">
          <span>종료 시각</span>
          <strong>
            {{
              new Date(
                completionOutcome.receipt.completed_at,
              ).toLocaleString('ko-KR')
            }}
          </strong>
        </div>

        <div class="completion-meta-item">
          <span>서버 처리 결과</span>
          <strong>
            {{
              completionOutcome.created
                ? '신규 종료 기록'
                : '기존 종료 기록 재확인'
            }}
          </strong>
        </div>
      </div>

      <div
        v-if="
          completionOutcome.receipt.verdict_source ===
          'USER_REPORTED'
        "
        class="verdict-notice"
      >
        외부 채점 결과는 사용자가 보고한 정보입니다.
        AlgoCoach가 직접 코드를 실행하거나 채점하지 않았습니다.
      </div>

      <div
        v-else
        class="verdict-notice"
      >
        외부 채점 결과가 기록되지 않았습니다.
      </div>

      <section
        class="coaching-record"
        :class="`feedback-${feedbackSaveStatus}`"
        aria-live="polite"
      >
        <h2>AI 코칭 평가</h2>
        <p>{{ feedbackStatusLabel }}</p>

        <p
          v-if="
            feedbackSaveStatus === 'saved' &&
            feedbackReceipt
          "
          class="feedback-time"
        >
          기록 시각:
          {{
            new Date(
              feedbackReceipt.recorded_at,
            ).toLocaleString('ko-KR')
          }}
        </p>

        <template v-if="feedbackSaveStatus === 'failed'">
          <p class="feedback-error">
            {{ feedbackError }}
          </p>

          <button
            type="button"
            class="retry-feedback-button"
            @click="retryCoachingFeedback"
          >
            동일한 평가 다시 저장
          </button>

          <p class="feedback-hint">
            평가 저장에 실패해도 풀이 종료 기록은
            유지됩니다.
          </p>
        </template>
      </section>

      <section
        v-if="completionOutcome.request.notes"
        class="completion-section"
      >
        <h2>풀이 메모</h2>
        <p class="completion-notes">
          {{ completionOutcome.request.notes }}
        </p>
      </section>

      <section class="completion-section">
        <h2>최종 코드</h2>

        <pre class="final-code">{{ completionOutcome.request.final_code || '작성한 코드가 없습니다.' }}</pre>
      </section>

      <p class="completion-limitation">
        완료 기록과 코칭 품질 평가는 로컬 SQLite에
        저장됩니다. 현재 개발용 환경에서는
        사용자 계정과 클라우드 동기화를 제공하지 않습니다.
      </p>

      <button
        type="button"
        class="return-button"
        :disabled="feedbackSaveStatus === 'saving'"
        @click="returnToProblemInput"
      >
        {{
          feedbackSaveStatus === 'saving'
            ? '코칭 평가 기록 확인 중...'
            : '문제 입력 화면으로 돌아가기'
        }}
      </button>
    </div>
  </div>

  <!-- Active solver -->
  <div
    v-else
    class="workspace"
  >
    <header class="workspace-header">
      <div class="brand">
        <h1>AlgoCoach</h1>
        <span>코딩테스트 풀이 환경</span>
      </div>

      <div class="header-actions">
        <SessionCompletionPanel
          :session-id="sessionId"
          :problem-text="problemText"
          :current-code="currentCode"
          :language="selectedLanguage"
          :current-revision="codeRevision"
          @completed="handleSessionCompleted"
        />

        <button
          type="button"
          class="back-button"
          @click="returnToProblemInput"
        >
          ← 문제 입력으로
        </button>
      </div>
    </header>

    <div class="workspace-grid">
      <!-- Left: problem -->
      <section class="panel problem-panel">
        <div class="panel-header">
          <h2>문제</h2>
        </div>

        <ProblemReadingPanel
          :original-text="problemText"
          :structured-problem="structuredProblem"
        />
      </section>

      <!-- Center: editor -->
      <section class="panel editor-panel">
        <div class="panel-header">
          <h2>코드 에디터</h2>

          <div class="editor-controls">
            <label
              for="language-select"
              class="sr-only"
            >
              프로그래밍 언어
            </label>

            <select
              id="language-select"
              v-model="selectedLanguage"
              class="language-select"
            >
              <option value="python">Python</option>
              <option value="java">Java</option>
              <option value="cpp">C++</option>
              <option value="c">C</option>
            </select>

            <span class="revision">
              Revision {{ codeRevision }}
            </span>
          </div>
        </div>

        <div class="editor-content">
          <CodeEditor
            v-model="currentCode"
            :language="selectedLanguage"
          />

          <div class="editor-footer">
            Monaco Editor · 4 Spaces · LLM Analysis
          </div>
        </div>
      </section>

      <!-- Right: agent -->
      <aside class="panel coach-panel">
        <div class="panel-header">
          <h2>AI Coach</h2>
          <span class="provider-label">LLM</span>
        </div>

        <div class="coach-content">
          <!--
            Stage 5.8B:
            Forward real editor and API activity
            to the agent status display.
          -->
          <CoachInterventionPanel
            :analysis-result="autoAnalysisResult"
            :manual-analysis-result="analysisResult"
            :current-revision="codeRevision"
            :issue-recovery="issueRecovery"
            :auto-enabled="autoAnalysisEnabled"
            :is-auto-analyzing="isAutoAnalyzing"
            :is-manual-analyzing="isAnalyzing"
            :is-question-answering="isQuestionAnswering"
            :observation-phase="observationPhase"
            :auto-analysis-limit-reached="autoAnalysisLimitReached"
            :auto-analysis-error="autoAnalysisError"
            :manual-analysis-error="errorMessage"
            :question-exchanges="questionExchanges"
          />

          <div class="coach-action-dock">
            <div class="auto-control-row">
              <label class="auto-control-label">
                <input
                  v-model="autoAnalysisEnabled"
                  type="checkbox"
                  class="auto-checkbox"
                />

                <span>자동 AI 코칭</span>

                <strong>
                  {{ autoAnalysisEnabled ? 'ON' : 'OFF' }}
                </strong>
              </label>

              <span class="auto-usage">
                {{ autoAnalysisCalls }}/{{ MAX_AUTO_ANALYSES }}
              </span>
            </div>

            <p
              v-if="autoAnalysisLimitReached"
              class="auto-limit-notice"
            >
              자동 분석 한도에 도달했습니다.
              수동 피드백과 질문은 계속 사용할 수 있습니다.
            </p>

            <button
              type="button"
              class="analyze-button"
              :disabled="
                isAnalyzing ||
                isAutoAnalyzing ||
                !currentCode.trim()
              "
              @click="runAnalysis"
            >
              {{
                isAnalyzing
                  ? 'AI 피드백 생성 중...'
                  : isAutoAnalyzing
                    ? '자동 분석 진행 중...'
                    : '지금 피드백 받기'
              }}
            </button>

            <!--
              Question activity events are forwarded
              to the main agent status.
            -->
            <CoachQuestionPanel
              :session-id="sessionId"
              :problem-text="problemText"
              :current-code="currentCode"
              :language="selectedLanguage"
              :current-revision="codeRevision"
              :latest-coaching="latestCoachingText"
              @answered="handleQuestionAnswered"
              @activity="handleQuestionActivity"
            />

            <details class="secondary-tools">
              <summary>
                추가 코칭 도구 · 힌트 / 제출 전 점검
              </summary>

              <div class="secondary-tool-content">
                <ProgressiveHintPanel
                  :session-id="sessionId"
                  :problem-text="problemText"
                  :current-code="currentCode"
                  :language="selectedLanguage"
                  :current-revision="codeRevision"
                />

                <SubmissionReviewPanel
                  :session-id="sessionId"
                  :problem-text="problemText"
                  :current-code="currentCode"
                  :language="selectedLanguage"
                  :current-revision="codeRevision"
                  :disabled="isAnalyzing || isAutoAnalyzing"
                />
              </div>
            </details>

            <p
              v-if="errorMessage"
              class="error-message"
              role="alert"
            >
              {{ errorMessage }}
            </p>

            <p
              v-if="autoAnalysisError"
              class="error-message"
              role="alert"
            >
              자동 분석 실패: {{ autoAnalysisError }}
            </p>

            <details
              v-if="showDeveloperMonitor"
              class="developer-monitor"
            >
              <summary>개발용 코드 관찰 정보</summary>

              <p>
                관찰 상태:
                {{ observationStatusText }}
              </p>

              <p>
                최근 편집:
                {{ idleStatusText }}
                · idle={{ isIdle }}
              </p>

              <p v-if="stableSnapshot">
                안정된 Revision:
                {{ stableSnapshot.revision }}
              </p>

              <p v-if="triggerDecision">
                분석 후보:
                {{ triggerDecision.message }}
              </p>

              <p>
                코드 변경 기록:
                {{ history.length }}개
              </p>

              <p v-if="latestEntry">
                최근 변경 Revision:
                {{ latestEntry.revision }}
              </p>
            </details>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.workspace {
  min-height: 100vh;
  padding: 20px;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 20px;
}

.brand {
  display: flex;
  align-items: baseline;
  gap: 16px;
}

.brand h1 {
  margin: 0;
  font-size: 24px;
}

.brand span,
.revision {
  color: #64748b;
  font-size: 13px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.back-button {
  padding: 10px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: white;
  color: #334155;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.workspace-grid {
  display: grid;
  grid-template-columns:
    minmax(240px, 1fr)
    minmax(400px, 1.8fr)
    minmax(270px, 1fr);
  align-items: stretch;
  gap: 16px;
}

.panel {
  display: flex;
  min-height: 650px;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: white;
}

.panel-header {
  display: flex;
  min-height: 58px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.panel-header h2 {
  margin: 0;
  font-size: 15px;
}

.editor-content {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  padding: 12px;
}

.editor-footer {
  padding-top: 12px;
  color: #94a3b8;
  font-size: 12px;
}

.editor-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.language-select {
  padding: 7px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: white;
  color: #334155;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.coach-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.provider-label {
  padding: 4px 8px;
  border-radius: 6px;
  background: #e2e8f0;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
}

.coach-action-dock {
  display: flex;
  flex-direction: column;
  gap: 9px;
  min-width: 0;
}

.auto-control-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.auto-control-label {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.auto-checkbox {
  width: 17px;
  height: 17px;
  flex-shrink: 0;
  accent-color: #2563eb;
  cursor: pointer;
}

.auto-control-label strong {
  color: #2563eb;
  font-size: 11px;
}

.auto-usage {
  color: #94a3b8;
  font-size: 11px;
  white-space: nowrap;
}

.auto-limit-notice {
  margin: 0;
  color: #b45309;
  font-size: 11px;
  line-height: 1.6;
}

.analyze-button {
  width: 100%;
  min-height: 44px;
  padding: 11px 13px;
  border: none;
  border-radius: 9px;
  background: #2563eb;
  color: white;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.analyze-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.secondary-tools {
  min-width: 0;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 9px;
  background: #f8fafc;
}

.secondary-tools summary {
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
}

.secondary-tool-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  margin-top: 12px;
}

.developer-monitor {
  padding: 10px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #64748b;
  font-size: 11px;
}

.developer-monitor summary {
  cursor: pointer;
}

.developer-monitor p {
  line-height: 1.6;
}

.error-message {
  margin: 0;
  color: #dc2626;
  font-size: 12px;
  line-height: 1.6;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

.completion-page {
  min-height: 100vh;
  padding: 60px 20px;
  background: #f8fafc;
}

.completion-summary {
  width: min(100%, 780px);
  margin: 0 auto;
  padding: 36px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: white;
}

.completion-eyebrow {
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.completion-summary h1 {
  margin: 12px 0;
  color: #0f172a;
  font-size: 29px;
}

.completion-description {
  margin: 0 0 28px;
  color: #64748b;
  font-size: 14px;
  line-height: 1.8;
}

.completion-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.completion-meta-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 14px;
  border-radius: 9px;
  background: #f1f5f9;
}

.completion-meta-item span {
  color: #64748b;
  font-size: 11px;
}

.completion-meta-item strong {
  color: #0f172a;
  font-size: 13px;
  overflow-wrap: anywhere;
}

.verdict-notice {
  margin-top: 20px;
  padding: 14px;
  border: 1px solid #bfdbfe;
  border-radius: 9px;
  background: #eff6ff;
  color: #1e40af;
  font-size: 12px;
  line-height: 1.8;
}

.coaching-record {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.coaching-record h2 {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 14px;
}

.coaching-record p {
  margin: 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.8;
}

.coaching-record.feedback-saved {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.coaching-record.feedback-failed {
  border-color: #fed7aa;
  background: #fff7ed;
}

.coaching-record .feedback-time {
  margin-top: 6px;
  color: #64748b;
  font-size: 11px;
}

.coaching-record .feedback-error {
  margin-top: 8px;
  color: #b91c1c;
}

.coaching-record .feedback-hint {
  margin-top: 8px;
  color: #64748b;
  font-size: 11px;
}

.retry-feedback-button {
  margin-top: 12px;
  padding: 10px 13px;
  border: 1px solid #d97706;
  border-radius: 7px;
  background: white;
  color: #92400e;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.completion-section {
  margin-top: 28px;
}

.completion-section h2 {
  margin: 0 0 12px;
  color: #0f172a;
  font-size: 16px;
}

.completion-notes {
  margin: 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.final-code {
  max-height: 380px;
  overflow: auto;
  margin: 0;
  padding: 18px;
  border-radius: 9px;
  background: #0f172a;
  color: #e2e8f0;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre;
  tab-size: 4;
}

.completion-limitation {
  margin: 22px 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.8;
}

.return-button {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 9px;
  background: #2563eb;
  color: white;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.return-button:hover:not(:disabled) {
  background: #1d4ed8;
}

.return-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 1050px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .panel {
    min-height: auto;
  }
}

@media (max-width: 600px) {
  .workspace-header,
  .brand,
  .header-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .completion-page {
    padding: 24px 12px;
  }

  .completion-summary {
    padding: 20px;
  }

  .completion-meta {
    grid-template-columns: 1fr;
  }
}
</style>