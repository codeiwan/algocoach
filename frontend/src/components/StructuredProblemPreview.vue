<script setup lang="ts">
import type { StructuredProblem } from '@/types/problem'

defineProps<{
  problem: StructuredProblem
}>()
</script>

<template>
  <article class="structured-problem">
    <header class="problem-heading">
      <span class="section-label">STRUCTURED PROBLEM</span>
      <h2>{{ problem.title ?? '제목이 제공되지 않은 문제' }}</h2>
    </header>

    <section class="problem-section">
      <h3>문제 설명</h3>
      <p>{{ problem.goal }}</p>
    </section>

    <section v-if="problem.input_format" class="problem-section">
      <h3>입력</h3>
      <p>{{ problem.input_format }}</p>
    </section>

    <section v-if="problem.output_format" class="problem-section">
      <h3>출력</h3>
      <p>{{ problem.output_format }}</p>
    </section>

    <section
      v-if="problem.constraints.length > 0"
      class="problem-section"
    >
      <h3>제약 조건</h3>

      <ul class="constraint-list">
        <li
          v-for="(constraint, index) in problem.constraints"
          :key="index"
        >
          {{ constraint }}
        </li>
      </ul>
    </section>

    <section
      v-if="problem.examples.length > 0"
      class="problem-section"
    >
      <h3>예제</h3>

      <div
        v-for="(example, index) in problem.examples"
        :key="index"
        class="example-card"
      >
        <h4>예제 {{ index + 1 }}</h4>

        <div class="example-grid">
          <div class="example-block">
            <strong>입력</strong>
            <pre>{{ example.input }}</pre>
          </div>

          <div class="example-block">
            <strong>출력</strong>
            <pre>{{ example.output }}</pre>
          </div>
        </div>

        <p
          v-if="example.explanation"
          class="example-explanation"
        >
          {{ example.explanation }}
        </p>
      </div>
    </section>

    <section
      v-if="problem.ambiguities.length > 0"
      class="problem-section ambiguity-section"
    >
      <h3>확인이 필요한 사항</h3>

      <ul>
        <li
          v-for="(ambiguity, index) in problem.ambiguities"
          :key="index"
        >
          {{ ambiguity }}
        </li>
      </ul>
    </section>

    <footer class="preview-footer">
      AI가 문제 원문을 정리한 결과입니다.
      중요한 조건과 예제는 원문과 비교하여 확인하세요.
    </footer>
  </article>
</template>

<style scoped>
.structured-problem {
  padding: 28px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: white;
}

.problem-heading {
  padding-bottom: 20px;
  border-bottom: 1px solid #e2e8f0;
}

.section-label {
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.problem-heading h2 {
  margin: 10px 0 0;
  font-size: 23px;
  line-height: 1.4;
}

.problem-section {
  margin-top: 26px;
}

.problem-section h3 {
  margin: 0 0 12px;
  font-size: 15px;
}

.problem-section p {
  margin: 0;
  color: #334155;
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.constraint-list,
.ambiguity-section ul {
  margin: 0;
  padding-left: 20px;
  color: #334155;
  font-size: 14px;
  line-height: 1.9;
  overflow-wrap: anywhere;
}

.example-card {
  margin-top: 12px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.example-card h4 {
  margin: 0 0 12px;
  font-size: 13px;
}

.example-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.example-block {
  min-width: 0;
}

.example-block strong {
  display: block;
  margin-bottom: 8px;
  color: #475569;
  font-size: 12px;
}

.example-block pre {
  min-height: 52px;
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: #f1f5f9;
  color: #0f172a;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.example-explanation {
  margin-top: 14px !important;
}

.ambiguity-section {
  padding: 16px;
  border: 1px solid #fed7aa;
  border-radius: 10px;
  background: #fff7ed;
}

.preview-footer {
  margin-top: 28px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.7;
}

@media (max-width: 600px) {
  .structured-problem {
    padding: 18px;
  }

  .example-grid {
    grid-template-columns: 1fr;
  }
}
</style>