<template>
  <router-view />
  <!-- 全局悬浮 AI 助手（登录后所有页面） -->
  <AssistantWidget v-if="showAssistant" />
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AssistantWidget from '@/components/assistant/AssistantWidget.vue'

const auth = useAuthStore()
const showAssistant = computed(() => auth.isLoggedIn)

onMounted(() => {
  // 刷新页面时恢复登录态（路由守卫也会调用，此处兜底）
  if (!auth.user && localStorage.getItem('access_token')) {
    auth.fetchMe().catch(() => {})
  }
})
</script>
