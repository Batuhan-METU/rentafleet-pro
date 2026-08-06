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
    riskyDrivers: (state) => state.drivers.filter((d) => d.risk_score != null && d.risk_score >= 61),
  },

  actions: {
    async fetchDrivers({ vehicleId = null } = {}) {
      this.loading = true
      this.error = false
      try {
        const params = vehicleId ? { vehicle_id: vehicleId } : undefined
        const { data } = await apiClient.get('drivers/', { params })
        this.drivers = data.drivers ?? []
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
        risk_score: data.risk?.skor ?? data.current_risk_score,
        risk_level: data.risk?.seviye,
        risk_level_label: data.risk?.seviye_label ?? '—',
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
        this.rentalHistory = rentals.data.rentals ?? []
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
