import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

const PAST_PAGE_SIZE = 20

export const useRentalStore = defineStore('rental', {
  state: () => ({
    // Aktif + Gelecek — filo büyüklüğüyle sınırlı, hep tek seferde çekilir.
    // Geçmiş buna HİÇBİR ZAMAN dahil değildir (aşağıya bkz.).
    rentals: [],
    summary: {
      active: 0,
      active_overdue: 0,
      upcoming: 0,
      past: 0,
      past_on_time: 0,
      past_early: 0,
      past_late: 0,
    },
    loading: false,
    error: false,
    creating: false,
    cancellingId: null,
    previewingId: null,
    returningId: null,
    extendingId: null,

    // Geçmiş kiralamalar — gerçek sunucu sayfalaması (20/sayfa), hangi
    // sayfaya basılırsa sadece onun verisi çekilir.
    pastRentals: [],
    pastPage: 1,
    pastTotalPages: 1,
    pastCount: 0,
    pastLoading: false,
    pastError: false,
  }),

  getters: {
    activeRentals: (state) => state.rentals.filter((r) => r.period_code === 'ACTIVE'),
    upcomingRentals: (state) => state.rentals.filter((r) => r.period_code === 'UPCOMING'),
    // Bildirim zili (NotificationBell.vue) için — teslim tarihi geçmiş ama
    // henüz teslim alınmamış aktif kiralamalar. Ayrı bir "okundu/kapatıldı"
    // durumu yok: bir kiralama uzatılıp/teslim alınıp `is_overdue` false
    // olduğunda bu liste kendiliğinden küçülür.
    overdueRentals: (state) => state.rentals.filter((r) => r.is_overdue),
  },

  actions: {
    _mergeSummary(summary) {
      if (summary) this.summary = { ...this.summary, ...summary }
    },

    // Bildirim zili başka bir sayfadayken mount olduğunda çağırır — Kiralamalar
    // sayfası zaten fetchRentals() yaptıysa gereksiz ikinci bir istek atılmaz.
    async ensureRentalsLoaded() {
      if (!this.rentals.length && !this.loading) await this.fetchRentals()
    },

    // Aktif/Gelecek — iki küçük istek paralel çekilir; her yanıt zaten TAM
    // özet (summary) içerir, hangisinden gelirse gelsin aynıdır.
    async fetchRentals() {
      this.loading = true
      this.error = false
      try {
        const [activeRes, upcomingRes] = await Promise.all([
          apiClient.get('rentals/', { params: { period: 'ACTIVE' } }),
          apiClient.get('rentals/', { params: { period: 'UPCOMING' } }),
        ])
        this.rentals = [
          ...(activeRes.data.rentals ?? []),
          ...(upcomingRes.data.rentals ?? []),
        ]
        this._mergeSummary(upcomingRes.data.summary)
      } catch {
        this.error = true
        this.rentals = []
      } finally {
        this.loading = false
      }
    },

    // Geçmiş kiralamalar — asla tek seferde tamamı çekilmez. `returnTiming`
    // ('TUMU' | 'ON_TIME' | 'EARLY' | 'LATE') sunucu tarafında filtrelenir.
    async fetchPastRentals({ page = 1, returnTiming = null } = {}) {
      this.pastLoading = true
      this.pastError = false
      try {
        const params = { period: 'PAST', page }
        if (returnTiming && returnTiming !== 'TUMU') params.return_timing = returnTiming
        const { data } = await apiClient.get('rentals/', { params })
        this.pastRentals = data.results ?? []
        this.pastCount = data.count ?? 0
        this.pastPage = page
        this.pastTotalPages = Math.max(1, Math.ceil((data.count ?? 0) / PAST_PAGE_SIZE))
        this._mergeSummary(data.summary)
      } catch {
        this.pastError = true
        this.pastRentals = []
      } finally {
        this.pastLoading = false
      }
    },

    // Araç Detayı sekmesindeki tam kiralama geçmişi — dönem/sayfalama
    // olmadan, tek bir aracın TÜM kiralamaları (durumu ne olursa olsun).
    async fetchVehicleRentalHistory(vehicleId) {
      const { data } = await apiClient.get('rentals/', { params: { vehicle_id: vehicleId } })
      return data.rentals ?? []
    },

    async createRental(payload) {
      this.creating = true
      try {
        const { data } = await apiClient.post('rentals/', payload)
        this.rentals.unshift(data)
        if (data.period_code === 'ACTIVE') this.summary.active += 1
        else if (data.period_code === 'UPCOMING') this.summary.upcoming += 1
        return data
      } finally {
        this.creating = false
      }
    },

    // Gelecek kiralama: doğrudan iptal (fiyat farkı yok), listeden kalkar.
    // Aktif kiralama (teslim tarihi geçmiş olsa da): iptal = erken teslim —
    // sunucu farkı hesaplayıp kapatır, kayıt Geçmiş'e düşer (artık `rentals`
    // içinde tutulmaz, bir sonraki Geçmiş sayfa isteğinde görünür).
    async cancelRental(rentalId) {
      this.cancellingId = rentalId
      try {
        const { data } = await apiClient.post(`rentals/${rentalId}/cancel/`)
        const idx = this.rentals.findIndex((r) => r.id === rentalId)
        if (idx !== -1) {
          const prev = this.rentals[idx]
          this.rentals.splice(idx, 1)
          if (prev.period_code === 'ACTIVE') {
            this.summary.active = Math.max(0, this.summary.active - 1)
            if (prev.is_overdue) this.summary.active_overdue = Math.max(0, this.summary.active_overdue - 1)
          } else if (prev.period_code === 'UPCOMING') {
            this.summary.upcoming = Math.max(0, this.summary.upcoming - 1)
          }
          if (data.rental) this.summary.past += 1
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
        if (idx !== -1) {
          const prev = this.rentals[idx]
          // Uzatma yeni bitiş tarihini ileri taşıdığı için genelde
          // "teslim alınmadı" uyarısını kaldırır (is_overdue true→false).
          if (prev.is_overdue && !data.is_overdue) {
            this.summary.active_overdue = Math.max(0, this.summary.active_overdue - 1)
          } else if (!prev.is_overdue && data.is_overdue) {
            this.summary.active_overdue += 1
          }
          this.rentals.splice(idx, 1, data)
        }
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

    // Kalıcı teslim alma — kiralamayı kapatır, aracı serbest bırakır.
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
          this.rentals.splice(idx, 1)
          if (prev.period_code === 'ACTIVE') {
            this.summary.active = Math.max(0, this.summary.active - 1)
            if (prev.is_overdue) this.summary.active_overdue = Math.max(0, this.summary.active_overdue - 1)
          } else if (prev.period_code === 'UPCOMING') {
            this.summary.upcoming = Math.max(0, this.summary.upcoming - 1)
          }
          this.summary.past += 1
        }
        return data
      } finally {
        this.returningId = null
      }
    },
  },
})
