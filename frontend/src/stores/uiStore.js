import { defineStore } from 'pinia'

const MANAGER_ONLY_VIEWS = new Set(['overview', 'pricing', 'rentals', 'loans'])

// Detay ekranı türleri (araç/sürücü/kredi) — hash formatı, state anahtarı ve
// liste görünümü türe göre değişir ama açma/kapama MANTIĞI birebir aynıdır;
// bu tablo o tekrarı tek noktada tutar (bkz. audit bulgusu #22).
const DETAIL_KINDS = {
  vehicle: { view: 'vehicle-detail', idKey: 'activeVehicleId', listView: 'vehicles', hashPrefix: 'vehicles' },
  driver: { view: 'driver-detail', idKey: 'activeDriverId', listView: 'drivers', hashPrefix: 'drivers' },
  loan: { view: 'loan-detail', idKey: 'activeLoanId', listView: 'loans', hashPrefix: 'loans' },
}

export const useUiStore = defineStore('ui', {
  state: () => ({
    aiChatOpen: false,
    activeView: 'overview',
    activeVehicleId: null,
    activeDriverId: null,
    activeLoanId: null,
    initialized: false,
  }),

  actions: {
    initNavigation(isFleetManager) {
      if (this.initialized) return
      const parsed = this.parseHash(isFleetManager)
      this.activeView = parsed.view
      this.activeVehicleId = parsed.vehicleId
      this.activeDriverId = parsed.driverId
      this.activeLoanId = parsed.loanId
      this.syncHash(parsed.view, parsed.vehicleId, parsed.driverId, parsed.loanId)
      this.initialized = true
    },

    syncHash(view, vehicleId = null, driverId = null, loanId = null) {
      const target = vehicleId != null
        ? `#/vehicles/${vehicleId}`
        : driverId != null
          ? `#/drivers/${driverId}`
          : loanId != null
            ? `#/loans/${loanId}`
            : `#/${view}`
      if (window.location.hash !== target) {
        const base = `${window.location.pathname}${window.location.search}`
        window.history.replaceState(null, '', `${base}${target}`)
      }
    },

    parseHash(isFleetManager) {
      const raw = window.location.hash.replace(/^#\/?/, '').split('?')[0]
      const fallback = isFleetManager ? 'overview' : 'vehicles'
      if (!raw) return { view: fallback, vehicleId: null, driverId: null, loanId: null }

      for (const [kind, cfg] of Object.entries(DETAIL_KINDS)) {
        const match = raw.match(new RegExp(`^${cfg.hashPrefix}/(\\d+)$`))
        if (!match) continue
        const id = Number(match[1])
        return {
          view: cfg.view,
          vehicleId: kind === 'vehicle' ? id : null,
          driverId: kind === 'driver' ? id : null,
          loanId: kind === 'loan' ? id : null,
        }
      }

      if (!isFleetManager && MANAGER_ONLY_VIEWS.has(raw)) return { view: 'vehicles', vehicleId: null, driverId: null, loanId: null }
      return { view: raw, vehicleId: null, driverId: null, loanId: null }
    },

    navigate(view, { isFleetManager = true } = {}) {
      if (!view) return
      if (!isFleetManager && MANAGER_ONLY_VIEWS.has(view)) return
      this.activeView = view
      this.activeVehicleId = null
      this.activeDriverId = null
      this.activeLoanId = null
      window.location.hash = `#/${view}`
    },

    // Ortak açma/kapama mantığı — türe özel `open*Detail`/`close*Detail`
    // aksiyonları (aşağıda) geriye dönük uyumluluk için birer ince sarmalayıcı
    // olarak korunur; çağıran bileşenler hiçbir şey değiştirmeden çalışmaya
    // devam eder.
    _openDetail(kind, id) {
      if (id == null) return
      const cfg = DETAIL_KINDS[kind]
      this.activeView = cfg.view
      this.activeVehicleId = kind === 'vehicle' ? id : null
      this.activeDriverId = kind === 'driver' ? id : null
      this.activeLoanId = kind === 'loan' ? id : null
      window.location.hash = `#/${cfg.hashPrefix}/${id}`
    },

    _closeDetail(kind) {
      const cfg = DETAIL_KINDS[kind]
      this.activeView = cfg.listView
      this[cfg.idKey] = null
      window.location.hash = `#/${cfg.listView}`
    },

    openVehicleDetail(vehicleId) {
      this._openDetail('vehicle', vehicleId)
    },

    closeVehicleDetail() {
      this._closeDetail('vehicle')
    },

    openDriverDetail(driverId) {
      this._openDetail('driver', driverId)
    },

    closeDriverDetail() {
      this._closeDetail('driver')
    },

    openLoanDetail(loanId) {
      this._openDetail('loan', loanId)
    },

    closeLoanDetail() {
      this._closeDetail('loan')
    },

    onHashChange(isFleetManager) {
      const parsed = this.parseHash(isFleetManager)
      this.activeView = parsed.view
      this.activeVehicleId = parsed.vehicleId
      this.activeDriverId = parsed.driverId
      this.activeLoanId = parsed.loanId
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
