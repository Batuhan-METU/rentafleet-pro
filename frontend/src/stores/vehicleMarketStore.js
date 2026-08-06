import { defineStore } from 'pinia'
import apiClient from '../services/api.js'
import { getDefaultRentalWindow } from '../utils/defaultRentalWindow.js'
import { MARKET_CACHE_PREFIX } from '../utils/storageKeys.js'

// Varsayılan pencere ön-yüklemesinin oturum başına yalnızca bir kez
// tetiklenmesini sağlar (reaktif olmasına gerek yok).
let defaultMarketPrefetchStarted = false

function todayLocalDate() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// v2: API yanıt şekli tek bloktan (matchedVehicles/statistics/matchBasis)
// iki bağımsız bloğa (sipp_eslesme/tsb_eslesme) geçti — eski v1 önbellek
// girdileri bu yeni alanlara sahip değil ve sessizce boş sonuç gibi
// okunurdu (üstelik açık tarihli girdiler hiç süresi dolmadığı için
// tarayıcıda KALICI olarak yanlış/boş kalırdı). Öneki değiştirmek eski
// girdileri kalıcı olarak geçersiz kılar, yeni bir fetch tetiklenir
// (bkz. utils/storageKeys.js — MARKET_CACHE_PREFIX).

function vehicleMarketCacheKey(vehicleId, baslangic = null, bitis = null) {
  if (!baslangic && !bitis) return `${MARKET_CACHE_PREFIX}${todayLocalDate()}_${vehicleId}`
  return `${MARKET_CACHE_PREFIX}${baslangic}_${bitis}_${vehicleId}`
}

// Yalnızca "varsayılan pencere" anahtarlarını hedefler (rf_market_v2_<tarih>_<id>);
// açık alış/dönüş pencereli anahtarlar (rf_market_v2_<alis>_<donus>_<id>) kullanıcının
// aradığı belirli tarih aralıklarını temsil eder ve kendi kendini sınırlar, silinmez.
const DEFAULT_WINDOW_KEY_RE = /^rf_market_v2_(\d{4}-\d{2}-\d{2})_[^_]+$/

// Bugüne ait olmayan varsayılan-pencere market önbelleklerini temizler;
// aksi halde localStorage her gün yeni bir anahtar biriktirir ve hiç boşalmaz.
// vehicleStore.fetchVehicles() her araç listesi çekişinde çağırır (bkz. orada).
export function pruneStaleMarketCache() {
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

// Araçların piyasa/rakip fiyat verisi — vehicleStore'dan ayrı, çünkü bu
// TAMAMEN bağımsız bir kaygı (Enuygun eşleşmesi + localStorage önbelleği),
// araç CRUD/listeleme ile hiçbir state paylaşmaz (audit bulgusu #21).
export const useVehicleMarketStore = defineStore('vehicleMarket', {
  state: () => ({
    // Piyasa rakip fiyatları (PricingManager) — iki BAĞIMSIZ eşleşme
    // yöntemi (SIPP / TSB Tip Kodu), her biri kendi bloğunda
    // ({ matchedSegment, vehicleCount, matchedVehicles, statistics,
    // rakipler }), slot anahtarı = marketSlotKey(vehicleId, baslangic, bitis).
    sippMatchById: {},
    tsbMatchById: {},
    marketSyncing: false,
    competitorLoadingId: null,
  }),

  actions: {
    marketSlotKey(id, baslangic = null, bitis = null) {
      if (!baslangic && !bitis) return String(id)
      return `${id}|${baslangic}|${bitis}`
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
            if (slot in this.sippMatchById) return
          }
        } catch {
          // önbellek okunamadı
        }
      }

      if (!force && slot in this.sippMatchById) return

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
        this.sippMatchById[slot] = null
        this.tsbMatchById[slot] = null
      } finally {
        if (this.competitorLoadingId === slot) this.competitorLoadingId = null
      }
    },

    _applyVehicleCompetitorPayload(slot, data) {
      this.sippMatchById[slot] = data.sipp_eslesme ?? null
      this.tsbMatchById[slot] = data.tsb_eslesme ?? null
    },

    // Filodaki TÜM araçların rakip fiyatlarını TEK istekte çeker ve her
    // birini fetchCompetitorPrices'ın (tekil araç) kullandığı AYNI slot
    // anahtarıyla (`marketSlotKey`) önbelleğe yazar — böylece kullanıcı
    // daha sonra Fiyatlandırma'da aynı tarih aralığıyla bir araç seçtiğinde
    // veri zaten hazır olur, tekrar Enuygun'a gidilmez.
    async fetchAllCompetitorPrices({ baslangic = null, bitis = null } = {}) {
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
        for (const [rawId, payload] of Object.entries(araclar)) {
          const id = Number(rawId)
          const slot = this.marketSlotKey(id, baslangic, bitis)
          this._applyVehicleCompetitorPayload(slot, payload)
          try {
            localStorage.setItem(vehicleMarketCacheKey(id, baslangic, bitis), JSON.stringify(payload))
          } catch {
            // localStorage dolu
          }
        }
        return Object.keys(araclar).length
      } catch {
        return 0
      } finally {
        this.marketSyncing = false
      }
    },

    // Uygulama açılışında (giriş yapılır yapılmaz) varsayılan fiyatlandırma
    // penceresi (yarın → yarın+3 gün) için filo genelinde rakip fiyatları
    // arka planda ısıtır — kullanıcı Fiyatlandırma'ya girip araç seçtiğinde
    // beklemeden sonucu görür. Oturum başına yalnızca bir kez tetiklenir.
    prefetchDefaultMarketWindow() {
      if (defaultMarketPrefetchStarted) return
      defaultMarketPrefetchStarted = true
      const { pickupDate, dropoffDate } = getDefaultRentalWindow()
      void this.fetchAllCompetitorPrices({ baslangic: pickupDate, bitis: dropoffDate })
    },
  },
})
