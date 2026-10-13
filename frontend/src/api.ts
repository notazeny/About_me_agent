import axios from 'axios'

// axios 实例：统一 baseURL（后端地址）
const api = axios.create({ baseURL: 'http://localhost:8000' })

// 请求拦截器：每个请求发出前，自动把 token 塞进 Authorization 头
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('aboutme_token')
  if (token) config.headers.Authorization = 'Bearer ' + token
  return config
})

export default api
