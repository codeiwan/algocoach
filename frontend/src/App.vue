<script setup lang="ts">
import { ref } from 'vue'

import SolverWorkspace from '@/components/SolverWorkspace.vue'

const problemText = ref('')
const activeProblem = ref<string | null>(null)

function startSolving() {
  if (!problemText.value.trim()) {
    return
  }

  activeProblem.value = problemText.value
}

function returnToHome() {
  activeProblem.value = null
}
</script>

<template>
  <main class="app-shell">
    <section v-if="activeProblem === null" class="home">
      <header class="home-header">
        <span class="eyebrow">AI CODING COACH</span>
        <h1>AlgoCoach</h1>
        <p>
          코딩테스트 문제를 입력하고 풀이를 시작하세요.
          AI가 풀이 과정을 관찰하고 필요한 순간에 도움을 제공합니다.
        </p>
      </header>

      <form class="problem-form" @submit.prevent="startSolving">
        <label for="problem-input">문제 입력</label>

        <textarea
          id="problem-input"
          v-model="problemText"
          rows="14"
          placeholder="문제 설명, 입력 조건, 출력 조건, 예제를 붙여넣으세요."
        />

        <div class="form-footer">
          <span>지원 언어: Python · Java · C++ · C</span>

          <button type="submit" :disabled="!problemText.trim()">
            풀이 시작 →
          </button>
        </div>
      </form>

      <p class="notice">
        현재 개발 단계에서는 입력한 문제를 그대로 표시합니다.
        AI 문제 구조화 기능은 추후 연결됩니다.
      </p>
    </section>

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

.home {
  width: min(100% - 40px, 850px);
  margin: 0 auto;
  padding: 90px 0 60px;
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

h1 {
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

.problem-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 28px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: white;
}

label {
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
  line-height: 1.7;
  resize: vertical;
}

textarea:focus {
  border-color: #2563eb;
  outline: 2px solid #bfdbfe;
}

.form-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.form-footer span,
.notice {
  color: #64748b;
  font-size: 13px;
}

button {
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: white;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.notice {
  margin-top: 20px;
  text-align: center;
}

@media (max-width: 600px) {
  .home {
    padding-top: 48px;
  }

  .problem-form {
    padding: 18px;
  }

  .form-footer {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>