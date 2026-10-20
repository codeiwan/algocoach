<script setup lang="ts">
import { onMounted, ref } from 'vue'

const apiStatus = ref('연결 확인 중...')
const isConnected = ref(false)

async function checkBackendConnection() {
  try {
    const response = await fetch('/api/v1/health')

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()

    if (data.status !== 'ok') {
      throw new Error('Unexpected API response')
    }

    isConnected.value = true
    apiStatus.value = 'FastAPI 서버 연결 성공'
  } catch (error) {
    isConnected.value = false
    apiStatus.value = 'FastAPI 서버 연결 실패'
    console.error('Backend connection error:', error)
  }
}

onMounted(() => {
  checkBackendConnection()
})
</script>

<template>
  <main class="container">
    <h1>AlgoCoach</h1>
    <p>Real-time AI Coding Coach</p>

    <div class="status" :class="{ connected: isConnected }" role="status">
      {{ apiStatus }}
    </div>
  </main>
</template>

<style scoped>
.container {
  max-width: 960px;
  margin: 100px auto;
  padding: 24px;
  text-align: center;
  font-family: system-ui, sans-serif;
}

.status {
  margin-top: 32px;
  padding: 16px;
  border-radius: 8px;
  background-color: #fee2e2;
  color: #991b1b;
}

.status.connected {
  background-color: #dcfce7;
  color: #166534;
}
</style>