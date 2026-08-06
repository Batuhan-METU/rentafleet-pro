import { defineStore } from 'pinia'
import apiClient, { setUnauthorizedHandler } from '../services/api.js'
import { useBrandingStore } from './brandingStore.js'
import { inferCompanySlug, setCompanySlug } from '../utils/company.js'
import { TOKEN_KEY, USER_KEY } from '../utils/storageKeys.js'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY),
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
    loading: false,
    error: null,
    bootstrapped: false,
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    isFleetManager: (state) => state.user?.role === 'FLEET_MANAGER',
    isOperationsStaff: (state) => state.user?.role === 'OPERATIONS_STAFF',
    roleLabel: (state) => state.user?.role_display ?? '',
    displayName: (state) => state.user?.full_name || state.user?.username || '',
    initials: (state) => {
      const name = state.user?.full_name || state.user?.username || '?'
      const parts = name.trim().split(/\s+/)
      if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
      return name.slice(0, 2).toUpperCase()
    },
  },

  actions: {
    init() {
      setUnauthorizedHandler(() => this.clearSession())
    },

    _persist() {
      if (this.token) localStorage.setItem(TOKEN_KEY, this.token)
      else localStorage.removeItem(TOKEN_KEY)
      if (this.user) localStorage.setItem(USER_KEY, JSON.stringify(this.user))
      else localStorage.removeItem(USER_KEY)
    },

    _applyUser(user) {
      this.user = user
      this._persist()
      if (user?.company_name) setCompanySlug(user.company_name)
      useBrandingStore().applyFromUser(user)
    },

    async bootstrap() {
      if (!this.token) {
        this.bootstrapped = true
        return
      }
      try {
        const { data } = await apiClient.get('auth/me/')
        this._applyUser(data.user)
      } catch {
        this.clearSession()
      } finally {
        this.bootstrapped = true
      }
    },

    async login(username, password) {
      this.loading = true
      this.error = null
      setCompanySlug(inferCompanySlug(username))

      try {
        const { data } = await apiClient.post('auth/login/', { username, password })
        this.token = data.token
        this._applyUser(data.user)
        return true
      } catch (err) {
        if (!err.response) {
          this.error = 'Sunucuya bağlanılamadı. `python manage.py runserver` çalışıyor mu?'
        } else {
          this.error = err.response.data?.error || 'Giriş yapılamadı.'
        }
        return false
      } finally {
        this.loading = false
      }
    },

    async logout() {
      try {
        await apiClient.post('auth/logout/')
      } catch { /* ignore */ }
      this.clearSession()
    },

    clearSession() {
      this.token = null
      this.user = null
      this.error = null
      this._persist()
    },
  },
})
