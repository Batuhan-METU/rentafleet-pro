import { defineStore } from 'pinia'
import apiClient from '../services/api.js'
import { VEHICLE_STATUS_LABELS } from '../utils/vehicleStatus.js'

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

const MARKET_CACHE_PREFIX = 'rf_market_v1_'

function vehicleMarketCacheKey(vehicleId, baslangic = null, bitis = null) {
  if (!baslangic && !bitis) return `${MARKET_CACHE_PREFIX}${todayLocalDate()}_${vehicleId}`
  return `${MARKET_CACHE_PREFIX}${baslangic}_${bitis}_${vehicleId}`
}

// Yalnızca "varsayılan pencere" anahtarlarını hedefler (rf_market_v1_<tarih>_<id>);
// açık alış/dönüş pencereli anahtarlar (rf_market_v1_<alis>_<donus>_<id>) kullanıcının
// aradığı belirli tarih aralıklarını temsil eder ve kendi kendini sınırlar, silinmez.
const DEFAULT_WINDOW_KEY_RE = /^rf_market_v1_(\d{4}-\d{2}-\d{2})_[^_]+$/

// Bugüne ait olmayan varsayılan-pencere market önbelleklerini temizler;
// aksi halde localStorage her gün yeni bir anahtar biriktirir ve hiç boşalmaz.
function pruneStaleMarketCache() {
  const today = todayLocalDate()
  const staleKeys = []
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i)
    const match = key && key.match(DEFAULT_WINDOW_KEY_RE)
    if (match && match[1] !== today) {
      staleKeys.push(key)
    }
  }
  for (const key of staleKeys) {
    try {
      localStorage.removeItem(key)
    } catch {
      // localStorage erişilemedi; sessizce geç
    }
  }
}

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

export const useVehicleStore = defineStore('vehicle', {
  state: () => ({
    vehicles: [],
    loading: false,
    error: false,

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

    async fetchCompetitorPrices(id, { force = false, baslangic = null, bitis = null } = {}) {
      const slot = this.marketSlotKey(id, baslangic, bitis)
      const params = {}
      if (baslangic && bitis) {
        params.baslangic_tarihi = baslangic
        params.bitis_tarihi = bitis
      }
      if (force) {
        params.force = 'true'
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
          timeout: 120000,
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
          timeout: 120000,
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
