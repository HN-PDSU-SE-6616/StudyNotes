<template>
  <div class="min-h-screen flex">
    <div class="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-gradient-to-br from-indigo-600 via-brand-600 to-cyan-600">
      <div class="absolute inset-0 opacity-30">
        <div class="absolute top-32 right-20 w-80 h-80 bg-cyan-300/20 rounded-full blur-3xl" />
        <div class="absolute bottom-32 left-16 w-64 h-64 bg-white/20 rounded-full blur-3xl" />
      </div>
      <div class="relative z-10 flex flex-col justify-center px-16 text-white">
        <h1 class="text-4xl font-bold mb-4">开始你的知识之旅</h1>
        <p class="text-lg text-white/80 max-w-md leading-relaxed">
          创建账户，构建属于你的知识体系。支持 Block 编辑、页面嵌套、热点追踪。
        </p>
      </div>
    </div>

    <div class="flex-1 flex items-center justify-center p-8 bg-slate-50">
      <div class="w-full max-w-md animate-slide-up">
        <div class="glass-card rounded-2xl p-8">
          <h2 class="text-2xl font-bold text-slate-800 mb-1">创建账户</h2>
          <p class="text-sm text-slate-500 mb-8">填写信息完成注册</p>

          <form @submit.prevent="handleRegister" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1.5">用户名</label>
              <input v-model="form.username" type="text" class="input-field" required />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1.5">邮箱</label>
              <input v-model="form.email" type="email" class="input-field" required />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1.5">显示名称</label>
              <input v-model="form.display_name" type="text" class="input-field" placeholder="可选" />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1.5">密码</label>
              <input v-model="form.password" type="password" class="input-field" minlength="6" required />
            </div>

            <p v-if="error" class="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{{ error }}</p>

            <button type="submit" class="btn-primary" :disabled="auth.loading">
              {{ auth.loading ? '注册中...' : '注 册' }}
            </button>
          </form>

          <p class="mt-6 text-center text-sm text-slate-500">
            已有账户？
            <router-link to="/login" class="text-brand-600 font-medium hover:underline">去登录</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const error = ref('')

const form = reactive({
  username: '',
  email: '',
  password: '',
  display_name: '',
})

async function handleRegister() {
  error.value = ''
  try {
    await auth.register(form)
    router.push('/')
  } catch {
    error.value = '注册失败，用户名或邮箱可能已存在'
  }
}
</script>
