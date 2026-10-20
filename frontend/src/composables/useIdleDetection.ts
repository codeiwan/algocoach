
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type Ref,
} from 'vue'

import { MIN_CODE_LENGTH } from '@/services/analysis-trigger'
import type { ProgrammingLanguage } from '@/types/programming-language'

export const IDLE_THRESHOLD_MS = 30_000

type IdlePhase = 'waiting' | 'observing' | 'idle' | 'paused'

/**
 * Observe editor inactivity.
 *
 * Inactivity is not equivalent to being stuck.
 * This composable never calls an LLM.
 */
export function useIdleDetection(
  currentCode: Ref<string>,
  selectedLanguage: Ref<ProgrammingLanguage>,
) {
  const idlePhase = ref<IdlePhase>('waiting')

  let idleTimer: ReturnType<typeof setTimeout> | null = null

  const isIdle = computed(() => idlePhase.value === 'idle')

  const idleStatusText = computed(() => {
    switch (idlePhase.value) {
      case 'observing':
        return '편집 활동 관찰 중'

      case 'idle':
        return '장시간 코드 미입력'

      case 'paused':
        return '관찰 일시 정지'

      default:
        return '코드 입력 대기'
    }
  })

  function hasEnoughCode(): boolean {
    return (
      currentCode.value.replace(/\s/g, '').length >= MIN_CODE_LENGTH
    )
  }

  function isPageActive(): boolean {
    return (
      document.visibilityState === 'visible' &&
      document.hasFocus()
    )
  }

  function clearIdleTimer() {
    if (idleTimer !== null) {
      clearTimeout(idleTimer)
      idleTimer = null
    }
  }

  /**
   * Reset the idle timer after editor activity,
   * language changes, or page focus changes.
   */
  function restartObservation() {
    clearIdleTimer()

    // Empty or very short code is not treated as inactivity.
    if (!hasEnoughCode()) {
      idlePhase.value = 'waiting'
      return
    }

    // Do not count time spent in an inactive window or tab.
    if (!isPageActive()) {
      idlePhase.value = 'paused'
      return
    }

    idlePhase.value = 'observing'

    idleTimer = setTimeout(() => {
      idleTimer = null

      // Recheck activity before confirming inactivity.
      if (!hasEnoughCode() || !isPageActive()) {
        restartObservation()
        return
      }

      idlePhase.value = 'idle'
    }, IDLE_THRESHOLD_MS)
  }

  // Any code or language change restarts the observation period.
  watch([currentCode, selectedLanguage], restartObservation)

  onMounted(() => {
    document.addEventListener('visibilitychange', restartObservation)
    window.addEventListener('focus', restartObservation)
    window.addEventListener('blur', restartObservation)

    restartObservation()
  })

  onBeforeUnmount(() => {
    clearIdleTimer()

    document.removeEventListener('visibilitychange', restartObservation)
    window.removeEventListener('focus', restartObservation)
    window.removeEventListener('blur', restartObservation)
  })

  return {
    idlePhase,
    isIdle,
    idleStatusText,
  }
}
