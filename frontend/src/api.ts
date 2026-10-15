import axios from 'axios'

// axios 实例。
// baseURL 留空 = 向「当前页面所在的源」发请求（同源）。
//   · 开发环境：页面在 localhost:5173，请求也发到 5173，
//     由 vite.config.ts 里的 server.proxy 转发到后端 8000。
//   · 生产环境：前端和后端都在同一台服务器上，浏览器直接请求同源地址，
//     由 Nginx 把 /login、/sessions 等转发给 FastAPI。
// ⚠️ 千万不要写死 'http://localhost:8000'——那样部署后
//    每个访问者的浏览器都会去连「访问者自己电脑」的 8000 端口，必然失败。
const api = axios.create({ baseURL: '' })

// 请求拦截器：每个请求发出前，自动把 token 塞进 Authorization 头
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('aboutme_token')
  if (token) config.headers.Authorization = 'Bearer ' + token
  return config
})

export interface ApiNotice {
  kind: 'expired' | 'busy' | 'error'
  message: string
}

// 用自定义事件，而不是在 api.ts 里 import store：
// stores/app.ts 已经 import 了 api.ts，反过来再 import 就成环了。
// 事件让两边解耦，也把"谁来响应"变成可替换的。
function notify(detail: ApiNotice) {
  window.dispatchEvent(new CustomEvent<ApiNotice>('aboutme:notice', { detail }))
}

// ============================================================
// 响应拦截器：统一处理「服务端已经明确告诉你不该继续」的情况
// ============================================================
//
// 为什么必须有它：JWT 只活 24 小时。token 一过期，
// 前端**什么都不会发生**——localStorage 里的旧 token 还在，
// `store.token` 就是有值的，于是页面看起来仍然是"已登录"状态；
// 但每个请求都 401，用户完全不知道出了什么事，
// 只会觉得"这网站坏了"。真正的问题不是某个页面出错，
// 而是**没有任何人告诉用户发生了什么**。
//
// 后端在第一阶段就给了稳定错误码，前端就该**按码分支**，
// 而不是去解析中文 message——前后端各做一半，这个设计才闭合。
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status
    const code = err.response?.data?.code

    if (status === 401 && (code === 40101 || code === 40102)) {
      // 40101 = 请求没带 token；40102 = token 无效或过期
      notify({ kind: 'expired', message: '登录已过期，请重新登录' })
    } else if (status === 429) {
      notify({ kind: 'busy', message: '请求有点频繁，稍等一下再试' })
    } else if (status && status >= 500) {
      notify({ kind: 'error', message: '服务暂时异常，请稍后重试' })
    }

    return Promise.reject(err)
  },
)

export default api
