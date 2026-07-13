import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

const ALLOWED_STAT_KEYS = new Set([
  'net_kazanc',
  'yillik_gelir',
  'net_kar',
  'kiralama_sayisi',
  'kiralanan_gun',
])

const STAT_ORDER = [
  'net_kazanc',
  'yillik_gelir',
  'net_kar',
  'kiralama_sayisi',
  'kiralanan_gun',
]

const STAT_ALIASES = {
  net_kazanc: ['net_kazanc', 'yillik_net_kar'],
  yillik_gelir: ['yillik_gelir', 'toplam_gelir'],
  net_kar: ['net_kar', 'biriken_kar'],
  kiralama_sayisi: ['kiralama_sayisi'],
  kiralanan_gun: ['kiralanan_gun'],
}

const STAT_LABELS = {
  net_kazanc: 'Net Kazanç',
  yillik_gelir: 'Yıllık Gelir',
  net_kar: 'Net Kar',
  kiralama_sayisi: 'Toplam Kiralama',
  kiralanan_gun: 'Kiralanan Gün',
}

function pickStat(rows, keys, fallbackKey) {
  const byKey = Object.fromEntries(rows.map((r) => [r.anahtar, r]))
  for (const key of keys) {
    if (byKey[key]) return byKey[key]
  }
  return null
}

function normalizeStats(rows) {
  return STAT_ORDER.map((key) => {
    const found = pickStat(rows, STAT_ALIASES[key], key)
    if (found) {
      return { ...found, etiket: STAT_LABELS[key], anahtar: key }
    }
    return {
      anahtar: key,
      etiket: STAT_LABELS[key],
      deger: 0,
      birim: key === 'kiralama_sayisi' ? 'adet' : key === 'kiralanan_gun' ? 'gün' : 'TL',
    }
  })
}

function isStalePayload(data) {
  if (!data) return true
  if (!data.filo_durumu) return true
  const stats = data.istatistikler ?? []
  if (stats.length !== 5) return true
  return stats.some((s) => !ALLOWED_STAT_KEYS.has(s.anahtar))
}

export const useOverviewStore = defineStore('overview', {
  state: () => ({
    data: null,
    selectedYear: new Date().getFullYear(),
    loading: false,
    error: false,
  }),

  getters: {
    stats: (state) => normalizeStats(state.data?.istatistikler ?? []),
    monthlyRevenue: (state) => state.data?.grafik?.aylik_gelir ?? [],
  },

  actions: {
    async fetchOverview({ force = false, year = null } = {}) {
      const y = year ?? this.selectedYear
      if (this.data?.yil === y && !force && !isStalePayload(this.data)) {
        return this.data
      }

      this.loading = true
      this.error = false
      try {
        const { data } = await apiClient.get('fleet/overview/', { params: { yil: y } })
        this.data = data
        this.selectedYear = data.yil ?? y
        return data
      } catch {
        this.error = true
        if (force) this.data = null
        return null
      } finally {
        this.loading = false
      }
    },

    async setYear(year) {
      this.selectedYear = year
      return this.fetchOverview({ force: true, year })
    },
  },
})
