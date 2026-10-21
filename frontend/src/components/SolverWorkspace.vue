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
import ProblemReadingPanel from '@/components/ProblemReadingPanel.vue'
import ProgressiveHintPanel from '@/components/ProgressiveHintPanel.vue'
import SessionCompletionPanel from '@/components/SessionCompletionPanel.vue'
import SubmissionReviewPanel from '@/components/SubmissionReviewPanel.vue'

import { useCodeHistory } from '@/composables/useCodeHistory'
import { useIdleDetection } from '@/composables/useIdleDetection'
import { analyzeCode } from '@/services/analysis'

import {
  evaluateAnalysisTrigger,
  type CodeSnapshot,
  type TriggerDecision,
  type TriggerSuggestion,
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

const autoAnalysisEnabled = ref(false)
const autoAnalysisCalls = ref(0)

const isAutoAnalyzing = ref(false)
const autoAnalysisResult = ref<AnalysisResult | null>(null)
const autoAnalysisError = ref('')

let autoAbortController: AbortController | null = null

const autoAnalysisLimitReached = computed(
  () => autoAnalysisCalls.value >= MAX_AUTO_ANALYSES,
)

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
// Idle detection and code history
// --------------------------------------------------

const { isIdle, idleStatusText } = useIdleDetection(
  currentCode,
  selectedLanguage,
)

const { history, latestEntry } = useCodeHistory(
  stableSnapshot,
)

// --------------------------------------------------
// Analysis trigger policy
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
// Code change detection
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
// Automatic analysis toggle
// --------------------------------------------------

watch(autoAnalysisEnabled, (enabled) => {
  if (!enabled) {
    autoAbortController?.abort()
    autoAbortController = null

    isAutoAnalyzing.value = false
    autoAnalysisResult.value = null
    autoAnalysisError.value = ''
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
// Manual analysis
// --------------------------------------------------

async function runAnalysis() {
  if (
    completionOutcome.value !== null ||
    isAnalyzing.value ||
    isAutoAnalyzing.value
  ) {
    return
  }

  const revision = codeRevision.value
  const codeSnapshot = currentCode.value
  const languageSnapshot = selectedLanguage.value

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
        '분석 중 코드 또는 언어가 변경되었습니다. 다시 분석해 주세요.'
      return
    }

    if (result.analyzed_revision !== revision) {
      throw new Error(
        '분석 결과의 코드 Revision이 일치하지 않습니다.',
      )
    }

    analysisResult.value = result
  } catch (error) {
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
// Automatic analysis
// --------------------------------------------------

async function runAutomaticAnalysis(
  snapshot: CodeSnapshot,
) {
  if (
    completionOutcome.value !== null ||
    !autoAnalysisEnabled.value ||
    isAnalyzing.value ||
    autoAnalysisLimitReached.value
  ) {
    return
  }

  autoAbortController?.abort()

  const controller = new AbortController()
  autoAbortController = controller

  // This is a development-only request limit.
  autoAnalysisCalls.value += 1

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

    if (
      result.analyzed_revision !== snapshot.revision
    ) {
      throw new Error(
        '자동 분석 결과의 Revision이 일치하지 않습니다.',
      )
    }

    autoAnalysisResult.value = result
  } catch (error) {
    if (
      completionOutcome.value !== null ||
      controller.signal.aborted ||
      autoAbortController !== controller
    ) {
      return
    }

    if (
      lastSuggestion.value?.snapshot === snapshot
    ) {
      lastSuggestion.value = null
    }

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
// Session completion
// --------------------------------------------------

function handleSessionCompleted(
  outcome: SessionCompletionOutcome,
) {
  if (completionOutcome.value !== null) {
    return
  }

  // Stop new automatic analyses after completing the session.
  autoAnalysisEnabled.value = false

  autoAbortController?.abort()
  autoAbortController = null

  isAutoAnalyzing.value = false

  if (observationTimer !== null) {
    clearTimeout(observationTimer)
    observationTimer = null
  }

  completionOutcome.value = outcome
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
})

function returnToProblemInput() {
  emit('back')
}
</script>

<template>
  <!-- Completed Session -->
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
        아래 내용은 종료 요청 당시의 코드와
        사용자가 직접 입력한 결과입니다.
      </p>

      <div class="completion-meta">
        <div class="completion-meta-item">
          <span>종료 방식</span>

          <strong>
            {{
              completionOutcome.receipt.completion_mode
                === 'EXTERNAL_JUDGE'
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
        v-if="completionOutcome.receipt.verdict_source === 'USER_REPORTED'"
        class="verdict-notice"
      >
        이 채점 결과는 사용자가 외부 사이트에서 확인하여
        직접 입력한 정보입니다.
        AlgoCoach가 코드를 실행하거나 채점한 결과가 아닙니다.
      </div>

      <div
        v-else
        class="verdict-notice"
      >
        이번 풀이에는 외부 채점 결과가 기록되지 않았습니다.
      </div>

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
        현재 개발 버전에서는 완료 기록을 서버 메모리에 보관합니다.
        서버가 재시작되면 저장된 기록이 사라질 수 있습니다.
      </p>

      <button
        type="button"
        class="return-button"
        @click="returnToProblemInput"
      >
        문제 입력 화면으로 돌아가기
      </button>
    </div>
  </div>

  <!-- Active Solver Workspace -->
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
      <!-- Problem Panel -->
      <section class="panel problem-panel">
        <div class="panel-header">
          <h2>문제</h2>
        </div>

        <ProblemReadingPanel
          :original-text="problemText"
          :structured-problem="structuredProblem"
        />
      </section>

      <!-- Code Editor Panel -->
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

      <!-- AI Coach Panel -->
      <aside class="panel coach-panel">
        <div class="panel-header">
          <h2>AI Coach</h2>
          <span class="provider-label">LLM</span>
        </div>

        <div class="coach-content">
          <!-- Automatic Analysis Control -->
          <section class="control-card">
            <div class="control-heading">
              <h3>자동 AI 분석</h3>

              <label class="switch-label">
                <input
                  v-model="autoAnalysisEnabled"
                  type="checkbox"
                />
                <span>
                  {{ autoAnalysisEnabled ? 'ON' : 'OFF' }}
                </span>
              </label>
            </div>

            <p class="control-description">
              자동 분석은 기본적으로 비활성화됩니다.
              활성화하면 코드 변경에 따라 실제 LLM API가
              호출될 수 있습니다.
            </p>

            <p class="usage-count">
              자동 분석 요청:
              <strong>
                {{ autoAnalysisCalls }} / {{ MAX_AUTO_ANALYSES }}
              </strong>
            </p>

            <p
              v-if="autoAnalysisLimitReached"
              class="limit-message"
            >
              이 풀이 화면의 자동 분석 요청 한도에 도달했습니다.
              추가 자동 요청은 실행하지 않습니다.
            </p>
          </section>

          <!-- Code Observation -->
          <section class="observation-card">
            <h3>코드 관찰 상태</h3>

            <p>
              현재 상태:
              <strong>{{ observationStatusText }}</strong>
            </p>

            <p
              v-if="stableSnapshot"
              class="snapshot-info"
            >
              안정된 스냅샷:
              Revision {{ stableSnapshot.revision }}
              · {{ stableSnapshot.language }}
            </p>

            <p class="observation-description">
              편집 활동:
              <strong>{{ idleStatusText }}</strong>
            </p>

            <p
              v-if="isIdle"
              class="observation-description"
            >
              최근 30초 동안 코드 수정이 감지되지 않았습니다.
              실제 풀이 정체 여부는 아직 판단하지 않습니다.
            </p>

            <div
              v-if="triggerDecision"
              class="trigger-decision"
            >
              <p>
                분석 후보:
                <strong>
                  {{
                    triggerDecision.eligible
                      ? '추천'
                      : '보류'
                  }}
                </strong>
              </p>

              <p class="trigger-reason">
                {{ triggerDecision.message }}
              </p>
            </div>

            <p class="observation-description">
              분석 후보라도 자동 분석이 OFF이거나
              요청 한도에 도달하면 호출하지 않습니다.
            </p>

            <p class="observation-description">
              기록된 코드 변경:
              {{ history.length }}개 (최근 최대 20개)
            </p>

            <p
              v-if="latestEntry"
              class="observation-description"
            >
              최근 기록:
              Revision {{ latestEntry.revision }}
              · {{ latestEntry.language }}
              ·
              {{
                latestEntry.changedCharacters === null
                  ? '첫 코드 기록'
                  : `약 ${latestEntry.changedCharacters}자 변경`
              }}
            </p>
          </section>

          <!-- Internal Automatic Analysis -->
          <section class="observation-card">
            <h3>내부 자동 분석</h3>

            <p
              v-if="isAutoAnalyzing"
              role="status"
            >
              LangGraph 자동 분석 실행 중...
            </p>

            <p v-else-if="autoAnalysisResult">
              자동 분석 완료 · Revision
              {{ autoAnalysisResult.analyzed_revision }}
            </p>

            <p
              v-else-if="autoAnalysisError"
              class="error-message"
              role="alert"
            >
              자동 분석 실패: {{ autoAnalysisError }}
            </p>

            <p v-else-if="!autoAnalysisEnabled">
              자동 분석이 비활성화되어 있습니다.
            </p>

            <p v-else>
              아직 자동 분석 결과가 없습니다.
            </p>

            <p class="observation-description">
              분석 결과는 개입 정책으로 전달되며,
              충분한 코칭 근거가 있을 때만 메시지로 표시됩니다.
            </p>
          </section>

          <!-- Proactive Coach Feed -->
          <CoachInterventionPanel
            :analysis-result="autoAnalysisResult"
            :current-revision="codeRevision"
          />

          <!-- Progressive Hints -->
          <ProgressiveHintPanel
            :session-id="sessionId"
            :problem-text="problemText"
            :current-code="currentCode"
            :language="selectedLanguage"
            :current-revision="codeRevision"
          />

          <!-- Pre-submission Review -->
          <SubmissionReviewPanel
            :session-id="sessionId"
            :problem-text="problemText"
            :current-code="currentCode"
            :language="selectedLanguage"
            :current-revision="codeRevision"
            :disabled="isAnalyzing || isAutoAnalyzing"
          />

          <!-- Manual AI Analysis -->
          <button
            type="button"
            class="analyze-button"
            :disabled="isAnalyzing || isAutoAnalyzing"
            @click="runAnalysis"
          >
            {{
              isAnalyzing
                ? '분석 중...'
                : '수동 AI 분석 실행'
            }}
          </button>

          <section
            v-if="analysisResult"
            class="feedback-card"
          >
            <h3>수동 분석 결과</h3>

            <dl>
              <dt>Revision</dt>
              <dd>
                {{ analysisResult.analyzed_revision }}
              </dd>

              <dt>진행 상태</dt>
              <dd>{{ analysisResult.progress_status }}</dd>

              <dt>알고리즘</dt>
              <dd>
                {{ analysisResult.algorithm ?? '미판단' }}
              </dd>

              <dt>복잡도</dt>
              <dd>
                {{
                  analysisResult.complexity_estimate
                    ?? '미판단'
                }}
              </dd>
            </dl>

            <p>{{ analysisResult.summary }}</p>

            <p
              v-if="analysisResult.positive_observation"
              class="positive-observation"
            >
              {{ analysisResult.positive_observation }}
            </p>

            <div
              v-if="analysisResult.issues.length > 0"
              class="issue-list"
            >
              <h3>검토할 문제</h3>

              <ul>
                <li
                  v-for="(issue, index) in analysisResult.issues"
                  :key="index"
                >
                  <strong>{{ issue.severity }}</strong>
                  · {{ issue.description }}

                  <p>{{ issue.evidence }}</p>
                </li>
              </ul>
            </div>
          </section>

          <p
            v-if="errorMessage"
            class="error-message"
            role="alert"
          >
            {{ errorMessage }}
          </p>

          <p
            v-if="!analysisResult && !errorMessage"
            class="empty-state"
          >
            수동 분석 결과가 이곳에 표시됩니다.
          </p>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
/* --------------------------------------------------
   Workspace Layout
-------------------------------------------------- */

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
  gap: 16px;
  padding: 16px;
}

.provider-label {
  padding: 4px 8px;
  border-radius: 6px;
  background: #e2e8f0;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
}

/* --------------------------------------------------
   Existing AI Coach Controls
-------------------------------------------------- */

.observation-card,
.feedback-card,
.control-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.observation-card h3,
.feedback-card h3,
.control-card h3 {
  margin: 0 0 12px;
  font-size: 14px;
}

.observation-card p,
.feedback-card p,
.control-card p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
}

.control-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.control-heading h3 {
  margin-bottom: 0;
}

.switch-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.switch-label input {
  width: 16px;
  height: 16px;
  accent-color: #2563eb;
  cursor: pointer;
}

.control-description {
  margin-top: 12px !important;
  color: #64748b;
}

.usage-count {
  margin-top: 12px !important;
  color: #334155;
}

.limit-message {
  margin-top: 10px !important;
  color: #b45309;
  font-weight: 600;
}

.snapshot-info {
  margin-top: 10px !important;
  color: #2563eb;
  font-weight: 600;
}

.observation-description {
  margin-top: 12px !important;
  color: #64748b;
}

.trigger-decision {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.trigger-reason {
  margin-top: 6px !important;
  color: #64748b;
}

.analyze-button {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: white;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.analyze-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.feedback-card dl {
  display: grid;
  grid-template-columns: 85px 1fr;
  gap: 8px;
  margin: 0 0 16px;
  font-size: 12px;
}

.feedback-card dt {
  color: #64748b;
}

.feedback-card dd {
  margin: 0;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.feedback-card ul {
  padding-left: 20px;
  font-size: 13px;
}

.feedback-card li + li {
  margin-top: 12px;
}

.feedback-card li p {
  margin-top: 4px;
  color: #475569;
}

.positive-observation {
  margin-top: 12px !important;
  color: #166534;
}

.issue-list {
  margin-top: 16px;
}

.error-message {
  color: #dc2626;
  font-size: 13px;
  line-height: 1.6;
}

.empty-state {
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

/* --------------------------------------------------
   Completed Session
-------------------------------------------------- */

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

.return-button:hover {
  background: #1d4ed8;
}

/* --------------------------------------------------
   Responsive
-------------------------------------------------- */

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