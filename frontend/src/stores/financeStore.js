// Finansal karar destek store — araç maliyet kartı ve kiralama fiyatı.
import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

export const useFinanceStore = defineStore('finance', {
  state: () => ({
    categories: [],
    quoteById: {},
    expensesById: {},
    incomesById: {},
    saving: false,
    quoteLoading: false,
    error: null,
  }),

  getters: {
    quoteFor: (state) => (vehicleId) => state.quoteById[vehicleId] ?? null,
    expensesFor: (state) => (vehicleId) => state.expensesById[vehicleId] ?? [],
    incomesFor: (state) => (vehicleId) => state.incomesById[vehicleId] ?? [],
  },

  actions: {
    async fetchExpenseCategories() {
      if (this.categories.length) return this.categories
      const { data } = await apiClient.get('expense-categories/')
      this.categories = data.kategoriler ?? []
      return this.categories
    },

    async createVehicle(payload) {
      this.saving = true
      this.error = null
      try {
        const { data } = await apiClient.post('vehicles/', payload)
        return data
      } catch (err) {
        this.error = err?.response?.data ?? 'Araç kaydedilemedi.'
        throw err
      } finally {
        this.saving = false
      }
    },

    async updateVehicle(vehicleId, payload) {
      this.saving = true
      this.error = null
      try {
        const { data } = await apiClient.patch(`vehicles/${vehicleId}/`, payload)
        return data
      } catch (err) {
        this.error = err?.response?.data ?? 'Araç güncellenemedi.'
        throw err
      } finally {
        this.saving = false
      }
    },

    async fetchRentalQuote(vehicleId, { force = false, baslangic = null, bitis = null } = {}) {
      const cacheKey = `${vehicleId}:${baslangic ?? ''}:${bitis ?? ''}`
      if (!force && this.quoteById[cacheKey]) {
        this.quoteById = { ...this.quoteById, [vehicleId]: this.quoteById[cacheKey] }
        return this.quoteById[cacheKey]
      }

      const hadQuote = !!this.quoteById[vehicleId]
      if (!hadQuote) this.quoteLoading = true
      this.error = null
      try {
        const params = {}
        if (baslangic && bitis) {
          params.baslangic_tarihi = baslangic
          params.bitis_tarihi = bitis
        }

        const { data } = await apiClient.get(`vehicles/${vehicleId}/rental-quote/`, {
          params,
          timeout: 30000,
        })
        this.quoteById = { ...this.quoteById, [cacheKey]: data, [vehicleId]: data }
        return data
      } catch (err) {
        this.error = 'Kiralama fiyatı hesaplanamadı.'
        throw err
      } finally {
        this.quoteLoading = false
      }
    },

    async fetchProfile(vehicleId) {
      const { data } = await apiClient.get(`vehicles/${vehicleId}/financial-profile/`)
      return data?.finansal_profil_var === false ? null : data
    },

    async fetchExpenses(vehicleId) {
      const { data } = await apiClient.get(`vehicles/${vehicleId}/expenses/`)
      const rows = data.results ?? data
      this.expensesById = { ...this.expensesById, [vehicleId]: rows }
      return rows
    },

    async fetchIncomes(vehicleId) {
      const { data } = await apiClient.get(`vehicles/${vehicleId}/incomes/`)
      const rows = data.results ?? data
      this.incomesById = { ...this.incomesById, [vehicleId]: rows }
      return rows
    },
  },
})
