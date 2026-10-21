<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  ref,
  watch,
} from 'vue'

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
// Required AI problem structuring
// --------------------------------------------------

const structuredProblem = ref<StructuredProblem | null>(null)

// Remember exactly which source text was analyzed.
// A result must never be used for a different problem text.
const structuredSourceText = ref<string | null>(null)

const isStructuring = ref(false)
const structureError = ref('')

let structureAbortController: AbortController | null = null

const canAnalyzeProblem = computed(() => {
  return (
    problemText.value.trim().length > 0 &&
    !isStructuring.value
  )
})

const canStartSolving = computed(() => {
  return (
    structuredProblem.value !== null &&
    structuredSourceText.value !== null &&
    structuredSourceText.value === problemText.value &&
    problemText.value.trim().length > 0 &&
    !isStructuring.value
  )
})

// --------------------------------------------------
// Invalidate stale results whenever the source changes
// --------------------------------------------------

watch(problemText, () => {
  structureAbortController?.abort()
  structureAbortController = null

  isStructuring.value = false

  structuredProblem.value = null
  structuredSourceText.value = null
  structureError.value = ''
})

// --------------------------------------------------
// Step 1: Analyze the input problem
// --------------------------------------------------

async function runProblemStructuring() {
  if (!canAnalyzeProblem.value) {
    return
  }

  const textSnapshot = problemText.value
  const controller = new AbortController()

  structureAbortController = controller

  isStructuring.value = true
  structuredProblem.value = null
  structuredSourceText.value = null
  structureError.value = ''

  try {
    const result = await structureProblem(
      {
        problem_text: textSnapshot,
      },
      controller.signal,
    )

    // Ignore results that belong to cancelled or outdated requests.
    if (
      controller.signal.aborted ||
      structureAbortController !== controller ||
      textSnapshot !== problemText.value
    ) {
      return
    }

    // Do not expose the solver before a valid AI result exists.
    if (
      !result ||
      typeof result.goal !== 'string' ||
      !result.goal.trim() ||
      !Array.isArray(result.constraints) ||
      !Array.isArray(result.examples) ||
      !Array.isArray(result.ambiguities)
    ) {
      throw new Error(
        'AI 문제 정리 결과가 올바르지 않습니다. 다시 시도해 주세요.',
      )
    }

    structuredProblem.value = result
    structuredSourceText.value = textSnapshot

    // The input form is replaced by the review screen.
    // Start the review screen at the top.
    await nextTick()

    window.scrollTo(0, 0)
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
        : '문제 정리 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    if (structureAbortController === controller) {
      structureAbortController = null
      isStructuring.value = false
    }
  }
}

// --------------------------------------------------
// Step 2: Return to editing if the review needs changes
// --------------------------------------------------

function editProblem() {
  if (isStructuring.value) {
    return
  }

  structuredProblem.value = null
  structuredSourceText.value = null
  structureError.value = ''

  // Preserve the original text so the user can edit it.
  void nextTick(() => {
    window.scrollTo(0, 0)
  })
}

// --------------------------------------------------
// Step 3: Enter the solver only after structuring
// --------------------------------------------------

function startSolving() {
  if (
    !canStartSolving.value ||
    structuredSourceText.value === null
  ) {
    return
  }

  // Always send the original problem statement to the solver
  // and downstream code-analysis APIs.
  activeProblem.value = structuredSourceText.value

  void nextTick(() => {
    window.scrollTo(0, 0)
  })
}

// --------------------------------------------------
// Return from the solver
// --------------------------------------------------

function returnToHome() {
  activeProblem.value = null

  // Keep the reviewed problem available.
  // The user can resume or return to the input form.
  void nextTick(() => {
    window.scrollTo(0, 0)
  })
}

// --------------------------------------------------
// Cleanup
// --------------------------------------------------

onBeforeUnmount(() => {
  structureAbortController?.abort()
  structureAbortController = null
})
</script>

<template>
  <main class="app-shell">
    <section
      v-if="activeProblem === null"
      class="home"
    >
      <header class="home-header">
        <span class="eyebrow">AI CODING COACH</span>

        <h1>AlgoCoach</h1>

        <p v-if="structuredProblem">
          AI가 정리한 문제를 확인했습니다.
          내용을 검토한 뒤 풀이를 시작하세요.
        </p>

        <p v-else>
          코딩테스트 문제를 입력하세요.
          AI가 먼저 문제를 정리한 다음
          코딩 풀이를 시작할 수 있습니다.
        </p>
      </header>

      <!-- ----------------------------------------
           STEP 1: Problem input
      ----------------------------------------- -->

      <form
        v-if="structuredProblem === null"
        class="problem-form"
        @submit.prevent="runProblemStructuring"
      >
        <div class="step-heading">
          <span class="step-number">01</span>

          <div>
            <h2>문제 입력</h2>

            <p>
              문제 원문을 입력하면
              AI가 풀이에 필요한 조건을 정리합니다.
            </p>
          </div>
        </div>

        <label for="problem-input">
          문제 원문
        </label>

        <textarea
          id="problem-input"
          v-model="problemText"
          rows="12"
          maxlength="20000"
          placeholder="문제 설명, 입력 조건, 출력 조건, 예제를 붙여넣으세요."
        />

        <div class="form-footer">
          <span>
            지원 언어: Python · Java · C++ · C
          </span>

          <span>
            {{ problemText.length.toLocaleString() }}
            / 20,000자
          </span>
        </div>

        <div class="form-actions">
          <button
            type="submit"
            class="start-button"
            :disabled="!canAnalyzeProblem"
          >
            {{
              isStructuring
                ? 'AI가 문제를 분석하고 있습니다...'
                : structureError
                  ? '문제 분석 다시 시도 →'
                  : '문제 분석하기 →'
            }}
          </button>
        </div>

        <p class="form-hint">
          AI 문제 정리는 필수 단계입니다.
          분석 결과를 확인한 다음 풀이를 시작할 수 있습니다.
        </p>

        <div
          v-if="isStructuring"
          class="processing-panel"
          role="status"
          aria-live="polite"
        >
          <span
            class="loading-indicator"
            aria-hidden="true"
          />

          <div>
            <strong>문제를 분석하고 있습니다.</strong>

            <p>
              문제의 목표, 입력과 출력,
              제한 조건 및 예제를 정리하고 있습니다.
            </p>
          </div>
        </div>

        <div
          v-if="structureError"
          class="error-panel"
          role="alert"
        >
          <strong>문제 분석에 실패했습니다.</strong>

          <p>{{ structureError }}</p>

          <p>
            입력한 문제는 그대로 유지됩니다.
            다시 분석하면 결과를 확인할 수 있습니다.
          </p>
        </div>
      </form>

      <!-- ----------------------------------------
           STEP 2: AI result review
      ----------------------------------------- -->

      <section
        v-else
        class="result-section"
      >
        <div class="step-heading result-heading">
          <span class="step-number">02</span>

          <div>
            <h2>AI 문제 정리 결과</h2>

            <p>
              AI가 정리한 내용을 확인한 뒤
              풀이를 시작하세요.
            </p>
          </div>
        </div>

        <StructuredProblemPreview
          :problem="structuredProblem"
        />

        <details class="source-details">
          <summary>
            문제 원문 확인하기
          </summary>

          <pre>{{ problemText }}</pre>
        </details>

        <p class="review-hint">
          AI 정리 과정에서 중요한 조건이 누락될 수 있습니다.
          필요한 경우 원문을 확인하세요.
          풀이 화면에서도 원문과 AI 정리 보기를
          전환할 수 있습니다.
        </p>

        <div class="review-actions">
          <button
            type="button"
            class="edit-button"
            @click="editProblem"
          >
            ← 문제 수정하기
          </button>

          <button
            type="button"
            class="start-button"
            :disabled="!canStartSolving"
            @click="startSolving"
          >
            풀이 시작하기 →
          </button>
        </div>
      </section>
    </section>

    <!-- ----------------------------------------
         STEP 3: Solver
    ----------------------------------------- -->

    <SolverWorkspace
      v-else
      :problem-text="activeProblem"
      :structured-problem="structuredProblem"
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

.home {
  width: min(100% - 40px, 850px);
  margin: 0 auto;
  padding: 64px 0 60px;
}

.home-header {
  margin-bottom: 32px;
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

.problem-form,
.result-section {
  padding: 28px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: white;
}

.problem-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-heading {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 12px;
}

.step-heading h2 {
  margin: 0 0 7px;
  color: #0f172a;
  font-size: 20px;
}

.step-heading p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.step-number {
  display: flex;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 14px;
  font-weight: 800;
}

.problem-form label {
  font-size: 14px;
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

.form-footer {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

.form-actions,
.review-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
}

button {
  min-height: 46px;
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.start-button {
  background: #2563eb;
  color: white;
}

.start-button:not(:disabled):hover {
  background: #1d4ed8;
}

.edit-button {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
}

.edit-button:not(:disabled):hover {
  background: #f1f5f9;
}

.form-hint,
.review-hint {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.8;
}

.processing-panel,
.error-panel {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-radius: 10px;
}

.processing-panel {
  border: 1px solid #bfdbfe;
  background: #eff6ff;
}

.processing-panel strong {
  color: #1d4ed8;
  font-size: 13px;
}

.processing-panel p {
  margin: 6px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.7;
}

.loading-indicator {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  margin-top: 2px;
  border: 2px solid #93c5fd;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-panel {
  display: block;
  border: 1px solid #fecaca;
  background: #fef2f2;
}

.error-panel strong {
  color: #b91c1c;
  font-size: 13px;
}

.error-panel p {
  margin: 7px 0 0;
  color: #991b1b;
  font-size: 12px;
  line-height: 1.7;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.result-heading {
  margin-bottom: 0;
}

.source-details {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.source-details summary {
  color: #475569;
  font-size: 13px;
  font-weight: 700;
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

.review-actions {
  padding-top: 6px;
  border-top: 1px solid #e2e8f0;
}

@media (max-width: 600px) {
  .home {
    padding-top: 40px;
  }

  .home-header h1 {
    font-size: 34px;
  }

  .problem-form,
  .result-section {
    padding: 18px;
  }

  .form-actions,
  .review-actions {
    flex-direction: column;
  }

  .form-actions button,
  .review-actions button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .loading-indicator {
    animation: none;
  }
}
</style>