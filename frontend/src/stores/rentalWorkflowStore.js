import { defineStore } from 'pinia'

const STORAGE_KEY = 'rf_rental_workflow'

function defaultState() {
  return {
    active: false,
    vehicleId: null,
    vehicleLabel: null,
    agreedPrice: null,
    pickupDate: null,
    dropoffDate: null,
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

/** Bayi kiralama süreci: fiyatlandırma → sürücü → rezervasyon */
export const useRentalWorkflowStore = defineStore('rentalWorkflow', {
  state: () => loadPersisted() ?? defaultState(),

  getters: {
    step: (state) => {
      if (!state.active && !state.vehicleId) return null
      if (state.agreedPrice == null) return 'pricing'
      if (!state.driverId) return 'driver'
      if (!state.riskApproved) return 'risk'
      return 'reservation'
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
        reservation: 'Rezervasyon',
      }
      return labels[this.step] ?? ''
    },
    canCreateReservation: (state) =>
      state.vehicleId
      && state.driverId
      && state.pickupDate
      && state.dropoffDate,
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
          pickupDate: this.pickupDate,
          dropoffDate: this.dropoffDate,
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
    acceptPricingOffer({ vehicle, agreedPrice, pickupDate, dropoffDate }) {
      this.vehicleId = vehicle.id
      this.vehicleLabel = `${vehicle.plate_number} — ${vehicle.brand} ${vehicle.model}`
      this.agreedPrice = agreedPrice
      this.pickupDate = pickupDate
      this.dropoffDate = dropoffDate
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

    setPricing({ agreedPrice, pickupDate, dropoffDate }) {
      this.agreedPrice = agreedPrice
      this.pickupDate = pickupDate
      this.dropoffDate = dropoffDate
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
      this.driverName = driver.ad_soyad ?? driver.full_name ?? ''
      this.riskApproved = approved
      this.depositAmount = risk?.depozito ? Number(risk.depozito) : null
      if (!this.active) this.active = true
      this._persist()
    },

    clear() {
      Object.assign(this, defaultState())
      sessionStorage.removeItem(STORAGE_KEY)
    },
  },
})
