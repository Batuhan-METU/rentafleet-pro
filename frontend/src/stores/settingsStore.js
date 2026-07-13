import { defineStore } from 'pinia'
import apiClient from '../services/api.js'
import { useAuthStore } from './authStore.js'
import { useBrandingStore } from './brandingStore.js'
import { useOverviewStore } from './overviewStore.js'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    company: null,
    personnel: [],
    personnelLoading: false,
    loading: false,
    saving: false,
    error: false,
    saveError: '',
    personnelError: '',
    systemStatus: null,
  }),

  actions: {
    async fetchSettings() {
      this.loading = true
      this.error = false
      try {
        const { data } = await apiClient.get('company/settings/')
        this.company = data
        return data
      } catch {
        this.error = true
        this.company = null
        return null
      } finally {
        this.loading = false
      }
    },

    async saveSettings(payload) {
      this.saving = true
      this.saveError = ''
      try {
        const { data } = await apiClient.patch('company/settings/', payload)
        this.company = data
        const branding = useBrandingStore()
        branding.applyBranding({
          display_name: data.display_name,
          logo_url: data.logo_url,
          primary_color: data.primary_color,
          secondary_color: data.secondary_color,
          company_id: data.id,
        })
        const auth = useAuthStore()
        if (auth.user) {
          const updated = {
            ...auth.user,
            display_name: data.display_name,
            logo_url: data.logo_url,
            primary_color: data.primary_color,
            secondary_color: data.secondary_color,
          }
          auth.user = updated
          localStorage.setItem('rf_user', JSON.stringify(updated))
        }
        useOverviewStore().data = null
        return data
      } catch (err) {
        const msg = err?.response?.data
        if (msg && typeof msg === 'object') {
          this.saveError = Object.entries(msg)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
            .join(' | ')
        } else {
          this.saveError = 'Ayarlar kaydedilemedi.'
        }
        throw err
      } finally {
        this.saving = false
      }
    },

    async fetchPersonnel() {
      this.personnelLoading = true
      this.personnelError = ''
      try {
        const { data } = await apiClient.get('personnel/')
        this.personnel = data.personeller ?? []
        return this.personnel
      } catch {
        this.personnelError = 'Personel listesi yüklenemedi.'
        this.personnel = []
        return []
      } finally {
        this.personnelLoading = false
      }
    },

    async addPersonnel(payload) {
      this.personnelError = ''
      try {
        const { data } = await apiClient.post('personnel/', payload)
        await this.fetchPersonnel()
        return data.personel
      } catch (err) {
        this.personnelError = err?.response?.data?.error ?? 'Personel eklenemedi.'
        throw err
      }
    },

    async fetchSystemStatus() {
      try {
        const { data, status } = await apiClient.get('health/', { validateStatus: () => true })
        this.systemStatus = {
          ok: status < 500,
          clickhouse: data?.stores?.clickhouse ?? 'unknown',
          relational: data?.stores?.relational ?? 'ok',
        }
      } catch {
        this.systemStatus = { ok: false, clickhouse: 'unknown', relational: 'unknown' }
      }
    },
  },
})
