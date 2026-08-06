import { defineStore } from 'pinia'
import apiClient from '../services/api.js'
import { VEHICLE_STATUS_LABELS } from '../utils/vehicleStatus.js'
import { pruneStaleMarketCache } from './vehicleMarketStore.js'

// Backend'in İngilizce durum kodlarının Tailwind renk sınıfları. Etiket
// metinleri ../utils/vehicleStatus.js'den gelir (TEK kaynak); buradaki
// renk/stil seçimleri yalnızca bu bileşen bağlamına özeldir.
const STATUS_MAP = {
  AVAILABLE: {
    label: VEHICLE_STATUS_LABELS.AVAILABLE,
    badge: 'bg-emerald-100 text-emerald-700 ring-emerald-600/20',
    dot: 'bg-emerald-500',
    accent: 'text-emerald-600',
  },
  RENTED: {
    label: VEHICLE_STATUS_LABELS.RENTED,
    badge: 'bg-blue-100 text-blue-700 ring-blue-600/20',
    dot: 'bg-blue-500',
    accent: 'text-blue-600',
  },
  MAINTENANCE: {
    label: VEHICLE_STATUS_LABELS.MAINTENANCE,
    badge: 'bg-red-100 text-red-700 ring-red-600/20',
    dot: 'bg-red-500',
    accent: 'text-red-600',
  },
}

const STATUS_FALLBACK = {
  label: 'Bilinmiyor',
  badge: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  dot: 'bg-slate-400',
  accent: 'text-slate-500',
}

// Araç CRUD/listeleme — piyasa fiyatı (vehicleMarketStore), canlı takip
// (vehicleLiveTrackingStore) ve öngörücü bakım (vehicleMaintenanceStore)
// buradan ayrıldı; dördü de birbirinden bağımsız kaygılardı, tek store'da
// "god store" oluşturuyordu (audit bulgusu #21).
export const useVehicleStore = defineStore('vehicle', {
  state: () => ({
    vehicles: [],
    loading: false,
    error: false,
  }),

  getters: {
    // İngilizce durum kodunu Türkçe etiket + stillere çeviren yardımcı.
    statusInfo: () => (status) => STATUS_MAP[status] ?? STATUS_FALLBACK,

    // Her aracı, hazır Türkçe `statusInfo` alanıyla zenginleştirir; böylece
    // bileşenler tamamen "aptal" (sadece sunum) kalabilir.
    localizedVehicles: (state) =>
      state.vehicles.map((vehicle) => ({
        ...vehicle,
        statusInfo: STATUS_MAP[vehicle.status] ?? STATUS_FALLBACK,
      })),

    vehicleCount: (state) => state.vehicles.length,

    // Genel bakış sayaçları (Toplam / Müsait / Kirada / Bakımda).
    statusCounts: (state) => {
      const counts = { total: state.vehicles.length, AVAILABLE: 0, RENTED: 0, MAINTENANCE: 0 }
      for (const vehicle of state.vehicles) {
        if (counts[vehicle.status] !== undefined) counts[vehicle.status] += 1
      }
      return counts
    },
  },

  actions: {
    async fetchVehicles() {
      this.loading = true
      this.error = false
      try {
        pruneStaleMarketCache()
        const all = []
        let page = 1
        let hasMore = true
        while (hasMore) {
          const { data } = await apiClient.get(`vehicles/?page=${page}`)
          if (Array.isArray(data)) {
            this.vehicles = data
            return
          }
          const batch = data.results ?? []
          all.push(...batch)
          hasMore = Boolean(data.next)
          page += 1
        }
        this.vehicles = all
      } catch {
        this.error = true
      } finally {
        this.loading = false
      }
    },
  },
})
