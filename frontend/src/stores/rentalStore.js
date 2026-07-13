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
    previewingId: null,
    returningId: null,
    extendingId: null,
  }),

  getters: {
    activeRentals: (state) => state.rentals.filter((r) => r.donem_kodu === 'AKTIF'),
    upcomingRentals: (state) => state.rentals.filter((r) => r.donem_kodu === 'GELECEK'),
    pastRentals: (state) => state.rentals.filter((r) => r.donem_kodu === 'GECMIS'),
    onTimeRentals: (state) =>
      state.rentals.filter((r) => r.donem_kodu === 'GECMIS' && r.return_status === 'ON_TIME'),
    earlyReturnedRentals: (state) =>
      state.rentals.filter((r) => r.donem_kodu === 'GECMIS' && r.return_status === 'EARLY'),
    lateReturnedRentals: (state) =>
      state.rentals.filter((r) => r.donem_kodu === 'GECMIS' && r.return_status === 'LATE'),
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

    // Gelecek rezervasyon: doğrudan iptal (fiyat farkı yok), listeden kalkar.
    // Aktif rezervasyon: iptal = erken teslim — sunucu farkı hesaplayıp kapatır,
    // yanıt `kiralama` alanıyla birlikte gelir ve kayıt geçmişe düşer.
    async cancelRental(rentalId) {
      this.cancellingId = rentalId
      try {
        const { data } = await apiClient.post(`rentals/${rentalId}/cancel/`)
        const idx = this.rentals.findIndex((r) => r.id === rentalId)
        if (idx !== -1) {
          const prev = this.rentals[idx]
          if (data.kiralama) {
            if (prev.donem_kodu === 'AKTIF') this.summary.aktif = Math.max(0, this.summary.aktif - 1)
            this.summary.gecmis += 1
            this.rentals.splice(idx, 1, data.kiralama)
          } else {
            if (prev.donem_kodu === 'GELECEK') this.summary.gelecek = Math.max(0, this.summary.gelecek - 1)
            this.rentals.splice(idx, 1)
          }
        }
        return data
      } finally {
        this.cancellingId = null
      }
    },

    // Aktif kiralamayı uzat — çakışma varsa sunucu hata döner, hiçbir şey değişmez.
    async extendRental(rentalId, { new_ended_at } = {}) {
      this.extendingId = rentalId
      try {
        const { data } = await apiClient.post(`rentals/${rentalId}/extend/`, { new_ended_at })
        const idx = this.rentals.findIndex((r) => r.id === rentalId)
        if (idx !== -1) this.rentals.splice(idx, 1, data)
        return data
      } finally {
        this.extendingId = null
      }
    },

    // Canlı önizleme — hiçbir kaydı değiştirmez, yalnızca farkı hesaplar.
    // Modal'daki tarih/not girişi değiştikçe (debounce'lu) çağrılır.
    async previewReturn(rentalId, { actual_return_at, notes = '' } = {}) {
      this.previewingId = rentalId
      try {
        const { data } = await apiClient.post(`rentals/${rentalId}/return/`, {
          actual_return_at,
          notes,
          preview: true,
        })
        return data
      } finally {
        this.previewingId = null
      }
    },

    // Kalıcı teslim alma — rezervasyonu kapatır, aracı serbest bırakır.
    async returnRental(rentalId, { actual_return_at, notes = '' } = {}) {
      this.returningId = rentalId
      try {
        const { data } = await apiClient.post(`rentals/${rentalId}/return/`, {
          actual_return_at,
          notes,
          preview: false,
        })
        const idx = this.rentals.findIndex((r) => r.id === rentalId)
        if (idx !== -1) {
          const prev = this.rentals[idx]
          if (prev.donem_kodu === 'AKTIF') this.summary.aktif = Math.max(0, this.summary.aktif - 1)
          else if (prev.donem_kodu === 'GELECEK') this.summary.gelecek = Math.max(0, this.summary.gelecek - 1)
          this.summary.gecmis += 1
          if (data.kiralama) this.rentals.splice(idx, 1, data.kiralama)
        }
        return data
      } finally {
        this.returningId = null
      }
    },
  },
})
