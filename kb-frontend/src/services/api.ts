import axios from 'axios'

const api = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const raw = sessionStorage.getItem('kb_token')
  if (raw) {
    try {
      const data = JSON.parse(raw)
      if (data.access_token) {
        config.headers.Authorization = `Bearer ${data.access_token}`
      }
    } catch { /* ignore */ }
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      sessionStorage.removeItem('kb_token')
      localStorage.removeItem('kb_token')
      if (window.location.pathname !== '/login') {
        window.location.replace('/login')
      }
    }
    return Promise.reject(err)
  },
)

export default api