<script setup lang="ts">
import { ref, watch } from 'vue'

import { analyzeCode } from '@/services/analysis'
import type { AnalysisResult } from '@/types/analysis'

const problemText = ref('그래프의 최단 경로를 구하세요.')
const currentCode = ref('import heapq\n')

const codeRevision = ref(0)
const isAnalyzing = ref(false)

const analysisResult = ref<AnalysisResult | null>(null)
const errorMessage = ref('')

// 코드가 변경되면 Revision을 증가시키고 이전 결과를 초기화합니다.
watch(currentCode, () => {
  codeRevision.value += 1
  analysisResult.value = null
  errorMessage.value = ''
})

watch(problemText, () => {
  analysisResult.value = null
  errorMessage.value = ''
})

async function runAnalysis() {
  if (isAnalyzing.value || !problemText.value.trim()) {
    return
  }

  const revision = codeRevision.value
  const problemSnapshot = problemText.value
  const codeSnapshot = currentCode.value

  isAnalyzing.value = true
  analysisResult.value = null
  errorMessage.value = ''

  try {
    const result = await analyzeCode({
      session_id: 'vue-dev-session',
      code_revision: revision,
      problem_text: problemSnapshot,
      current_code: codeSnapshot,
    })

    // 분석 중 입력 내용이 변경되었다면 이전 결과를 표시하지 않습니다.
    if (
      revision !== codeRevision.value ||
      problemSnapshot !== problemText.value
    ) {
      errorMessage.value = '분석 중 입력이 변경되었습니다. 다시 분석해 주세요.'
      return
    }

    analysisResult.value = result
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.'
  } finally {
    isAnalyzing.value = false
  }
}
</script>

<template>
  <main class="container">
    <header>
      <h1>AlgoCoach</h1>
      <p>LangGraph Mock Analysis Test</p>
    </header>

    <form class="editor-form" @submit.prevent="runAnalysis">
      <label for="problem">문제 설명</label>

      <textarea
        id="problem"
        v-model="problemText"
        rows="4"
        placeholder="코딩테스트 문제를 입력하세요."
      />

      <div class="label-row">
        <label for="code">Python 코드</label>
        <span>Revision {{ codeRevision }}</span>
      </div>

      <textarea
        id="code"
        v-model="currentCode"
        rows="10"
        spellcheck="false"
        class="code-editor"
        placeholder="Python 코드를 작성하세요."
      />

      <button
        type="submit"
        :disabled="isAnalyzing || !problemText.trim()"
      >
        {{ isAnalyzing ? '분석 중...' : 'Mock 분석 실행' }}
      </button>
    </form>

    <section v-if="analysisResult" class="result">
      <h2>분석 결과</h2>

      <dl>
        <dt>분석 Revision</dt>
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

      <p v-if="analysisResult.issues.length">
        발견된 문제: {{ analysisResult.issues.length }}개
      </p>
    </section>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>
  </main>
</template>

<style scoped>
.container {
  max-width: 960px;
  margin: 48px auto;
  padding: 24px;
  font-family: system-ui, sans-serif;
}

header {
  margin-bottom: 32px;
}

header h1 {
  margin-bottom: 8px;
}

header p {
  color: #64748b;
}

.editor-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

label {
  font-weight: 600;
}

.label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.label-row span {
  font-size: 13px;
  color: #64748b;
}

textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  resize: vertical;
}

.code-editor {
  font-family: ui-monospace, monospace;
  line-height: 1.6;
}

button {
  align-self: flex-start;
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: white;
  cursor: pointer;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.result {
  margin-top: 32px;
  padding: 24px;
  border: 1px solid #bbf7d0;
  border-radius: 12px;
  background: #f0fdf4;
  color: #14532d;
}

.result h2 {
  margin-top: 0;
}

.result dl {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 8px;
}

.result dt {
  font-weight: 600;
}

.result dd {
  margin: 0;
}

.error {
  margin-top: 24px;
  color: #dc2626;
}
</style>