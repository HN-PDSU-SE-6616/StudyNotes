import { defineStore } from 'pinia'
import { ref } from 'vue'
import { hotspotsApi } from '@/api/hotspots'
import type { HotspotResponse } from '@/types'

export const useHotspotStore = defineStore('hotspot', () => {
  const data = ref<HotspotResponse | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function fetchHotspots() {
    loading.value = true
    error.value = ''
    try {
      const res = await hotspotsApi.list()
      data.value = res.data
    } catch (e: unknown) {
      error.value = '热点数据加载失败，请稍后重试'
      data.value = { github: [], bilibili: [], community: [] }
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, fetchHotspots }
})
