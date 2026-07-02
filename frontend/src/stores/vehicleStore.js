import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

// Canlı takip zamanlayıcısı store state'i DIŞINDA tutulur: interval kimliği
// reaktif/serileştirilebilir bir değer olmamalı ve birden fazla kez
// kurulmamalıdır (bellek sızıntısı/çift interval önlenir).
let liveTimer = null
const LIVE_POLL_MS = 5000

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
    // Kart için araç kimliği -> önerilen fiyat verisi önbelleği.
    pricingById: {},
    // Piyasa rakip fiyatları ve AI önerisi (PricingManager).
    competitorPricesById: {},
    marketPricingById: {},
    marketListingsById: {},
    marketMetaById: {},
    marketStatisticsById: {},
    marketSyncing: false,

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

    // Kart için önerilen fiyatı (önbellekli) yükler; hata olursa sessiz kalır.
    async fetchVehiclePricing(id, force = false) {
      if (!force && this.pricingById[id] !== undefined && this.marketPricingById[id]) {
        return this.marketPricingById[id]
      }
      try {
        const { data } = await apiClient.get(`vehicles/${id}/suggested-price/`)
        this.pricingById[id] = { price: data.onerilen_fiyat, reason: data.gerekce }
        this.marketPricingById[id] = {
          onerilen_fiyat: data.onerilen_fiyat,
          ai_tavsiyesi: data.ai_tavsiyesi,
          gerekce: data.gerekce,
          piyasa_ortalamasi: data.piyasa_ortalamasi,
          rakip_sayisi: data.rakip_sayisi ?? 0,
          rakipler: data.rakipler ?? [],
          yield_fiyat: data.yield_fiyat,
          yield_gerekce: data.yield_gerekce,
          taban_fiyat: data.taban_fiyat,
        }
      } catch {
        // Fiyat rozeti gösterilmez; kart yine de çalışır.
      }
      return this.marketPricingById[id]
    },

    async fetchCompetitorPrices(id) {
      try {
        const { data } = await apiClient.get(`vehicles/${id}/competitor-prices/`)
        this.competitorPricesById[id] = data.rakipler ?? []
        this.marketListingsById[id] = this._mapMatchedVehicles(data)
        this.marketMetaById[id] = {
          matchedSegment: data.matchedSegment,
          vehicleCount: data.vehicleCount,
          arama: data.arama,
        }
        this.marketStatisticsById[id] = data.statistics ?? null
      } catch {
        this.competitorPricesById[id] = []
        this.marketListingsById[id] = []
        this.marketStatisticsById[id] = null
      }
      return this.competitorPricesById[id]
    },

    async fetchAllCompetitorPrices() {
      try {
        const { data } = await apiClient.get('fleet/competitor-prices/', { timeout: 60000 })
        const araclar = data.araclar ?? {}
        this._applyCompetitorPayloadMap(araclar, data.arama)
        return Object.keys(araclar).length
      } catch {
        return 0
      }
    },

    async syncFleetMarketPrices() {
      if (this.marketSyncing) return
      this.marketSyncing = true
      this.competitorPricesById = {}
      this.marketListingsById = {}
      this.marketMetaById = {}
      this.marketStatisticsById = {}
      try {
        const { data } = await apiClient.post('fleet/market-prices/sync/', {}, { timeout: 180000 })
        const araclar = data.araclar ?? {}
        if (Object.keys(araclar).length) {
          this._applyCompetitorPayloadMap(araclar, data.arama)
        } else {
          await this.fetchAllCompetitorPrices()
        }
      } catch {
        await this.fetchAllCompetitorPrices()
      } finally {
        this.marketSyncing = false
      }
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
