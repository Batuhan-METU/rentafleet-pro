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
    riskyDrivers: (state) => state.drivers.filter((d) => d.surus_skoru < 70),
  },

  actions: {
    async fetchDrivers() {
      this.loading = true
      this.error = false
      try {
        const { data } = await apiClient.get('drivers/')
        this.drivers = data.surucular ?? []
      } catch {
        this.error = true
      } finally {
        this.loading = false
      }
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
