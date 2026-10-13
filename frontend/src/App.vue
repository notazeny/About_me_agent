<script setup lang="ts">
import { ref, watch } from 'vue'
import api from './api'
import { useAppStore } from './stores/app'
import { mdToHtml } from './utils/markdown'
import Login from './components/Login.vue'
import SessionList from './components/SessionList.vue'
import ChatPanel from './components/ChatPanel.vue'

const store = useAppStore()
const portfolioMd = ref('')

// 作品集弹窗打开时，懒加载一次 markdown
watch(() => store.showPortfolio, async (show) => {
  if (show && !portfolioMd.value) {
    const res = await api.get('/api/portfolio')
    portfolioMd.value = res.data.markdown
  }
})
</script>

<template>
  <Login v-if="!store.token" />
  <div v-else class="app">
    <SessionList />
    <ChatPanel />
  </div>

  <!-- 作品集弹窗 -->
  <div v-if="store.showPortfolio" class="modal" @click="store.showPortfolio = false">
    <div class="modal-box" @click.stop>
      <div class="modal-head">
        <h2>sazeny 的作品集</h2>
        <button class="close" @click="store.showPortfolio = false">×</button>
      </div>
      <div class="modal-body" v-html="mdToHtml(portfolioMd)"></div>
    </div>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  height: 100vh;
}
/* 弹窗 */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.modal-box {
  background: #fff;
  width: min(860px, 90vw);
  height: 80vh;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-head {
  padding: 14px 20px;
  border-bottom: 1px solid #e5e5e5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-head h2 { font-size: 16px; }
.modal-head .close { border: none; background: none; font-size: 22px; cursor: pointer; color: #6b7280; }
.modal-body { flex: 1; overflow-y: auto; padding: 20px; font-size: 14px; line-height: 1.7; }
</style>
