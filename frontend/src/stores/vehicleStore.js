import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

// Canlı takip zamanlayıcısı store state'i DIŞINDA tutulur: interval kimliği
// reaktif/serileştirilebilir bir değer olmamalı ve birden fazla kez
// kurulmamalıdır (bellek sızıntısı/çift interval önlenir).
let liveTimer = null
const LIVE_POLL_MS = 5000

function todayLocalDate() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function vehicleMarketCacheKey(vehicleId, baslangic = null, bitis = null) {
  if (!baslangic && !bitis) return `rf_market_v1_${todayLocalDate()}_${vehicleId}`
  return `rf_market_v1_${baslangic}_${bitis}_${vehicleId}`
}

// Backend'in İngilizce durum kodlarının Türkçe karşılıkları + Tailwind
// renk sınıfları. Dönüşüm mantığının TEK kaynağı burasıdır.
const STATUS_MAP = {
  AVAILABLE: {
    label: 'Müsait',
    badge: 'bg-emerald-100 text-emerald-700 ring-emerald-600/20',
    dot: 'bg-emerald-500',
    accent: 'text-emerald-600',
  },
  RENTED: {
    label: 'Kirada',
    badge: 'bg-blue-100 text-blue-700 ring-blue-600/20',
    dot: 'bg-blue-500',
    accent: 'text-blue-600',
  },
  MAINTENANCE: {
    label: 'Bakımda',
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

export const useVehicleStore = defineStore('vehicle', {
  state: () => ({
    vehicles: [],
    loading: false,
    error: false,

    // Seçili aracın detay (AI/analitik) verileri — modal kullanır.
    currentVehicleScore: null,
    currentVehicleFuelData: null,
    currentVehicleAnomalies: null,
    detailLoading: false,
    detailError: false,

    // Kart rozetleri kaldırıldı — skor artık sürücüye aittir (driverStore).
    // Piyasa rakip fiyatları (PricingManager).
    competitorPricesById: {},
    marketListingsById: {},
    marketMetaById: {},
    marketStatisticsById: {},
    marketSyncing: false,
    competitorLoadingId: null,

    // Canlı takip: tüm araçların en güncel konum/hız/durum verisi.
    liveVehicles: [],
    liveTracking: false,

    // Dashboard analitiği (metrik kartları + grafikler).
    fleetAnalytics: null,
    analyticsLoading: false,

    // Öngörücü bakım uyarıları.
    maintenanceAlerts: [],
    maintenanceLoading: false,
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
    marketSlotKey(id, baslangic = null, bitis = null) {
      if (!baslangic && !bitis) return String(id)
      return `${id}|${baslangic}|${bitis}`
    },

    async fetchVehicles() {
      this.loading = true
      this.error = false
      try {
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

    // Güncel kiracının skorunu çeker (skor sürücüye aittir).
    async fetchCurrentRenterScore(vehicleId) {
      const { data } = await apiClient.get(`vehicles/${vehicleId}/current-renter-score/`)
      if (!data.kiraci_var_mi) {
        this.currentVehicleScore = null
        return null
      }
      this.currentVehicleScore = {
        driver_id: data.driver_id,
        driver_score: data.driver_score,
        summary: data.summary,
      }
      return this.currentVehicleScore
    },

    async fetchCompetitorPrices(id, { force = false, baslangic = null, bitis = null } = {}) {
      const slot = this.marketSlotKey(id, baslangic, bitis)
      const params = {}
      if (baslangic && bitis) {
        params.baslangic_tarihi = baslangic
        params.bitis_tarihi = bitis
      }
      const cacheKey = vehicleMarketCacheKey(id, baslangic, bitis)

      if (!force) {
        try {
          const raw = localStorage.getItem(cacheKey)
          if (raw) {
            const data = JSON.parse(raw)
            this._applyVehicleCompetitorPayload(slot, data)
            if (this.marketListingsById[slot]?.length) {
              return this.competitorPricesById[slot]
            }
          }
        } catch {
          // önbellek okunamadı
        }
      }

      if (!force && this.marketListingsById[slot]?.length) {
        return this.competitorPricesById[slot]
      }

      this.competitorLoadingId = slot
      try {
        const { data } = await apiClient.get(`vehicles/${id}/competitor-prices/`, {
          params,
          timeout: baslangic && bitis ? 120000 : 15000,
        })
        this._applyVehicleCompetitorPayload(slot, data)
        try {
          localStorage.setItem(cacheKey, JSON.stringify(data))
        } catch {
          // localStorage dolu
        }
      } catch {
        this.competitorPricesById[slot] = []
        this.marketListingsById[slot] = []
        this.marketStatisticsById[slot] = null
      } finally {
        if (this.competitorLoadingId === slot) this.competitorLoadingId = null
      }
      return this.competitorPricesById[slot]
    },

    _applyVehicleCompetitorPayload(slot, data) {
      this.competitorPricesById[slot] = data.rakipler ?? []
      this.marketListingsById[slot] = this._mapMatchedVehicles(data)
      this.marketMetaById[slot] = {
        matchedSegment: data.matchedSegment,
        vehicleCount: data.vehicleCount,
        arama: data.arama,
      }
      this.marketStatisticsById[slot] = data.statistics ?? null
    },

    async fetchAllCompetitorPrices({ force = false, baslangic = null, bitis = null } = {}) {
      if (!force && Object.keys(this.marketListingsById).length > 0) {
        return Object.keys(this.marketListingsById).length
      }
      this.marketSyncing = true
      try {
        const params = {}
        if (baslangic && bitis) {
          params.baslangic_tarihi = baslangic
          params.bitis_tarihi = bitis
        }
        const { data } = await apiClient.get('fleet/competitor-prices/', {
          params,
          timeout: baslangic && bitis ? 120000 : 120000,
        })
        const araclar = data.araclar ?? {}
        this._applyCompetitorPayloadMap(araclar, data.arama)
        return Object.keys(araclar).length
      } catch {
        return Object.keys(this.marketListingsById).length
      } finally {
        this.marketSyncing = false
      }
    },

    async syncFleetMarketPrices() {
      return this.fetchAllCompetitorPrices({ force: true })
    },

    _applyCompetitorPayloadMap(araclar, aramaFallback = null) {
      for (const [rawId, payload] of Object.entries(araclar)) {
        const id = Number(rawId)
        this.competitorPricesById[id] = payload.rakipler ?? []
        this.marketListingsById[id] = this._mapMatchedVehicles(payload)
        this.marketMetaById[id] = {
          matchedSegment: payload.matchedSegment,
          vehicleCount: payload.vehicleCount,
          arama: payload.arama ?? aramaFallback,
        }
        this.marketStatisticsById[id] = payload.statistics ?? null
      }
    },

    _mapMatchedVehicles(payload) {
      if (payload.matchedVehicles?.length) {
        return payload.matchedVehicles.map((row) => ({
          provider: row.provider,
          brand: row.brand,
          model: row.model,
          segment: row.segment,
          kaynak: row.provider,
          benzer_arac: `${row.brand} ${row.model}`.trim(),
          gunluk_fiyat: row.dailyPrice,
          dailyPrice: row.dailyPrice,
        }))
      }
      return payload.piyasa_teklifleri ?? []
    },

    // Tek aracın güncel kiracı skorunu çeker.
    async fetchVehicleScore(id) {
      return this.fetchCurrentRenterScore(id)
    },

    // Tek aracın yakıt optimizasyon verisini çeker. Hata orkestratöre fırlatılır.
    async fetchVehicleFuelData(id) {
      const { data } = await apiClient.get(`vehicles/${id}/fuel-optimization/`)
      this.currentVehicleFuelData = data
      return data
    },

    // Tek aracın güvenlik anomalilerini çeker. Hata orkestratöre fırlatılır.
    async fetchVehicleAnomalies(id) {
      const { data } = await apiClient.get(`vehicles/${id}/anomalies/`)
      this.currentVehicleAnomalies = data
      return data
    },

    // Modal için skor + yakıt + anomali verisini paralel yükleyen orkestratör.
    async loadVehicleDetail(id) {
      this.detailLoading = true
      this.detailError = false
      this.currentVehicleScore = null
      this.currentVehicleFuelData = null
      this.currentVehicleAnomalies = null
      try {
        await Promise.all([
          this.fetchVehicleScore(id),
          this.fetchVehicleFuelData(id),
          this.fetchVehicleAnomalies(id),
        ])
      } catch {
        this.detailError = true
      } finally {
        this.detailLoading = false
      }
    },

    // Modal kapanınca detay durumunu sıfırlar.
    clearVehicleDetail() {
      this.currentVehicleScore = null
      this.currentVehicleFuelData = null
      this.currentVehicleAnomalies = null
      this.detailError = false
      this.detailLoading = false
    },

    // Tüm araçların en güncel canlı konumunu çeker; hata olursa eski veriyi
    // korur (canlı ekran "donmaz", bir sonraki başarılı çağrıda güncellenir).
    async fetchLiveStream() {
      try {
        const { data } = await apiClient.get('vehicles/live-stream/')
        this.liveVehicles = data.araclar ?? []
      } catch {
        // Geçici ağ hatası: mevcut liveVehicles korunur.
      }
    },

    // Canlı takibi başlatır: anında bir kez çeker, ardından her 5 sn'de bir
    // yeniler. Tekrar çağrılırsa yeni interval kurmaz (çift interval/sızıntı
    // engeli).
    initLiveTracking() {
      if (liveTimer !== null) return
      this.liveTracking = true
      this.fetchLiveStream()
      liveTimer = setInterval(() => this.fetchLiveStream(), LIVE_POLL_MS)
    },

    // Canlı takibi durdurur ve interval'i temizler (bileşen unmount olunca
    // çağrılmalı). Birden fazla çağrıya karşı güvenlidir.
    stopLiveTracking() {
      if (liveTimer !== null) {
        clearInterval(liveTimer)
        liveTimer = null
      }
      this.liveTracking = false
    },

    // Dashboard analitiğini çeker. Eşzamanlı/tekrar çağrılara karşı korumalı;
    // veri zaten varsa yeniden çekmez (force=true ile zorlanabilir).
    async fetchFleetAnalytics(force = false) {
      if (this.analyticsLoading) return
      if (this.fleetAnalytics && !force) return
      this.analyticsLoading = true
      try {
        const { data } = await apiClient.get('fleet/analytics/')
        this.fleetAnalytics = data
      } catch {
        // Analitik gösterilemez; dashboard'ın geri kalanı çalışmaya devam eder.
      } finally {
        this.analyticsLoading = false
      }
    },

    // Öngörücü bakım uyarılarını çeker.
    async fetchMaintenanceAlerts() {
      this.maintenanceLoading = true
      try {
        const { data } = await apiClient.get('vehicles/maintenance-alerts/')
        this.maintenanceAlerts = data.araclar ?? []
      } catch {
        // Uyarılar gösterilemez; ekranın geri kalanı çalışmaya devam eder.
      } finally {
        this.maintenanceLoading = false
      }
    },
  },
})
