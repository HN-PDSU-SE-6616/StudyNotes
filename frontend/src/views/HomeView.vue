<template>
  <div class="min-h-screen bg-slate-50">
    <header class="bg-gradient-to-r from-brand-600 to-purple-600 text-white">
      <div class="max-w-6xl mx-auto px-4 py-6 flex items-center justify-between">
        <div>
          <p class="text-sm text-white/70 mb-1">{{ greeting }}，{{ auth.displayName }}</p>
          <h1 class="text-2xl md:text-3xl font-bold">知识库工作台</h1>
        </div>
        <div class="flex items-center gap-2">
          <router-link
            to="/notes"
            class="hidden sm:inline-flex px-4 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-sm font-medium transition-colors"
          >
            进入笔记
          </router-link>
          <button
            class="px-4 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-sm font-medium transition-colors"
            @click="logout"
          >
            退出
          </button>
        </div>
      </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-8 space-y-10">
      <!-- 组织/项目 -->
      <section>
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold text-slate-800">我的组织</h2>
          <button class="text-sm text-brand-600 hover:underline" @click="createOrgOpen = true">＋ 新建组织</button>
        </div>

        <div v-if="loading" class="text-sm text-slate-400 py-8 text-center">加载中…</div>
        <div v-else-if="!orgStore.orgs.length" class="text-sm text-slate-400 py-8 text-center bg-white rounded-2xl">
          还没有组织，创建一个开始记录你的知识吧。
        </div>

        <div class="grid gap-4 md:grid-cols-2">
          <div
            v-for="org in orgStore.orgs"
            :key="org.id"
            class="bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-md transition-shadow"
          >
            <div class="flex items-center gap-3 mb-3">
              <span class="w-11 h-11 rounded-xl bg-brand-50 flex items-center justify-center text-2xl">{{ org.icon || '🏢' }}</span>
              <div class="min-w-0 flex-1">
                <div class="font-semibold text-slate-800 truncate">{{ org.name }}</div>
                <div class="text-xs text-slate-400">我的角色：{{ roleText(org.my_role) }}</div>
              </div>
              <router-link :to="{ path: '/notes', query: { project: org.id === orgStore.activeOrg?.id ? orgStore.activeProject?.id : undefined } }" class="hidden"> </router-link>
            </div>

            <div class="space-y-1.5">
              <button
                v-for="p in org.projects"
                :key="p.id"
                class="w-full flex items-center gap-2 px-3 py-2 rounded-xl hover:bg-slate-50 text-left transition-colors"
                @click="enterProject(p)"
              >
                <span>{{ p.icon || '📚' }}</span>
                <span class="text-sm text-slate-600 truncate flex-1">{{ p.name }}</span>
                <svg class="w-4 h-4 text-slate-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                </svg>
              </button>
              <div v-if="!org.projects.length" class="text-xs text-slate-400 px-2">（暂无项目）</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 为你推荐 -->
      <section>
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-bold text-slate-800">🎯 为你推荐</h2>
          <span class="text-xs text-slate-400">每日凌晨按兴趣刷新</span>
        </div>
        <div v-if="recoLoading" class="text-sm text-slate-400 py-6 text-center">加载中…</div>
        <div v-else-if="!recommendations.length" class="text-sm text-slate-400 py-6 text-center bg-white rounded-2xl">
          暂无推荐——多浏览一些笔记后，第二天会生成个性化推荐。
        </div>
        <div v-else class="grid gap-3 md:grid-cols-3">
          <button
            v-for="(r, i) in recommendations"
            :key="r.note_id + '-' + i"
            class="bg-white rounded-2xl border border-slate-200 p-4 text-left hover:border-brand-300 hover:shadow-md transition-all"
            @click="openRecommendation(r)"
          >
            <div class="text-sm font-medium text-slate-700 truncate">{{ r.title }}</div>
            <div v-if="r.heading_path" class="text-xs text-brand-600 mt-1 truncate">{{ r.heading_path }}</div>
            <div class="text-[10px] text-slate-400 mt-2">相关度 {{ (r.score * 100).toFixed(0) }}%</div>
          </button>
        </div>
      </section>

      <!-- 今日热点（外部源） -->
      <section v-if="hotspot.data">
        <h2 class="text-lg font-bold text-slate-800 mb-4">🔥 今日热点</h2>
        <HotspotSection title="GitHub 热门项目" subtitle="开源社区最受关注的项目" icon="⭐" :items="hotspot.data.github ?? []" :loading="hotspot.loading" />
        <HotspotSection title="B站编程教程" subtitle="热门编程学习视频" icon="📺" :items="hotspot.data.bilibili ?? []" :loading="hotspot.loading" />
        <HotspotSection title="编程社区" subtitle="Hacker News & V2EX 最新讨论" icon="💬" :items="hotspot.data.community ?? []" :loading="hotspot.loading" />
      </section>
    </main>

    <!-- 新建组织弹窗 -->
    <Teleport to="body">
      <div v-if="createOrgOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="createOrgOpen = false">
        <div class="bg-white rounded-2xl p-6 w-full max-w-sm shadow-xl">
          <h3 class="text-lg font-semibold text-slate-800 mb-4">新建组织</h3>
          <input v-model="newOrgName" class="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30" placeholder="组织名称" />
          <div class="flex justify-end gap-3 mt-5">
            <button class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl" @click="createOrgOpen = false">取消</button>
            <button class="px-4 py-2 text-sm bg-brand-600 text-white rounded-xl hover:bg-brand-700" @click="confirmCreateOrg">创建</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useOrgStore } from '@/stores/org'
import { useHotspotStore } from '@/stores/hotspot'
import { orgsApi } from '@/api/orgs'
import { recommendationsApi } from '@/api/files'
import HotspotSection from '@/components/hotspot/HotspotSection.vue'
import type { OrgWithRole, ProjectWithRole, RecommendationItem } from '@/types'

interface OrgCard extends OrgWithRole {
  projects: ProjectWithRole[]
}

const router = useRouter()
const auth = useAuthStore()
const orgStore = useOrgStore()
const hotspot = useHotspotStore()

const loading = ref(true)
const recoLoading = ref(true)
const recommendations = ref<RecommendationItem[]>([])
const orgCards = ref<OrgCard[]>([])
const createOrgOpen = ref(false)
const newOrgName = ref('')

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
})

async function load() {
  loading.value = true
  try {
    await orgStore.fetchOrgs()
    orgCards.value = await Promise.all(
      orgStore.orgs.map(async (org) => {
        const { data } = await orgsApi.listProjects(org.id)
        return { ...org, projects: data }
      }),
    )
  } finally {
    loading.value = false
  }
  try {
    const { data } = await recommendationsApi.list()
    recommendations.value = data
  } finally {
    recoLoading.value = false
  }
}

function enterProject(p: ProjectWithRole) {
  router.push({ path: '/notes', query: { project: p.id } })
}

function openRecommendation(r: RecommendationItem) {
  router.push({ path: `/notes/${r.slug}`, query: { project: r.project_id, anchor: r.heading_path || '' } })
}

function roleText(role: string) {
  const map: Record<string, string> = {
    owner: '所有者',
    admin: '管理员',
    maintainer: '维护者',
    reporter: '只读',
    guest: '访客',
  }
  return map[role] || role
}

async function confirmCreateOrg() {
  const name = newOrgName.value.trim()
  if (!name) return
  const { data } = await orgsApi.create({ name })
  createOrgOpen.value = false
  newOrgName.value = ''
  orgStore.orgs.push(data as OrgWithRole)
  await orgStore.selectOrg(data as OrgWithRole)
  router.push({ path: '/notes', query: { project: orgStore.activeProject?.id } })
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(() => {
  load()
  hotspot.fetchHotspots()
})
</script>
