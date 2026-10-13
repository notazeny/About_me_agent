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

  return { token, currentSessionId, sessions, messages, showPortfolio, setToken, logout, loadSessions }
})
