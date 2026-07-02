// Merkezi Axios örneği — tüm v1 API istekleri buradan geçer.
// Token varsa Authorization başlığı otomatik eklenir; 401'de oturum temizlenir.
import axios from 'axios'

const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api/v1/',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('rf_token')
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.includes('auth/login')) {
      localStorage.removeItem('rf_token')
      localStorage.removeItem('rf_user')
      window.location.reload()
    }
    return Promise.reject(error)
  },
)

export default apiClient
