// Kiracı white-label marka durumu (subdomain branding).
import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

const DEFAULTS = {
  display_name: 'RentA-Fleet PRO',
  logo_url: null,
  primary_color: '#3B82F6',
  secondary_color: '#1E3A8A',
}

function shadeHex(hex, percent) {
  const num = parseInt(hex.replace('#', ''), 16)
  const r = Math.min(255, Math.max(0, (num >> 16) + percent))
  const g = Math.min(255, Math.max(0, ((num >> 8) & 0xff) + percent))
  const b = Math.min(255, Math.max(0, (num & 0xff) + percent))
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`
}

export const useBrandingStore = defineStore('branding', {
  state: () => ({
    display_name: DEFAULTS.display_name,
    logo_url: DEFAULTS.logo_url,
    primary_color: DEFAULTS.primary_color,
    secondary_color: DEFAULTS.secondary_color,
    tenant_id: null,
    loaded: false,
  }),

  getters: {
    panelTitle: (state) => state.display_name,
    logoInitials: (state) => {
      const words = state.display_name.trim().split(/\s+/).filter(Boolean)
      if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase()
      return state.display_name.slice(0, 2).toUpperCase()
    },
  },

  actions: {
    applyBranding(data = {}) {
      this.display_name = data.display_name || DEFAULTS.display_name
      this.logo_url = data.logo_url || null
      this.primary_color = data.primary_color || DEFAULTS.primary_color
      this.secondary_color = data.secondary_color || DEFAULTS.secondary_color
      this.tenant_id = data.tenant_id ?? null
      this._injectCssVariables()
      document.title = this.display_name
    },

    applyFromUser(user) {
      if (!user) return
      this.applyBranding({
        display_name: user.display_name || user.branding?.display_name,
        logo_url: user.logo_url ?? user.branding?.logo_url,
        primary_color: user.primary_color || user.branding?.primary_color,
        secondary_color: user.secondary_color || user.branding?.secondary_color,
        tenant_id: user.company_id,
      })
    },

    _injectCssVariables() {
      const root = document.documentElement
      const primary = this.primary_color
      const secondary = this.secondary_color
      root.style.setProperty('--primary-color', primary)
      root.style.setProperty('--secondary-color', secondary)
      root.style.setProperty('--color-brand-500', primary)
      root.style.setProperty('--color-brand-600', primary)
      root.style.setProperty('--color-brand-700', shadeHex(primary, -20))
      root.style.setProperty('--color-brand-900', secondary)
      root.style.setProperty('--color-brand-100', shadeHex(primary, 80))
      root.style.setProperty('--color-brand-50', shadeHex(primary, 110))
    },

    async fetchBranding() {
      try {
        const { data } = await apiClient.get('tenant/branding/')
        this.applyBranding(data)
      } catch {
        this.applyBranding(DEFAULTS)
      } finally {
        this.loaded = true
      }
    },
  },
})
