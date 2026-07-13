// Finansal karar destek store — araç maliyet kartı ve kiralama fiyatı.
import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

export const useFinanceStore = defineStore('finance', {
  state: () => ({
    categories: [],
    quoteById: {},
    decisionById: {},
    expensesById: {},
    incomesById: {},
    saving: false,
    quoteLoading: false,
    offerPreviewLoading: false,
    error: null,
  }),

  getters: {
    quoteFor: (state) => (vehicleId) => state.quoteById[vehicleId] ?? null,
    decisionFor: (state) => (vehicleId) => state.decisionById[vehicleId] ?? null,
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

    async fetchPricingDecision(
      vehicleId,
      { force = false, baslangic = null, bitis = null, teklif = null } = {},
    ) {
      const cacheKey = `${vehicleId}:${baslangic ?? ''}:${bitis ?? ''}:${teklif ?? ''}`
      if (!force && this.decisionById[cacheKey]) {
        this.decisionById = { ...this.decisionById, [vehicleId]: this.decisionById[cacheKey] }
        if (this.decisionById[cacheKey]?.kiralama) {
          this.quoteById = { ...this.quoteById, [vehicleId]: this.decisionById[cacheKey].kiralama }
        }
        return this.decisionById[cacheKey]
      }

      const hadDecision = !!this.decisionById[vehicleId]
      const isOfferRefresh = hadDecision && teklif != null && teklif > 0
      if (!hadDecision) this.quoteLoading = true
      else if (isOfferRefresh) this.offerPreviewLoading = true
      this.error = null
      try {
        const params = {}
        if (baslangic && bitis) {
          params.baslangic_tarihi = baslangic
          params.bitis_tarihi = bitis
        }
        if (teklif != null && teklif > 0) {
          params.teklif = teklif
        }

        const { data } = await apiClient.get(`vehicles/${vehicleId}/pricing-decision/`, {
          params,
          timeout: 30000,
        })
        this.decisionById = { ...this.decisionById, [cacheKey]: data, [vehicleId]: data }
        if (data.kiralama) {
          this.quoteById = { ...this.quoteById, [vehicleId]: data.kiralama }
        }
        return data
      } catch (err) {
        this.error = 'Fiyat karar desteği yüklenemedi.'
        throw err
      } finally {
        this.quoteLoading = false
        this.offerPreviewLoading = false
      }
    },

    async fetchRentalQuote(vehicleId, { force = false, baslangic = null, bitis = null } = {}) {
      return this.fetchPricingDecision(vehicleId, { force, baslangic, bitis })
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
