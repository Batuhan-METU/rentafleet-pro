import axios from 'axios'
import { getCompanySlug } from '../utils/company.js'
import { TOKEN_KEY } from '../utils/storageKeys.js'

const apiClient = axios.create({
  // Dev: Vite proxy (/api → Django). Prod: doğrudan backend URL'i ayarlanır.
  baseURL: '/api/',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Token ${token}`

  const slug = getCompanySlug()
  if (slug) {
    config.params = { ...config.params, company: slug }
  }
  return config
})

let onUnauthorized = null

/** Pinia auth store bootstrap sonrası bağlanır — sayfa reload yok. */
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLogin = error.config?.url?.includes('auth/login')
    if (error.response?.status === 401 && !isLogin && onUnauthorized) {
      onUnauthorized()
    }
    return Promise.reject(error)
  },
)

export default apiClient
