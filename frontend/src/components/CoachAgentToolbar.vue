<script setup lang="ts">
import { computed } from 'vue'
import type { CoachingAssistanceActivity } from '@/types/coaching-assistance'

import type { AnalysisResult } from '@/types/analysis'
import type { IssueRecoveryNotice } from '@/services/analysis-trigger'

type ObservationPhase = 'waiting' | 'editing' | 'settled'
type ActivityTone = 'idle' | 'working' | 'done' | 'warning'

const props = defineProps<{
  autoEnabled: boolean
  autoAnalysisCalls: number
  maxAutoAnalyses: number
  autoScheduleStatus?: string | null
  currentRevision: number
  observationPhase: ObservationPhase
  isAutoAnalyzing: boolean
  isManualAnalyzing: boolean
  isQuestionAnswering: boolean
  assistanceActivity?: CoachingAssistanceActivity
  autoAnalysisResult: AnalysisResult | null
  manualAnalysisResult: AnalysisResult | null
  autoAnalysisError: string
  manualAnalysisError: string
  issueRecovery: IssueRecoveryNotice | null
}>()

const emit = defineEmits<{
  'update:autoEnabled': [enabled: boolean]
}>()

const limitReached = computed(
  () => props.autoAnalysisCalls >= props.maxAutoAnalyses,
)

const modeLabel = computed(() => {
  if (!props.autoEnabled) return 'OFF'
  return limitReached.value ? '한도 도달' : 'ON'
})

const activity = computed<{
  text: string
  tone: ActivityTone
}>(() => {
  if (props.assistanceActivity === 'hint') {
    return {
      text: '요청한 단계별 AI 힌트의 응답을 기다리고 있습니다.',
      tone: 'working',
    }
  }

  if (props.assistanceActivity === 'review') {
    return {
      text: '제출 전 AI 정적 검토 응답을 기다리고 있습니다.',
      tone: 'working',
    }
  }

  if (props.isQuestionAnswering) {
    return {
      text: 'AI 질문에 대한 응답을 기다리고 있습니다.',
      tone: 'working',
    }
  }

  if (props.isManualAnalyzing) {
    return {
      text: '요청한 코드의 AI 분석 응답을 기다리고 있습니다.',
      tone: 'working',
    }
  }

  if (props.isAutoAnalyzing) {
    return {
      text: '자동 코드 분석 요청이 진행 중입니다.',
      tone: 'working',
    }
  }

  if (props.issueRecovery?.phase === 'checking') {
    return {
      text: '수정한 코드의 AI 재검증 응답 대기',
      tone: 'working',
    }
  }

  if (props.issueRecovery?.phase === 'pending') {
    return {
      text: '이전 경고 위치 수정 감지 · 재검증 전',
      tone: 'idle',
    }
  }

  if (props.observationPhase === 'editing') {
    return {
      text: '코드 변경 감지 · 입력 안정화 대기',
      tone: 'idle',
    }
  }

  if (props.issueRecovery?.phase === 'failed') {
    return {
      text: '수정 코드 재검증 실패 · 다시 요청 가능',
      tone: 'warning',
    }
  }

  if (props.manualAnalysisError || props.autoAnalysisError) {
    return {
      text: '최근 분석 요청에 실패했습니다. 다시 요청할 수 있습니다.',
      tone: 'warning',
    }
  }

  if (
    props.manualAnalysisResult?.analyzed_revision ===
    props.currentRevision
  ) {
    return {
      text: '요청한 코드 피드백이 도착했습니다.',
      tone: 'done',
    }
  }

  if (
    props.autoAnalysisResult?.analyzed_revision ===
    props.currentRevision
  ) {
    return {
      text: '자동 코드 분석이 완료됐습니다.',
      tone: 'done',
    }
  }

  if (props.issueRecovery?.phase === 'cleared') {
    return {
      text: '최신 분석에서 이전 경고 재발견되지 않음',
      tone: 'done',
    }
  }

  if (props.issueRecovery?.phase === 'issues_found') {
    return {
      text: '최신 재분석에서 검토할 내용 보고됨',
      tone: 'warning',
    }
  }

  if (!props.autoEnabled) {
    return {
      text: '자동 코칭 OFF · 질문과 수동 피드백 사용 가능',
      tone: 'idle',
    }
  }

  if (limitReached.value) {
    return {
      text: '자동 분석 한도 도달 · 추가 자동 요청 없음',
      tone: 'warning',
    }
  }

  if (props.autoScheduleStatus) {
    return {
      text: props.autoScheduleStatus,
      tone: 'idle',
    }
  }

  if (props.observationPhase === 'settled') {
    return {
      text: '코드 입력 안정 · 다음 동작 대기',
      tone: 'idle',
    }
  }

  return {
    text: '코드를 관찰하고 있습니다.',
    tone: 'idle',
  }
})

function onAutoToggle(event: Event) {
  const input = event.target as HTMLInputElement
  emit('update:autoEnabled', input.checked)
}
</script>

<template>
  <header
    class="coach-agent-toolbar"
    aria-label="AlgoCoach 자동 코칭 및 활동 상태"
  >
    <div class="toolbar-identity">
      <div class="toolbar-avatar" aria-hidden="true">
        <span class="avatar-face">
          <i />
          <i />
        </span>
      </div>

      <div class="toolbar-name">
        <strong>AlgoCoach</strong>
        <span>AI CODING AGENT</span>
      </div>
    </div>

    <div class="toolbar-controls">
      <label class="auto-toggle">
        <input
          type="checkbox"
          :checked="autoEnabled"
          aria-label="자동 AI 코칭"
          @change="onAutoToggle"
        />

        <span class="mode-label">
          자동 코칭 {{ modeLabel }}
        </span>
      </label>

      <span class="usage-label">
        자동 분석 {{ autoAnalysisCalls }}/{{ maxAutoAnalyses }}
      </span>
    </div>

    <div
      class="toolbar-activity"
      role="status"
      aria-live="polite"
    >
      <span
        class="activity-dot"
        :class="activity.tone"
        aria-hidden="true"
      />
      <span>{{ activity.text }}</span>
    </div>
  </header>
</template>

<style scoped>
.coach-agent-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px 8px;
  min-width: 0;
  padding: 12px;
  border: 1px solid #c7d2fe;
  border-radius: 14px;
  background: linear-gradient(135deg, #eff6ff, #eef2ff);
}

.toolbar-identity {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 11px;
}

.toolbar-avatar {
  display: grid;
  flex: 0 0 44px;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
}

.avatar-face {
  display: flex;
  width: 29px;
  height: 21px;
  align-items: center;
  justify-content: space-evenly;
  border-radius: 7px;
  background: white;
}

.avatar-face i {
  width: 5px;
  height: 7px;
  border-radius: 4px;
  background: #2563eb;
}

.toolbar-name {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.toolbar-name strong {
  overflow: hidden;
  color: #0f172a;
  font-size: 16px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar-name span {
  color: #64748b;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.toolbar-controls {
  display: flex;
  align-items: flex-end;
  flex-direction: column;
  gap: 5px;
}

.auto-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #1e40af;
  cursor: pointer;
}

.auto-toggle input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: #2563eb;
  cursor: pointer;
}

.mode-label {
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

.usage-label {
  color: #64748b;
  font-size: 10px;
  white-space: nowrap;
}

.toolbar-activity {
  display: flex;
  grid-column: 1 / -1;
  min-height: 31px;
  align-items: center;
  gap: 8px;
  padding: 7px 9px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  color: #475569;
  font-size: 11px;
  line-height: 1.45;
}

.activity-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
  background: #94a3b8;
}

.activity-dot.working {
  background: #2563eb;
  animation: activity-pulse 1.1s ease-in-out infinite alternate;
}

.activity-dot.done {
  background: #16a34a;
}

.activity-dot.warning {
  background: #d97706;
}

@keyframes activity-pulse {
  to {
    opacity: 0.3;
  }
}

@media (prefers-reduced-motion: reduce) {
  .activity-dot.working {
    animation: none;
  }
}
</style>