<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { HintApiError, requestNextHint } from '@/services/hint'

import {
  PROACTIVE_POLL_MS,
  PROACTIVE_REPEAT_WINDOW_MS,
  evaluateProactiveOffer,
  type OfferReason,
  type StableEdit,
} from '@/services/proactive-coaching-policy'

import type {
  CoachingAssistanceActivity,
  CoachingAssistanceEvent,
} from '@/types/coaching-assistance'

import type { HintLevel } from '@/types/hint'
import type { ProgrammingLanguage } from '@/types/programming-language'

const props = defineProps<{
  sessionId: string
  problemText: string
  currentCode: string
  language: ProgrammingLanguage
  currentRevision: number
  autoEnabled: boolean
  busy?: boolean
}>()

const emit = defineEmits<{
  delivered: [event: CoachingAssistanceEvent]
  activity: [state: CoachingAssistanceActivity]
}>()

interface Offer {
  id: number
  revision: number
  reason: OfferReason
  phase: 'offered' | 'loading'
}

const levelNames: Record<HintLevel, string> = {
  DIRECTION: '방향',
  ALGORITHM: '알고리즘',
  IMPLEMENTATION: '구현',
}

const startedAtMs = Date.now()
const lastEditedAtMs = ref(Date.now())
const stableEdits = ref<StableEdit[]>([])

const lastStableCode = ref(props.currentCode)

const lastOfferAtMs = ref<number | null>(null)
const lastOfferRevision = ref<number | null>(null)
const lastOfferHintCount = ref<number | null>(null)

const lastDeclineAtMs = ref<number | null>(null)
const lastDeclinedRevision = ref<number | null>(null)

const offer = ref<Offer | null>(null)
const hintCount = ref(0)
const exhausted = ref(false)
const errorMessage = ref('')

let nextOfferId = 0
let stableTimer: ReturnType<typeof setTimeout> | null = null
let pollingTimer: ReturnType<typeof setInterval> | null = null
let requestController: AbortController | null = null

const showDebug =
  import.meta.env.DEV && new URLSearchParams(window.location.search).get('debugCoach') === '1'

const nextHintName = computed(() => {
  if (hintCount.value === 0) return '방향'
  if (hintCount.value === 1) return '알고리즘'
  return '구현'
})

const offerText = computed(() => {
  if (hintCount.value > 0) {
    return (
      '앞서 드린 힌트 이후에도 고민이 이어지고 있나요? ' +
      `필요하시면 ${nextHintName.value} 단계에서 ` +
      '조금 더 구체적으로 도와드릴게요.'
    )
  }

  if (offer.value?.reason === 'repeated_edits') {
    return (
      '비슷한 부분을 여러 번 수정하고 계신 것 같아요. ' +
      '여러 방법을 시도하는 중일 수도 있겠네요. ' +
      '원하시면 작은 방향 힌트를 드릴까요?'
    )
  }

  return (
    '잠시 코드 변경이 없어서 확인차 여쭤봐요. ' +
    '생각을 정리하는 중이시라면 그대로 이어가셔도 됩니다. ' +
    '방향을 잡는 데 도움이 필요하실까요?'
  )
})

function createOffer(reason: OfferReason) {
  if (offer.value || !props.autoEnabled || exhausted.value || hintCount.value >= 3) {
    return
  }

  const now = Date.now()

  offer.value = {
    id: ++nextOfferId,
    revision: props.currentRevision,
    reason,
    phase: 'offered',
  }

  lastOfferAtMs.value = now
  lastOfferRevision.value = props.currentRevision
  lastOfferHintCount.value = hintCount.value
  errorMessage.value = ''
}

// Periodically decide whether an optional offer
// makes sense. This never makes an API request.
function observe() {
  if (exhausted.value) return

  const reason = evaluateProactiveOffer({
    nowMs: Date.now(),
    startedAtMs,
    lastEditedAtMs: lastEditedAtMs.value,
    currentRevision: props.currentRevision,
    hasCode: props.currentCode.trim().length > 0,
    autoEnabled: props.autoEnabled,
    busy: Boolean(props.busy),
    offerPending: offer.value !== null,
    hintCount: hintCount.value,
    lastOfferAtMs: lastOfferAtMs.value,
    lastOfferRevision: lastOfferRevision.value,
    lastOfferHintCount: lastOfferHintCount.value,
    lastDeclineAtMs: lastDeclineAtMs.value,
    lastDeclinedRevision: lastDeclinedRevision.value,
    stableEdits: stableEdits.value,
  })

  if (reason !== null) {
    createOffer(reason)
  }
}

// Track stable edit snapshots instead of treating
// every individual keystroke as progress.
watch([() => props.currentCode, () => props.language], ([code]) => {
  lastEditedAtMs.value = Date.now()

  if (stableTimer !== null) {
    clearTimeout(stableTimer)
  }

  if (offer.value?.phase === 'offered') {
    offer.value = null
  }

  stableTimer = setTimeout(() => {
    stableTimer = null

    if (code !== props.currentCode || code === lastStableCode.value) {
      return
    }

    lastStableCode.value = code

    const now = Date.now()

    stableEdits.value = [
      ...stableEdits.value.filter((item) => now - item.atMs <= PROACTIVE_REPEAT_WINDOW_MS),
      {
        atMs: now,
        codeLength: code.replace(/\s/g, '').length,
      },
    ].slice(-20)
  }, 2_000)
})

watch(
  () => props.autoEnabled,
  (enabled) => {
    if (!enabled && offer.value?.phase === 'offered') {
      offer.value = null
    }
  },
)

function declineOffer() {
  if (offer.value?.phase !== 'offered') return

  lastDeclineAtMs.value = Date.now()
  lastDeclinedRevision.value = props.currentRevision
  offer.value = null
}

async function acceptOffer() {
  const currentOffer = offer.value

  if (currentOffer?.phase !== 'offered' || props.busy || exhausted.value) {
    return
  }

  const snapshot = {
    session_id: props.sessionId,
    code_revision: props.currentRevision,
    problem_text: props.problemText,
    current_code: props.currentCode,
    language: props.language,
  }

  const controller = new AbortController()
  requestController = controller

  currentOffer.phase = 'loading'
  errorMessage.value = ''
  emit('activity', 'hint')

  try {
    const result = await requestNextHint(snapshot, controller.signal)

    if (controller.signal.aborted || requestController !== controller) {
      return
    }

    if (result.hinted_revision !== snapshot.code_revision) {
      throw new Error('힌트 결과의 코드 Revision이 일치하지 않습니다.')
    }

    const levels: HintLevel[] = ['DIRECTION', 'ALGORITHM', 'IMPLEMENTATION']

    hintCount.value = Math.max(hintCount.value, levels.indexOf(result.level) + 1)

    if (hintCount.value >= 3) {
      exhausted.value = true
    }

    const details = result.code_reference?.trim()
      ? `\n\n관련 코드:\n${result.code_reference.trim()}`
      : ''

    emit('delivered', {
      id: Date.now(),
      source: 'hint',
      title: `${hintCount.value}단계 · ${levelNames[result.level]} 힌트`,
      revision: result.hinted_revision,
      text: result.message + details,
      tone: 'neutral',
      atMs: Date.now(),
    })

    offer.value = null
  } catch (error) {
    if (controller.signal.aborted || requestController !== controller) {
      return
    }

    if (error instanceof HintApiError && error.status === 409) {
      exhausted.value = true
      offer.value = null
    } else {
      currentOffer.phase = 'offered'
    }

    errorMessage.value = error instanceof Error ? error.message : '단계별 힌트 요청에 실패했습니다.'
  } finally {
    if (requestController === controller) {
      requestController = null
      emit('activity', null)
    }
  }
}

function simulateOffer() {
  if (!showDebug || props.busy) return
  createOffer('idle')
}

onMounted(() => {
  pollingTimer = setInterval(observe, PROACTIVE_POLL_MS)
})

onBeforeUnmount(() => {
  if (stableTimer !== null) clearTimeout(stableTimer)
  if (pollingTimer !== null) clearInterval(pollingTimer)

  requestController?.abort()
  requestController = null

  emit('activity', null)
})
</script>

<template>
  <section v-if="offer" class="proactive-card" aria-label="AlgoCoach의 선제적 도움 제안">
    <div class="offer-heading">
      <strong>AlgoCoach가 먼저 말을 걸었습니다</strong>
      <span>선택적 도움</span>
    </div>

    <p>{{ offerText }}</p>

    <div v-if="offer.phase === 'offered'" class="offer-actions">
      <button type="button" class="accept-button" :disabled="busy" @click="acceptOffer">
        네, {{ nextHintName }} 힌트가 필요해요
      </button>

      <button type="button" class="decline-button" @click="declineOffer">조금 더 생각할게요</button>
    </div>

    <p v-else class="loading-text" role="status">요청하신 힌트를 생성하고 있습니다...</p>
  </section>

  <p v-if="errorMessage" class="proactive-error" role="alert">
    {{ errorMessage }}
  </p>

  <div v-if="showDebug" class="proactive-debug">
    <button type="button" :disabled="!!offer || !!busy" @click="simulateOffer">
      개발용 · 도움 제안 시뮬레이션
    </button>
  </div>
</template>

<style scoped>
.proactive-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid #bfdbfe;
  border-left: 4px solid #6366f1;
  border-radius: 12px;
  background: #f5f7ff;
}

.offer-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.offer-heading strong {
  color: #312e81;
  font-size: 12px;
}

.offer-heading span {
  color: #6366f1;
  font-size: 10px;
}

.proactive-card p {
  margin: 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.75;
}

.offer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.offer-actions button {
  min-height: 34px;
  padding: 8px 10px;
  border-radius: 8px;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.accept-button {
  border: 1px solid #4f46e5;
  background: #4f46e5;
  color: white;
}

.accept-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.decline-button {
  border: 1px solid #cbd5e1;
  background: white;
  color: #475569;
}

.proactive-error {
  margin: 0;
  color: #b91c1c;
  font-size: 11px;
}

.proactive-debug {
  padding: 3px 0;
}

.proactive-debug button {
  padding: 6px 8px;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
  background: white;
  color: #64748b;
  font-size: 10px;
  cursor: pointer;
}

.proactive-debug button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
