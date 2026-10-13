<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import api from '../api'
import { useAppStore, type Message } from '../stores/app'
import { mdToHtml } from '../utils/markdown'

const store = useAppStore()
const input = ref('')
const streaming = ref(false)
const openSources = ref<number | null>(null)

async function loadMessages() {
  if (!store.currentSessionId) { store.messages = []; return }
  const res = await api.get('/sessions/' + store.currentSessionId)
  store.messages = res.data.messages
}

watch(() => store.currentSessionId, loadMessages)

async function send() {
  const q = input.value.trim()
  if (!q || !store.currentSessionId || streaming.value) return
  input.value = ''
  streaming.value = true

  store.messages.push({ role: 'user', content: q, sources: null, created_at: '' })

  const aiMsg = reactive<Message>({ role: 'assistant', content: '', sources: [], created_at: '' })
  store.messages.push(aiMsg)

  try {
    const resp = await fetch('http://localhost:8000/sessions/' + store.currentSessionId + '/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + store.token,
      },
      body: JSON.stringify({ question: q }),
    })
    if (!resp.ok) throw new Error('HTTP ' + resp.status)

    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const raw = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        const line = raw.trim()
        if (!line.startsWith('data:')) continue
        let data: any
        try { data = JSON.parse(line.slice(5).trim()) } catch { continue }
        if (data.delta) aiMsg.content += data.delta
        if (data.done) aiMsg.sources = data.sources || []
      }
    }
  } catch (e: any) {
    aiMsg.content = '[出错了] ' + (e?.message || '')
  } finally {
    streaming.value = false
    store.loadSessions()   // 刷新会话列表（第一条消息后标题会变）
  }
}

function toggleSources(i: number) {
  openSources.value = openSources.value === i ? null : i
}
</script>

<template>
  <main class="chat">
    <div class="chat-header">🤖 这是 sazeny 的个人 AI 分身，可就简历与项目做初步面试；正式沟通请以 sazeny 本人为准。</div>

    <div class="messages">
      <div v-if="!store.messages.length" class="empty">问我任何关于 sazeny 的项目、技术栈或求职方向的问题吧</div>

      <div v-for="(m, i) in store.messages" :key="i" :class="['msg', m.role]">
        <div v-if="m.role === 'assistant'" class="bubble">
          <!-- 流式期间、还没吐出第一个字时，显示旋转加载动画 -->
          <span v-if="streaming && !m.content" class="spinner"></span>
          <div v-html="mdToHtml(m.content)"></div>
        </div>
        <div v-else class="bubble user">{{ m.content }}</div>

        <button
          v-if="m.role === 'assistant' && m.sources?.length"
          class="src-btn"
          @click="toggleSources(i)"
        >查看源文本({{ m.sources.length }})</button>
        <div v-if="openSources === i" class="sources">
          <div v-for="s in m.sources" :key="s.text" class="src-item">
            <div class="src-name">{{ s.source === 'persona_qa.md' ? 'sazeny 原话' : '语料 · ' + s.source }}</div>
            <div class="src-text">{{ s.text }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="input-bar">
      <textarea v-model="input" placeholder="输入你的问题，Enter 发送、Shift+Enter 换行" @keydown.enter.exact.prevent="send"></textarea>
      <button @click="send" :disabled="streaming">发送</button>
    </div>
  </main>
</template>

<style scoped>
.chat { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-header {
  padding: 12px 20px;
  border-bottom: 1px solid #e5e5e5;
  background: #fff;
  font-size: 13px;
  color: #6b7280;
}
.messages { flex: 1; overflow-y: auto; padding: 20px; }
.empty { color: #6b7280; text-align: center; margin-top: 60px; }
.msg { max-width: 760px; margin: 0 auto 16px; }
.msg.user { display: flex; justify-content: flex-end; }
.bubble { padding: 10px 14px; border-radius: 12px; line-height: 1.6; word-break: break-word; overflow-wrap: break-word; }
.msg.assistant .bubble { background: #fff; border: 1px solid #e5e5e5; }
.bubble.user { background: #4f46e5; color: #fff; max-width: 70%; white-space: pre-wrap; }

/* markdown 里 v-html 渲染的内容不受 scoped 影响，用 :deep 穿透 */
/* 全局重置了 padding，列表数字/圆点会跑到气泡外，补回缩进 */
.bubble :deep(ul), .bubble :deep(ol) { padding-left: 22px; margin: 6px 0; }
/* 表格/代码块太宽会撑破气泡，加横向滚动 */
.bubble :deep(table) { display: block; max-width: 100%; overflow-x: auto; }
.bubble :deep(pre) { overflow-x: auto; }
.bubble :deep(img) { max-width: 100%; }

/* 旋转加载动画 */
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #e5e5e5;
  border-top-color: #4f46e5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }

.src-btn { margin-top: 8px; font-size: 12px; color: #4f46e5; background: none; border: none; cursor: pointer; padding: 0; }
.sources { margin-top: 8px; border-top: 1px dashed #e5e5e5; padding-top: 8px; }
.src-item { margin-bottom: 10px; }
.src-name { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.src-text { font-size: 13px; color: #374151; white-space: pre-wrap; background: #f9fafb; padding: 8px; border-radius: 6px; }
.input-bar { padding: 14px 20px; border-top: 1px solid #e5e5e5; background: #fff; display: flex; gap: 10px; }
.input-bar textarea { flex: 1; resize: none; height: 48px; padding: 12px; border: 1px solid #e5e5e5; border-radius: 10px; font-size: 15px; font-family: inherit; }
.input-bar button { padding: 0 20px; background: #4f46e5; color: #fff; border: none; border-radius: 10px; cursor: pointer; }
.input-bar button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
