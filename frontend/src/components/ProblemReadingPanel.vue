<script setup lang="ts">
import { ref } from 'vue'

import type { StructuredProblem } from '@/types/problem'

const props = defineProps<{
  originalText: string
  structuredProblem: StructuredProblem | null
}>()

type ProblemView = 'structured' | 'original'

const activeView = ref<ProblemView>(
  props.structuredProblem ? 'structured' : 'original',
)
</script>

<template>
  <div class="problem-reader">
    <div v-if="structuredProblem" class="view-controls">
      <button
        type="button"
        :class="{ active: activeView === 'structured' }"
        :aria-pressed="activeView === 'structured'"
        @click="activeView = 'structured'"
      >
        AI 정리
      </button>

      <button
        type="button"
        :class="{ active: activeView === 'original' }"
        :aria-pressed="activeView === 'original'"
        @click="activeView = 'original'"
      >
        원문
      </button>
    </div>

    <div
      v-if="activeView === 'structured' && structuredProblem"
      class="problem-content"
    >
      <h3 v-if="structuredProblem.title" class="problem-title">
        {{ structuredProblem.title }}
      </h3>

      <section class="problem-section">
        <h4>문제 설명</h4>
        <p>{{ structuredProblem.goal }}</p>
      </section>

      <section
        v-if="structuredProblem.input_format"
        class="problem-section"
      >
        <h4>입력</h4>
        <p>{{ structuredProblem.input_format }}</p>
      </section>

      <section
        v-if="structuredProblem.output_format"
        class="problem-section"
      >
        <h4>출력</h4>
        <p>{{ structuredProblem.output_format }}</p>
      </section>

      <section
        v-if="structuredProblem.constraints.length > 0"
        class="problem-section"
      >
        <h4>제약 조건</h4>

        <ul>
          <li
            v-for="(constraint, index) in structuredProblem.constraints"
            :key="index"
          >
            {{ constraint }}
          </li>
        </ul>
      </section>

      <section
        v-if="structuredProblem.examples.length > 0"
        class="problem-section"
      >
        <h4>예제</h4>

        <div
          v-for="(example, index) in structuredProblem.examples"
          :key="index"
          class="example-card"
        >
          <h5>예제 {{ index + 1 }}</h5>

          <span class="example-label">입력</span>
          <pre>{{ example.input }}</pre>

          <span class="example-label">출력</span>
          <pre>{{ example.output }}</pre>

          <p
            v-if="example.explanation"
            class="example-explanation"
          >
            {{ example.explanation }}
          </p>
        </div>
      </section>

      <section
        v-if="structuredProblem.ambiguities.length > 0"
        class="problem-section ambiguity-section"
      >
        <h4>확인이 필요한 사항</h4>

        <ul>
          <li
            v-for="(ambiguity, index) in structuredProblem.ambiguities"
            :key="index"
          >
            {{ ambiguity }}
          </li>
        </ul>
      </section>

      <p class="ai-notice">
        AI가 정리한 내용입니다. 중요한 조건은 원문과 비교하세요.
      </p>
    </div>

    <div v-else class="original-content">
      {{ originalText }}
    </div>
  </div>
</template>

<style scoped>
.problem-reader {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: auto;
}

.view-controls {
  display: flex;
  gap: 6px;
  margin: 14px 14px 0;
  padding: 4px;
  border-radius: 8px;
  background: #f1f5f9;
}

.view-controls button {
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.view-controls button.active {
  background: white;
  color: #1d4ed8;
  box-shadow: 0 1px 3px rgb(15 23 42 / 8%);
}

.problem-content,
.original-content {
  padding: 18px;
  color: #334155;
  font-size: 13px;
  line-height: 1.85;
  overflow-wrap: anywhere;
}

.original-content {
  white-space: pre-wrap;
}

.problem-title {
  margin: 0 0 22px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
  color: #0f172a;
  font-size: 19px;
  line-height: 1.5;
}

.problem-section {
  margin-top: 24px;
}

.problem-section:first-child {
  margin-top: 0;
}

.problem-section h4 {
  margin: 0 0 10px;
  color: #0f172a;
  font-size: 14px;
}

.problem-section p {
  margin: 0;
  white-space: pre-wrap;
}

.problem-section ul {
  margin: 0;
  padding-left: 18px;
}

.problem-section li + li {
  margin-top: 5px;
}

.example-card {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.example-card h5 {
  margin: 0 0 12px;
  color: #0f172a;
  font-size: 12px;
}

.example-label {
  display: block;
  margin: 10px 0 5px;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}

.example-card pre {
  margin: 0;
  padding: 10px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #0f172a;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.example-explanation {
  margin-top: 12px !important;
}

.ambiguity-section {
  padding: 12px;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  background: #fff7ed;
}

.ai-notice {
  margin: 28px 0 0;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 11px;
  line-height: 1.7;
}
</style>