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
  // 失败不在这里处理：api.ts 的响应拦截器已经统一接住了
  // （401 会登出并提示"登录已过期"）。
  // 这里吞掉，只是为了不产生 unhandled rejection 刷满控制台。
  store.loadSessions().catch(() => {})
  loadLinks().catch(() => {})
})
</script>

<template>
  <aside class="rail">
    <div class="brand">sazeny<span> · 个人 AI 分身</span></div>

    <!-- 图标全部是手写的 SVG：同一套 viewBox、同一个 stroke-width、同一组线帽。
         原来用的是 ＋ / ✕ 这类 Unicode 字符——它们在不同系统上的字重、
         大小、基线全都不一样，是"拼出来的页面"最明显的信号。 -->
    <button class="new-chat" @click="newChat">
      <svg class="i" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M8 3.25v9.5M3.25 8h9.5" />
      </svg>
      新建对话
    </button>

    <nav class="session-list" aria-label="对话记录">
      <button
        v-for="s in store.sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === store.currentSessionId }"
        :aria-current="s.id === store.currentSessionId ? 'true' : undefined"
        @click="selectSession(s.id)"
      >
        <span class="title">{{ s.title || '新对话' }}</span>
        <span
          class="del"
          role="button"
          tabindex="0"
          :aria-label="`删除对话：${s.title || '新对话'}`"
          @click.stop="deleteSession(s.id)"
          @keydown.enter.stop.prevent="deleteSession(s.id)"
          @keydown.space.stop.prevent="deleteSession(s.id)"
        >
          <svg class="i" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M3 5.5h10" />
            <path d="M6.5 5.5V4.2a.9.9 0 0 1 .9-.9h1.2a.9.9 0 0 1 .9.9v1.3" />
            <path d="M4.6 5.5l.55 7.1a.9.9 0 0 0 .9.83h3.9a.9.9 0 0 0 .9-.83l.55-7.1" />
          </svg>
        </span>
      </button>

      <p v-if="!store.sessions.length" class="rail-empty">还没有对话</p>
    </nav>

    <div class="rail-foot">
      <a :href="links.github" target="_blank" rel="noopener">GitHub</a>
      <a :href="links.gitee" target="_blank" rel="noopener">Gitee</a>
      <button @click="store.showPortfolio = true">作品集</button>
      <button @click="store.logout()">退出登录</button>
    </div>
  </aside>
</template>

<style scoped>
/* 侧栏不再是一条"深色 ChatGPT 皮"。
   它和主区是同一张桌面的两个区域，靠**色调差**分区，不靠明暗对撞——
   这样注意力始终落在正文上，也就是这个产品真正要人读的东西。 */
.rail {
  width: 264px;
  flex-shrink: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--sp-4) var(--sp-3);
  background: var(--surface-sunk);
  border-right: 1px solid var(--rule);
}

.brand {
  font-size: var(--fs-body);
  font-weight: 680;
  letter-spacing: -0.01em;
  padding: 0 var(--sp-2);
  margin-bottom: var(--sp-4);
}
.brand span { color: var(--ink-faint); font-weight: 450; font-size: var(--fs-small); }

/* ---------- 新建对话 ---------- */
.new-chat {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  width: 100%;
  height: 38px;
  padding: 0 var(--sp-3);
  margin-bottom: var(--sp-4);
  font: inherit;
  font-size: var(--fs-small);
  font-weight: 550;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--rule-strong);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: border-color var(--dur) var(--ease), color var(--dur) var(--ease);
}
.new-chat:hover { border-color: var(--accent); color: var(--accent); }

/* ---------- 对话列表 ---------- */
.session-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin: 0;
}

/* 每个会话是一个 <button>：天然可聚焦、可 Enter 触发，
   不用自己给 div 补 tabindex 和键盘事件 */
.session-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  width: 100%;
  padding: var(--sp-2) var(--sp-2) var(--sp-2) var(--sp-3);
  font: inherit;
  font-size: var(--fs-small);
  color: var(--ink-muted);
  text-align: left;
  background: none;
  border: none;
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: background var(--dur) var(--ease), color var(--dur) var(--ease);
}

.session-item:hover { background: rgba(26, 26, 24, .045); color: var(--ink); }

/* 选中态不用色块堆，用一个淡底 + 加重的墨色 */
.session-item.active {
  background: var(--accent-wash);
  color: var(--accent-deep);
  font-weight: 600;
}

.session-item .title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---------- 删除 ----------
   原来写的是 display:none → hover 才出现。
   那等于：键盘用户永远够不到，触屏用户永远够不到。
   改成 opacity:0——它一直在 DOM 里、一直可聚焦，
   只是视觉上退到背景；hover / 聚焦 / 当前项 / 触屏设备上会显形。 */
.del {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border-radius: var(--r-sm);
  color: var(--ink-faint);
  opacity: 0;
  cursor: pointer;
  transition: opacity var(--dur) var(--ease), color var(--dur) var(--ease),
              background var(--dur) var(--ease);
}

.session-item:hover .del,
.session-item.active .del,
.del:focus-visible { opacity: 1; }

.del:hover {
  color: var(--danger);
  background: var(--danger-wash);
}

/* 没有 hover 能力的设备（触屏）：别让操作藏起来 */
@media (hover: none) {
  .del { opacity: 1; }
}

.rail-empty {
  padding: var(--sp-3);
  font-size: var(--fs-small);
  color: var(--ink-faint);
}

/* ---------- 页脚 ---------- */
.rail-foot {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: var(--sp-3);
  margin-top: var(--sp-3);
  border-top: 1px solid var(--rule);
}

.rail-foot a,
.rail-foot button {
  padding: var(--sp-2);
  font: inherit;
  font-size: var(--fs-small);
  color: var(--ink-muted);
  text-align: left;
  text-decoration: none;
  background: none;
  border: none;
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: background var(--dur) var(--ease), color var(--dur) var(--ease);
}

.rail-foot a:hover,
.rail-foot button:hover {
  color: var(--accent);
  background: rgba(15, 95, 99, .07);
}

/* ---------- 图标：一套统一的笔画 ---------- */
.i {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

/* ---------- 窄屏：侧栏收成顶部一条，对话列表横向滚动 ---------- */
@media (max-width: 860px) {
  .rail {
    width: 100%;
    height: auto;
    flex-direction: row;
    align-items: center;
    gap: var(--sp-3);
    padding: var(--sp-2) var(--sp-3);
    border-right: none;
    border-bottom: 1px solid var(--rule);
  }
  .brand { margin: 0; white-space: nowrap; }
  .brand span { display: none; }
  .new-chat { width: auto; margin: 0; white-space: nowrap; }
  .session-list {
    flex-direction: row;
    overflow-x: auto;
    overflow-y: hidden;
    gap: var(--sp-1);
  }
  .session-item { width: auto; white-space: nowrap; }
  .session-item .title { max-width: 12ch; }
  .rail-empty { display: none; }
  /* 窄屏上把 GitHub / Gitee / 退出挤在一行尾巴上不现实，
     收进主区右上角更合理——这里先只留作品集和退出 */
  .rail-foot {
    flex-direction: row;
    padding: 0;
    margin: 0;
    border: none;
    gap: 0;
  }
  .rail-foot a { display: none; }
}
</style>
