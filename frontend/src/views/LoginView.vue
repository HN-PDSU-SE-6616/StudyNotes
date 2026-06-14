<template>
  <div class="min-h-screen flex">
    <!-- 左侧品牌区 -->
    <div class="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-gradient-to-br from-brand-600 via-purple-600 to-indigo-800">
      <div class="absolute inset-0 opacity-30">
        <div class="absolute top-20 left-20 w-72 h-72 bg-white/20 rounded-full blur-3xl" />
        <div class="absolute bottom-20 right-20 w-96 h-96 bg-purple-300/20 rounded-full blur-3xl" />
        <div class="absolute top-1/2 left-1/3 w-64 h-64 bg-indigo-300/20 rounded-full blur-3xl" />
      </div>
      <div class="relative z-10 flex flex-col justify-center px-16 text-white">
        <div class="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center mb-8">
          <span class="text-3xl font-bold">T</span>
        </div>
        <h1 class="text-4xl font-bold leading-tight mb-4">Taot 知识库</h1>
        <p class="text-lg text-white/80 leading-relaxed max-w-md">
          集笔记管理、热点聚合、知识图谱于一体的个人知识平台。记录灵感，连接知识。
        </p>
        <div class="mt-12 flex gap-6 text-sm text-white/60">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-green-400" />
            Block 式编辑
          </div>
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-blue-400" />
            页面关系图
          </div>
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-yellow-400" />
            热点聚合
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧表单 -->
    <div class="flex-1 flex items-center justify-center p-8 bg-slate-50">
      <div class="w-full max-w-md animate-slide-up">
        <div class="lg:hidden text-center mb-8">
          <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center mx-auto mb-3">
            <span class="text-white text-xl font-bold">T</span>
          </div>
          <h1 class="text-2xl font-bold text-slate-800">Taot 知识库</h1>
        </div>

        <div class="glass-card rounded-2xl p-8">
          <h2 class="text-2xl font-bold text-slate-800 mb-1">欢迎回来</h2>
          <p class="text-sm text-slate-500 mb-8">登录你的知识库账户</p>

          <form @submit.prevent="handleLogin" class="space-y-5">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1.5">用户名</label>
              <input v-model="form.username" type="text" class="input-field" placeholder="请输入用户名" required />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1.5">密码</label>
              <input v-model="form.password" type="password" class="input-field" placeholder="请输入密码" required />
            </div>

            <p v-if="error" class="text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">{{ error }}</p>

            <button type="submit" class="btn-primary" :disabled="auth.loading">
              {{ auth.loading ? '登录中...' : '登 录' }}
            </button>
          </form>

          <p class="mt-6 text-center text-sm text-slate-500">
            还没有账户？
            <router-link to="/register" class="text-brand-600 font-medium hover:underline">立即注册</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const error = ref('')

const form = reactive({ username: '', password: '' })

async function handleLogin() {
  error.value = ''
  try {
    await auth.login(form.username, form.password)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: unknown) {
    error.value = '用户名或密码错误'
  }
}
</script>
