import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// 后端地址（仅开发时用：由 Vite 开发服务器代理转发）
const BACKEND = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],

  // 开发代理：把发到 5173 的接口请求转发给 8000 的后端。
  // 这样前端代码里 baseURL 可以留空（同源），开发和生产行为一致——
  // 避免了「本地写死 localhost、上线就挂」这类问题。
  server: {
    proxy: {
      '/login': BACKEND,
      '/register': BACKEND,
      '/sessions': BACKEND,
      '/api': BACKEND,
      '/static': BACKEND,
    },
  },
})
