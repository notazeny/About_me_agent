<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import api, { type ApiNotice } from './api'
import { useAppStore } from './stores/app'
import { mdToHtml } from './utils/markdown'
import Login from './components/Login.vue'
import SessionList from './components/SessionList.vue'
import ChatPanel from './components/ChatPanel.vue'

const store = useAppStore()
const portfolioMd = ref('')

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') store.showPortfolio = false
}

// api.ts 的响应拦截器发现「登录过期 / 限流 / 服务异常」时，用事件通知这里。
// 登录过期必须真的退出去——否则页面会一直停在"看起来还登录着"的假象里：
// localStorage 里旧 token 还在，界面照常渲染，但每个请求都 401，
// 而用户完全不知道发生了什么，只会觉得"这网站坏了"。
function onNotice(e: Event) {
  const { kind, message } = (e as CustomEvent<ApiNotice>).detail
  if (kind === 'expired') store.logout()
  store.authNotice = message
}
onMounted(() => window.addEventListener('aboutme:notice', onNotice))

// 弹窗打开时：懒加载一次 markdown、挂上 Esc、锁住背后的滚动。
// 原来三件事都缺 —— 一个只能用鼠标点、还会让背景跟着滚的弹窗，
// 是把键盘用户和触屏用户一起关在门外。
watch(() => store.showPortfolio, async (show) => {
  if (show) {
    window.addEventListener('keydown', onKeydown)
    document.body.style.overflow = 'hidden'
    if (!portfolioMd.value) {
      const res = await api.get('/api/portfolio')
      portfolioMd.value = res.data.markdown
    }
  } else {
    window.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = ''
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('aboutme:notice', onNotice)
  document.body.style.overflow = ''
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
    <div class="modal-box" role="dialog" aria-modal="true" aria-label="sazeny 的作品集" @click.stop>
      <div class="modal-head">
        <h2>sazeny 的作品集</h2>
        <button class="modal-close" aria-label="关闭" @click="store.showPortfolio = false">
          <svg class="i" viewBox="0 0 16 16" aria-hidden="true">
            <path d="m4.5 4.5 7 7M11.5 4.5l-7 7" />
          </svg>
        </button>
      </div>
      <div class="modal-body md" v-html="mdToHtml(portfolioMd)"></div>
    </div>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  height: 100vh;
  height: 100dvh;   /* 移动端地址栏收放时，vh 会算错 */
}

/* ---------- 弹窗 ---------- */
.modal {
  position: fixed;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-5);
  background: rgba(26, 26, 24, .38);
  animation: veil var(--dur) var(--ease);
}

.modal-box {
  display: flex;
  flex-direction: column;
  width: min(820px, 100%);
  height: min(78vh, 100%);
  background: var(--surface);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-2);
  overflow: hidden;
  animation: rise 240ms var(--ease);
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-4);
  padding: var(--sp-4) var(--sp-5);
  border-bottom: 1px solid var(--rule);
}

.modal-head h2 {
  font-size: var(--fs-title);
  font-weight: 650;
  letter-spacing: -0.01em;
}

.modal-close {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  color: var(--ink-muted);
  background: none;
  border: none;
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: color var(--dur) var(--ease), background var(--dur) var(--ease);
}
.modal-close:hover { color: var(--ink); background: var(--surface-sunk); }

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-5) var(--sp-6);
}

/* 一个节制的出场：遮罩淡入、卡片轻轻上浮。
   注意 prefers-reduced-motion 在 style.css 里已全局兜住。 */
@keyframes veil { from { opacity: 0; } }
@keyframes rise {
  from { opacity: 0; transform: translateY(8px); }
}

.i {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

/* ---------- 窄屏：侧栏收成顶栏 ---------- */
@media (max-width: 860px) {
  .app { flex-direction: column; }
  .modal { padding: 0; }
  .modal-box {
    width: 100%;
    height: 100%;
    border-radius: 0;
  }
  .modal-body { padding: var(--sp-4); }
}
</style>
