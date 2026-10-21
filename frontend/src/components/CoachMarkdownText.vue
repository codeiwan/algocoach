<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ text: string }>()

type InlinePart =
  | { kind: 'text' | 'code'; value: string }
  | { kind: 'strong'; value: string; children: InlinePart[] }

type MessageBlock =
  | { kind: 'paragraph'; text: string; parts: InlinePart[] }
  | { kind: 'code'; text: string; language: string }

/** Never interpret model output as HTML. */
function inlineParts(input: string, allowBold = true): InlinePart[] {
  const result: InlinePart[] = []
  const pattern = allowBold
    ? /\*\*([\s\S]+?)\*\*|`([^`\r\n]+)`/g
    : /`([^`\r\n]+)`/g
  let cursor = 0

  for (const match of input.matchAll(pattern)) {
    const index = match.index
    if (index > cursor) {
      result.push({ kind: 'text', value: input.slice(cursor, index) })
    }
    if (allowBold && match[1] !== undefined) {
      result.push({
        kind: 'strong',
        value: match[1],
        children: inlineParts(match[1], false),
      })
    } else {
      result.push({ kind: 'code', value: match[2] ?? match[1] ?? '' })
    }
    cursor = index + match[0].length
  }
  if (cursor < input.length) {
    result.push({ kind: 'text', value: input.slice(cursor) })
  }
  return result
}

function paragraph(text: string): MessageBlock {
  return { kind: 'paragraph', text, parts: inlineParts(text) }
}

/**
 * Supports fenced Markdown code and AlgoCoach's `관련 코드:` section.
 * The latter intentionally consumes the remainder of the message: the hint
 * API appends this section at the very end of its output.
 */
function parseBlocks(input: string): MessageBlock[] {
  const blocks: MessageBlock[] = []
  const normalized = input.replace(/\r\n/g, '\n')
  const fenced = /(^|\n)```([a-zA-Z0-9_+.-]*)[^\n]*\n([\s\S]*?)\n```(?=\n|$)/g
  let cursor = 0

  function addProse(prose: string) {
    if (!prose) return
    const match = /(?:^|\n)관련 코드:[ \t]*\n/.exec(prose)
    if (match?.index !== undefined) {
      const before = prose.slice(0, match.index)
      if (before.trim()) blocks.push(paragraph(before.trimEnd()))
      const code = prose.slice(match.index + match[0].length).trimEnd()
      if (code) blocks.push({ kind: 'code', text: code, language: '' })
      return
    }
    blocks.push(paragraph(prose))
  }

  for (const match of normalized.matchAll(fenced)) {
    const start = match.index + (match[1]?.length ?? 0)
    addProse(normalized.slice(cursor, match.index))
    blocks.push({
      kind: 'code',
      language: match[2] ?? '',
      text: (match[3] ?? '').replace(/^\n/, ''),
    })
    cursor = start + match[0].length - (match[1]?.length ?? 0)
  }
  addProse(normalized.slice(cursor))
  return blocks
}

const blocks = computed(() => parseBlocks(props.text))
</script>

<template>
  <span class="coach-markdown-text">
    <template v-for="(block, blockIndex) in blocks" :key="blockIndex">
      <span v-if="block.kind === 'code'" class="coach-code-block">
        <span class="coach-code-heading">{{ block.language || 'CODE' }}</span>
        <code class="coach-code-content">{{ block.text }}</code>
      </span>
      <span v-else class="coach-prose-block">
        <template v-for="(piece, index) in block.parts" :key="index">
          <code v-if="piece.kind === 'code'" class="coach-inline-code">{{ piece.value }}</code>
          <strong v-else-if="piece.kind === 'strong'" class="coach-strong">
            <template v-for="(child, childIndex) in piece.children" :key="childIndex">
              <code v-if="child.kind === 'code'" class="coach-inline-code">{{ child.value }}</code>
              <span v-else>{{ child.value }}</span>
            </template>
          </strong>
          <span v-else>{{ piece.value }}</span>
        </template>
      </span>
    </template>
  </span>
</template>

<style scoped>
.coach-markdown-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.coach-strong { font-weight: 700; }
.coach-prose-block { white-space: pre-wrap; }
.coach-inline-code {
  display: inline;
  padding: 1px 4px;
  border: 1px solid rgba(100, 116, 139, 0.17);
  border-radius: 4px;
  background: rgba(148, 163, 184, 0.16);
  color: #1d4ed8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.92em;
  white-space: break-spaces;
  overflow-wrap: anywhere;
}
.coach-code-block {
  display: block;
  min-width: 0;
  margin: 12px 0 2px;
  padding: 0;
  overflow: hidden;
  border: 1px solid #d8e2f0;
  border-radius: 9px;
  background: #edf2f9;
  white-space: normal;
}
.coach-code-heading {
  display: block;
  padding: 5px 11px;
  border-bottom: 1px solid #d8e2f0;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.coach-code-content {
  display: block;
  max-width: 100%;
  padding: 11px 12px;
  overflow-x: auto;
  color: #1e293b;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 450;
  line-height: 1.7;
  white-space: pre;
  tab-size: 4;
}
</style>
