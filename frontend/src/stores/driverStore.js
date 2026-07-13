import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

export const useDriverStore = defineStore('driver', {
  state: () => ({
    drivers: [],
    loading: false,
    error: false,
    selectedDriver: null,
    detailLoading: false,
    rentalHistory: [],
  }),

  getters: {
    driverCount: (state) => state.drivers.length,
    riskyDrivers: (state) => state.drivers.filter((d) => d.risk_skoru != null && d.risk_skoru >= 61),
  },

  actions: {
    async fetchDrivers({ vehicleId = null } = {}) {
      this.loading = true
      this.error = false
      try {
        const params = vehicleId ? { vehicle_id: vehicleId } : undefined
        const { data } = await apiClient.get('drivers/', { params })
        this.drivers = data.surucular ?? []
      } catch {
        this.error = true
      } finally {
        this.loading = false
      }
    },

    async createDriver(payload) {
      const { data } = await apiClient.post('drivers/create/', payload)
      const existing = this.drivers.findIndex((d) => d.id === data.id)
      const listItem = {
        ...data,
        risk_skoru: data.risk?.skor ?? data.current_risk_score,
        risk_seviye: data.risk?.seviye,
        risk_seviye_label: data.risk?.seviye_label ?? '—',
      }
      if (existing >= 0) {
        this.drivers.splice(existing, 1, listItem)
      } else {
        this.drivers.unshift(listItem)
      }
      return data
    },

    async fetchDriverDetail(id) {
      this.detailLoading = true
      try {
        const { data } = await apiClient.get(`drivers/${id}/`)
        this.selectedDriver = data
        const rentals = await apiClient.get(`drivers/${id}/rentals/`)
        this.rentalHistory = rentals.data.kiralamalar ?? []
      } catch {
        this.selectedDriver = null
        this.rentalHistory = []
      } finally {
        this.detailLoading = false
      }
    },

    clearSelectedDriver() {
      this.selectedDriver = null
      this.rentalHistory = []
      this.detailLoading = false
    },
  },
})
