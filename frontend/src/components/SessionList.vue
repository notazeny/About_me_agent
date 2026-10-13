<script setup lang="ts">
import { onMounted, ref } from 'vue'
import api from '../api'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const links = ref({ github: '', gitee: '' })

function selectSession(id: string) {
  store.currentSessionId = id
}
async function newChat() {
  const res = await api.post('/sessions')
  await store.loadSessions()
  selectSession(res.data.id)
}
async function deleteSession(id: string) {
  await api.delete('/sessions/' + id)
  await store.loadSessions()
}
async function loadLinks() {
  const res = await api.get('/api/links')
  links.value = res.data
}

onMounted(() => {
  store.loadSessions()
  loadLinks()
})
</script>

<template>
  <aside class="sidebar">
    <div class="brand">sazeny · 个人 AI 分身</div>
    <button class="new-chat" @click="newChat">＋ 新建对话</button>

    <div class="session-list">
      <div
        v-for="s in store.sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === store.currentSessionId }"
        @click="selectSession(s.id)"
      >
        <span class="title">{{ s.title || '新对话' }}</span>
        <button class="del" @click.stop="deleteSession(s.id)">✕</button>
      </div>
    </div>

    <div class="footer">
      <a :href="links.github" target="_blank" rel="noopener">GitHub</a>
      <a :href="links.gitee" target="_blank" rel="noopener">Gitee</a>
      <button @click="store.showPortfolio = true">查看作品集 portfolio</button>
      <button @click="store.logout()">退出登录</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px;
  height: 100%;
  background: #202123;
  color: #ececf1;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.brand { font-weight: 700; font-size: 15px; margin-bottom: 8px; }
.new-chat {
  padding: 10px;
  border: 1px solid #4a4a52;
  border-radius: 8px;
  background: transparent;
  color: #ececf1;
  cursor: pointer;
  margin-bottom: 8px;
}
.session-list { flex: 1; overflow-y: auto; }
.session-item {
  display: flex;
  align-items: center;
  padding: 9px 12px;
  border-radius: 8px;
  cursor: pointer;
  gap: 6px;
}
.session-item:hover { background: #2a2b32; }
.session-item.active { background: #343541; }
.session-item .title {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-item .del {
  background: none;
  border: none;
  color: #8e8ea0;
  cursor: pointer;
  display: none;
}
.session-item:hover .del { display: inline; }
.session-item .del:hover { color: #f87171; }
.footer {
  border-top: 1px solid #2a2b32;
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.footer a, .footer button {
  color: #c5c5d2;
  text-decoration: none;
  font-size: 13px;
  background: none;
  border: none;
  text-align: left;
  cursor: pointer;
  padding: 0;
}
.footer a:hover, .footer button:hover { color: #fff; }
</style>
