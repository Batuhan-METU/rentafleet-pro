// Kredi (§3.1) yönetimi — kredi tanımları + araç tahsisleri.
import { defineStore } from 'pinia'
import apiClient from '../services/api.js'

export const useLoanStore = defineStore('loan', {
  state: () => ({
    loans: [],
    loading: false,
    saving: false,
    error: null,

    // Kredi Detay sayfası — Taksit Listesi + Kredi Araç Listesi bundan beslenir.
    loanDetail: null,
    loanDetailLoading: false,
    loanDetailError: null,
  }),

  actions: {
    async fetchLoans() {
      this.loading = true
      this.error = null
      try {
        const { data } = await apiClient.get('loans/')
        this.loans = data.results ?? data
        return this.loans
      } catch (err) {
        this.error = err?.response?.data ?? 'Krediler yüklenemedi.'
        throw err
      } finally {
        this.loading = false
      }
    },

    async createLoan(payload) {
      this.saving = true
      this.error = null
      try {
        const { data } = await apiClient.post('loans/', payload)
        await this.fetchLoans()
        return data
      } catch (err) {
        this.error = err?.response?.data ?? 'Kredi kaydedilemedi.'
        throw err
      } finally {
        this.saving = false
      }
    },

    async deleteLoan(loanId) {
      this.saving = true
      this.error = null
      try {
        await apiClient.delete(`loans/${loanId}/`)
        this.loans = this.loans.filter((l) => l.id !== loanId)
      } catch (err) {
        this.error = err?.response?.data ?? 'Kredi silinemedi.'
        throw err
      } finally {
        this.saving = false
      }
    },

    // Kredi Detay sayfası — taksit planı + araç tahsisleri tek istekte gelir
    // (LoanDetailSerializer, backend/apps/vehicle_finance/serializers.py).
    async fetchLoanDetail(loanId) {
      this.loanDetailLoading = true
      this.loanDetailError = null
      try {
        const { data } = await apiClient.get(`loans/${loanId}/`)
        this.loanDetail = data
        return data
      } catch (err) {
        this.loanDetailError = err?.response?.data ?? 'Kredi detayı yüklenemedi.'
        this.loanDetail = null
        throw err
      } finally {
        this.loanDetailLoading = false
      }
    },

    clearLoanDetail() {
      this.loanDetail = null
      this.loanDetailError = null
    },
  },
})
