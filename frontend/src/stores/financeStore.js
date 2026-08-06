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
    insurancePoliciesById: {},
    loanAllocationsById: {},
    costAnalysisById: {},
    yearlySummaryById: {},
    registrationDetailById: {},
    documentsById: {},
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
    insurancePoliciesFor: (state) => (vehicleId) => state.insurancePoliciesById[vehicleId] ?? [],
    loanAllocationsFor: (state) => (vehicleId) => state.loanAllocationsById[vehicleId] ?? [],
    costAnalysisFor: (state) => (vehicleId) => state.costAnalysisById[vehicleId] ?? null,
    yearlySummaryFor: (state) => (vehicleId) => state.yearlySummaryById[vehicleId] ?? null,
    registrationDetailFor: (state) => (vehicleId) => state.registrationDetailById[vehicleId] ?? null,
    documentsFor: (state) => (vehicleId) => state.documentsById[vehicleId] ?? [],
  },

  actions: {
    async fetchExpenseCategories() {
      if (this.categories.length) return this.categories
      const { data } = await apiClient.get('expense-categories/')
      this.categories = data.categories ?? []
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
        if (this.decisionById[cacheKey]?.rental) {
          this.quoteById = { ...this.quoteById, [vehicleId]: this.decisionById[cacheKey].rental }
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
          params.pickup_date = baslangic
          params.dropoff_date = bitis
        }
        if (teklif != null && teklif > 0) {
          params.offered_price = teklif
        }

        const { data } = await apiClient.get(`vehicles/${vehicleId}/pricing-decision/`, {
          params,
          timeout: 30000,
        })
        this.decisionById = { ...this.decisionById, [cacheKey]: data, [vehicleId]: data }
        if (data.rental) {
          this.quoteById = { ...this.quoteById, [vehicleId]: data.rental }
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
      return data?.has_financial_profile === false ? null : data
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

    async fetchInsurancePolicies(vehicleId) {
      const { data } = await apiClient.get(`vehicles/${vehicleId}/insurance-policies/`)
      const rows = data.results ?? data
      this.insurancePoliciesById = { ...this.insurancePoliciesById, [vehicleId]: rows }
      return rows
    },

    async fetchLoanAllocations(vehicleId) {
      const { data } = await apiClient.get(`vehicles/${vehicleId}/loans/`)
      const rows = data.allocations ?? []
      this.loanAllocationsById = { ...this.loanAllocationsById, [vehicleId]: rows }
      return rows
    },

    async fetchCostAnalysis(vehicleId) {
      // §3.6/§4'ün TEK doğru orkestratörü (build_cost_analysis_payload) —
      // ömür-boyu (lifetime) anlık görüntü. "Finansman" sekmesi (kredi/nakit
      // tahsislerinin toplamda nereye geldiği) bunu kullanır. Yıla göre
      // kırılım için fetchYearlySummary'e bakın.
      const { data } = await apiClient.get(`vehicles/${vehicleId}/`)
      const analysis = data.cost_analysis ?? null
      this.costAnalysisById = { ...this.costAnalysisById, [vehicleId]: analysis }
      return analysis
    },

    async fetchRegistrationDetail(vehicleId) {
      // FYS ruhsat sihirbazının ek alanları — GET /api/vehicles/<pk>/'nin
      // aynı yanıtından (VehicleWriteSerializer.to_representation) okunur,
      // ayrı bir uç yok (cost_analysis'in fetchCostAnalysis'teki deseniyle
      // aynı).
      const { data } = await apiClient.get(`vehicles/${vehicleId}/`)
      const detail = data.registration_detail ?? null
      this.registrationDetailById = { ...this.registrationDetailById, [vehicleId]: detail }
      return detail
    },

    async fetchYearlySummary(vehicleId, year = null) {
      // Araç Detayı "Gelir & Gider Özeti" — seçili yıla göre gelir/gider/
      // günlük maliyet (build_vehicle_yearly_summary). Lifetime cost_analysis
      // ile KARIŞTIRILMAMALI, ayrı bir kavramdır.
      const params = year != null ? { yil: year } : {}
      const { data } = await apiClient.get(`vehicles/${vehicleId}/yearly-summary/`, { params })
      this.yearlySummaryById = { ...this.yearlySummaryById, [vehicleId]: data }
      return data
    },

    async fetchDocuments(vehicleId) {
      const { data } = await apiClient.get(`vehicles/${vehicleId}/documents/`)
      const rows = data.results ?? data
      this.documentsById = { ...this.documentsById, [vehicleId]: rows }
      return rows
    },

    async uploadDocument(vehicleId, file, label = '') {
      const formData = new FormData()
      formData.append('file', file)
      if (label) formData.append('label', label)
      const { data } = await apiClient.post(`vehicles/${vehicleId}/documents/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      this.documentsById = {
        ...this.documentsById,
        [vehicleId]: [data, ...(this.documentsById[vehicleId] ?? [])],
      }
      return data
    },

    async deleteDocument(vehicleId, documentId) {
      await apiClient.delete(`vehicle-documents/${documentId}/`)
      this.documentsById = {
        ...this.documentsById,
        [vehicleId]: (this.documentsById[vehicleId] ?? []).filter((d) => d.id !== documentId),
      }
    },
  },
})
