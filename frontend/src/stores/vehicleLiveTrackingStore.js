import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

// Canlı takip zamanlayıcısı store state'i DIŞINDA tutulur: interval kimliği
// reaktif/serileştirilebilir bir değer olmamalı ve birden fazla kez
// kurulmamalıdır (bellek sızıntısı/çift interval önlenir).
let liveTimer = null
const LIVE_POLL_MS = 5000

// Araçların canlı konum takibi — vehicleStore'dan ayrı, çünkü kendi
// polling yaşam döngüsüne (init/stop) sahip bağımsız bir kaygı
// (audit bulgusu #21).
export const useVehicleLiveTrackingStore = defineStore('vehicleLiveTracking', {
  state: () => ({
    // Canlı takip: tüm araçların en güncel konum/hız/durum verisi.
    liveVehicles: [],
    liveTracking: false,
  }),

  actions: {
    // Tüm araçların en güncel canlı konumunu çeker; hata olursa eski veriyi
    // korur (canlı ekran "donmaz", bir sonraki başarılı çağrıda güncellenir).
    async fetchLiveStream() {
      try {
        const { data } = await apiClient.get('vehicles/live-stream/')
        this.liveVehicles = data.vehicles ?? []
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
  },
})
