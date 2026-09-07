import { defineStore } from 'pinia'
import { ref } from 'vue'
import { orgsApi } from '@/api/orgs'
import type { OrgWithRole, ProjectWithRole } from '@/types'

/**
 * 组织/项目上下文（当前工作区）
 */
export const useOrgStore = defineStore('org', () => {
  const orgs = ref<OrgWithRole[]>([])
  const activeOrg = ref<OrgWithRole | null>(null)
  const projects = ref<ProjectWithRole[]>([])
  const activeProject = ref<ProjectWithRole | null>(null)
  const loading = ref(false)

  const isLoaded = () => orgs.value.length > 0

  async function fetchOrgs() {
    const { data } = await orgsApi.list()
    orgs.value = data
  }

  /** 确保上下文就绪：默认选第一个组织/项目 */
  async function ensureContext(orgId?: string, projectId?: string) {
    loading.value = true
    try {
      if (!isLoaded()) await fetchOrgs()
      if (!orgs.value.length) return
      const org = orgs.value.find((o) => o.id === orgId) || orgs.value[0]
      activeOrg.value = org
      const { data } = await orgsApi.listProjects(org.id)
      projects.value = data
      activeProject.value =
        data.find((p) => p.id === projectId) || data.find((p) => !p.is_archived) || data[0] || null
    } finally {
      loading.value = false
    }
  }

  async function selectOrg(org: OrgWithRole) {
    activeOrg.value = org
    activeProject.value = null
    const { data } = await orgsApi.listProjects(org.id)
    projects.value = data
    activeProject.value = data.find((p) => !p.is_archived) || data[0] || null
    return activeProject.value
  }

  function selectProject(project: ProjectWithRole) {
    activeProject.value = project
  }

  return {
    orgs,
    activeOrg,
    projects,
    activeProject,
    loading,
    fetchOrgs,
    ensureContext,
    selectOrg,
    selectProject,
  }
})
