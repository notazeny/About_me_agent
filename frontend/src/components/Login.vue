<script setup lang="ts">
import { ref } from 'vue'
import api from '../api'                    // axios 实例（自动带 token）
import { useAppStore } from '../stores/app'

const store = useAppStore()                 // 拿到全局 store

const username = ref('')
const password = ref('')
const error = ref('')

async function login() {
  if (!username.value.trim() || !password.value) { error.value = '请输入用户名和密码'; return }
  try {
    // axios POST：第二个参数是请求体（axios 自动转 JSON）
    const res = await api.post('/login', { username: username.value, password: password.value })
    store.setToken(res.data.token)          // 存 token → App.vue 自动切到主界面
    password.value = ''
    error.value = ''
  } catch (e: any) {
    // 后端统一错误格式 {code, message}，message 是人读的
    error.value = e.response?.data?.message || '出错了'
  }
}

async function register() {
  if (!username.value.trim() || !password.value) { error.value = '请输入用户名和密码'; return }
  try {
    await api.post('/register', { username: username.value, password: password.value })
    await login()                           // 注册成功后直接登录
  } catch (e: any) {
    error.value = e.response?.data?.message || '出错了'
  }
}
</script>

<template>
  <div class="login">
    <h2>sazeny · AI 分身</h2>
    <input v-model="username" placeholder="用户名" />
    <input v-model="password" type="password" placeholder="密码" @keydown.enter="login" />
    <p v-if="error" class="error">{{ error }}</p>
    <button @click="login">登录</button>
    <button @click="register">注册</button>
  </div>
</template>
