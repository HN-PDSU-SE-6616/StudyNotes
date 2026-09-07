<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useOrgStore } from '@/stores/org'
import { usePageStore } from '@/stores/page'

const emit = defineEmits<{ navigateHome: []; createProject: [] }>()

const router = useRouter()
const auth = useAuthStore()
const orgStore = useOrgStore()
const pageStore = usePageStore()

function onOrgChange() {
  if (!orgStore.activeOrg) return
  orgStore.selectOrg(orgStore.activeOrg).then(() => {
    pageStore.currentPage = null
    const pid = orgStore.activeProject?.id
    router.push(pid ? { path: '/notes', query: { project: pid } } : '/notes')
  })
}

function onProjectChange() {
  if (!orgStore.activeProject) return
  pageStore.currentPage = null
  router.push({ path: '/notes', query: { project: orgStore.activeProject.id } })
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="p-3 border-b border-slate-100 space-y-2 shrink-0">
    <div class="flex items-center gap-2">
      <router-link
        to="/"
        class="w-8 h-8 flex items-center justify-center rounded-xl hover:bg-slate-100 text-slate-500 shrink-0"
        title="工作台"
      >
        <svg class="w-4.5 h-4.5 w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 12l9-9 9 9M5 10v10a1 1 0 001 1h4v-6h4v6h4a1 1 0 001-1V10" />
        </svg>
      </router-link>
      <div class="min-w-0 flex-1">
        <select
          v-model="orgStore.activeOrg"
          class="w-full text-sm font-semibold text-slate-700 bg-transparent focus:outline-none truncate cursor-pointer"
          title="切换组织"
          @change="onOrgChange"
        >
          <option v-for="o in orgStore.orgs" :key="o.id" :value="o">
            {{ o.icon || '🏢' }} {{ o.name }}
          </option>
        </select>
        <select
          v-if="orgStore.projects.length"
          v-model="orgStore.activeProject"
          class="w-full text-xs text-slate-500 bg-transparent focus:outline-none truncate cursor-pointer"
          title="切换项目"
          @change="onProjectChange"
        >
          <option v-for="p in orgStore.projects" :key="p.id" :value="p">
            {{ p.icon || '📚' }} {{ p.name }}
          </option>
        </select>
      </div>
      <div class="flex items-center gap-1 shrink-0">
        <button
          class="w-8 h-8 flex items-center justify-center rounded-xl text-slate-500 hover:bg-slate-100"
          title="新建项目"
          @click="$emit('createProject')"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
        </button>
        <button
          class="w-8 h-8 flex items-center justify-center rounded-xl text-slate-500 hover:bg-slate-100"
          title="退出登录"
          @click="logout"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>
