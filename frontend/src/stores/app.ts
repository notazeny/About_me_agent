import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export interface Session {
  id: string
  title: string
  created_at: string
  updated_at: string
}
export interface Message {
  role: string
  content: string
  sources: { source: string; text: string }[] | null
  created_at: string
}

export const useAppStore = defineStore('app', () => {
  // ---- 状态 ----
  const token = ref(localStorage.getItem('aboutme_token') || '')
  const currentSessionId = ref('')
  const sessions = ref<Session[]>([])
  const messages = ref<Message[]>([])
  const showPortfolio = ref(false)
  // 全局提示（登录过期 / 限流 / 服务异常），由 api.ts 的响应拦截器经事件送来。
  // 放在 store 里而不是某个组件里：它能从任何页面触发，也该在任何页面被看见。
  const authNotice = ref('')

  // ---- 动作 ----
  function setToken(t: string) {
    token.value = t
    localStorage.setItem('aboutme_token', t)
  }
  function logout() {
    token.value = ''
    currentSessionId.value = ''
    sessions.value = []
    messages.value = []
    localStorage.removeItem('aboutme_token')
  }
  // 加载会话列表：空则自动建一个，否则自动选第一个（登录后不用手动点）
  async function loadSessions() {
    const res = await api.get('/sessions')
    sessions.value = res.data.items
    if (!sessions.value.length) {
      const r = await api.post('/sessions')
      sessions.value = [r.data]
      currentSessionId.value = r.data.id
    } else if (!currentSessionId.value) {
      currentSessionId.value = sessions.value[0].id
    }
  }

  return {
    token, currentSessionId, sessions, messages, showPortfolio, authNotice,
    setToken, logout, loadSessions,
  }
})
