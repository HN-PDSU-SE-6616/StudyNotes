<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { profileApi } from '@/api/profile'
import { useAuthStore } from '@/stores/auth'

interface CareerOption {
  key: string
  label: string
  tags: string[]
}

const router = useRouter()
const auth = useAuthStore()

const step = ref(1)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const options = ref<CareerOption[]>([])

// 第一步：职业
const jobRole = ref('')
const customJob = ref('')
// 第二步：技术栈
const selectedTags = ref<string[]>([])
const customTag = ref('')

const canNext = computed(() => jobRole.value !== '')
const activeOption = computed(
  () => options.value.find((o) => o.key === jobRole.value) ?? null,
)
const presetTags = computed(() => (activeOption.value ? activeOption.value.tags : []))
const suggestedTags = computed(() => {
  const set = new Set(presetTags.value)
  selectedTags.value.forEach((t) => set.add(t))
  return Array.from(set)
})

const displayJob = computed(() => {
  if (jobRole.value === 'custom') return customJob.value.trim()
  return activeOption.value?.label ?? ''
})

onMounted(async () => {
  try {
    const [{ data }, me] = await Promise.all([
      profileApi.options(),
      profileApi.get().catch(() => null),
    ])
    options.value = data.options
    if (me?.data?.job_role) {
      // 再次进入（设置里补充画像）：预填已保存内容
      jobRole.value = me.data.job_role
      customJob.value = me.data.job_role_custom ?? ''
      selectedTags.value = me.data.tech_tags ?? []
      step.value = 2
    }
  } catch {
    // options 加载失败也不阻塞页面
  } finally {
    loading.value = false
  }
})

function pickRole(key: string) {
  jobRole.value = key
  // 切换职业后清空已选技术栈，按新职业推荐
  selectedTags.value = []
}

function toggleTag(tag: string) {
  const i = selectedTags.value.indexOf(tag)
  if (i >= 0) selectedTags.value.splice(i, 1)
  else selectedTags.value.push(tag)
}

function addCustomTag() {
  const t = customTag.value.trim()
  if (t && !selectedTags.value.includes(t)) {
    selectedTags.value.push(t)
  }
  customTag.value = ''
}

function next() {
  if (jobRole.value === 'custom' && !customJob.value.trim()) {
    error.value = '请输入你的职业'
    return
  }
  error.value = ''
  step.value = 2
}

function prev() {
  step.value = 1
}

async function saveProfile() {
  saving.value = true
  error.value = ''
  try {
    await profileApi.save({
      job_role: jobRole.value,
      job_role_custom: jobRole.value === 'custom' ? customJob.value.trim() : null,
      tech_tags: selectedTags.value,
    })
    router.push('/')
  } catch {
    error.value = '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}

function skip() {
  router.push('/')
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-brand-600/10 via-white to-purple-600/10 flex flex-col">
    <header class="flex items-center justify-between px-6 py-4">
      <div class="text-lg font-bold text-brand-600">Taot 知识库</div>
      <button class="text-sm text-slate-500 hover:text-slate-700 transition-colors" @click="skip">
        跳过，稍后再说 →
      </button>
    </header>

    <main class="flex-1 flex flex-col items-center justify-center px-4 pb-16 w-full max-w-2xl mx-auto">
      <div class="w-full">
        <!-- 进度 -->
        <div class="flex items-center gap-3 mb-10">
          <div class="h-1.5 flex-1 rounded-full" :class="step >= 1 ? 'bg-brand-500' : 'bg-slate-200'" />
          <div class="h-1.5 flex-1 rounded-full" :class="step >= 2 ? 'bg-brand-500' : 'bg-slate-200'" />
        </div>

        <h1 class="text-2xl md:text-3xl font-bold text-slate-800 mb-2">
          {{ step === 1 ? '你在 IT 领域是什么职位？' : '你常用哪些技术栈？' }}
        </h1>
        <p class="text-sm text-slate-500 mb-8">
          {{ step === 1 ? '我们将据此为你推荐更相关的内容（可随时修改）' : '多选你熟悉或正在学习的技术，可自定义' }}
        </p>

        <!-- 第一步：职业 -->
        <div v-if="step === 1" class="space-y-3">
          <button
            v-for="opt in options"
            :key="opt.key"
            class="w-full flex items-center justify-between px-4 py-3 rounded-xl border-2 transition-all text-left"
            :class="jobRole === opt.key
              ? 'border-brand-500 bg-brand-50 text-brand-700'
              : 'border-slate-200 bg-white hover:border-brand-300'"
            @click="pickRole(opt.key)"
          >
            <span class="font-medium">{{ opt.label }}</span>
            <span v-if="jobRole === opt.key" class="text-brand-500">✓</span>
          </button>

          <input
            v-model="customJob"
            class="input-field w-full"
            placeholder="其他职位？直接输入，如：嵌入式工程师 / 项目经理..."
            @focus="pickRole('custom')"
          />

          <p v-if="error" class="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{{ error }}</p>

          <div class="flex gap-3 pt-4">
            <button class="flex-1 btn-primary" :disabled="!canNext" @click="next">
              下一步
            </button>
          </div>
        </div>

        <!-- 第二步：技术栈 -->
        <div v-else class="space-y-6">
          <div class="px-4 py-3 bg-brand-50 rounded-xl text-sm text-brand-700 flex items-center gap-2">
            <span class="w-5 h-5 rounded-full bg-brand-500 text-white text-xs flex items-center justify-center shrink-0">
              {{ (displayJob || '?').slice(0, 1) }}
            </span>
            <span class="font-medium">{{ displayJob || '未选择职位' }}</span>
            <button class="ml-auto text-brand-400 hover:text-brand-600" @click="prev">修改</button>
          </div>

          <div class="flex flex-wrap gap-2">
            <button
              v-for="tag in suggestedTags"
              :key="tag"
              class="px-3 py-1.5 rounded-full border text-sm transition-all"
              :class="selectedTags.includes(tag)
                ? 'bg-brand-500 border-brand-500 text-white'
                : 'bg-white border-slate-200 text-slate-600 hover:border-brand-300'"
              @click="toggleTag(tag)"
            >
              {{ tag }}
            </button>
          </div>

          <div class="flex gap-2">
            <input
              v-model="customTag"
              class="input-field flex-1"
              placeholder="添加自定义技术栈，如：LangChain..."
              @keydown.enter.prevent="addCustomTag"
            />
            <button class="px-4 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600" @click="addCustomTag">
              ＋ 添加
            </button>
          </div>

          <div class="flex items-center justify-between text-sm text-slate-500">
            <span>已选 {{ selectedTags.length }} 项</span>
          </div>

          <p v-if="error" class="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{{ error }}</p>

          <div class="flex gap-3">
            <button class="flex-1 btn-primary" :disabled="saving || loading" @click="saveProfile">
              {{ saving ? '保存中...' : '完成，进入工作台' }}
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
