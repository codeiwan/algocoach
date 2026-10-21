<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import * as monaco from 'monaco-editor/editor'
import 'monaco-editor/features/register.all'
import 'monaco-editor/languages/definitions/python/register'
import 'monaco-editor/languages/definitions/java/register'
import 'monaco-editor/languages/definitions/cpp/register'
import EditorWorker from 'monaco-editor/editor/editor.worker?worker'

import type { ProgrammingLanguage } from '@/types/programming-language'

const props = defineProps<{
  modelValue: string
  language: ProgrammingLanguage
  feedbackGlow?: 'success' | 'risk' | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const monacoLanguageIds: Record<ProgrammingLanguage, string> = {
  python: 'python',
  java: 'java',
  cpp: 'cpp',
  c: 'cpp',
}

const monacoGlobal = self as typeof self & {
  MonacoEnvironment?: {
    getWorker: () => Worker
  }
}

monacoGlobal.MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
}

const editorContainer = ref<HTMLElement | null>(null)
let editor: monaco.editor.IStandaloneCodeEditor | null = null

onMounted(() => {
  if (!editorContainer.value) return

  editor = monaco.editor.create(editorContainer.value, {
    value: props.modelValue,
    language: monacoLanguageIds[props.language],
    theme: 'vs',

    tabSize: 4,
    insertSpaces: true,
    detectIndentation: false,
    autoIndent: 'full',

    autoClosingBrackets: 'always',
    autoClosingQuotes: 'always',
    autoSurround: 'languageDefined',

    quickSuggestions: {
      other: true,
      comments: false,
      strings: false,
    },
    wordBasedSuggestions: 'currentDocument',

    automaticLayout: true,
    fontSize: 14,
    lineHeight: 23,
    lineNumbers: 'on',
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap: 'off',
    padding: { top: 16, bottom: 16 },
    ariaLabel: '코드 입력',
  })

  editor.onDidChangeModelContent(() => {
    if (!editor) return

    const value = editor.getValue()

    if (value !== props.modelValue) {
      emit('update:modelValue', value)
    }
  })
})

watch(
  () => props.modelValue,
  (newCode) => {
    if (editor && editor.getValue() !== newCode) {
      editor.setValue(newCode)
    }
  },
)

watch(
  () => props.language,
  (language) => {
    const model = editor?.getModel()

    if (model) {
      monaco.editor.setModelLanguage(
        model,
        monacoLanguageIds[language],
      )
    }
  },
)

onBeforeUnmount(() => {
  if (!editor) return

  const model = editor.getModel()
  editor.dispose()
  model?.dispose()
  editor = null
})
</script>

<template>
  <div
    ref="editorContainer"
    class="monaco-container"
    :class="{
      'analysis-glow-success': feedbackGlow === 'success',
      'analysis-glow-risk': feedbackGlow === 'risk',
    }"
  ></div>
</template>

<style scoped>
.monaco-container {
  width: 100%;
  min-height: 480px;
  flex: 1;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: white;
}

.monaco-container:focus-within {
  border-color: #93c5fd;
}
</style>
<style scoped>
.monaco-container.analysis-glow-success {
  border-color: #4ade80;
  animation: editor-verified-glow 2.4s ease-out both;
}
.monaco-container.analysis-glow-risk {
  border-color: #fb7185;
  animation: editor-risk-glow 2.4s ease-out both;
}
@keyframes editor-verified-glow {
  0% { box-shadow: 0 0 0 1px rgba(34,197,94,.32), 0 0 34px rgba(34,197,94,.28); }
  100% { box-shadow: 0 0 0 0 rgba(34,197,94,0), 0 0 0 rgba(34,197,94,0); }
}
@keyframes editor-risk-glow {
  0% { box-shadow: 0 0 0 1px rgba(239,68,68,.35), 0 0 34px rgba(239,68,68,.24); }
  100% { box-shadow: 0 0 0 0 rgba(239,68,68,0), 0 0 0 rgba(239,68,68,0); }
}
@media (prefers-reduced-motion: reduce) {
  .monaco-container.analysis-glow-success,
  .monaco-container.analysis-glow-risk { animation: none; }
}
</style>
