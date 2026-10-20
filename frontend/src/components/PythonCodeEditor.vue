<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import * as monaco from 'monaco-editor/editor'
import 'monaco-editor/features/register.all'
import 'monaco-editor/languages/definitions/python/register'
import EditorWorker from 'monaco-editor/editor/editor.worker?worker'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

// Python 편집에 필요한 기본 Monaco Worker를 등록합니다.
const monacoGlobal = self as typeof self & {
  MonacoEnvironment?: {
    getWorker: () => Worker
  }
}

monacoGlobal.MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
}

// Vue와 Monaco는 서로 다른 객체 수명주기를 사용합니다.
const editorContainer = ref<HTMLElement | null>(null)

let editor: monaco.editor.IStandaloneCodeEditor | null = null

onMounted(() => {
  if (!editorContainer.value) {
    return
  }

  editor = monaco.editor.create(editorContainer.value, {
    value: props.modelValue,
    language: 'python',
    theme: 'vs',

    // Python 편집 설정
    tabSize: 4,
    insertSpaces: true,
    detectIndentation: false,
    autoIndent: 'full',

    // 기본 편집 편의 기능
    autoClosingBrackets: 'always',
    autoClosingQuotes: 'always',
    autoSurround: 'languageDefined',

    quickSuggestions: {
      other: true,
      comments: false,
      strings: false,
    },
    wordBasedSuggestions: 'currentDocument',

    // 에디터 화면 설정
    automaticLayout: true,
    fontSize: 14,
    lineHeight: 23,
    lineNumbers: 'on',
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    wordWrap: 'off',
    padding: {
      top: 16,
      bottom: 16,
    },
    ariaLabel: 'Python 코드 입력',
  })

  // Monaco의 코드 변경을 부모 Vue 컴포넌트에 전달합니다.
  editor.onDidChangeModelContent(() => {
    if (!editor) {
      return
    }

    const newCode = editor.getValue()

    if (newCode !== props.modelValue) {
      emit('update:modelValue', newCode)
    }
  })
})

// 부모에서 코드가 변경되었을 때 Monaco에도 반영합니다.
watch(
  () => props.modelValue,
  (newCode) => {
    if (editor && editor.getValue() !== newCode) {
      editor.setValue(newCode)
    }
  },
)

// 화면에서 에디터가 제거되면 Monaco 리소스를 정리합니다.
onBeforeUnmount(() => {
  if (!editor) {
    return
  }

  const model = editor.getModel()

  editor.dispose()
  model?.dispose()

  editor = null
})
</script>

<template>
  <div ref="editorContainer" class="monaco-container"></div>
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
