<script setup lang="ts">
import { nextTick, reactive, ref, watch } from 'vue'
import api from '../api'
import { useAppStore, type Message } from '../stores/app'
import { mdToHtml } from '../utils/markdown'

const store = useAppStore()
const input = ref('')
const streaming = ref(false)
const openSources = ref<number | null>(null)
const error = ref('')
const scroller = ref<HTMLElement | null>(null)

// HR 面对一个空白输入框，最大的问题不是"不想问"，是"不知道该问什么"。
// 与其说一句"问我任何问题吧"，不如把最常问的几道直接摆出来，点一下就发。
const STARTERS = [
  '介绍一下你自己',
  '你最拿得出手的项目是哪个？',
  '你熟悉哪些技术栈？',
  '为什么想做 AI 方向？',
  '你的 RAG 项目是怎么做的？',
]

async function loadMessages() {
  if (!store.currentSessionId) { store.messages = []; return }
  try {
    const res = await api.get('/sessions/' + store.currentSessionId)
    store.messages = res.data.messages
    openSources.value = null
    error.value = ''
    await stickToBottom(true)
  } catch {
    error.value = '读不到这个对话的记录，换一个或新建一个试试。'
  }
}

watch(() => store.currentSessionId, loadMessages)

// ---------- 跟随底部 ----------
// 但只在用户本来就贴着底部时才跟。他要是往上翻着看，
// 每来一个字就把他拽回底部，是最让人恼火的交互之一。
function isNearBottom(el: HTMLElement) {
  return el.scrollHeight - el.scrollTop - el.clientHeight < 96
}
async function stickToBottom(force = false) {
  const el = scroller.value
  if (!el) return
  if (!force && !isNearBottom(el)) return
  await nextTick()
  el.scrollTop = el.scrollHeight
}

async function send() {
  const q = input.value.trim()
  if (!q || streaming.value) return
  // 以前是 `if (!q || !store.currentSessionId || ...) return` ——
  // 没有当前会话时，点了发送**什么都不发生**，用户只会觉得"这网站坏了"。
  // 宁可说一句人话。
  if (!store.currentSessionId) {
    error.value = '还没有可用的对话，先点「新建对话」。'
    return
  }
  input.value = ''
  error.value = ''
  streaming.value = true

  store.messages.push({ role: 'user', content: q, sources: null, created_at: '' })

  const aiMsg = reactive<Message>({ role: 'assistant', content: '', sources: [], created_at: '' })
  store.messages.push(aiMsg)

  try {
    // 相对路径 = 同源请求。
    //   · 开发时：请求发到 5173，由 vite.config.ts 的 server.proxy 转发到 8000
    //   · 生产时：请求发到同一台服务器，由 Nginx 转发给 FastAPI
    //
    // ⚠️ 这里曾经写死 'http://localhost:8000'，是线上「Failed to fetch」的元凶：
    //    fetch 是原生 API，不走 axios 实例的 baseURL，所以改 api.ts 时漏了这里。
    //    而本地测试时开发机上真的有 localhost:8000，错误地址恰好是通的，
    //    完美掩盖了 bug —— 「本地能跑」不能证明「线上能跑」。
    const resp = await fetch('/sessions/' + store.currentSessionId + '/chat', {
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
        if (data.delta) {
          aiMsg.content += data.delta
          stickToBottom()          // 只在贴着底部时才跟，见上
        }
        if (data.done) aiMsg.sources = data.sources || []
      }
    }
  } catch (e: any) {
    // 半截的回答比没有回答更糟——它会让人以为这就是全部内容。
    // 所以失败时把这一问一答整段撤回，问题还给输入框，能直接重发。
    store.messages.splice(-2, 2)
    input.value = q
    error.value = '没能取到回答。可能是网络中断或服务繁忙，稍等一下再试。'
  } finally {
    streaming.value = false
    store.loadSessions()   // 刷新会话列表（第一条消息后标题会变）
  }
}

function ask(q: string) {
  input.value = q
  send()
}

function toggleSources(i: number) {
  openSources.value = openSources.value === i ? null : i
}
</script>

<template>
  <main class="desk">
    <!-- 页眉：说明这东西是什么、边界在哪。
         原来是一行 emoji（🤖）+ 灰字；emoji 换成手写 SVG。 -->
    <header class="notice">
      <svg class="i" viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="8" cy="8" r="6.25" />
        <path d="M8 7.4v3.7" />
        <path d="M8 4.9h.01" />
      </svg>
      <p>
        这是 sazeny 的个人 AI 分身，可就简历与项目做初步问答；
        <strong>正式沟通请以 sazeny 本人为准</strong>。
      </p>
    </header>

    <div ref="scroller" class="messages" role="log">
      <!-- ---------- 空状态 ---------- -->
      <div v-if="!store.messages.length" class="start">
        <h2>从哪儿开始都行</h2>
        <p class="start-hint">下面是 HR 常问的几个，点一下直接问：</p>
        <ul class="starters">
          <li v-for="q in STARTERS" :key="q">
            <button @click="ask(q)">
              <span>{{ q }}</span>
              <svg class="i" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M3.5 8h9M8.6 4.1 12.5 8l-3.9 3.9" />
              </svg>
            </button>
          </li>
        </ul>
      </div>

      <!-- ---------- 对话 ---------- -->
      <article v-for="(m, i) in store.messages" :key="i" :class="['turn', m.role]">
        <template v-if="m.role === 'assistant'">
          <span v-if="streaming && !m.content" class="typing" aria-label="正在生成回答">
            <i></i><i></i><i></i>
          </span>
          <div v-else class="md" v-html="mdToHtml(m.content)"></div>

          <!-- 出处：这东西的价值就在"可核对"三个字。
               所以它不该是个藏起来的调试开关，而该是答案的一部分。 -->
          <div v-if="m.sources?.length" class="cite">
            <button class="cite-toggle" :aria-expanded="openSources === i" @click="toggleSources(i)">
              <svg class="i" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M6.3 9.7a2.5 2.5 0 0 0 3.5 0l1.9-1.9a2.5 2.5 0 0 0-3.5-3.5l-1 .9" />
                <path d="M9.7 6.3a2.5 2.5 0 0 0-3.5 0L4.3 8.2a2.5 2.5 0 0 0 3.5 3.5l1-.9" />
              </svg>
              <span>依据 {{ m.sources.length }} 处原文</span>
              <svg
                class="i chev"
                :class="{ open: openSources === i }"
                viewBox="0 0 16 16"
                aria-hidden="true"
              >
                <path d="m4.2 6.4 3.8 3.8 3.8-3.8" />
              </svg>
            </button>

            <ol v-if="openSources === i" class="cite-list">
              <li v-for="(s, k) in m.sources" :key="k" class="cite-item">
                <div class="cite-src">
                  {{ s.source === 'persona_qa.md' ? 'sazeny 原话' : s.source }}
                </div>
                <p class="cite-text">{{ s.text }}</p>
              </li>
            </ol>
          </div>
        </template>

        <div v-else class="question">{{ m.content }}</div>
      </article>
    </div>

    <!-- ---------- 输入 ---------- -->
    <footer class="composer">
      <p v-if="error" class="composer-error" role="alert">{{ error }}</p>
      <div class="composer-row">
        <textarea
          v-model="input"
          rows="1"
          :disabled="streaming"
          placeholder="问点什么…（Enter 发送，Shift+Enter 换行）"
          @keydown.enter.exact.prevent="send"
        ></textarea>
        <button class="send" :disabled="streaming || !input.trim()" @click="send">
          {{ streaming ? '生成中' : '发送' }}
        </button>
      </div>
    </footer>
  </main>
</template>

<style scoped>
.desk {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--canvas);
}

/* ---------- 页眉 ---------- */
.notice {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-5);
  border-bottom: 1px solid var(--rule);
  color: var(--ink-muted);
  font-size: var(--fs-small);
  line-height: 1.6;
}
.notice .i { margin-top: 3px; color: var(--ink-faint); }
.notice strong { color: var(--ink); font-weight: 600; }

/* ---------- 消息区 ---------- */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-5) var(--sp-5) var(--sp-6);
}

.turn { max-width: 720px; margin: 0 auto var(--sp-5); }
.turn:last-child { margin-bottom: 0; }

/* 提问：右边一张纸片。
   —— 有意把"回答"做成不加框的正文、"提问"做成加框的批注。
   反转了常见聊天界面的主次：这里真正要读的是回答。 */
.turn.user { display: flex; justify-content: flex-end; }

.question {
  max-width: 72%;
  padding: var(--sp-3) var(--sp-4);
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: var(--r-lg) var(--r-lg) var(--r-sm) var(--r-lg);
  white-space: pre-wrap;
  overflow-wrap: break-word;
}

/* ---------- 空状态 ---------- */
.start { max-width: 620px; margin: var(--sp-7) auto 0; }
.start h2 {
  font-size: var(--fs-title);
  font-weight: 650;
  letter-spacing: -0.01em;
}
.start-hint { margin-top: var(--sp-2); color: var(--ink-muted); font-size: var(--fs-small); }

.starters {
  list-style: none;
  margin: var(--sp-5) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.starters button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-4);
  width: 100%;
  padding: var(--sp-3) var(--sp-2);
  font: inherit;
  font-size: var(--fs-body);
  color: var(--ink);
  text-align: left;
  background: none;
  border: none;
  border-top: 1px solid var(--rule);
  cursor: pointer;
  transition: color var(--dur) var(--ease), padding-left var(--dur) var(--ease);
}
.starters li:last-child button { border-bottom: 1px solid var(--rule); }
.starters .i { color: var(--ink-faint); transition: color var(--dur) var(--ease); }
.starters button:hover { color: var(--accent); padding-left: var(--sp-4); }
.starters button:hover .i { color: var(--accent); }

/* ---------- 生成中 ---------- */
.typing { display: inline-flex; gap: 5px; padding: var(--sp-2) 0; }
.typing i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ink-faint);
  animation: typing 1.15s var(--ease) infinite;
}
.typing i:nth-child(2) { animation-delay: .14s; }
.typing i:nth-child(3) { animation-delay: .28s; }

@keyframes typing {
  0%, 55%, 100% { opacity: .22; transform: translateY(0); }
  28% { opacity: 1; transform: translateY(-2px); }
}

/* ---------- 出处 ---------- */
.cite { margin-top: var(--sp-4); }

.cite-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  font: inherit;
  font-size: var(--fs-meta);
  font-weight: 550;
  color: var(--ink-muted);
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 999px;
  cursor: pointer;
  transition: color var(--dur) var(--ease), border-color var(--dur) var(--ease);
}
.cite-toggle:hover { color: var(--accent); border-color: var(--accent-edge); }

.chev { transition: transform var(--dur) var(--ease); }
.chev.open { transform: rotate(180deg); }

.cite-list {
  list-style: none;
  margin: var(--sp-3) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.cite-src {
  font-size: var(--fs-meta);
  color: var(--ink-faint);
  margin-bottom: var(--sp-1);
}

/* 引用原文当成"证物"陈列：沉底的面 + 发型线，
   而不是靠一条粗色边去喊"看这里" */
.cite-text {
  padding: var(--sp-3);
  font-size: var(--fs-small);
  line-height: 1.7;
  color: var(--ink-muted);
  background: var(--surface-sunk);
  border: 1px solid var(--rule);
  border-radius: var(--r-md);
  white-space: pre-wrap;
  overflow-wrap: break-word;
}

/* ---------- 输入区 ---------- */
.composer {
  padding: var(--sp-4) var(--sp-5) var(--sp-5);
  border-top: 1px solid var(--rule);
  background: var(--canvas);
}

.composer-error {
  max-width: 720px;
  margin: 0 auto var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  font-size: var(--fs-small);
  color: var(--danger);
  background: var(--danger-wash);
  border-radius: var(--r-sm);
}

.composer-row {
  display: flex;
  gap: var(--sp-3);
  max-width: 720px;
  margin: 0 auto;
}

.composer-row textarea {
  flex: 1;
  height: 52px;
  padding: var(--sp-3) var(--sp-4);
  font: inherit;
  font-size: var(--fs-body);
  line-height: 1.5;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--rule-strong);
  border-radius: var(--r-md);
  resize: none;
  transition: border-color var(--dur) var(--ease);
}
.composer-row textarea::placeholder { color: var(--ink-faint); }
.composer-row textarea:hover:not(:disabled) { border-color: var(--ink-faint); }
.composer-row textarea:focus { border-color: var(--accent); }
.composer-row textarea:disabled { background: var(--surface-sunk); cursor: not-allowed; }

.send {
  padding: 0 var(--sp-5);
  font: inherit;
  font-weight: 600;
  color: #fff;
  background: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: background var(--dur) var(--ease), opacity var(--dur) var(--ease);
}
.send:hover:not(:disabled) { background: var(--accent-deep); border-color: var(--accent-deep); }
.send:active:not(:disabled) { transform: translateY(1px); }
.send:disabled { opacity: .45; cursor: not-allowed; }

/* ---------- 图标 ---------- */
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

/* ---------- 窄屏 ---------- */
@media (max-width: 860px) {
  .notice { padding: var(--sp-3) var(--sp-4); }
  .messages { padding: var(--sp-4); }
  .composer { padding: var(--sp-3) var(--sp-4) var(--sp-4); }
  .question { max-width: 85%; }
  .start { margin-top: var(--sp-5); }
}
</style>
