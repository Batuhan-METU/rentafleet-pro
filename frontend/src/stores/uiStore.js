import { defineStore } from 'pinia'

const MANAGER_ONLY_VIEWS = new Set(['overview', 'pricing', 'reservations'])

export const useUiStore = defineStore('ui', {
  state: () => ({
    aiChatOpen: false,
    activeView: 'overview',
    initialized: false,
  }),

  actions: {
    initNavigation(isFleetManager) {
      if (this.initialized) return
      const raw = window.location.hash.replace(/^#\/?/, '').split('?')[0]
      const fallback = isFleetManager ? 'overview' : 'vehicles'
      let view = raw || fallback
      if (!isFleetManager && MANAGER_ONLY_VIEWS.has(view)) view = 'vehicles'
      this.activeView = view
      this.syncHash(view)
      this.initialized = true
    },

    syncHash(view) {
      const target = `#/${view}`
      if (window.location.hash !== target) {
        const base = `${window.location.pathname}${window.location.search}`
        window.history.replaceState(null, '', `${base}${target}`)
      }
    },

    parseViewFromHash(isFleetManager) {
      const raw = window.location.hash.replace(/^#\/?/, '').split('?')[0]
      const fallback = isFleetManager ? 'overview' : 'vehicles'
      if (!raw) return fallback
      if (!isFleetManager && MANAGER_ONLY_VIEWS.has(raw)) return 'vehicles'
      return raw
    },

    navigate(view, { isFleetManager = true } = {}) {
      if (!view) return
      if (!isFleetManager && MANAGER_ONLY_VIEWS.has(view)) return
      this.activeView = view
      window.location.hash = `#/${view}`
    },

    onHashChange(isFleetManager) {
      this.activeView = this.parseViewFromHash(isFleetManager)
    },

    openAiChat() {
      this.aiChatOpen = true
    },
    closeAiChat() {
      this.aiChatOpen = false
    },
    toggleAiChat() {
      this.aiChatOpen = !this.aiChatOpen
    },
  },
})
