<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import SolverWorkspace from '@/components/SolverWorkspace.vue'
import StructuredProblemPreview from '@/components/StructuredProblemPreview.vue'

import { structureProblem } from '@/services/problem'
import type { StructuredProblem } from '@/types/problem'

// --------------------------------------------------
// Problem input and navigation
// --------------------------------------------------

const problemText = ref('')
const activeProblem = ref<string | null>(null)

// --------------------------------------------------
// AI problem structuring
// --------------------------------------------------

const structuredProblem = ref<StructuredProblem | null>(null)

const isStructuring = ref(false)
const structureError = ref('')

let structureAbortController: AbortController | null = null

/**
 * Invalidate an existing structure whenever the
 * original problem text changes.
 */
watch(problemText, () => {
  structureAbortController?.abort()
  structureAbortController = null

  isStructuring.value = false
  structuredProblem.value = null
  structureError.value = ''
})

/**
 * Call the backend to extract the structured problem.
 */
async function runProblemStructuring() {
  if (!problemText.value.trim() || isStructuring.value) {
    return
  }

  const textSnapshot = problemText.value

  const controller = new AbortController()
  structureAbortController = controller

  isStructuring.value = true
  structuredProblem.value = null
  structureError.value = ''

  try {
    const result = await structureProblem(
      {
        problem_text: textSnapshot,
      },
      controller.signal,
    )

    // Ignore a cancelled or superseded request.
    if (
      controller.signal.aborted ||
      structureAbortController !== controller
    ) {
      return
    }

    // Do not display results for an outdated problem.
    if (textSnapshot !== problemText.value) {
      return
    }

    structuredProblem.value = result
  } catch (error) {
    if (
      controller.signal.aborted ||
      structureAbortController !== controller
    ) {
      return
    }

    structureError.value =
      error instanceof Error
        ? error.message
        : '문제 구조화 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    if (structureAbortController === controller) {
      structureAbortController = null
      isStructuring.value = false
    }
  }
}

/**
 * Start the existing solver workspace with the original
 * problem text, regardless of whether AI structuring ran.
 */
function startSolving() {
  if (!problemText.value.trim() || isStructuring.value) {
    return
  }

  activeProblem.value = problemText.value
}

function returnToHome() {
  activeProblem.value = null
}

onBeforeUnmount(() => {
  structureAbortController?.abort()
  structureAbortController = null
})
</script>

<template>
  <main class="app-shell">
    <section v-if="activeProblem === null" class="home">
      <!-- Home Header -->
      <header class="home-header">
        <span class="eyebrow">AI CODING COACH</span>

        <h1>AlgoCoach</h1>

        <p>
          코딩테스트 문제를 입력하고 풀이를 시작하세요.
          AI가 문제를 구조화하고 풀이 과정을 관찰합니다.
        </p>
      </header>

      <!-- Problem Input -->
      <form
        class="problem-form"
        @submit.prevent="startSolving"
      >
        <label for="problem-input">
          문제 입력
        </label>

        <textarea
          id="problem-input"
          v-model="problemText"
          rows="12"
          maxlength="20000"
          placeholder="문제 설명, 입력 조건, 출력 조건, 예제를 붙여넣으세요."
        />

        <div class="form-footer">
          <span>지원 언어: Python · Java · C++ · C</span>

          <span>{{ problemText.length.toLocaleString() }} / 20,000자</span>
        </div>

        <!-- Actions -->
        <div class="form-actions">
          <button
            type="button"
            class="structure-button"
            :disabled="!problemText.trim() || isStructuring"
            @click="runProblemStructuring"
          >
            {{
              isStructuring
                ? 'AI가 문제 정리 중...'
                : 'AI로 문제 정리'
            }}
          </button>

          <button
            type="submit"
            class="start-button"
            :disabled="!problemText.trim() || isStructuring"
          >
            풀이 시작 →
          </button>
        </div>

        <p class="form-hint">
          문제 정리는 선택 사항입니다.
          AI 분석을 사용하지 않아도 원문으로 풀이를 시작할 수 있습니다.
        </p>

        <p
          v-if="isStructuring"
          class="processing-message"
          role="status"
        >
          문제 설명과 입출력 조건, 제약 및 예제를 분석하고 있습니다.
        </p>

        <p
          v-if="structureError"
          class="error-message"
          role="alert"
        >
          {{ structureError }}
          원문으로 풀이를 시작하는 것은 가능합니다.
        </p>
      </form>

      <!-- Structured Problem Preview -->
      <section
        v-if="structuredProblem"
        class="result-section"
      >
        <div class="result-header">
          <div>
            <h2>AI 문제 정리 결과</h2>
            <p>정리된 내용을 검토한 뒤 풀이를 시작하세요.</p>
          </div>
        </div>

        <StructuredProblemPreview
          :problem="structuredProblem"
        />

        <!-- Preserve the original source -->
        <details class="source-details">
          <summary>문제 원문 확인하기</summary>

          <pre>{{ problemText }}</pre>
        </details>
      </section>

      <p class="notice">
        다음 단계에서는 풀이 화면의 문제 패널에도
        구조화된 내용을 연결할 예정입니다.
      </p>
    </section>

    <!-- Existing Solver Workspace -->
    <SolverWorkspace
      v-else
      :problem-text="activeProblem"
      @back="returnToHome"
    />
  </main>
</template>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  display: block;
  min-width: 320px;
  min-height: 100vh;
  margin: 0;
  background: #f8fafc;
  color: #0f172a;
  font-family: system-ui, sans-serif;
}

:global(#app) {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
}

.app-shell {
  min-height: 100vh;
}

/* Home */

.home {
  width: min(100% - 40px, 850px);
  margin: 0 auto;
  padding: 80px 0 60px;
}

.home-header {
  margin-bottom: 36px;
  text-align: center;
}

.eyebrow {
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.home-header h1 {
  margin: 12px 0;
  font-size: 42px;
  letter-spacing: -0.04em;
}

.home-header p {
  max-width: 580px;
  margin: 0 auto;
  color: #64748b;
  line-height: 1.8;
}

/* Input Form */

.problem-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 28px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: white;
}

.problem-form label {
  font-weight: 700;
}

textarea {
  width: 100%;
  padding: 16px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: white;
  color: #0f172a;
  font: inherit;
  font-size: 14px;
  line-height: 1.7;
  resize: vertical;
}

textarea:focus {
  border-color: #2563eb;
  outline: 2px solid #bfdbfe;
}

/* Form Footer */

.form-footer {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

/* Actions */

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

button {
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.structure-button {
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #334155;
}

.structure-button:not(:disabled):hover {
  background: #e2e8f0;
}

.start-button {
  background: #2563eb;
  color: white;
}

.start-button:not(:disabled):hover {
  background: #1d4ed8;
}

/* Status Messages */

.form-hint,
.notice {
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

.form-hint {
  margin: 0;
}

.processing-message {
  margin: 0;
  color: #2563eb;
  font-size: 13px;
}

.error-message {
  margin: 0;
  color: #dc2626;
  font-size: 13px;
  line-height: 1.7;
}

.notice {
  margin-top: 20px;
  text-align: center;
}

/* Structured Result */

.result-section {
  margin-top: 32px;
}

.result-header {
  margin-bottom: 16px;
}

.result-header h2 {
  margin: 0 0 8px;
  font-size: 20px;
}

.result-header p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

/* Original Problem */

.source-details {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: white;
}

.source-details summary {
  color: #475569;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.source-details pre {
  margin: 16px 0 0;
  padding: 16px;
  border-radius: 8px;
  background: #f1f5f9;
  color: #334155;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

/* Responsive */

@media (max-width: 600px) {
  .home {
    padding-top: 48px;
  }

  .home-header h1 {
    font-size: 34px;
  }

  .problem-form {
    padding: 18px;
  }

  .form-actions {
    flex-direction: column;
  }

  .form-actions button {
    width: 100%;
  }
}
</style>