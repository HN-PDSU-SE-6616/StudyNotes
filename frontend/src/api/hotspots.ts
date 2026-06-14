import api from './index'
import type { HotspotResponse } from '@/types'

export const hotspotsApi = {
  list: () => api.get<HotspotResponse>('/hotspots/'),
}
