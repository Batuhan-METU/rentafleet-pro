import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

export const useRentalStore = defineStore('rental', {
  state: () => ({
    rentals: [],
    summary: { aktif: 0, gelecek: 0, gecmis: 0 },
    loading: false,
    error: false,
    creating: false,
    cancellingId: null,
  }),

  getters: {
    activeRentals: (state) => state.rentals.filter((r) => r.donem_kodu === 'AKTIF'),
    upcomingRentals: (state) => state.rentals.filter((r) => r.donem_kodu === 'GELECEK'),
    pastRentals: (state) => state.rentals.filter((r) => r.donem_kodu === 'GECMIS'),
  },

  actions: {
    async fetchRentals() {
      this.loading = true
      this.error = false
      try {
        const { data } = await apiClient.get('rentals/')
        this.rentals = data.kiralamalar ?? []
        this.summary = data.ozet ?? { aktif: 0, gelecek: 0, gecmis: 0 }
      } catch {
        this.error = true
        this.rentals = []
      } finally {
        this.loading = false
      }
    },

    async createRental(payload) {
      this.creating = true
      try {
        const { data } = await apiClient.post('rentals/', payload)
        this.rentals.unshift(data)
        if (data.donem_kodu === 'AKTIF') this.summary.aktif += 1
        else if (data.donem_kodu === 'GELECEK') this.summary.gelecek += 1
        else if (data.donem_kodu === 'GECMIS') this.summary.gecmis += 1
        return data
      } finally {
        this.creating = false
      }
    },

    async cancelRental(rentalId) {
      this.cancellingId = rentalId
      try {
        const { data } = await apiClient.post(`rentals/${rentalId}/cancel/`)
        const idx = this.rentals.findIndex((r) => r.id === rentalId)
        if (idx !== -1) {
          const prev = this.rentals[idx]
          if (prev.donem_kodu === 'AKTIF') this.summary.aktif = Math.max(0, this.summary.aktif - 1)
          else if (prev.donem_kodu === 'GELECEK') this.summary.gelecek = Math.max(0, this.summary.gelecek - 1)
          this.rentals.splice(idx, 1)
        }
        return data
      } finally {
        this.cancellingId = null
      }
    },
  },
})
