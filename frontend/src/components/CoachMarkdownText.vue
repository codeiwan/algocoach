<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  text: string
}>()

type BasicKind = 'text' | 'code'
type PieceKind = BasicKind | 'strong'

interface BasicPiece {
  kind: BasicKind
  value: string
}

interface Piece {
  kind: PieceKind
  value: string
  children: BasicPiece[]
}

/**
 * Parse inline code inside a bold span.
 *
 * Supported:
 *   **Use `answer += i` here**
 *
 * No HTML interpretation is performed.
 */
function parseCodePieces(input: string): BasicPiece[] {
  const result: BasicPiece[] = []
  const pattern = /`([^`\r\n]+)`/g

  let cursor = 0

  for (const match of input.matchAll(pattern)) {
    const index = match.index

    if (index > cursor) {
      result.push({
        kind: 'text',
        value: input.slice(cursor, index),
      })
    }

    result.push({
      kind: 'code',
      value: match[1] ?? '',
    })

    cursor = index + match[0].length
  }

  if (cursor < input.length) {
    result.push({
      kind: 'text',
      value: input.slice(cursor),
    })
  }

  return result
}

/**
 * Minimal, safe inline Markdown parser.
 *
 * Supported:
 *   **bold**
 *   `inline code`
 *   **bold with `inline code`**
 *
 * Unsupported Markdown remains ordinary text.
 * This component deliberately does not use v-html.
 */
function parseInlineMarkdown(input: string): Piece[] {
  const result: Piece[] = []

  const pattern = /\*\*([\s\S]+?)\*\*|`([^`\r\n]+)`/g

  let cursor = 0

  for (const match of input.matchAll(pattern)) {
    const index = match.index

    if (index > cursor) {
      result.push({
        kind: 'text',
        value: input.slice(cursor, index),
        children: [],
      })
    }

    if (match[1] !== undefined) {
      result.push({
        kind: 'strong',
        value: match[1],
        children: parseCodePieces(match[1]),
      })
    } else {
      result.push({
        kind: 'code',
        value: match[2] ?? '',
        children: [],
      })
    }

    cursor = index + match[0].length
  }

  if (cursor < input.length) {
    result.push({
      kind: 'text',
      value: input.slice(cursor),
      children: [],
    })
  }

  return result
}

const pieces = computed(() =>
  parseInlineMarkdown(props.text),
)
</script>

<template>
  <span class="coach-markdown-text">
    <template
      v-for="(piece, index) in pieces"
      :key="index"
    >
      <code
        v-if="piece.kind === 'code'"
        class="coach-inline-code"
      >{{ piece.value }}</code>

      <strong
        v-else-if="piece.kind === 'strong'"
        class="coach-strong"
      >
        <template
          v-for="(child, childIndex) in piece.children"
          :key="childIndex"
        >
          <code
            v-if="child.kind === 'code'"
            class="coach-inline-code"
          >{{ child.value }}</code>

          <span v-else>{{ child.value }}</span>
        </template>
      </strong>

      <span v-else>{{ piece.value }}</span>
    </template>
  </span>
</template>

<style scoped>
.coach-markdown-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.coach-strong {
  font-weight: 700;
}

.coach-inline-code {
  display: inline;
  padding: 1px 4px;
  border: 1px solid rgba(100, 116, 139, 0.17);
  border-radius: 4px;
  background: rgba(148, 163, 184, 0.16);
  color: #1d4ed8;
  font-family:
    ui-monospace,
    SFMono-Regular,
    Menlo,
    Monaco,
    Consolas,
    monospace;
  font-size: 0.92em;
  line-height: inherit;
  white-space: break-spaces;
  overflow-wrap: anywhere;
}
</style>