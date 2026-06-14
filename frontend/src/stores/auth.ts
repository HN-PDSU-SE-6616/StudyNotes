import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!user.value)
  const displayName = computed(() => user.value?.display_name || user.value?.username || '访客')
  const avatarUrl = computed(() => user.value?.avatar_url)

  function setTokens(access: string, refresh: string) {
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }

  function clearAuth() {
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const { data } = await authApi.login(username, password)
      setTokens(data.access_token, data.refresh_token)
      user.value = data.user
      return data
    } finally {
      loading.value = false
    }
  }

  async function register(form: { username: string; email: string; password: string; display_name?: string }) {
    loading.value = true
    try {
      const { data } = await authApi.register(form)
      setTokens(data.access_token, data.refresh_token)
      user.value = data.user
      return data
    } finally {
      loading.value = false
    }
  }

  async function fetchMe() {
    const token = localStorage.getItem('access_token')
    if (!token) return null
    try {
      const { data } = await authApi.me()
      user.value = data
      return data
    } catch {
      clearAuth()
      return null
    }
  }

  function logout() {
    clearAuth()
  }

  return {
    user,
    loading,
    isLoggedIn,
    displayName,
    avatarUrl,
    login,
    register,
    fetchMe,
    logout,
  }
})
