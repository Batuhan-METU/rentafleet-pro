import { defineStore } from 'pinia'
import { RENTAL_WORKFLOW_KEY as STORAGE_KEY } from '../utils/storageKeys.js'

function defaultState() {
  return {
    active: false,
    vehicleId: null,
    vehicleLabel: null,
    agreedPrice: null,
    agreedDailyRate: null,
    pickupDate: null,
    dropoffDate: null,
    pickupTime: '10:00',
    dropoffTime: '10:00',
    driverId: null,
    driverName: null,
    riskApproved: false,
    depositAmount: null,
  }
}

function loadPersisted() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (!data?.vehicleId || data.agreedPrice == null) return null
    return { ...defaultState(), ...data, active: true }
  } catch {
    return null
  }
}

/** Bayi kiralama süreci: fiyatlandırma → sürücü → kiralama */
export const useRentalWorkflowStore = defineStore('rentalWorkflow', {
  state: () => loadPersisted() ?? defaultState(),

  getters: {
    step: (state) => {
      if (!state.active && !state.vehicleId) return null
      if (state.agreedPrice == null) return 'pricing'
      if (!state.driverId) return 'driver'
      if (!state.riskApproved) return 'risk'
      return 'rental'
    },
    progressStep() {
      const s = this.step
      if (s === 'risk') return 'driver'
      return s
    },
    stepLabel() {
      const labels = {
        pricing: 'Fiyatlandırma',
        driver: 'Sürücü Bilgileri',
        risk: 'Risk Değerlendirmesi',
        rental: 'Kiralama',
      }
      return labels[this.step] ?? ''
    },
    readyForDriverPick: (state) =>
      Boolean(
        state.vehicleId
        && state.agreedPrice != null
        && state.pickupDate
        && state.dropoffDate,
      ),
    showWorkflowBanner() {
      return this.readyForDriverPick || this.active
    },
  },

  actions: {
    _persist() {
      if (this.readyForDriverPick) {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
          vehicleId: this.vehicleId,
          vehicleLabel: this.vehicleLabel,
          agreedPrice: this.agreedPrice,
          agreedDailyRate: this.agreedDailyRate,
          pickupDate: this.pickupDate,
          dropoffDate: this.dropoffDate,
          pickupTime: this.pickupTime,
          dropoffTime: this.dropoffTime,
          driverId: this.driverId,
          driverName: this.driverName,
          riskApproved: this.riskApproved,
          depositAmount: this.depositAmount,
          active: true,
        }))
      } else {
        sessionStorage.removeItem(STORAGE_KEY)
      }
    },

    start() {
      this.active = true
      this._persist()
    },

    beginFlow() {
      Object.assign(this, defaultState())
      this.active = true
      this._persist()
    },

    /** Müşteri fiyatı kabul etti — tek adımda süreci başlat */
    acceptPricingOffer({
      vehicle,
      agreedPrice,
      agreedDailyRate = null,
      pickupDate,
      dropoffDate,
      pickupTime = '10:00',
      dropoffTime = '10:00',
    }) {
      this.vehicleId = vehicle.id
      this.vehicleLabel = `${vehicle.plate_number} — ${vehicle.brand} ${vehicle.model}`
      this.agreedPrice = agreedPrice
      this.agreedDailyRate = agreedDailyRate
      this.pickupDate = pickupDate
      this.dropoffDate = dropoffDate
      this.pickupTime = pickupTime
      this.dropoffTime = dropoffTime
      this.driverId = null
      this.driverName = null
      this.riskApproved = false
      this.depositAmount = null
      this.active = true
      this._persist()
    },

    selectVehicle(vehicle) {
      this.vehicleId = vehicle.id
      this.vehicleLabel = `${vehicle.plate_number} — ${vehicle.brand} ${vehicle.model}`
      this._persist()
    },

    setPricing({
      agreedPrice,
      agreedDailyRate = null,
      pickupDate,
      dropoffDate,
      pickupTime = '10:00',
      dropoffTime = '10:00',
    }) {
      this.agreedPrice = agreedPrice
      this.agreedDailyRate = agreedDailyRate
      this.pickupDate = pickupDate
      this.dropoffDate = dropoffDate
      this.pickupTime = pickupTime
      this.dropoffTime = dropoffTime
      this.active = true
      this._persist()
    },

    setDriver({ id, name, riskApproved, depositAmount }) {
      this.driverId = id
      this.driverName = name
      this.riskApproved = riskApproved
      this.depositAmount = depositAmount ?? null
      this._persist()
    },

    attachDriver(driver) {
      if (!driver) return
      const risk = driver.risk
      const approved = risk?.onaylandi ?? (
        !risk?.blokajlar?.length && (risk?.uygun_araclar?.length > 0)
      )
      this.driverId = driver.id
      this.driverName = driver.full_name ?? ''
      this.riskApproved = approved
      // Depozito, aracın fiyatı değil ANLAŞILAN KİRALAMA FİYATININ bir
      // yüzdesidir — backend yalnızca oranı (depozito_orani) döner, tutar
      // burada fiyatlandırma ekranında kabul edilen fiyat üzerinden hesaplanır.
      this.depositAmount = (risk?.depozito_orani != null && this.agreedPrice != null)
        ? Number(risk.depozito_orani) * Number(this.agreedPrice)
        : null
      if (!this.active) this.active = true
      this._persist()
    },

    clear() {
      Object.assign(this, defaultState())
      sessionStorage.removeItem(STORAGE_KEY)
    },
  },
})
