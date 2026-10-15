<script setup lang="ts">
import { ref } from 'vue'
import api from '../api'
import { useAppStore } from '../stores/app'

const store = useAppStore()

const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)   // 请求中：两个按钮一起禁用，避免连点重复注册

// 提交：注册 + 登录走同一条路。
// 用 <form> 包着，Enter 键由浏览器原生处理——不用手写 keydown，
// 屏幕阅读器也知道这是个表单。
async function submit(action: 'login' | 'register') {
  error.value = ''
  store.authNotice = ''   // 用户重新动手了，旧提示就该让位
  if (!username.value.trim() || !password.value) {
    error.value = '用户名和密码都要填'
    return
  }
  if (busy.value) return
  busy.value = true
  try {
    if (action === 'register') {
      await api.post('/register', { username: username.value, password: password.value })
    }
    const res = await api.post('/login', { username: username.value, password: password.value })
    store.setToken(res.data.token)
    password.value = ''
  } catch (e: any) {
    // 后端统一错误格式 {code, message}，message 是给人读的。
    // 出错要说清"哪儿错了"，笼统的"出错了"等于没说。
    error.value = e.response?.data?.message || '网络不太顺，请稍后再试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="gate">
    <div class="gate-card">
      <header class="gate-head">
        <h1>sazeny · AI 分身</h1>
        <p class="lede">
          这里可以就 sazeny 的简历、项目和技术栈直接提问。<br />
          回答由公开语料生成，<strong>每条都附原文出处</strong>，可以逐条核对。
        </p>
      </header>

      <!-- 登录过期 / 限流 / 服务异常，由 api.ts 的响应拦截器经事件送到 store -->
      <p v-if="store.authNotice" class="gate-notice" role="status">{{ store.authNotice }}</p>

      <form class="gate-form" @submit.prevent="submit('login')">
        <label class="field">
          <span class="field-label">用户名</span>
          <input
            v-model="username"
            name="username"
            autocomplete="username"
            placeholder="随便起一个，用来保存对话记录"
            :disabled="busy"
          />
        </label>

        <label class="field">
          <span class="field-label">密码</span>
          <input
            v-model="password"
            name="password"
            type="password"
            autocomplete="current-password"
            placeholder="至少 6 位"
            :disabled="busy"
          />
        </label>

        <p v-if="error" class="gate-error" role="alert">{{ error }}</p>

        <div class="gate-actions">
          <button type="submit" class="btn-primary" :disabled="busy">
            {{ busy ? '请稍候…' : '进入' }}
          </button>
          <button type="button" class="btn-quiet" :disabled="busy" @click="submit('register')">
            首次使用，注册一个
          </button>
        </div>
      </form>
    </div>
  </main>
</template>

<style scoped>
/* 居中的一张"卡片"，但用留白定位，不用边框和阴影去"框"它 */
.gate {
  min-height: 100%;
  display: grid;
  place-items: center;
  padding: var(--sp-6) var(--sp-4);
}

.gate-card { width: min(420px, 100%); }

/* ---------- 抬头 ---------- */
.gate-head { margin-bottom: var(--sp-6); }

.gate-head h1 {
  font-size: var(--fs-brand);
  font-weight: 680;
  letter-spacing: -0.02em;
  line-height: 1.25;
}

.lede {
  margin-top: var(--sp-3);
  color: var(--ink-muted);
  font-size: var(--fs-small);
  line-height: 1.75;
}

/* "附原文出处"是这东西和普通聊天机器人的区别，这里给它正常的墨色 */
.lede strong { color: var(--ink); font-weight: 600; }

/* ---------- 表单 ---------- */
.gate-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.field { display: flex; flex-direction: column; gap: var(--sp-2); }

.field-label {
  font-size: var(--fs-small);
  font-weight: 550;
  color: var(--ink-muted);
}

.field input {
  height: 44px;
  padding: 0 var(--sp-3);
  font: inherit;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--rule-strong);
  border-radius: var(--r-md);
  transition: border-color var(--dur) var(--ease);
}

.field input::placeholder { color: var(--ink-faint); }

.field input:hover:not(:disabled) { border-color: var(--ink-faint); }

/* 聚焦时描边换强调色；键盘操作还会叠一层全局的 :focus-visible 焦点环 */
.field input:focus { border-color: var(--accent); }

.field input:disabled {
  background: var(--surface-sunk);
  color: var(--ink-faint);
  cursor: not-allowed;
}

/* ---------- 提示（不是错误，是"发生了什么"）---------- */
.gate-notice {
  margin-bottom: var(--sp-4);
  padding: var(--sp-2) var(--sp-3);
  font-size: var(--fs-small);
  color: var(--accent-deep);
  background: var(--accent-wash);
  border-radius: var(--r-sm);
}

/* ---------- 错误 ---------- */
.gate-error {
  font-size: var(--fs-small);
  color: var(--danger);
  background: var(--danger-wash);
  border-radius: var(--r-sm);
  padding: var(--sp-2) var(--sp-3);
}

/* ---------- 动作 ----------
   一个主一个次。"登录"和"注册"长得一模一样的时候，人反而不知道点哪个。 */
.gate-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  margin-top: var(--sp-1);
}

.btn-primary {
  height: 44px;
  padding: 0 var(--sp-5);
  font: inherit;
  font-weight: 600;
  color: #fff;
  background: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: background var(--dur) var(--ease), transform var(--dur) var(--ease);
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-deep);
  border-color: var(--accent-deep);
}

.btn-primary:active:not(:disabled) { transform: translateY(1px); }

.btn-primary:disabled { opacity: .55; cursor: not-allowed; }

.btn-quiet {
  font: inherit;
  font-size: var(--fs-small);
  color: var(--ink-muted);
  background: none;
  border: none;
  padding: var(--sp-2) 0;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: var(--rule-strong);
  text-decoration-thickness: 1px;
  transition: color var(--dur) var(--ease), text-decoration-color var(--dur) var(--ease);
}

.btn-quiet:hover:not(:disabled) {
  color: var(--accent);
  text-decoration-color: var(--accent);
}

.btn-quiet:disabled { opacity: .5; cursor: not-allowed; }
</style>
