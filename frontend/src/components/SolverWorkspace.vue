
<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'

import CodeEditor from '@/components/CodeEditor.vue'
import { analyzeCode } from '@/services/analysis'
import {
  evaluateAnalysisTrigger,
  type CodeSnapshot,
  type TriggerDecision,
  type TriggerSuggestion,
} from '@/services/analysis-trigger'
import type { AnalysisResult } from '@/types/analysis'
import type { ProgrammingLanguage } from '@/types/programming-language'

const props = defineProps<{
  problemText: string
}>()

const emit = defineEmits<{
  back: []
}>()

// --------------------------------------------------
// Code editor state
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
// Manual analysis state
// --------------------------------------------------

const isAnalyzing = ref(false)
const analysisResult = ref<AnalysisResult | null>(null)
const errorMessage = ref('')

// --------------------------------------------------
// Automatic analysis state
// --------------------------------------------------

const isAutoAnalyzing = ref(false)
const autoAnalysisResult = ref<AnalysisResult | null>(null)
const autoAnalysisError = ref('')

let autoAbortController: AbortController | null = null

// --------------------------------------------------
// Code observation state
// --------------------------------------------------

type ObservationPhase = 'waiting' | 'editing' | 'settled'

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
// Code and language change observation
// --------------------------------------------------

watch([selectedLanguage, currentCode], () => {
  // 1. Update the revision immediately.
  codeRevision.value += 1

  // Invalidate the previous manual analysis result.
  analysisResult.value = null
  errorMessage.value = ''

  // 2. Cancel and invalidate previous automatic analysis.
  autoAbortController?.abort()
  autoAbortController = null

  isAutoAnalyzing.value = false
  autoAnalysisResult.value = null
  autoAnalysisError.value = ''

  // 3. Reset the observation state.
  stableSnapshot.value = null
  triggerDecision.value = null
  observationPhase.value = 'editing'

  // 4. Cancel the previous debounce timer.
  if (observationTimer !== null) {
    clearTimeout(observationTimer)
    observationTimer = null
  }

  // 5. Capture the current editor state.
  const snapshot: CodeSnapshot = {
    language: selectedLanguage.value,
    code: currentCode.value,
    revision: codeRevision.value,
  }

  // 6. Wait until editing settles.
  observationTimer = setTimeout(() => {
    observationTimer = null

    // Discard an outdated snapshot.
    if (
      snapshot.revision !== codeRevision.value ||
      snapshot.language !== selectedLanguage.value ||
      snapshot.code !== currentCode.value
    ) {
      return
    }

    // 7. Evaluate the analysis trigger policy.
    const nowMs = Date.now()

    const decision = evaluateAnalysisTrigger(
      snapshot,
      lastSuggestion.value,
      nowMs,
    )

    stableSnapshot.value = snapshot
    triggerDecision.value = decision
    observationPhase.value = 'settled'

    // 8. Record eligible analysis candidates.
    if (decision.eligible) {
      lastSuggestion.value = {
        snapshot,
        suggestedAtMs: nowMs,
      }

      // Automatic analysis is skipped while manual analysis is running.
      if (!isAnalyzing.value) {
        void runAutomaticAnalysis(snapshot)
      }
    }
  }, OBSERVATION_DELAY_MS)
})

// --------------------------------------------------
// Manual analysis
// --------------------------------------------------

async function runAnalysis() {
  // Prevent overlapping manual and automatic requests.
  if (isAnalyzing.value || isAutoAnalyzing.value) {
    return
  }

  // Capture the editor state at request time.
  const revision = codeRevision.value
  const codeSnapshot = currentCode.value
  const languageSnapshot = selectedLanguage.value

  isAnalyzing.value = true
  analysisResult.value = null
  errorMessage.value = ''

  try {
    const result = await analyzeCode({
      session_id: 'vue-dev-session',
      code_revision: revision,
      problem_text: props.problemText,
      current_code: codeSnapshot,
      language: languageSnapshot,
    })

    // Ignore results if the editor state changed.
    if (
      revision !== codeRevision.value ||
      codeSnapshot !== currentCode.value ||
      languageSnapshot !== selectedLanguage.value
    ) {
      errorMessage.value =
        '분석 중 코드 또는 언어가 변경되었습니다. 다시 분석해 주세요.'
      return
    }

    // Verify the response revision.
    if (result.analyzed_revision !== revision) {
      throw new Error('분석 결과의 코드 Revision이 일치하지 않습니다.')
    }

    analysisResult.value = result
  } catch (error) {
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

async function runAutomaticAnalysis(snapshot: CodeSnapshot) {
  // Give priority to a running manual analysis.
  if (isAnalyzing.value) {
    return
  }

  // Cancel any previous automatic request.
  autoAbortController?.abort()

  const controller = new AbortController()
  autoAbortController = controller

  isAutoAnalyzing.value = true
  autoAnalysisResult.value = null
  autoAnalysisError.value = ''

  try {
    const result = await analyzeCode(
      {
        session_id: 'vue-dev-session',
        code_revision: snapshot.revision,
        problem_text: props.problemText,
        current_code: snapshot.code,
        language: snapshot.language,
      },
      controller.signal,
    )

    // Ignore cancelled or superseded requests.
    if (
      controller.signal.aborted ||
      autoAbortController !== controller
    ) {
      return
    }

    // Accept only results belonging to the current editor state.
    if (
      snapshot.revision !== codeRevision.value ||
      snapshot.language !== selectedLanguage.value ||
      snapshot.code !== currentCode.value
    ) {
      return
    }

    // Ensure the backend analyzed the requested revision.
    if (result.analyzed_revision !== snapshot.revision) {
      throw new Error('자동 분석 결과의 Revision이 일치하지 않습니다.')
    }

    // Store the result internally.
    // Do not publish proactive coaching messages yet.
    autoAnalysisResult.value = result
  } catch (error) {
    // Cancellation is expected when the user edits the code.
    if (
      controller.signal.aborted ||
      autoAbortController !== controller
    ) {
      return
    }

    autoAnalysisError.value =
      error instanceof Error
        ? error.message
        : '자동 분석 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    // Only the current request may update the loading state.
    if (autoAbortController === controller) {
      autoAbortController = null
      isAutoAnalyzing.value = false
    }
  }
}

// --------------------------------------------------
// Component cleanup
// --------------------------------------------------

onBeforeUnmount(() => {
  // Stop observation.
  if (observationTimer !== null) {
    clearTimeout(observationTimer)
    observationTimer = null
  }

  // Cancel an in-flight automatic request.
  autoAbortController?.abort()
  autoAbortController = null
})

// --------------------------------------------------
// Navigation
// --------------------------------------------------

function returnToProblemInput() {
  emit('back')
}
</script>

<template>
  <div class="workspace">
    <!-- Workspace Header -->
    <header class="workspace-header">
      <div class="brand">
        <h1>AlgoCoach</h1>
        <span>코딩테스트 풀이 환경</span>
      </div>

      <button
        type="button"
        class="back-button"
        @click="returnToProblemInput"
      >
        ← 문제 입력으로
      </button>
    </header>

    <div class="workspace-grid">
      <!-- Problem Panel -->
      <section class="panel problem-panel">
        <div class="panel-header">
          <h2>문제</h2>
        </div>

        <div class="problem-content">
          {{ problemText }}
        </div>
      </section>

      <!-- Code Editor Panel -->
      <section class="panel editor-panel">
        <div class="panel-header">
          <h2>코드 에디터</h2>

          <div class="editor-controls">
            <label for="language-select" class="sr-only">
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
            <span>Monaco Editor · 4 Spaces · Mock Analysis</span>
          </div>
        </div>
      </section>

      <!-- AI Coach Panel -->
      <aside class="panel coach-panel">
        <div class="panel-header">
          <h2>AI Coach</h2>
          <span class="mock-label">MOCK</span>
        </div>

        <div class="coach-content">
          <!-- Code Observation -->
          <div class="observation-card">
            <h3>코드 관찰 상태</h3>

            <p>
              현재 상태:
              <strong>{{ observationStatusText }}</strong>
            </p>

            <p v-if="stableSnapshot" class="snapshot-info">
              안정된 스냅샷:
              Revision {{ stableSnapshot.revision }}
              · {{ stableSnapshot.language }}
            </p>

            <div v-if="triggerDecision" class="trigger-decision">
              <p>
                분석 후보:
                <strong>
                  {{ triggerDecision.eligible ? '추천' : '보류' }}
                </strong>
              </p>

              <p class="trigger-reason">
                {{ triggerDecision.message }}
              </p>
            </div>

            <p class="observation-description">
              코드 입력이 안정되면 분석 트리거 정책을 평가합니다.
              조건을 통과하면 LangGraph 자동 분석을 실행합니다.
            </p>
          </div>

          <!-- Automatic Analysis Status -->
          <div class="observation-card">
            <h3>내부 자동 분석</h3>

            <p v-if="isAutoAnalyzing" role="status">
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

            <p v-else>
              아직 자동 분석 결과가 없습니다.
            </p>

            <p class="observation-description">
              자동 분석 결과는 내부 상태에 저장되며,
              사용자에게 코칭 메시지로 공개하지 않습니다.
            </p>
          </div>

          <!-- Manual Analysis Button -->
          <button
            type="button"
            class="analyze-button"
            :disabled="isAnalyzing || isAutoAnalyzing"
            @click="runAnalysis"
          >
            {{ isAnalyzing ? '분석 중...' : 'Mock 분석 실행' }}
          </button>

          <!-- Manual Analysis Result -->
          <div v-if="analysisResult" class="feedback-card">
            <h3>수동 분석 결과</h3>

            <dl>
              <dt>Revision</dt>
              <dd>{{ analysisResult.analyzed_revision }}</dd>

              <dt>진행 상태</dt>
              <dd>{{ analysisResult.progress_status }}</dd>

              <dt>알고리즘</dt>
              <dd>{{ analysisResult.algorithm ?? '미판단' }}</dd>
            </dl>

            <p>{{ analysisResult.summary }}</p>

            <p v-if="analysisResult.positive_observation">
              {{ analysisResult.positive_observation }}
            </p>

            <div v-if="analysisResult.issues.length > 0">
              <h3>발견된 문제</h3>

              <ul>
                <li
                  v-for="(issue, index) in analysisResult.issues"
                  :key="index"
                >
                  {{ issue.description }}
                </li>
              </ul>
            </div>
          </div>

          <!-- Manual Analysis Error -->
          <p
            v-if="errorMessage"
            class="error-message"
            role="alert"
          >
            {{ errorMessage }}
          </p>

          <!-- Empty Manual Analysis State -->
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
   Workspace
-------------------------------------------------- */

.workspace {
  min-height: 100vh;
  padding: 20px;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
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

.back-button {
  padding: 10px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: white;
  color: #334155;
  font: inherit;
  cursor: pointer;
}

/* --------------------------------------------------
   Workspace Grid
-------------------------------------------------- */

.workspace-grid {
  display: grid;
  grid-template-columns:
    minmax(240px, 1fr)
    minmax(400px, 1.8fr)
    minmax(270px, 1fr);
  align-items: stretch;
  gap: 16px;
}

/* --------------------------------------------------
   Common Panels
-------------------------------------------------- */

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

/* --------------------------------------------------
   Problem Panel
-------------------------------------------------- */

.problem-content {
  padding: 20px;
  font-size: 14px;
  line-height: 1.8;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

/* --------------------------------------------------
   Code Editor Panel
-------------------------------------------------- */

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

/* --------------------------------------------------
   AI Coach Panel
-------------------------------------------------- */

.coach-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.mock-label {
  padding: 4px 8px;
  border-radius: 6px;
  background: #e2e8f0;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
}

/* --------------------------------------------------
   Observation & Feedback Cards
-------------------------------------------------- */

.observation-card,
.feedback-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.observation-card h3,
.feedback-card h3 {
  margin: 0 0 12px;
  font-size: 14px;
}

.observation-card p,
.feedback-card p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
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

/* --------------------------------------------------
   Manual Analysis Button
-------------------------------------------------- */

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

/* --------------------------------------------------
   Analysis Result
-------------------------------------------------- */

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

/* --------------------------------------------------
   Accessibility
-------------------------------------------------- */

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

/* --------------------------------------------------
   Responsive Layout
-------------------------------------------------- */

@media (max-width: 1050px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .panel {
    min-height: auto;
  }
}
</style>
