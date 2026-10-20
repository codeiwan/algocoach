<script setup lang="ts">
import { analyzeCode } from '@/services/analysis'
import type { AnalysisResult } from '@/types/analysis'

import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'

import CodeEditor from '@/components/CodeEditor.vue'
import type { ProgrammingLanguage } from '@/types/programming-language'

import {
  evaluateAnalysisTrigger,
  type CodeSnapshot,
  type TriggerDecision,
  type TriggerSuggestion,
} from '@/services/analysis-trigger'

const props = defineProps<{
  problemText: string
}>()

const emit = defineEmits<{
  back: []
}>()

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

const isAnalyzing = ref(false)
const analysisResult = ref<AnalysisResult | null>(null)
const errorMessage = ref('')

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

watch([selectedLanguage, currentCode], () => {
  // 1. Code or language changed.
  codeRevision.value += 1
  analysisResult.value = null
  errorMessage.value = ''

  stableSnapshot.value = null
  triggerDecision.value = null
  observationPhase.value = 'editing'

  // 2. Cancel the previous debounce timer.
  if (observationTimer !== null) {
    clearTimeout(observationTimer)
  }

  // 3. Capture the current state.
  const snapshot: CodeSnapshot = {
    language: selectedLanguage.value,
    code: currentCode.value,
    revision: codeRevision.value,
  }

  // 4. Wait for a stable editing state.
  observationTimer = setTimeout(() => {
    observationTimer = null

    if (
      snapshot.revision !== codeRevision.value ||
      snapshot.language !== selectedLanguage.value ||
      snapshot.code !== currentCode.value
    ) {
      return
    }

    // 5. Evaluate the analysis trigger policy.
    const nowMs = Date.now()

    const decision = evaluateAnalysisTrigger(
      snapshot,
      lastSuggestion.value,
      nowMs,
    )

    stableSnapshot.value = snapshot
    triggerDecision.value = decision
    observationPhase.value = 'settled'

    // 6. Record eligible candidates.
    if (decision.eligible) {
      lastSuggestion.value = {
        snapshot,
        suggestedAtMs: nowMs,
      }
    }
  }, OBSERVATION_DELAY_MS)
})

async function runAnalysis() {
  if (isAnalyzing.value) {
    return
  }

  // 분석 요청 시점의 상태를 고정합니다.
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

    // 응답을 기다리는 동안 코드나 언어가 변경되었는지 확인합니다.
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

onBeforeUnmount(() => {
  if (observationTimer !== null) {
    clearTimeout(observationTimer)
    observationTimer = null
  }
})

function returnToProblemInput() {
  emit('back')
}
</script>

<template>
  <div class="workspace">
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
              코드 변경 후 0.8초 동안 추가 입력이 없으면
              안정된 스냅샷을 생성합니다.
              AI 분석은 아직 수동으로 실행됩니다.
            </p>
          </div>

          <button
            type="button"
            class="analyze-button"
            :disabled="isAnalyzing"
            @click="runAnalysis"
          >
            {{ isAnalyzing ? '분석 중...' : 'Mock 분석 실행' }}
          </button>

          <div v-if="analysisResult" class="feedback-card">
            <h3>분석 결과</h3>

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

          <p v-if="errorMessage" class="error-message" role="alert">
            {{ errorMessage }}
          </p>

          <p v-if="!analysisResult && !errorMessage" class="empty-state">
            분석 결과가 이곳에 표시됩니다.
          </p>
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

.problem-content {
  padding: 20px;
  font-size: 14px;
  line-height: 1.8;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
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

@media (max-width: 1050px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .panel {
    min-height: auto;
  }

  .code-input {
    min-height: 350px;
  }
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
</style>
