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

export default api
